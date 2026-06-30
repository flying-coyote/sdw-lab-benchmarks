#!/usr/bin/env python3
"""#68 fair-test complement: the COLUMNAR half of the two-regime on EDR/Sysmon, with the flagship's
HEAVY scan-aggregation shape at scale — not the cheap terms-aggs of the first EDR run (where the
index's doc-values won). #68 honestly flagged that confound; this closes it.

Adds numeric measure fields (bytes_sent/bytes_recv) to the EDR corpus so we can run the flagship's
top-talkers-by-SUM heavy aggregations + a high-cardinality SUM + a computed-over-scan measure, plus the
command_line text lookup as the index-turf control. 10M rows (the fair scale — the columnar advantage
grows with scan size; the first run was 3M). ClickHouse (columnar) vs OpenSearch (index), host-run.
Tier B, single host. Hypothesis: on HEAVY scan-aggregations at 10M, ClickHouse wins (the columnar half
generalizes to EDR), even though cheap terms-aggs at 3M went to the index.
"""
import os
import json, time, sys, urllib.request
import duckdb, clickhouse_connect

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000_000
CH = dict(host="localhost", port=8323, password="ejsbench123")
OS = "http://localhost:9200"; IDX = "edr_heavy"; TBL = "edr_heavy"
IMAGES = ["C:\\Windows\\System32\\svchost.exe", "C:\\Windows\\System32\\cmd.exe", "C:\\Windows\\System32\\powershell.exe",
          "C:\\Windows\\explorer.exe", "C:\\Windows\\System32\\wmic.exe", "C:\\Windows\\System32\\rundll32.exe",
          "C:\\Program Files\\app\\app.exe", "C:\\Windows\\System32\\schtasks.exe"]
TEMPLATES = ["-k netsvcs -p -s Schedule", "process call create", "/IM explorer.exe /F", "-enc SQBFAFgA",
             "/c whoami", "-Command Get-Process", "/query /v", "--headless --disable-gpu"]


def req(method, path, body=None, ctype="application/json", timeout=1800):
    data = body.encode() if isinstance(body, str) else body
    r = urllib.request.Request(f"{OS}{path}", data=data, method=method, headers={"Content-Type": ctype} if data else {})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.load(resp)


def gen(con):
    imgs = "[" + ",".join(f"'{x}'" for x in IMAGES) + "]"; tmpl = "[" + ",".join(f"'{x}'" for x in TEMPLATES) + "]"
    con.execute(f"""CREATE OR REPLACE TABLE edr AS SELECT
        (1781000000 + (hash(i) % 604800))::BIGINT AS event_time,
        'WIN-' || lpad(((hash(i) % 5000))::VARCHAR,4,'0') AS hostname,
        'CORP\\u' || ((hash(i+11) % 20000))::VARCHAR AS subject_user,
        ({imgs})[(hash(i+1) % {len(IMAGES)})::BIGINT + 1] AS image,
        ({imgs})[(hash(i+1) % {len(IMAGES)})::BIGINT + 1] || ' ' || ({tmpl})[(hash(i+3) % {len(TEMPLATES)})::BIGINT + 1] || ' ' || md5(i::VARCHAR) AS command_line,
        md5(i::VARCHAR || 'pg') AS process_guid,
        (hash(i+7) % 100000)::BIGINT AS bytes_sent,
        (hash(i+8) % 500000)::BIGINT AS bytes_recv,
        (['System','High','Medium','Low'])[(hash(i+4) % 4)::BIGINT + 1] AS integrity_level
        FROM range({N}) t(i)""")
    return con.execute("SELECT count(*) FROM edr").fetchone()[0]


def load_clickhouse(con):
    c = clickhouse_connect.get_client(**CH, settings={"max_execution_time": 1200})
    c.command(f"DROP TABLE IF EXISTS {TBL}")
    c.command(f"""CREATE TABLE {TBL} (event_time UInt32, hostname String, subject_user String, image String,
        command_line String, process_guid String, bytes_sent UInt64, bytes_recv UInt64, integrity_level String)
        ENGINE=MergeTree ORDER BY (event_time, hostname)""")
    c.insert_arrow(TBL, con.execute("SELECT * FROM edr").fetch_arrow_table())
    c.command(f"OPTIMIZE TABLE {TBL} FINAL")
    return c, c.query(f"SELECT count() FROM {TBL}").result_rows[0][0]


def load_opensearch(con):
    try:
        req("DELETE", f"/{IDX}")
    except Exception:
        pass
    req("PUT", f"/{IDX}", json.dumps({"settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0, "refresh_interval": "-1"}},
        "mappings": {"properties": {"event_time": {"type": "long"}, "hostname": {"type": "keyword"}, "subject_user": {"type": "keyword"},
            "image": {"type": "keyword"}, "command_line": {"type": "text"}, "process_guid": {"type": "keyword"},
            "bytes_sent": {"type": "long"}, "bytes_recv": {"type": "long"}, "integrity_level": {"type": "keyword"}}}}))
    reader = con.execute("SELECT * FROM edr").fetch_record_batch(50000)
    total = 0
    for batch in reader:
        rows = batch.to_pylist(); lines = []
        for r in rows:
            lines.append('{"index":{}}'); lines.append(json.dumps(r))
        req("POST", f"/{IDX}/_bulk", "\n".join(lines) + "\n", ctype="application/x-ndjson")
        total += len(rows)
    req("POST", f"/{IDX}/_forcemerge?max_num_segments=1"); req("POST", f"/{IDX}/_refresh")
    return req("GET", f"/{IDX}/_count")["count"]


def timeit(fn, trials=5):
    fn()
    ds = []
    for _ in range(trials):
        t0 = time.perf_counter(); out = fn(); ds.append(time.perf_counter() - t0)
    ds.sort(); return round(ds[len(ds)//2]*1000, 1), out


def main():
    con = duckdb.connect(); con.execute("SET threads=8")
    n = gen(con); print(f"generated {n:,} EDR rows (+bytes_sent/recv)", flush=True)
    ch, chn = load_clickhouse(con); print(f"clickhouse loaded {chn:,}", flush=True)
    osn = load_opensearch(con); print(f"opensearch loaded {osn:,}", flush=True)
    TOKEN = "netsvcs"
    Q = {}
    # HEAVY AGG 1: top hosts by SUM(bytes) — the flagship top-talkers analog
    Q["heavy_top_hosts_by_bytes"] = ("heavy_agg",
        lambda: ch.query(f"SELECT hostname, sum(bytes_sent+bytes_recv) b FROM {TBL} GROUP BY hostname ORDER BY b DESC LIMIT 10").result_rows,
        lambda: req("POST", f"/{IDX}/_search?request_cache=false", json.dumps({"size": 0, "aggs": {"h": {"terms": {"field": "hostname", "size": 10, "order": {"b": "desc"}}, "aggs": {"b": {"sum": {"field": "bytes_sent"}}, "b2": {"sum": {"field": "bytes_recv"}}}}}})))
    # HEAVY AGG 2: high-cardinality group-by SUM (subject_user ~20k)
    Q["heavy_highcard_user_bytes"] = ("heavy_agg",
        lambda: ch.query(f"SELECT subject_user, sum(bytes_sent) b FROM {TBL} GROUP BY subject_user ORDER BY b DESC LIMIT 20").result_rows,
        lambda: req("POST", f"/{IDX}/_search?request_cache=false", json.dumps({"size": 0, "aggs": {"u": {"terms": {"field": "subject_user", "size": 20, "order": {"b": "desc"}}, "aggs": {"b": {"sum": {"field": "bytes_sent"}}}}}})))
    # HEAVY AGG 3: computed-over-scan measure (avg command_line length by image) — text field has no doc-value
    Q["heavy_computed_cmdlen"] = ("heavy_agg",
        lambda: ch.query(f"SELECT image, avg(length(command_line)) a FROM {TBL} GROUP BY image ORDER BY a DESC").result_rows,
        lambda: req("POST", f"/{IDX}/_search?request_cache=false", json.dumps({"size": 0, "aggs": {"i": {"terms": {"field": "image", "size": 20}, "aggs": {"a": {"avg": {"script": {"source": "params._source.command_line.length()"}}}}}}})))
    # LOOKUP control (index turf): command_line text search
    Q["lookup_cmdline_text"] = ("lookup",
        lambda: ch.query(f"SELECT count() FROM {TBL} WHERE positionCaseInsensitive(command_line,'{TOKEN}')>0").result_rows,
        lambda: req("POST", f"/{IDX}/_search?request_cache=false", json.dumps({"size": 0, "track_total_hits": True, "query": {"match": {"command_line": TOKEN}}})))

    res = {"bench": "edr-heavy-scan-agg (#68 columnar-half fair-test)", "tier": "B", "n_rows": n, "token": TOKEN, "queries": {}}
    for name, (regime, chf, osf) in Q.items():
        try:
            ch_ms, _ = timeit(chf)
        except Exception as e:
            ch_ms = None; print(f"  {name} CH ERR {str(e)[:100]}", flush=True)
        try:
            os_ms, _ = timeit(osf)
        except Exception as e:
            os_ms = None; print(f"  {name} OS ERR {str(e)[:100]}", flush=True)
        winner = ("columnar(CH)" if (ch_ms or 9e9) < (os_ms or 9e9) else "index(OS)") if (ch_ms and os_ms) else "n/a"
        ratio = round(max(ch_ms, os_ms)/max(min(ch_ms, os_ms), 0.01), 1) if (ch_ms and os_ms) else None
        res["queries"][name] = {"regime": regime, "ch_ms": ch_ms, "os_ms": os_ms, "winner": winner, "ratio": ratio}
        print(f"  {name:28} [{regime:9}] CH={ch_ms}ms OS={os_ms}ms -> {winner} {ratio}x", flush=True)
    heavy = [v for v in res["queries"].values() if v["regime"] == "heavy_agg" and v["winner"] != "n/a"]
    res["columnar_wins_heavy_aggs"] = all(v["winner"].startswith("columnar") for v in heavy) if heavy else None
    res["columnar_heavy_agg_win_count"] = f"{sum(v['winner'].startswith('columnar') for v in heavy)}/{len(heavy)}"
    json.dump(res, open(os.path.expanduser("~/sdw-lab-benchmarks/edr-two-regime/results/edr_heavy_scan_agg.json"), "w"), indent=2, default=str)
    print(f"\ncolumnar wins HEAVY aggs at {n//1_000_000}M: {res['columnar_heavy_agg_win_count']} "
          f"(all={res['columnar_wins_heavy_aggs']}) | lookup stays index-turf")


if __name__ == "__main__":
    main()

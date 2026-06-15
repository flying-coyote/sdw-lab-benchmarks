#!/usr/bin/env python3
"""#68 — does the two-regime split GENERALIZE beyond Zeek conn? Tested on an EDR/Sysmon
process-creation stream (a structurally different log shape: wide, high-entropy command lines,
GUIDs, text-y fields) instead of flat Zeek flow.

Two-regime claim: a columnar/OLAP engine (ClickHouse) wins hunting AGGREGATIONS; an inverted index
(OpenSearch) wins selective LOOKUPS and TEXT search. The flagship measured this on Zeek conn; this
re-measures the SHAPE on EDR/Sysmon to test generalization (the latency split, not the absolute ms).

Corpus: synthetic Sysmon process-creation (reuses the B-COST `second_corpus` generator shape — image/
parent_image/command_line+md5-tail/process_guid/sha256/...). ClickHouse = MergeTree (columnar arm);
OpenSearch = index arm (keyword fields + analyzed `command_line`). Host-run: ClickHouse :8323,
OpenSearch :9200. Synthetic/structured only. Tier B, single host.
"""
import json, time, urllib.request, sys
import duckdb, pyarrow as pa
import clickhouse_connect

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3_000_000
CH = dict(host="localhost", port=8323, password="ejsbench123")
OS = "http://localhost:9200"
IDX = "edr_2regime"; TBL = "edr_2regime"
IMAGES = ["C:\\Windows\\System32\\svchost.exe", "C:\\Windows\\System32\\cmd.exe", "C:\\Windows\\System32\\powershell.exe",
          "C:\\Windows\\explorer.exe", "C:\\Windows\\System32\\wmic.exe", "C:\\Windows\\System32\\rundll32.exe",
          "C:\\Program Files\\app\\app.exe", "C:\\Windows\\System32\\schtasks.exe"]
TEMPLATES = ["-k netsvcs -p -s Schedule", "process call create", "/IM explorer.exe /F", "-enc SQBFAFgA",
             "/c whoami", "-Command Get-Process", "/query /v", "--headless --disable-gpu"]


def req(method, path, body=None, ctype="application/json", timeout=600):
    data = body.encode() if isinstance(body, str) else body
    r = urllib.request.Request(f"{OS}{path}", data=data, method=method, headers={"Content-Type": ctype} if data else {})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.load(resp)


def gen(con):
    imgs = "[" + ",".join(f"'{x}'" for x in IMAGES) + "]"
    tmpl = "[" + ",".join(f"'{x}'" for x in TEMPLATES) + "]"
    con.execute(f"""CREATE OR REPLACE TABLE edr AS SELECT
        (1781000000 + (hash(i) % 604800))::BIGINT AS event_time,
        'WIN-' || lpad(((hash(i) % 5000))::VARCHAR,4,'0') AS hostname,
        'CORP\\u' || ((hash(i+11) % 20000))::VARCHAR AS subject_user,
        ({imgs})[(hash(i+1) % {len(IMAGES)})::BIGINT + 1] AS image,
        ({imgs})[(hash(i+2) % {len(IMAGES)})::BIGINT + 1] AS parent_image,
        ({imgs})[(hash(i+1) % {len(IMAGES)})::BIGINT + 1] || ' ' || ({tmpl})[(hash(i+3) % {len(TEMPLATES)})::BIGINT + 1] || ' ' || md5(i::VARCHAR) AS command_line,
        md5(i::VARCHAR || 'pg') AS process_guid,
        md5('sha' || ((hash(i+1) % {len(IMAGES)}))::VARCHAR) AS sha256,
        (['System','High','Medium','Low'])[(hash(i+4) % 4)::BIGINT + 1] AS integrity_level
        FROM range({N}) t(i)""")
    return con.execute("SELECT count(*) FROM edr").fetchone()[0]


def load_clickhouse(tbl_arrow):
    c = clickhouse_connect.get_client(**CH, settings={"max_execution_time": 600})
    c.command(f"DROP TABLE IF EXISTS {TBL}")
    c.command(f"""CREATE TABLE {TBL} (event_time UInt32, hostname String, subject_user String, image String,
        parent_image String, command_line String, process_guid String, sha256 String, integrity_level String)
        ENGINE=MergeTree ORDER BY (event_time, hostname)""")
    c.insert_arrow(TBL, tbl_arrow)
    c.command(f"OPTIMIZE TABLE {TBL} FINAL")
    return c, c.query(f"SELECT count() FROM {TBL}").result_rows[0][0]


def load_opensearch(tbl_arrow):
    try:
        req("DELETE", f"/{IDX}")
    except Exception:
        pass
    req("PUT", f"/{IDX}", json.dumps({"settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0, "refresh_interval": "-1"}},
        "mappings": {"properties": {"event_time": {"type": "long"}, "hostname": {"type": "keyword"}, "subject_user": {"type": "keyword"},
            "image": {"type": "keyword"}, "parent_image": {"type": "keyword"}, "command_line": {"type": "text"},
            "process_guid": {"type": "keyword"}, "sha256": {"type": "keyword"}, "integrity_level": {"type": "keyword"}}}}))
    cols = tbl_arrow.column_names
    rows = tbl_arrow.to_pylist()
    B = 20000; buf = []
    for i, r in enumerate(rows):
        buf.append('{"index":{}}'); buf.append(json.dumps(r))
        if len(buf) >= B * 2:
            req("POST", f"/{IDX}/_bulk", "\n".join(buf) + "\n", ctype="application/x-ndjson")
            buf = []
    if buf:
        req("POST", f"/{IDX}/_bulk", "\n".join(buf) + "\n", ctype="application/x-ndjson")
    req("POST", f"/{IDX}/_forcemerge?max_num_segments=1", timeout=1800)
    req("POST", f"/{IDX}/_refresh")
    return req("GET", f"/{IDX}/_count")["count"]


def timeit(fn, trials=5):
    fn()  # warmup
    ds = []
    for _ in range(trials):
        t0 = time.perf_counter(); out = fn(); ds.append(time.perf_counter() - t0)
    ds.sort()
    return round(ds[len(ds)//2] * 1000, 1), out


def main():
    con = duckdb.connect()
    n = gen(con)
    tbl = con.execute("SELECT * FROM edr").fetch_arrow_table()
    print(f"generated {n:,} EDR rows", flush=True)
    ch, ch_n = load_clickhouse(tbl); print(f"clickhouse loaded {ch_n:,}", flush=True)
    os_n = load_opensearch(tbl); print(f"opensearch loaded {os_n:,}", flush=True)
    # pick a real process_guid for the point-lookup
    guid = ch.query(f"SELECT process_guid FROM {TBL} LIMIT 1 OFFSET {N//2}").result_rows[0][0]
    TOKEN = "netsvcs"  # appears in one command-line template -> text search

    # --- two-regime query suite: 3 aggregations (columnar turf) + 2 lookups (index turf) ---
    Q = {}
    # AGG 1: top hosts by event count
    Q["agg_top_hosts"] = ("agg",
        lambda: ch.query(f"SELECT hostname, count() c FROM {TBL} GROUP BY hostname ORDER BY c DESC LIMIT 10").result_rows,
        lambda: req("POST", f"/{IDX}/_search?request_cache=false", json.dumps({"size": 0, "aggs": {"h": {"terms": {"field": "hostname", "size": 10}}}})))
    # AGG 2: distinct users per image (high-card distinct)
    Q["agg_distinct_users"] = ("agg",
        lambda: ch.query(f"SELECT image, uniqExact(subject_user) u FROM {TBL} GROUP BY image ORDER BY u DESC").result_rows,
        lambda: req("POST", f"/{IDX}/_search?request_cache=false", json.dumps({"size": 0, "aggs": {"i": {"terms": {"field": "image", "size": 20}, "aggs": {"u": {"cardinality": {"field": "subject_user"}}}}}})))
    # AGG 3: integrity_level histogram
    Q["agg_integrity_hist"] = ("agg",
        lambda: ch.query(f"SELECT integrity_level, count() c FROM {TBL} GROUP BY integrity_level").result_rows,
        lambda: req("POST", f"/{IDX}/_search?request_cache=false", json.dumps({"size": 0, "aggs": {"g": {"terms": {"field": "integrity_level"}}}})))
    # LOOKUP 1: exact process_guid (point lookup — index turf)
    Q["lookup_guid"] = ("lookup",
        lambda: ch.query(f"SELECT count() FROM {TBL} WHERE process_guid='{guid}'").result_rows,
        lambda: req("POST", f"/{IDX}/_search?request_cache=false", json.dumps({"size": 0, "track_total_hits": True, "query": {"term": {"process_guid": guid}}})))
    # LOOKUP 2: command_line text token (text search — index home turf)
    Q["lookup_cmdline_text"] = ("lookup",
        lambda: ch.query(f"SELECT count() FROM {TBL} WHERE positionCaseInsensitive(command_line,'{TOKEN}')>0").result_rows,
        lambda: req("POST", f"/{IDX}/_search?request_cache=false", json.dumps({"size": 0, "track_total_hits": True, "query": {"match": {"command_line": TOKEN}}})))

    res = {"bench": "edr-two-regime (#68 generalization)", "tier": "B", "n_rows": n, "guid": guid, "token": TOKEN,
           "ch_version": "26.5", "os_version": "3.7.0", "queries": {}}
    for name, (regime, chf, osf) in Q.items():
        ch_ms, ch_out = timeit(chf); os_ms, os_out = timeit(osf)
        # answer-equality where comparable (lookup counts)
        ch_cnt = ch_out[0][0] if regime == "lookup" else None
        os_cnt = (os_out.get("hits", {}).get("total", {}) or {}).get("value") if regime == "lookup" else None
        winner = "columnar(CH)" if ch_ms < os_ms else "index(OS)"
        ratio = round(max(ch_ms, os_ms) / max(min(ch_ms, os_ms), 0.01), 1)
        res["queries"][name] = {"regime": regime, "ch_ms": ch_ms, "os_ms": os_ms, "winner": winner,
                                "ratio": ratio, "ch_count": ch_cnt, "os_count": os_cnt,
                                "answer_equal": (ch_cnt == os_cnt) if ch_cnt is not None else None}
        print(f"  {name:24} [{regime:6}] CH={ch_ms}ms OS={os_ms}ms -> {winner} {ratio}x"
              + (f" (cnt {ch_cnt}=={os_cnt}? {ch_cnt==os_cnt})" if ch_cnt is not None else ""), flush=True)
    # two-regime verdict
    aggs = [v for v in res["queries"].values() if v["regime"] == "agg"]
    lkps = [v for v in res["queries"].values() if v["regime"] == "lookup"]
    res["columnar_wins_all_aggs"] = all(v["winner"].startswith("columnar") for v in aggs)
    res["index_wins_all_lookups"] = all(v["winner"].startswith("index") for v in lkps)
    res["two_regime_holds"] = res["columnar_wins_all_aggs"] and res["index_wins_all_lookups"]
    json.dump(res, open("/home/USER/sdw-lab-benchmarks/edr-two-regime/results/edr_two_regime.json", "w"), indent=2, default=str)
    print(f"\ntwo-regime on EDR/Sysmon: columnar wins all aggs={res['columnar_wins_all_aggs']} | "
          f"index wins all lookups={res['index_wins_all_lookups']} | HOLDS={res['two_regime_holds']}")


if __name__ == "__main__":
    main()

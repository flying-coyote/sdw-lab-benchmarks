#!/usr/bin/env python3
"""SOC query-shape bench #1 — C2 BEACONING detection (window-function regime).

External-review P4 named window/sort-heavy detection shapes as a candidate to INVERT the engine
ranking the flagship (flat scan-aggregation) and engine-join benches established. This measures the
beaconing shape — per (orig_h, resp_h) pair, the inter-arrival time gaps (LAG over time-ordered
connections), then the coefficient of variation of those gaps (low CV = a regular beacon) — across
the four Iceberg-reading engines on the SAME shared soc.conn table, alongside a matched FLAT
aggregation, so we can see whether the window regime reorders the engines.

SAFETY: structured Zeek conn flow only (ts/IPs/ports/proto — no free-text/message fields). Output is
aggregate (per-pair gap stats, counts, latencies) — no raw event rows are surfaced. Runs in-engine
inside the ejs-lab container. Tier B, single host (ejs stack).

Run: docker exec ejs-lab python3 /repo/soc-query-shapes/beacon_bench.py
"""
import json, os, statistics, time
from pathlib import Path

S3 = {"s3.endpoint": "http://minio:9000", "s3.access-key-id": "ejsbench",
      "s3.secret-access-key": "ejsbench123", "s3.path-style-access": "true"}
NESSIE = "http://nessie:19120/iceberg/"
CH_PW = "ejsbench123"
TIMEOUT = 300
TRIALS = 5
OUT = Path(os.environ.get("OUT_DIR", "/tmp/soc_shapes_results"))

SR_CATALOG = """CREATE EXTERNAL CATALOG IF NOT EXISTS iceberg PROPERTIES (
 'type'='iceberg','iceberg.catalog.type'='rest','iceberg.catalog.uri'='http://nessie:19120/iceberg/',
 'iceberg.catalog.warehouse'='warehouse','aws.s3.endpoint'='http://minio:9000',
 'aws.s3.enable_path_style_access'='true','aws.s3.enable_ssl'='false',
 'aws.s3.access_key'='ejsbench','aws.s3.secret_key'='ejsbench123','aws.s3.region'='us-east-1')"""


CONN = os.environ.get("CONN_TABLE", "soc.conn")     # namespace.name
LIM = int(os.environ.get("BEACON_LIMIT", "20"))
TRUTH_FILE = os.environ.get("TRUTH_FILE", "")        # optional ground-truth json for detection scoring

def ch_table_ref(table=CONN):
    from pyiceberg.catalog.rest import RestCatalog
    cat = RestCatalog("nessie", uri=NESSIE, warehouse="warehouse", **S3)
    loc = cat.load_table(table).metadata_location               # s3://warehouse/<ns>/<name>_<uuid>/metadata/xxx.metadata.json
    root = loc.split("/metadata/")[0].replace("s3://", "http://minio:9000/")
    return f"icebergS3('{root}', 'ejsbench', 'ejsbench123')"


# beaconing (window) + a matched flat aggregation. {T}=table, {LAG}, {SD}=stddev fn.
BEACON = """WITH gaps AS (
  SELECT orig_h, resp_h, ts - {LAG}(ts) OVER (PARTITION BY orig_h, resp_h ORDER BY ts) AS gap
  FROM {T} WHERE proto = 'tcp'
)
SELECT orig_h, resp_h, count(*) AS n, avg(gap) AS avg_gap, {SD}(gap) AS sd_gap, {SD}(gap)/avg(gap) AS cv
FROM gaps WHERE gap IS NOT NULL AND gap > 0
GROUP BY orig_h, resp_h HAVING count(*) >= 8 AND avg(gap) > 0
ORDER BY cv ASC, n DESC LIMIT {LIM}"""

FLAT = "SELECT proto, count(*) AS c FROM {T} GROUP BY proto ORDER BY c DESC"

ARMS = {
    "starrocks":         {"LAG": "lag",        "SD": "stddev_pop", "T": None},
    "trino":             {"LAG": "lag",        "SD": "stddev_pop", "T": None},
    "dremio":            {"LAG": "lag",        "SD": "stddev_pop", "T": None},
    "clickhouse_iceberg":{"LAG": "lagInFrame", "SD": "stddevPop",  "T": None},  # all filled at runtime from CONN
}


def median(xs): xs=sorted(xs); n=len(xs); return xs[n//2] if n%2 else (xs[n//2-1]+xs[n//2])/2


class StarRocks:
    def __init__(self):
        import pymysql
        self.c = pymysql.connect(host="starrocks", port=9030, user="root", connect_timeout=20, read_timeout=TIMEOUT)
        cur=self.c.cursor(); cur.execute(SR_CATALOG)
        try: cur.execute("SET new_planner_optimize_timeout=60000")
        except Exception: pass
    def run(self, sql):
        cur=self.c.cursor(); cur.execute(sql); return list(cur.fetchall())

class ClickHouse:
    def __init__(self):
        import clickhouse_connect
        self.c=clickhouse_connect.get_client(host="clickhouse", port=8123, password=CH_PW,
            send_receive_timeout=TIMEOUT, settings={"use_query_cache":0,"max_execution_time":TIMEOUT,
            "max_memory_usage":18_000_000_000})
    def run(self, sql): return [list(r) for r in self.c.query(sql).result_rows]

class Trino:
    def run(self, sql):
        import requests
        r=requests.post("http://trino:8080/v1/statement", data=sql.encode(), headers={"X-Trino-User":"ejs"}, timeout=TIMEOUT); r.raise_for_status()
        doc=r.json(); rows=[]; deadline=time.time()+TIMEOUT
        while True:
            rows+=doc.get("data",[]) or []
            if err:=doc.get("error"): raise RuntimeError(f"trino: {err.get('message')}")
            nxt=doc.get("nextUri")
            if not nxt: return rows
            if time.time()>deadline: raise TimeoutError("trino timeout")
            doc=requests.get(nxt, timeout=TIMEOUT).json()

class Dremio:
    BASE="http://dremio:9047"
    def __init__(self):
        import requests
        r=requests.post(f"{self.BASE}/apiv2/login", json={"userName":"admin","password":"dremioAdmin123"}, timeout=30); r.raise_for_status()
        self.auth={"Authorization":"_dremio"+r.json()["token"]}
    def run(self, sql):
        import requests
        job=requests.post(f"{self.BASE}/api/v3/sql", json={"sql":sql}, headers=self.auth, timeout=30).json()["id"]
        deadline=time.time()+TIMEOUT
        while True:
            st=requests.get(f"{self.BASE}/api/v3/job/{job}", headers=self.auth, timeout=30).json()
            s=st["jobState"]
            if s=="COMPLETED": break
            if s in ("FAILED","CANCELED"): raise RuntimeError(f"dremio: {st.get('errorMessage',s)}")
            if time.time()>deadline: raise TimeoutError("dremio timeout")
            time.sleep(0.05)
        rows=[]; off=0
        while True:
            pg=requests.get(f"{self.BASE}/api/v3/job/{job}/results?offset={off}&limit=500", headers=self.auth, timeout=30).json()
            b=[[row.get(c["name"]) for c in pg["schema"]] for row in pg["rows"]]; rows+=b; off+=len(b)
            if off>=pg["rowCount"] or not b: return rows

CLIENTS={"starrocks":StarRocks,"trino":Trino,"dremio":Dremio,"clickhouse_iceberg":ClickHouse}


def time_query(client, sql):
    client.run(sql)  # warmup
    ds=[]
    for _ in range(TRIALS):
        t0=time.perf_counter(); rows=client.run(sql); ds.append(time.perf_counter()-t0)
    return median(ds), ds, rows


def pairset(rows):
    # top-20 (orig_h,resp_h)+n integer set for answer-equality (cv/sd are float-fragile, kept informational)
    return sorted([(str(r[0]), str(r[1]), int(r[2])) for r in rows])


def main():
    ns, name = CONN.split(".")
    ARMS["starrocks"]["T"]=f"iceberg.{CONN}"
    ARMS["trino"]["T"]=f"iceberg.{CONN}"
    ARMS["dremio"]["T"]=f'nessie."{ns}"."{name}"'
    ARMS["clickhouse_iceberg"]["T"]=ch_table_ref(CONN)
    truth=set()
    if TRUTH_FILE and os.path.exists(TRUTH_FILE):
        td=json.loads(open(TRUTH_FILE).read()); truth={(p[0],p[1]) for p in td.get("truth_pairs",[])}
    print(f"table={CONN} limit={LIM} truth_pairs={len(truth)} CH={ARMS['clickhouse_iceberg']['T']}", flush=True)
    out={"bench":"soc-query-shapes/beaconing (window-function regime)","tier":"B","host":"ejs single host",
         "table":CONN,"trials":TRIALS,"limit":LIM,"n_truth":len(truth),"arms":{}}
    for arm, sub in ARMS.items():
        try:
            client=CLIENTS[arm]()
            beacon_sql=BEACON.format(**sub, LIM=LIM); flat_sql=FLAT.format(T=sub["T"])
            bmed,bds,brows=time_query(client, beacon_sql)
            fmed,fds,frows=time_query(client, flat_sql)
            ps=pairset(brows); pairs=[(p[0],p[1]) for p in ps]
            rec={"beacon_median_s":round(bmed,4),"beacon_trials":[round(x,4) for x in bds],
                 "beacon_cv_pct":round(100*statistics.stdev(bds)/statistics.mean(bds),1) if len(bds)>1 else 0,
                 "flat_median_s":round(fmed,4),
                 "window_over_flat_x":round(bmed/fmed,1) if fmed else None,
                 "suspicious_pairs":len(ps),"top_pairset_hash":hash(tuple(ps))}
            if truth:
                tp=sum(1 for p in pairs if p in truth)
                rec["detection"]={"returned":len(ps),"true_pos":tp,"false_pos":len(ps)-tp,
                    "recall_pct":round(100*tp/len(truth),1),
                    "precision_pct":round(100*tp/len(ps),1) if ps else None}
            out["arms"][arm]=rec
            det=(" | recall %.0f%% prec %.0f%%" % (rec["detection"]["recall_pct"], rec["detection"]["precision_pct"])) if truth and rec.get("detection",{}).get("precision_pct") is not None else ""
            print(f"{arm:20} beacon {bmed:.3f}s (cv {rec['beacon_cv_pct']}%) | flat {fmed:.3f}s "
                  f"| window/flat {rec['window_over_flat_x']}x | pairs {len(ps)}{det}", flush=True)
        except Exception as e:
            out["arms"][arm]={"error":str(e)[:300]}
            print(f"{arm:20} FAIL: {str(e)[:200]}", flush=True)
    # ranking under each regime
    bl={a:v["beacon_median_s"] for a,v in out["arms"].items() if "beacon_median_s" in v}
    fl={a:v["flat_median_s"] for a,v in out["arms"].items() if "flat_median_s" in v}
    out["beacon_ranking"]=sorted(bl, key=bl.get)
    out["flat_ranking"]=sorted(fl, key=fl.get)
    out["ranking_inverted"]=(out["beacon_ranking"]!=out["flat_ranking"])
    # answer-equality across arms (pairset hash agreement)
    hashes={a:v.get("top_pairset_hash") for a,v in out["arms"].items() if "top_pairset_hash" in v}
    out["pairset_agreement"]=(len(set(hashes.values()))==1) if hashes else None
    print("\nbeacon ranking:", out["beacon_ranking"])
    print("flat ranking:  ", out["flat_ranking"])
    print("ranking inverted by window regime:", out["ranking_inverted"])
    print("top-pairset agreement across arms:", out["pairset_agreement"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/"beacon.json").write_text(json.dumps(out, indent=2))
    print("-> results/beacon.json")


if __name__ == "__main__":
    main()

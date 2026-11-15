#!/usr/bin/env python3
"""Timed passes for deterministic-routing-noncircular (runs in the drn-lab container).

Adapted from engine-join-specialization/run_bench.py: same arm clients, same table-reference rendering,
same DNF classifier, same 300 s timeout with two strikes. Changes (pre-registered):
  * query sets: `anchor` = the 11 original ejs texts (ejs_queries.py, byte-identical copy), `corpus` =
    queries/corpus.json (frozen); answers gated against queries/anchor_ground_truth.json and
    results/oracle.json (DuckDB) respectively;
  * 1 discarded warmup + 5 timed trials (original: 7), median + CV;
  * every execution records the 1/5/15-minute load average (/proc/loadavg, host-wide) beside its duration;
  * server-side timeouts set on every arm so a client timeout cannot leave a query running;
  * results written after every query (resumable with --resume).

  python run_engines.py --arm <arm> [--set anchor|corpus|all] [--resume] [--trials 5]
  python run_engines.py --version <arm>
"""
import argparse
import json
import os
import statistics
import time
from pathlib import Path

from ejs_queries import QUERIES as ANCHORS, render, normalize, answers_equal

HERE = Path(__file__).parent
WORK = HERE / "_work"
RESULTS = HERE / "results"
S3_ENDPOINT = "http://minio:9000"
AK, SK = "drnbench", "drnbench123"
CH_PASSWORD = "drnbench123"
TIMEOUT = 300
ARMS = ["starrocks", "clickhouse_iceberg", "clickhouse_native", "trino"]

SR_CATALOG_SQL = f"""
CREATE EXTERNAL CATALOG IF NOT EXISTS iceberg PROPERTIES (
  'type'='iceberg','iceberg.catalog.type'='rest',
  'iceberg.catalog.uri'='http://nessie:19120/iceberg/',
  'iceberg.catalog.warehouse'='warehouse',
  'aws.s3.endpoint'='http://minio:9000','aws.s3.enable_path_style_access'='true',
  'aws.s3.enable_ssl'='false','aws.s3.access_key'='{AK}',
  'aws.s3.secret_key'='{SK}','aws.s3.region'='us-east-1')
"""


def loadavg():
    try:
        return [float(x) for x in Path("/proc/loadavg").read_text().split()[:3]]
    except Exception:
        return None


def table_refs(arm):
    locations = json.loads((WORK / "table_locations.json").read_text())
    refs = {}
    for ident, meta in locations.items():
        ns, name = ident.split(".")
        if arm in ("starrocks", "trino"):
            refs[name] = f"iceberg.{ns}.{name}"
        elif arm == "clickhouse_iceberg":
            http_loc = meta["location"].replace("s3://", f"{S3_ENDPOINT}/")
            refs[name] = f"icebergS3('{http_loc}', '{AK}', '{SK}')"
        elif arm == "clickhouse_native":
            refs[name] = f"bench.{name}"
    return refs


class StarRocks:
    def __init__(self):
        import pymysql
        self.conn = pymysql.connect(host="starrocks", port=9030, user="root",
                                    connect_timeout=20, read_timeout=TIMEOUT + 30)
        with self.conn.cursor() as c:
            c.execute(SR_CATALOG_SQL)
            for s in ("SET new_planner_optimize_timeout = 60000", f"SET query_timeout = {TIMEOUT}"):
                try:
                    c.execute(s)
                except Exception:
                    pass

    def run(self, sql):
        with self.conn.cursor() as c:
            c.execute(sql)
            return list(c.fetchall())

    def version(self):
        return self.run("SELECT current_version()")[0][0]


class ClickHouse:
    def __init__(self):
        import clickhouse_connect
        self.client = clickhouse_connect.get_client(
            host="clickhouse", port=8123, password=CH_PASSWORD, send_receive_timeout=TIMEOUT + 30,
            settings={"use_query_cache": 0, "max_execution_time": TIMEOUT,
                      "max_memory_usage": 18_000_000_000, "joined_subquery_requires_alias": 0})

    def run(self, sql):
        return [list(r) for r in self.client.query(sql).result_rows]

    def version(self):
        return self.run("SELECT version()")[0][0]


class Trino:
    HDR = {"X-Trino-User": "drn", "X-Trino-Session": f"query_max_run_time={TIMEOUT}s"}

    def run(self, sql):
        import requests
        r = requests.post("http://trino:8080/v1/statement", data=sql.encode(), headers=self.HDR, timeout=60)
        r.raise_for_status()
        doc = r.json()
        rows = []
        deadline = time.time() + TIMEOUT + 20
        while True:
            rows += doc.get("data", []) or []
            if err := doc.get("error"):
                raise RuntimeError(f"trino: {err.get('message')}")
            nxt = doc.get("nextUri")
            if not nxt:
                return rows
            if time.time() > deadline:
                try:
                    requests.delete(nxt, timeout=10)
                finally:
                    raise TimeoutError("trino: timeout")
            doc = requests.get(nxt, timeout=TIMEOUT).json()

    def version(self):
        return self.run("SELECT node_version FROM system.runtime.nodes")[0][0]


def make_client(arm):
    return {"starrocks": StarRocks, "clickhouse_iceberg": ClickHouse,
            "clickhouse_native": ClickHouse, "trino": Trino}[arm]()


def reconnect(arm, old):
    for _ in range(24):
        try:
            return make_client(arm)
        except Exception:
            time.sleep(5)
    return old


def classify(exc):
    s = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in s or "timed out" in s:
        return "timeout"
    if any(k in s for k in ("memory", "oom", "resource", "exceeded", "insufficient")):
        return "resource"
    if any(k in s for k in ("syntax", "parse", "unknown function", "cannot resolve",
                            "unsupported", "doesn't exist", "not supported", "mismatch")):
        return "dialect"
    return "error"


def query_set(which):
    out = []
    if which in ("anchor", "all"):
        gt = json.loads((HERE / "queries" / "anchor_ground_truth.json").read_text())
        out += [("anchor", qid, sql, gt[qid]) for qid, sql in ANCHORS.items()]
    if which in ("corpus", "all"):
        corpus = json.loads((HERE / "queries" / "corpus.json").read_text())["queries"]
        oracle = json.loads((RESULTS / "oracle.json").read_text())["answers"]
        out += [("corpus", q["id"], q["sql"], oracle.get(q["id"])) for q in corpus]
    return out


def run(arm, which, trials, resume):
    refs = table_refs(arm)
    client = make_client(arm)
    path = RESULTS / f"raw_{arm}.json"
    out = json.loads(path.read_text()) if (resume and path.exists()) else {"arm": arm, "queries": {}}
    out["engine_version"] = client.version()
    out["trials"] = trials
    for setname, qid, sql, gt in query_set(which):
        key = f"{setname}:{qid}"
        if resume and key in out["queries"] and ("median_s" in out["queries"][key] or "dnf" in out["queries"][key]):
            continue
        q = render(sql, refs)
        rec = {"set": setname, "id": qid, "runs": []}
        strikes, durations, answer = 0, [], None
        for i in range(trials + 1):
            la = loadavg()
            try:
                t0 = time.perf_counter()
                rows = client.run(q)
                dt = time.perf_counter() - t0
                rec["runs"].append({"i": i, "s": round(dt, 4), "load": la})
                if i > 0:
                    durations.append(dt)
                answer = normalize(rows)
            except Exception as e:
                dt = time.perf_counter() - t0
                strikes += 1
                rec["runs"].append({"i": i, "s": round(dt, 4), "load": la, "err": str(e)[:300]})
                rec["dnf"] = classify(e)
                rec["error"] = str(e)[:500]
                print(f"  {key} [{rec['dnf']}] {dt:.1f}s: {str(e)[:160]}", flush=True)
                if any(k in str(e).lower() for k in ("connection", "refused", "max retries", "broken pipe",
                                                     "lost connection", "remote end closed")):
                    client = reconnect(arm, client)
                if strikes >= 2:
                    break
        if durations and strikes < 2:
            rec.pop("dnf", None)
            rec.pop("error", None)
            rec["strikes"] = strikes
            rec["median_s"] = round(statistics.median(durations), 4)
            rec["cv_pct"] = round(100 * statistics.stdev(durations) / statistics.mean(durations), 1) \
                if len(durations) > 1 else None
            rec["answer"] = answer
            rec["matches_oracle"] = (answers_equal(answer, gt) if gt is not None else None)
            print(f"  {key}: median {rec['median_s']:.3f}s cv {rec['cv_pct']}% "
                  f"{'OK' if rec['matches_oracle'] else '**MISMATCH**'} load {rec['runs'][-1]['load']}", flush=True)
        out["queries"][key] = rec
        RESULTS.mkdir(exist_ok=True)
        path.write_text(json.dumps(out, indent=1))
    print(f"wrote {path}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=ARMS)
    ap.add_argument("--set", default="all", choices=["anchor", "corpus", "all"])
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--version", choices=ARMS)
    a = ap.parse_args()
    if a.version:
        print(make_client(a.version).version())
    else:
        run(a.arm, a.set, a.trials, a.resume)

#!/usr/bin/env python3
"""Timed passes + equality gate (runs in the ejs-lab container).

  python run_bench.py --smoke              # every arm reachable runs every query once,
                                           # answers gated vs _work/ground_truth.json
  python run_bench.py --arm <arm>          # 1 warmup + 7 timed trials per query
  python run_bench.py --compare            # equality matrix + CV-gated pairwise +
                                           # completion matrix -> results/comparison.json

Protocol (pre-registered): client-side wall time, persistent protocol per engine, 300 s
per-query timeout, two strikes = DNF (reason: dialect|resource|timeout), median + CV over
7 trials, claims gated on gap% > max(CV_a, CV_b).
"""
import argparse
import json
import statistics
import time
from pathlib import Path

from queries import QUERIES, FAMILIES, TPCH_TABLES, SOC_TABLES, render, normalize, \
    answers_equal

HERE = Path(__file__).parent
WORK = HERE / "_work"
RESULTS = HERE / "results"

S3_ENDPOINT = "http://minio:9000"
AK, SK = "ejsbench", "ejsbench123"
CH_PASSWORD = "ejsbench123"
TIMEOUT = 300
TRIALS = 7
ARMS = ["starrocks", "clickhouse_iceberg", "clickhouse_native", "trino", "dremio"]

SR_CATALOG_SQL = """
CREATE EXTERNAL CATALOG IF NOT EXISTS iceberg PROPERTIES (
  'type'='iceberg','iceberg.catalog.type'='rest',
  'iceberg.catalog.uri'='http://nessie:19120/iceberg/',
  'iceberg.catalog.warehouse'='warehouse',
  'aws.s3.endpoint'='http://minio:9000','aws.s3.enable_path_style_access'='true',
  'aws.s3.enable_ssl'='false','aws.s3.access_key'='ejsbench',
  'aws.s3.secret_key'='ejsbench123','aws.s3.region'='us-east-1')
"""


def table_refs(arm: str) -> dict:
    locations = json.loads((WORK / "table_locations.json").read_text())
    refs = {}
    for ident, meta in locations.items():
        ns, name = ident.split(".")
        if arm in ("starrocks", "trino"):
            refs[name] = f"iceberg.{ns}.{name}"
        elif arm == "clickhouse_iceberg":
            # icebergS3 with a planted sort-last metadata pin (load_tables.py pin):
            # Nessie's non-sequential metadata naming makes unpinned resolution unsafe
            http_loc = meta["location"].replace("s3://", f"{S3_ENDPOINT}/")
            refs[name] = f"icebergS3('{http_loc}', '{AK}', '{SK}')"
        elif arm == "clickhouse_native":
            refs[name] = f"bench.{name}"
        elif arm == "dremio":
            refs[name] = f'nessie."{ns}"."{name}"'
    return refs


# ---------------------------------------------------------------- arm clients

class StarRocks:
    def __init__(self):
        import pymysql
        self.conn = pymysql.connect(host="starrocks", port=9030, user="root",
                                    connect_timeout=20, read_timeout=TIMEOUT)
        with self.conn.cursor() as c:
            c.execute(SR_CATALOG_SQL)
            try:
                # planner-time guard, not perf tuning: cold-FE logical phase exceeded
                # the 3s default on Q3 in smoke; same spirit as the 300s query timeout
                c.execute("SET new_planner_optimize_timeout = 60000")
            except Exception:
                pass

    def run(self, sql):
        with self.conn.cursor() as c:
            c.execute(sql)
            return list(c.fetchall())


class ClickHouse:
    def __init__(self):
        import clickhouse_connect
        self.client = clickhouse_connect.get_client(
            host="clickhouse", port=8123, password=CH_PASSWORD,
            send_receive_timeout=TIMEOUT,
            settings={"use_query_cache": 0, "max_execution_time": TIMEOUT,
                      # protective cap below the 24g cgroup so an oversized join is a
                      # loud per-query MEMORY_LIMIT_EXCEEDED (resource DNF), not a dead
                      # server (Q21 OOM-killed the container in smoke)
                      "max_memory_usage": 18_000_000_000,
                      # icebergS3() is a table FUNCTION; CH requires aliases on table
                      # functions in JOINs unless relaxed (the canonical TPC-H texts
                      # don't alias). CH's own error message names this relaxation.
                      "joined_subquery_requires_alias": 0})

    def run(self, sql):
        return [list(r) for r in self.client.query(sql).result_rows]


class Trino:
    def run(self, sql):
        import requests
        r = requests.post("http://trino:8080/v1/statement", data=sql.encode(),
                          headers={"X-Trino-User": "ejs"}, timeout=TIMEOUT)
        r.raise_for_status()
        doc = r.json()
        rows = []
        deadline = time.time() + TIMEOUT
        while True:
            rows += doc.get("data", []) or []
            if err := doc.get("error"):
                raise RuntimeError(f"trino: {err.get('message')}")
            nxt = doc.get("nextUri")
            if not nxt:
                return rows
            if time.time() > deadline:
                raise TimeoutError("trino: timeout")
            doc = requests.get(nxt, timeout=TIMEOUT).json()


class Dremio:
    BASE = "http://dremio:9047"

    def __init__(self):
        import requests
        r = requests.post(f"{self.BASE}/apiv2/login", json={
            "userName": "admin", "password": "dremioAdmin123"}, timeout=30)
        r.raise_for_status()
        self.auth = {"Authorization": "_dremio" + r.json()["token"]}

    def run(self, sql):
        import requests
        job = requests.post(f"{self.BASE}/api/v3/sql", json={"sql": sql},
                            headers=self.auth, timeout=30).json()["id"]
        deadline = time.time() + TIMEOUT
        while True:
            st = requests.get(f"{self.BASE}/api/v3/job/{job}", headers=self.auth,
                              timeout=30).json()
            state = st["jobState"]
            if state == "COMPLETED":
                break
            if state in ("FAILED", "CANCELED"):
                raise RuntimeError(f"dremio: {st.get('errorMessage', state)}")
            if time.time() > deadline:
                raise TimeoutError("dremio: timeout")
            time.sleep(0.05)
        rows, offset = [], 0
        while True:
            page = requests.get(
                f"{self.BASE}/api/v3/job/{job}/results?offset={offset}&limit=500",
                headers=self.auth, timeout=30).json()
            batch = [[row.get(c["name"]) for c in page["schema"]] for row in page["rows"]]
            rows += batch
            offset += len(batch)
            if offset >= page["rowCount"] or not batch:
                return rows


def make_client(arm: str):
    return {"starrocks": StarRocks, "clickhouse_iceberg": ClickHouse,
            "clickhouse_native": ClickHouse, "trino": Trino, "dremio": Dremio}[arm]()


def reconnect(arm: str, old):
    """A crashed/restarting server must cost only its own query (DNF), not every
    query after it — retry the connection for up to 2 minutes."""
    for _ in range(24):
        try:
            return make_client(arm)
        except Exception:
            time.sleep(5)
    return old


def classify(exc: Exception) -> str:
    s = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in s or "timed out" in s:
        return "timeout"
    if any(k in s for k in ("memory", "oom", "resource", "exceeded", "insufficient")):
        return "resource"
    if any(k in s for k in ("syntax", "parse", "unknown function", "cannot resolve",
                            "unsupported", "doesn't exist", "not supported", "mismatch")):
        return "dialect"
    return "error"


# ---------------------------------------------------------------- passes

def run_queries(arm: str, trials: int, smoke: bool):
    gt = json.loads((WORK / "ground_truth.json").read_text())
    refs = table_refs(arm)
    client = make_client(arm)
    out = {"arm": arm, "smoke": smoke, "queries": {}}
    for name, sql in QUERIES.items():
        q = render(sql, refs)
        rec = {"sql": q}
        strikes = 0
        durations = []
        answer = None
        n_runs = 1 if smoke else trials + 1  # warmup + trials
        for i in range(n_runs):
            try:
                t0 = time.perf_counter()
                rows = client.run(q)
                dt = time.perf_counter() - t0
                if i > 0 or smoke:
                    durations.append(dt)
                answer = normalize(rows)
            except Exception as e:
                strikes += 1
                rec["dnf"] = classify(e)
                rec["error"] = str(e)[:500]
                print(f"  {name} [{rec['dnf']}]: {str(e)[:160]}", flush=True)
                s = str(e).lower()
                if any(k in s for k in ("connection", "refused", "max retries",
                                        "broken pipe", "lost connection")):
                    client = reconnect(arm, client)
                if strikes >= 2:
                    break
        if "dnf" not in rec or durations:
            rec.pop("dnf", None)
            rec.pop("error", None)
            rec["durations"] = [round(d, 4) for d in durations]
            rec["median_s"] = round(statistics.median(durations), 4)
            if len(durations) > 1:
                rec["cv_pct"] = round(
                    100 * statistics.stdev(durations) / statistics.mean(durations), 1)
            rec["answer"] = answer
            rec["matches_ground_truth"] = answers_equal(answer, gt[name])
            flag = "OK" if rec["matches_ground_truth"] else "**MISMATCH**"
            print(f"  {name}: median {rec['median_s']:.3f}s "
                  f"cv {rec.get('cv_pct', 0)}% answer {flag}", flush=True)
        out["queries"][name] = rec
    RESULTS.mkdir(exist_ok=True)
    suffix = "_smoke" if smoke else ""
    (RESULTS / f"raw_{arm}{suffix}.json").write_text(json.dumps(out, indent=2))
    print(f"wrote results/raw_{arm}{suffix}.json", flush=True)


def smoke_all():
    for arm in ARMS:
        print(f"--- smoke: {arm}", flush=True)
        try:
            run_queries(arm, 1, smoke=True)
        except Exception as e:
            print(f"  {arm} UNREACHABLE: {str(e)[:200]}", flush=True)


def compare():
    gt = json.loads((WORK / "ground_truth.json").read_text())
    raw = {}
    for arm in ARMS:
        p = RESULTS / f"raw_{arm}.json"
        if p.exists():
            raw[arm] = json.loads(p.read_text())["queries"]
    comp = {"queries": {}, "completion": {}}
    for name in QUERIES:
        entry = {"ground_truth_rows": len(gt[name]), "arms": {}, "pairwise": {}}
        ok_arms = {}
        for arm, queries in raw.items():
            rec = queries.get(name, {})
            if "median_s" in rec:
                entry["arms"][arm] = {
                    "median_s": rec["median_s"], "cv_pct": rec.get("cv_pct"),
                    "matches_ground_truth": rec["matches_ground_truth"]}
                if rec["matches_ground_truth"]:
                    ok_arms[arm] = rec
            else:
                entry["arms"][arm] = {"dnf": rec.get("dnf", "missing")}
        arms_sorted = sorted(ok_arms)
        for i, a in enumerate(arms_sorted):
            for b in arms_sorted[i + 1:]:
                ma, mb = ok_arms[a]["median_s"], ok_arms[b]["median_s"]
                gap = abs(ma - mb) / max(min(ma, mb), 1e-9) * 100
                cv_max = max(ok_arms[a].get("cv_pct") or 0, ok_arms[b].get("cv_pct") or 0)
                entry["pairwise"][f"{a}_vs_{b}"] = {
                    "faster": a if ma < mb else b,
                    "speedup": round(max(ma, mb) / max(min(ma, mb), 1e-9), 2),
                    "gap_pct": round(gap, 1), "cv_gate_pct": round(cv_max, 1),
                    "claimable": gap > cv_max}
        comp["queries"][name] = entry
    for arm in raw:
        done = sum(1 for n in QUERIES if "median_s" in raw[arm].get(n, {}))
        comp["completion"][arm] = f"{done}/{len(QUERIES)}"
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "comparison.json").write_text(json.dumps(comp, indent=2))
    print(json.dumps(comp["completion"], indent=2), flush=True)
    print("wrote results/comparison.json", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=ARMS)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()
    if args.smoke and args.arm:
        run_queries(args.arm, 1, smoke=True)
    elif args.smoke:
        smoke_all()
    elif args.compare:
        compare()
    elif args.arm:
        run_queries(args.arm, TRIALS, smoke=False)
    else:
        ap.print_help()

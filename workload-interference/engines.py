"""Per-arm engine clients for the workload-interference bench (#23).

Reuses the engine-join-specialization run_bench.py client patterns verbatim where they
exist (StarRocks/pymysql, ClickHouse/clickhouse_connect, Trino/statement-API,
Dremio/v3-job-API) and adds the two arms ejs did not carry:

  duckdb_parquet  an in-process DuckDB connection over the byte-identical pinned parquet
                  (lib.common.connect + configure_duckdb), so the embedded arm runs with
                  the repo's shared resource limits.
  starrocks_mv    a StarRocks client identical to `starrocks` except it leaves MV query
                  rewrite ON and exposes explain(), so run.py can EXPLAIN-verify that the
                  scheduled set rewrites onto the pre-built async MVs before scoring.
                  Building/refreshing the MVs is an operator step (see make_mvs.sql),
                  outside this client.

Design rule the harness depends on: every client is INDEPENDENTLY constructible and
holds its OWN session/connection. run.py opens one client per concurrent scheduled-load
worker and one for the probe driver, so the only contention measured is the engine's,
never a Python-side shared-cursor artifact. CH/SR/Trino/Dremio caches are disabled here
(README: "Result caches off").
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))  # repo root, for lib.common

ARMS = [
    "starrocks",
    "starrocks_mv",
    "clickhouse_iceberg",
    "clickhouse_native",
    "trino",
    "dremio",
    "duckdb_parquet",
]

# Server arms run inside the ejs docker network; the lab container reaches them by
# service name. duckdb_parquet runs in-process in whatever container/host invokes run.py
# (the lab container, which mounts the bench dir).
CH_PASSWORD = "ejsbench123"
TIMEOUT = 300  # per-query DNF ceiling, carried from the house protocol

SR_CATALOG_SQL = """
CREATE EXTERNAL CATALOG IF NOT EXISTS iceberg PROPERTIES (
  'type'='iceberg','iceberg.catalog.type'='rest',
  'iceberg.catalog.uri'='http://nessie:19120/iceberg/',
  'iceberg.catalog.warehouse'='warehouse',
  'aws.s3.endpoint'='http://minio:9000','aws.s3.enable_path_style_access'='true',
  'aws.s3.enable_ssl'='false','aws.s3.access_key'='ejsbench',
  'aws.s3.secret_key'='ejsbench123','aws.s3.region'='us-east-1')
"""


class StarRocks:
    """MV rewrite OFF (the README's `starrocks` arm). Reuses ejs StarRocks verbatim, plus
    a session-level switch that DISABLES transparent MV rewrite so the base-table plan is
    what runs."""

    mv_rewrite = False

    def __init__(self):
        import pymysql
        self.conn = pymysql.connect(host="starrocks", port=9030, user="root",
                                    connect_timeout=20, read_timeout=TIMEOUT)
        with self.conn.cursor() as c:
            c.execute(SR_CATALOG_SQL)
            try:
                c.execute("SET new_planner_optimize_timeout = 60000")
            except Exception:
                pass
            try:
                # explicit so both SR arms declare their rewrite state (README: the arm
                # "must declare the stats state it runs with"; same spirit for MV rewrite).
                c.execute(
                    f"SET enable_materialized_view_rewrite = "
                    f"{'true' if self.mv_rewrite else 'false'}")
            except Exception:
                pass

    def run(self, sql):
        with self.conn.cursor() as c:
            c.execute(sql)
            return list(c.fetchall())

    def explain(self, sql):
        with self.conn.cursor() as c:
            c.execute("EXPLAIN " + sql)
            return "\n".join(str(r[0]) for r in c.fetchall())


class StarRocksMV(StarRocks):
    """MV rewrite ON (the README's `starrocks_mv` arm, labeled an UPPER BOUND). Identical
    client; the pre-built async MVs (make_mvs.sql) plus this rewrite switch are the whole
    difference. run.py EXPLAIN-verifies rewrite on every scheduled shape before scoring."""

    mv_rewrite = True


class ClickHouse:
    """Reuses ejs ClickHouse verbatim, including the 18 GB max_memory_usage cap below the
    24 g cgroup (loud per-query resource DNF, not a dead server) and use_query_cache=0."""

    def __init__(self):
        import clickhouse_connect
        self.client = clickhouse_connect.get_client(
            host="clickhouse", port=8123, password=CH_PASSWORD,
            send_receive_timeout=TIMEOUT,
            settings={"use_query_cache": 0, "max_execution_time": TIMEOUT,
                      "max_memory_usage": 18_000_000_000,
                      "joined_subquery_requires_alias": 0})

    def run(self, sql):
        return [list(r) for r in self.client.query(sql).result_rows]


class Trino:
    """Reuses ejs Trino verbatim: statement API, follow nextUri to completion, 300 s
    deadline. A new client per call is stateless (no persistent session object), so each
    worker constructing its own Trino() is independent by construction."""

    def run(self, sql):
        import requests
        r = requests.post("http://trino:8080/v1/statement", data=sql.encode(),
                          headers={"X-Trino-User": "wi"}, timeout=TIMEOUT)
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
            import requests as _rq
            doc = _rq.get(nxt, timeout=TIMEOUT).json()


class Dremio:
    """Reuses ejs Dremio verbatim: v3 login + job API, poll to COMPLETED, page results.
    Reflections OFF is an engine-side state (README arm note), not set here."""

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


class DuckDBParquet:
    """In-process DuckDB over the pinned parquet, with the repo's shared resource limits
    (lib.common.connect applies memory_limit + temp_directory). The embedded arm: one
    engine per client, sharing the host cores — exactly the concurrency MODEL the
    H-ARCH-02 sweep contrasts with a server scheduler. Each worker's own DuckDBParquet()
    is its own connection, which is the real architecture, not a harness artifact."""

    def __init__(self):
        from lib import common
        self.con = common.connect()

    def run(self, sql):
        return self.con.execute(sql).fetchall()


_CLIENTS = {
    "starrocks": StarRocks,
    "starrocks_mv": StarRocksMV,
    "clickhouse_iceberg": ClickHouse,
    "clickhouse_native": ClickHouse,
    "trino": Trino,
    "dremio": Dremio,
    "duckdb_parquet": DuckDBParquet,
}


def make_client(arm: str):
    return _CLIENTS[arm]()


def reconnect(arm, old, attempts=24, wait=5):
    """A crashed/restarting server must cost only its own query, not every fire after it —
    retry the connection for up to ~2 min (ejs reconnect discipline)."""
    for _ in range(attempts):
        try:
            return make_client(arm)
        except Exception:
            time.sleep(wait)
    return old


def classify(exc: Exception) -> str:
    """Map an exception to a DNF reason, identical taxonomy to ejs run_bench.classify."""
    s = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in s or "timed out" in s:
        return "timeout"
    if any(k in s for k in ("memory", "oom", "resource", "exceeded", "insufficient")):
        return "resource"
    if any(k in s for k in ("syntax", "parse", "unknown function", "cannot resolve",
                            "unsupported", "doesn't exist", "not supported", "mismatch")):
        return "dialect"
    if any(k in s for k in ("connection", "refused", "max retries", "broken pipe",
                            "lost connection")):
        return "server"
    return "error"

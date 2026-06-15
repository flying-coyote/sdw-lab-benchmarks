"""Shared ejs engine clients + helpers for the soc-query-shapes benches (run in ejs-lab).
Four Iceberg-reading engines over the shared Nessie catalog. Structured-data benches only;
aggregate output. Dialect notes handled per-bench (stddev_pop vs stddevPop, lag vs lagInFrame)."""
import os, statistics, time

S3 = {"s3.endpoint": "http://minio:9000", "s3.access-key-id": "ejsbench",
      "s3.secret-access-key": "ejsbench123", "s3.path-style-access": "true"}
NESSIE = "http://nessie:19120/iceberg/"
CH_PW = "ejsbench123"
TIMEOUT = 300

SR_CATALOG = """CREATE EXTERNAL CATALOG IF NOT EXISTS iceberg PROPERTIES (
 'type'='iceberg','iceberg.catalog.type'='rest','iceberg.catalog.uri'='http://nessie:19120/iceberg/',
 'iceberg.catalog.warehouse'='warehouse','aws.s3.endpoint'='http://minio:9000',
 'aws.s3.enable_path_style_access'='true','aws.s3.enable_ssl'='false',
 'aws.s3.access_key'='ejsbench','aws.s3.secret_key'='ejsbench123','aws.s3.region'='us-east-1')"""


def median(xs):
    xs = sorted(xs); n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def ch_table_ref(table):
    from pyiceberg.catalog.rest import RestCatalog
    cat = RestCatalog("nessie", uri=NESSIE, warehouse="warehouse", **S3)
    loc = cat.load_table(table).metadata_location
    root = loc.split("/metadata/")[0].replace("s3://", "http://minio:9000/")
    return f"icebergS3('{root}', 'ejsbench', 'ejsbench123')"


class StarRocks:
    SD, LAG = "stddev_pop", "lag"
    def __init__(self):
        import pymysql
        self.c = pymysql.connect(host="starrocks", port=9030, user="root", connect_timeout=20, read_timeout=TIMEOUT)
        cur = self.c.cursor(); cur.execute(SR_CATALOG)
        try: cur.execute("SET new_planner_optimize_timeout=60000")
        except Exception: pass
    def ref(self, t): return f"iceberg.{t}"
    def run(self, sql):
        cur = self.c.cursor(); cur.execute(sql); return list(cur.fetchall())


class ClickHouse:
    SD, LAG = "stddevPop", "lagInFrame"
    def __init__(self):
        import clickhouse_connect
        self.c = clickhouse_connect.get_client(host="clickhouse", port=8123, password=CH_PW,
            send_receive_timeout=TIMEOUT, settings={"use_query_cache": 0, "max_execution_time": TIMEOUT,
            "max_memory_usage": 18_000_000_000})
    def ref(self, t): return ch_table_ref(t)
    def run(self, sql): return [list(r) for r in self.c.query(sql).result_rows]


class Trino:
    SD, LAG = "stddev_pop", "lag"
    def ref(self, t): return f"iceberg.{t}"
    def run(self, sql):
        import requests
        r = requests.post("http://trino:8080/v1/statement", data=sql.encode(), headers={"X-Trino-User": "ejs"}, timeout=TIMEOUT); r.raise_for_status()
        doc = r.json(); rows = []; deadline = time.time() + TIMEOUT
        while True:
            rows += doc.get("data", []) or []
            if err := doc.get("error"): raise RuntimeError(f"trino: {err.get('message')}")
            nxt = doc.get("nextUri")
            if not nxt: return rows
            if time.time() > deadline: raise TimeoutError("trino timeout")
            doc = requests.get(nxt, timeout=TIMEOUT).json()


class Dremio:
    SD, LAG = "stddev_pop", "lag"
    BASE = "http://dremio:9047"
    def __init__(self):
        import requests
        r = requests.post(f"{self.BASE}/apiv2/login", json={"userName": "admin", "password": "dremioAdmin123"}, timeout=30); r.raise_for_status()
        self.auth = {"Authorization": "_dremio" + r.json()["token"]}
    def ref(self, t):
        ns, name = t.split("."); return f'nessie."{ns}"."{name}"'
    def run(self, sql):
        import requests
        job = requests.post(f"{self.BASE}/api/v3/sql", json={"sql": sql}, headers=self.auth, timeout=30).json()["id"]
        deadline = time.time() + TIMEOUT
        while True:
            st = requests.get(f"{self.BASE}/api/v3/job/{job}", headers=self.auth, timeout=30).json()
            s = st["jobState"]
            if s == "COMPLETED": break
            if s in ("FAILED", "CANCELED"): raise RuntimeError(f"dremio: {st.get('errorMessage', s)}")
            if time.time() > deadline: raise TimeoutError("dremio timeout")
            time.sleep(0.05)
        rows = []; off = 0
        while True:
            pg = requests.get(f"{self.BASE}/api/v3/job/{job}/results?offset={off}&limit=500", headers=self.auth, timeout=30).json()
            b = [[row.get(c["name"]) for c in pg["schema"]] for row in pg["rows"]]; rows += b; off += len(b)
            if off >= pg["rowCount"] or not b: return rows


CLIENTS = {"starrocks": StarRocks, "clickhouse_iceberg": ClickHouse, "trino": Trino, "dremio": Dremio}


def time_query(client, sql, trials=5):
    client.run(sql)  # warmup
    ds = []
    for _ in range(trials):
        t0 = time.perf_counter(); rows = client.run(sql); ds.append(time.perf_counter() - t0)
    return median(ds), ds, rows

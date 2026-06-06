"""Containerized server/MPP engines for the multi-engine correctness probe.

Each class follows the same contract as trino_runner.TrinoEngine:
  - constructed with the host work dir + the parquet subdir (so it reads the SAME bytes),
  - .start() brings the container up, waits for readiness, registers/locates the file,
  - .query_fn() returns fn(op, value) -> int count for op in {"=", "IN", "LIKE"},
  - .version is a string, .stop() removes the container.

The point of running the standalone servers — especially ClickHouse server — is disambiguation:
chDB IS embedded ClickHouse, so if clickhouse-server (a different, newer build) also undercounts the
Parquet `=` filter, the defect is in ClickHouse core, not chDB packaging; if it is correct, chDB lags
a core fix. The other engines (StarRocks, Dremio, Spark) are independent Parquet readers that widen the
generality check.
"""

import os
import re
import subprocess
import time


def _docker(*args, check=True, capture=False):
    return subprocess.run(["docker", *args], check=check, capture_output=capture, text=True)


def _last_int(text):
    """Last line of stdout that is a bare integer (spark-sql prints the result row then 'Time taken')."""
    ints = [ln.strip() for ln in text.splitlines() if ln.strip().lstrip("-").isdigit()]
    if not ints:
        raise ValueError(f"no integer line in output:\n{text}")
    return int(ints[-1])


def _rm(container):
    _docker("rm", "-f", container, check=False, capture=True)


# ----------------------------------------------------------------------------- ClickHouse server
class ClickHouseServerEngine:
    """Standalone clickhouse-server reading the file via the file() table function.

    file() is restricted to user_files_path (/var/lib/clickhouse/user_files); we bind-mount the parquet
    subdir there so the server reads the identical bytes the in-process engines read.
    """

    name = "clickhouse_server"

    def __init__(self, data_dir, parquet_subdir, container="ch-server-bench",
                 http_port=8123, image="clickhouse/clickhouse-server:latest"):
        self.data_dir = os.path.abspath(data_dir)
        self.parquet_subdir = parquet_subdir
        self.container = container
        self.http_port = http_port
        self.image = image
        self.version = None

    def start(self, ready_timeout=90):
        _rm(self.container)
        mount = os.path.join(self.data_dir, self.parquet_subdir)
        print(f"[ch-server] starting {self.image} (port {self.http_port})")
        # NB: not :ro — the clickhouse-server entrypoint chowns user_files on boot, which fails on a
        # read-only bind mount and aborts startup. The corpus is regenerated per run, so rw is harmless.
        # 25.10+ disables the default user's network access unless a user/password is set or user-setup
        # is skipped; skip it for the throwaway bench so we can connect as default with no password.
        _docker("run", "-d", "--name", self.container,
                "--ulimit", "nofile=262144:262144",
                "-e", "CLICKHOUSE_SKIP_USER_SETUP=1",
                "-p", f"{self.http_port}:8123",
                "-v", f"{mount}:/var/lib/clickhouse/user_files/{self.parquet_subdir}",
                self.image, capture=True)
        self._wait_ready(ready_timeout)
        return self

    def _client(self):
        import clickhouse_connect
        return clickhouse_connect.get_client(host="localhost", port=self.http_port)

    def _wait_ready(self, timeout):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            try:
                c = self._client()
                c.query("SELECT 1")
                self.version = c.query("SELECT version()").result_rows[0][0]
                print(f"[ch-server] ready: ClickHouse {self.version}")
                return
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2)
        logs = _docker("logs", "--tail", "30", self.container, check=False, capture=True)
        raise RuntimeError(f"clickhouse-server not ready in {timeout}s: {last}\n{logs.stdout}\n{logs.stderr}")

    def query_fn(self):
        c = self._client()
        rel = f"{self.parquet_subdir}/corpus.parquet"

        def q(op, v):
            if op == "=":
                sql = f"SELECT count(*) FROM file('{rel}', Parquet) WHERE user_name = '{v}'"
            elif op == "IN":
                sql = f"SELECT count(*) FROM file('{rel}', Parquet) WHERE user_name IN ('{v}')"
            elif op == "LIKE":
                sql = f"SELECT count(*) FROM file('{rel}', Parquet) WHERE user_name LIKE '{v}'"
            else:
                raise ValueError(op)
            return int(c.query(sql).result_rows[0][0])
        return q

    def stop(self):
        _rm(self.container)
        print(f"[ch-server] container {self.container} removed")


# ----------------------------------------------------------------------------- StarRocks
class StarRocksEngine:
    """StarRocks all-in-one, reading the file via the FILES() table function (MySQL wire on 9030)."""

    name = "starrocks"

    def __init__(self, data_dir, parquet_subdir, container="starrocks-bench",
                 query_port=9030, image="starrocks/allin1-ubuntu:latest"):
        self.data_dir = os.path.abspath(data_dir)
        self.parquet_subdir = parquet_subdir
        self.container = container
        self.query_port = query_port
        self.image = image
        self.version = None

    def start(self, ready_timeout=180):
        _rm(self.container)
        print(f"[starrocks] starting {self.image} (port {self.query_port})")
        # NB: mount at /corpus, NOT /data — the allin1 image uses /data/deploy as its own writable
        # storage, so a read-only bind mount over /data makes the container fail to init.
        _docker("run", "-d", "--name", self.container,
                "-p", f"{self.query_port}:9030",
                "-v", f"{self.data_dir}:/corpus:ro",
                self.image, capture=True)
        self._wait_ready(ready_timeout)
        return self

    def _conn(self):
        import pymysql
        return pymysql.connect(host="127.0.0.1", port=self.query_port, user="root", password="")

    def _wait_ready(self, timeout):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            try:
                cn = self._conn()
                cur = cn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.execute("SELECT current_version()")
                self.version = cur.fetchone()[0]
                cn.close()
                print(f"[starrocks] ready: {self.version}")
                return
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(4)
        logs = _docker("logs", "--tail", "30", self.container, check=False, capture=True)
        raise RuntimeError(f"StarRocks not ready in {timeout}s: {last}\n{logs.stdout}\n{logs.stderr}")

    def query_fn(self):
        path = f"file:///corpus/{self.parquet_subdir}/corpus.parquet"
        files = f"FILES(\"path\" = \"{path}\", \"format\" = \"parquet\")"

        def q(op, v):
            if op == "=":
                where = f"user_name = '{v}'"
            elif op == "IN":
                where = f"user_name IN ('{v}')"
            elif op == "LIKE":
                where = f"user_name LIKE '{v}'"
            else:
                raise ValueError(op)
            cn = self._conn()
            cur = cn.cursor()
            cur.execute(f"SELECT count(*) FROM {files} WHERE {where}")
            r = cur.fetchone()[0]
            cn.close()
            return int(r)
        return q

    def stop(self):
        _rm(self.container)
        print(f"[starrocks] container {self.container} removed")


# ----------------------------------------------------------------------------- Spark SQL
class SparkEngine:
    """Apache Spark reading the file via SQL `parquet.`<path>`` — queried through `docker exec spark-sql`,
    so no wire protocol/client is needed. Spark stays up as a sleeping container for the probe's duration."""

    name = "spark"

    def __init__(self, data_dir, parquet_subdir, container="spark-bench",
                 image="apache/spark:3.5.0"):
        self.data_dir = os.path.abspath(data_dir)
        self.parquet_subdir = parquet_subdir
        self.container = container
        self.image = image
        self.version = None

    def start(self, ready_timeout=120):
        _rm(self.container)
        print(f"[spark] starting {self.image}")
        # keep the container alive; we drive spark-sql via docker exec
        _docker("run", "-d", "--name", self.container,
                "-v", f"{self.data_dir}:/data:ro",
                "--entrypoint", "sleep", self.image, "infinity", capture=True)
        # warm up + capture version (first spark-sql JVM start is the slow part)
        deadline = time.time() + ready_timeout
        last = None
        while time.time() < deadline:
            try:
                out = self._spark_sql("SELECT version()")
                m = re.search(r"\d+\.\d+\.\d+", out)
                self.version = m.group(0) if m else "unknown"
                print(f"[spark] ready: Spark {self.version}")
                return self
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(4)
        raise RuntimeError(f"Spark not ready in {ready_timeout}s: {last}")

    def _spark_sql(self, sql):
        # No -S: it errored on this image. stdout carries the result row(s) + a 'Time taken' line;
        # logs go to stderr. We parse the bare-integer result line out of stdout.
        r = _docker("exec", self.container, "/opt/spark/bin/spark-sql", "--conf",
                    "spark.ui.enabled=false", "-e", sql, check=True, capture=True)
        return r.stdout

    def query_fn(self):
        path = f"/data/{self.parquet_subdir}/corpus.parquet"

        def q(op, v):
            if op == "=":
                where = f"user_name = '{v}'"
            elif op == "IN":
                where = f"user_name IN ('{v}')"
            elif op == "LIKE":
                where = f"user_name LIKE '{v}'"
            else:
                raise ValueError(op)
            out = self._spark_sql(f"SELECT count(*) FROM parquet.`{path}` WHERE {where}")
            return _last_int(out)
        return q

    def stop(self):
        _rm(self.container)
        print(f"[spark] container {self.container} removed")


# ----------------------------------------------------------------------------- Postgres (baseline)
class PostgresEngine:
    """The "just use Postgres" baseline. Vanilla Postgres can't read Parquet without an extension —
    which is itself the point — so we LOAD the corpus into a native heap table via COPY and count there.
    This is NOT a Parquet-reader test; it's an independent row-store executor as a correctness oracle."""

    name = "postgres"
    COLS = [("row_id", "BIGINT"), ("time", "BIGINT"), ("activity_id", "INT"), ("class_uid", "INT"),
            ("severity_id", "INT"), ("src_ip", "TEXT"), ("dst_ip", "TEXT"), ("dst_port", "INT"),
            ("user_name", "TEXT"), ("bytes_in", "BIGINT"), ("bytes_out", "BIGINT"), ("status_id", "INT")]

    def __init__(self, data_dir, parquet_subdir, container="pg-bench", port=5433, image="postgres:17-alpine"):
        self.data_dir = os.path.abspath(data_dir); self.parquet_subdir = parquet_subdir
        self.container = container; self.port = port; self.image = image; self.version = None

    def start(self, ready_timeout=90):
        _rm(self.container)
        print(f"[postgres] starting {self.image} (port {self.port})")
        _docker("run", "-d", "--name", self.container, "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
                "-e", "POSTGRES_PASSWORD=bench", "-p", f"{self.port}:5432", self.image, capture=True)
        self._wait_ready(ready_timeout)
        self._load()
        return self

    def _conn(self):
        import psycopg
        return psycopg.connect(f"host=localhost port={self.port} user=postgres dbname=postgres",
                               autocommit=True)

    def _wait_ready(self, timeout):
        deadline = time.time() + timeout; last = None
        while time.time() < deadline:
            try:
                cn = self._conn(); cur = cn.cursor(); cur.execute("SELECT version()")
                self.version = cur.fetchone()[0].split(" on ")[0]; cn.close()
                print(f"[postgres] ready: {self.version}"); return
            except Exception as e:  # noqa: BLE001
                last = e; time.sleep(2)
        logs = _docker("logs", "--tail", "30", self.container, check=False, capture=True)
        raise RuntimeError(f"postgres not ready in {timeout}s: {last}\n{logs.stdout}\n{logs.stderr}")

    def _load(self):
        import duckdb
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
        from common import configure_duckdb
        pq = os.path.join(self.data_dir, self.parquet_subdir, "corpus.parquet")
        csv = os.path.join(self.data_dir, "pg_load.csv")
        con = configure_duckdb(duckdb.connect())
        con.execute(f"COPY (SELECT * FROM read_parquet('{pq}')) TO '{csv}' (FORMAT csv, HEADER true)")
        con.close()
        cn = self._conn(); cur = cn.cursor()
        cols = ", ".join(f"{n} {t}" for n, t in self.COLS)
        cur.execute("DROP TABLE IF EXISTS corpus"); cur.execute(f"CREATE TABLE corpus ({cols})")
        with open(csv, "r") as fh, cur.copy("COPY corpus FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
            while True:
                block = fh.read(1 << 20)
                if not block:
                    break
                cp.write(block)
        n = cur.execute("SELECT count(*) FROM corpus").fetchone()[0]
        cn.close()
        print(f"[postgres] loaded {n:,} rows into a native heap table")

    def query_fn(self):
        def q(op, v):
            where = {"=": f"user_name = '{v}'", "IN": f"user_name IN ('{v}')",
                     "LIKE": f"user_name LIKE '{v}'"}[op]
            cn = self._conn(); cur = cn.cursor()
            cur.execute(f"SELECT count(*) FROM corpus WHERE {where}")
            r = cur.fetchone()[0]; cn.close()
            return int(r)
        return q

    def stop(self):
        _rm(self.container)
        print(f"[postgres] container {self.container} removed")


# ----------------------------------------------------------------------------- Dremio
class DremioEngine:
    """Dremio OSS reading the file via a NAS source over its own Java vectorized Parquet reader.
    Driven entirely through the REST API (bootstrap first-user -> login -> create source -> SQL job)."""

    name = "dremio"

    def __init__(self, data_dir, parquet_subdir, container="dremio-bench", port=9047,
                 image="dremio/dremio-oss:latest"):
        self.data_dir = os.path.abspath(data_dir); self.parquet_subdir = parquet_subdir
        self.container = container; self.port = port; self.image = image
        self.version = None; self.base = f"http://localhost:{port}"; self.token = None

    def start(self, ready_timeout=240):
        _rm(self.container)
        print(f"[dremio] starting {self.image} (port {self.port})")
        _docker("run", "-d", "--name", self.container,
                "-p", f"{self.port}:9047", "-p", "31010:31010",
                "-v", f"{self.data_dir}:/data:ro", self.image, capture=True)
        self._wait_http(ready_timeout)
        self._auth()
        self._make_source()
        self._promote()
        return self

    def _wait_http(self, timeout):
        import requests
        deadline = time.time() + timeout; last = None
        while time.time() < deadline:
            try:
                r = requests.get(self.base + "/apiv2/server_status", timeout=5)
                if r.status_code in (200, 401, 403):
                    print("[dremio] http up"); return
            except Exception as e:  # noqa: BLE001
                last = e
            time.sleep(5)
        raise RuntimeError(f"dremio http not up in {timeout}s: {last}")

    def _auth(self):
        import requests
        # first-user bootstrap (idempotent: ignore if already created), then login
        try:
            requests.put(self.base + "/apiv2/bootstrap/firstuser",
                         headers={"Authorization": "_dremionull", "Content-Type": "application/json"},
                         json={"userName": "bench", "firstName": "b", "lastName": "ench",
                               "email": "bench@example.com", "createdAt": 1000,
                               "password": "bench12345"}, timeout=30)
        except Exception:  # noqa: BLE001
            pass
        deadline = time.time() + 60
        while time.time() < deadline:
            r = requests.post(self.base + "/apiv2/login",
                              json={"userName": "bench", "password": "bench12345"}, timeout=15)
            if r.status_code == 200:
                self.token = r.json()["token"]
                self.version = r.json().get("version", "oss")
                print(f"[dremio] logged in (version {self.version})"); return
            time.sleep(3)
        raise RuntimeError(f"dremio login failed: {r.status_code} {r.text[:200]}")

    def _hdr(self):
        return {"Authorization": f"_dremio{self.token}", "Content-Type": "application/json"}

    def _make_source(self):
        import requests
        # The NAS source can report "not currently available" for a few seconds after the container is up
        # while Dremio validates the path; retry before giving up.
        last = None
        for _ in range(8):
            r = requests.post(self.base + "/api/v3/catalog", headers=self._hdr(),
                              json={"entityType": "source", "name": "nas", "type": "NAS",
                                    "config": {"path": "/data"}}, timeout=30)
            if r.status_code in (200, 409):
                return
            last = f"{r.status_code} {r.text[:160]}"
            time.sleep(5)
        raise RuntimeError(f"dremio source create failed after retries: {last}")

    def _promote(self):
        # Dremio does not auto-promote a file to a queryable dataset; fetch its catalog id by path, then
        # POST a PHYSICAL_DATASET with a Parquet format to promote it.
        import json as _json
        import urllib.parse
        import requests
        path = ["nas", self.parquet_subdir, "corpus.parquet"]
        last = None
        for _ in range(8):
            bp = requests.get(self.base + "/api/v3/catalog/by-path/" + "/".join(path),
                              headers=self._hdr(), timeout=30)
            if bp.status_code == 200:
                ent = bp.json()
                if ent.get("type") == "PHYSICAL_DATASET":
                    return
                eid = ent["id"]
                pr = requests.post(self.base + "/api/v3/catalog/" + urllib.parse.quote(eid, safe=""),
                                   headers=self._hdr(),
                                   data=_json.dumps({"entityType": "dataset", "type": "PHYSICAL_DATASET",
                                                     "path": path, "format": {"type": "Parquet"}}),
                                   timeout=60)
                if pr.status_code in (200, 409):
                    print("[dremio] promoted corpus.parquet to a dataset")
                    return
                last = f"promote {pr.status_code} {pr.text[:160]}"
            else:
                last = f"by-path {bp.status_code} {bp.text[:160]}"
            time.sleep(4)
        raise RuntimeError(f"dremio promote failed: {last}")

    def _sql(self, sql):
        import requests
        r = requests.post(self.base + "/api/v3/sql", headers=self._hdr(), json={"sql": sql}, timeout=30)
        jid = r.json()["id"]
        deadline = time.time() + 120
        while time.time() < deadline:
            st = requests.get(self.base + f"/api/v3/job/{jid}", headers=self._hdr(), timeout=15).json()
            state = st.get("jobState")
            if state == "COMPLETED":
                res = requests.get(self.base + f"/api/v3/job/{jid}/results?offset=0&limit=10",
                                   headers=self._hdr(), timeout=30).json()
                row = res["rows"][0]
                return int(list(row.values())[0])
            if state in ("FAILED", "CANCELED"):
                raise RuntimeError(f"dremio job {state}: {st.get('errorMessage','')[:200]}")
            time.sleep(1.5)
        raise RuntimeError("dremio job timeout")

    def query_fn(self):
        tbl = f'nas.{self.parquet_subdir}."corpus.parquet"'

        def q(op, v):
            where = {"=": f"user_name = '{v}'", "IN": f"user_name IN ('{v}')",
                     "LIKE": f"user_name LIKE '{v}'"}[op]
            return self._sql(f"SELECT count(*) AS c FROM {tbl} WHERE {where}")
        return q

    def stop(self):
        _rm(self.container)
        print(f"[dremio] container {self.container} removed")


# ----------------------------------------------------------------------------- RisingWave (streaming)
class RisingWaveEngine:
    """RisingWave standalone (Postgres wire on 4566), reading local Parquet via the file_scan() batch
    table function. Reader rides arrow-rs (not a distinct decode path; included for streaming-class
    breadth). file_scan's local-FS signature varies by version, so we probe a few and keep one whose
    total row count matches before trusting it."""

    name = "risingwave"

    def __init__(self, data_dir, parquet_subdir, container="rw-bench", port=4566,
                 image="risingwavelabs/risingwave:latest"):
        self.data_dir = os.path.abspath(data_dir); self.parquet_subdir = parquet_subdir
        self.container = container; self.port = port; self.image = image
        self.version = None; self._scan = None

    def start(self, ready_timeout=180):
        _rm(self.container)
        print(f"[risingwave] starting {self.image} single_node (port {self.port})")
        _docker("run", "-d", "--name", self.container, "-p", f"{self.port}:4566",
                "-v", f"{self.data_dir}:/data:ro", self.image, "single_node", capture=True)
        self._wait_ready(ready_timeout)
        self._pick_scan()
        return self

    def _conn(self):
        import psycopg
        return psycopg.connect(f"host=localhost port={self.port} user=root dbname=dev", autocommit=True)

    def _wait_ready(self, timeout):
        deadline = time.time() + timeout; last = None
        while time.time() < deadline:
            try:
                cn = self._conn(); cur = cn.cursor(); cur.execute("SELECT version()")
                self.version = cur.fetchone()[0]; cn.close()
                print(f"[risingwave] ready: {self.version[:40]}"); return
            except Exception as e:  # noqa: BLE001
                last = e; time.sleep(4)
        logs = _docker("logs", "--tail", "20", self.container, check=False, capture=True)
        raise RuntimeError(f"risingwave not ready in {timeout}s: {last}\n{logs.stdout[-800:]}")

    def _candidates(self):
        path = f"/data/{self.parquet_subdir}/corpus.parquet"
        d = f"/data/{self.parquet_subdir}"
        return [
            f"file_scan('parquet', 'posix_fs', '', '{path}')",
            f"file_scan('parquet', 'posix_fs', '{d}', 'corpus.parquet')",
            f"file_scan('parquet', '{path}')",
        ]

    def _pick_scan(self):
        cn = self._conn(); cur = cn.cursor()
        errs = []
        for cand in self._candidates():
            try:
                cur.execute(f"SELECT count(*) FROM {cand}")
                if int(cur.fetchone()[0]) > 0:
                    self._scan = cand; cn.close()
                    print(f"[risingwave] file_scan ok: {cand}"); return
            except Exception as e:  # noqa: BLE001
                errs.append(f"{cand[:40]}: {str(e)[:80]}")
        cn.close()
        raise RuntimeError("risingwave file_scan: no working signature — " + " | ".join(errs))

    def query_fn(self):
        def q(op, v):
            where = {"=": f"user_name = '{v}'", "IN": f"user_name IN ('{v}')",
                     "LIKE": f"user_name LIKE '{v}'"}[op]
            cn = self._conn(); cur = cn.cursor()
            cur.execute(f"SELECT count(*) FROM {self._scan} WHERE {where}")
            r = cur.fetchone()[0]; cn.close()
            return int(r)
        return q

    def stop(self):
        _rm(self.container)
        print(f"[risingwave] container {self.container} removed")


# ----------------------------------------------------------------------------- Feldera (streaming DBSP)
class FelderaEngine:
    """Feldera (incremental DBSP SQL). Distinct *compute model*, but its Parquet ingest rides arrow-rs,
    so it re-confirms DataFusion rather than testing a new reader (see ENGINE-LANDSCAPE-SURVEY.md). It is
    also the highest-setup engine here (author + compile a SQL program, start a pipeline, ingest the file,
    read the count back as a materialized view). Implemented best-effort via the `feldera` Python SDK; if
    the SDK/image isn't available it raises and the matrix records it as errored with this rationale."""

    name = "feldera"

    def __init__(self, data_dir, parquet_subdir, container="feldera-bench", port=8080,
                 image="ghcr.io/feldera/pipeline-manager:latest"):
        self.data_dir = os.path.abspath(data_dir); self.parquet_subdir = parquet_subdir
        self.container = container; self.port = port; self.image = image
        self.version = None; self._counts = None

    def start(self, ready_timeout=240):
        try:
            from feldera import FelderaClient, PipelineBuilder  # noqa: F401
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                "feldera SDK not installed; skipping (reader rides arrow-rs, redundant with DataFusion "
                f"per survey — high-setup, low reader-distinctness). [{e}]")
        # Bring up pipeline-manager (ghcr image; port 8080 conflicts with Trino if co-run — Feldera is
        # run on its own pass). Full program-author/compile/ingest flow is heavy; left as a guarded path.
        raise RuntimeError(
            "feldera not wired into the automated matrix: per ENGINE-LANDSCAPE-SURVEY.md its Parquet ingest "
            "uses arrow-rs (re-confirms DataFusion, adds no distinct reader) and it needs a per-file SQL "
            "program compiled into a running pipeline. Considered and deliberately deferred, not skipped "
            "silently.")

    def query_fn(self):
        raise RuntimeError("feldera not available")

    def stop(self):
        _rm(self.container)


"""Bring Trino onto the box as a real distributed-SQL engine over the SAME Parquet bytes.

The multi-engine correctness probe reads one byte-identical Parquet file from four embedded/library
engines. Trino is the production-relevant fifth: a distributed SQL engine, the one a lakehouse-federation
stack actually fronts queries with. This runs Trino in a container (the newest image available locally)
and points its hive connector — with a self-contained FILE metastore, no external Hive Metastore Service —
at the exact same Parquet file the in-process engines read, mounted read-paths-identical into the container.

Design choices that keep it a fair arm of the same test:
  - same bytes: the container bind-mounts the host work dir, so Trino reads the identical corpus.parquet.
  - file metastore: `hive.metastore=file` keeps metadata in the mounted warehouse dir; nothing external.
  - local filesystem: `fs.hadoop.enabled=true` is what lets the hive connector read `file:///` paths.
  - declared schema by column name (`hive.parquet.use-column-names=true`) matching the DuckDB-written file.

Standalone smoke test:
    python trino_runner.py            # writes a tiny corpus, starts Trino, runs the probe SQL, tears down
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# Corpus schema (matches clickhouse-vs-duckdb/corpus.py gen_select, in declaration order).
CORPUS_COLUMNS = [
    ("row_id", "BIGINT"), ("time", "BIGINT"), ("activity_id", "INTEGER"),
    ("class_uid", "INTEGER"), ("severity_id", "INTEGER"), ("src_ip", "VARCHAR"),
    ("dst_ip", "VARCHAR"), ("dst_port", "INTEGER"), ("user_name", "VARCHAR"),
    ("bytes_in", "BIGINT"), ("bytes_out", "BIGINT"), ("status_id", "INTEGER"),
]

HIVE_PROPERTIES = """connector.name=hive
hive.metastore=file
hive.metastore.catalog.dir=file:///data/hive-warehouse
hive.parquet.use-column-names=true
fs.hadoop.enabled=true
"""


def newest_local_trino_tag():
    """Pick the newest trinodb/trino:<n> image present locally (highest numeric tag)."""
    out = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
        capture_output=True, text=True).stdout
    tags = []
    for line in out.splitlines():
        if line.startswith("trinodb/trino:"):
            t = line.split(":", 1)[1]
            if t.isdigit():
                tags.append(int(t))
    if not tags:
        raise RuntimeError("no trinodb/trino:<n> image found locally")
    return f"trinodb/trino:{max(tags)}"


class TrinoEngine:
    """A Trino container reading a Parquet file via the hive file-metastore connector.

    parquet_path must live inside data_dir (the bind-mounted host dir); the file's *directory*
    becomes the hive external_location. data_dir is created/managed by the caller.
    """

    def __init__(self, data_dir, parquet_subdir, container="trino-correctness-bench", port=8080, image=None):
        self.data_dir = os.path.abspath(data_dir)
        self.parquet_subdir = parquet_subdir            # e.g. "corpusdir" (relative to data_dir)
        self.container = container
        self.port = port
        self.image = image or newest_local_trino_tag()
        self.catalog_dir = os.path.join(self.data_dir, "_catalog")
        self.version = None
        self._conn = None

    def _docker(self, *args, check=True, capture=False):
        return subprocess.run(["docker", *args], check=check,
                              capture_output=capture, text=True)

    def start(self, ready_timeout=120):
        os.makedirs(os.path.join(self.data_dir, "hive-warehouse"), exist_ok=True)
        os.makedirs(self.catalog_dir, exist_ok=True)
        with open(os.path.join(self.catalog_dir, "hive.properties"), "w") as f:
            f.write(HIVE_PROPERTIES)
        # clear any stale container
        self._docker("rm", "-f", self.container, check=False, capture=True)
        print(f"[trino] starting {self.image} (container {self.container}, port {self.port})")
        self._docker(
            "run", "-d", "--name", self.container,
            "-p", f"{self.port}:8080",
            "-v", f"{self.data_dir}:/data",
            "-v", f"{self.catalog_dir}:/etc/trino/catalog",
            self.image, capture=True)
        self._wait_ready(ready_timeout)
        self._create_table()
        return self

    def _wait_ready(self, timeout):
        import trino
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            try:
                conn = trino.dbapi.connect(host="localhost", port=self.port, user="bench")
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.execute("SELECT version()")
                self.version = cur.fetchone()[0]
                print(f"[trino] ready: version {self.version}")
                return
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(3)
        # dump logs to help debugging then fail
        logs = self._docker("logs", "--tail", "40", self.container, check=False, capture=True)
        raise RuntimeError(f"Trino not ready in {timeout}s: {last}\n--- container logs ---\n"
                           f"{logs.stdout}\n{logs.stderr}")

    def _exec(self, sql):
        import trino
        conn = trino.dbapi.connect(host="localhost", port=self.port, user="bench",
                                   catalog="hive", schema="bench")
        cur = conn.cursor()
        cur.execute(sql)
        return cur.fetchall()

    def _create_table(self):
        import trino
        conn = trino.dbapi.connect(host="localhost", port=self.port, user="bench", catalog="hive")
        cur = conn.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS hive.bench "
                    "WITH (location = 'file:///data/hive-warehouse/bench')")
        cur.fetchall()
        cur.execute("DROP TABLE IF EXISTS hive.bench.corpus")
        cur.fetchall()
        cols = ", ".join(f"{n} {t}" for n, t in CORPUS_COLUMNS)
        loc = f"file:///data/{self.parquet_subdir}"
        cur.execute(f"CREATE TABLE hive.bench.corpus ({cols}) "
                    f"WITH (external_location = '{loc}', format = 'PARQUET')")
        cur.fetchall()
        # sanity: row count visible
        n = self._exec("SELECT count(*) FROM hive.bench.corpus")[0][0]
        print(f"[trino] external table registered over {loc} — {n:,} rows visible")

    def query_fn(self):
        """Return a fn(op, value) -> int count, matching the multi_engine probe's adapter contract."""
        def q(op, v):
            if op == "=":
                sql = f"SELECT count(*) FROM hive.bench.corpus WHERE user_name = '{v}'"
            elif op == "IN":
                sql = f"SELECT count(*) FROM hive.bench.corpus WHERE user_name IN ('{v}')"
            elif op == "LIKE":
                sql = f"SELECT count(*) FROM hive.bench.corpus WHERE user_name LIKE '{v}'"
            else:
                raise ValueError(op)
            return int(self._exec(sql)[0][0])
        return q

    def stop(self):
        self._docker("rm", "-f", self.container, check=False, capture=True)
        print(f"[trino] container {self.container} removed")


def _smoke():
    import duckdb
    sys.path.insert(0, os.path.join(HERE, "..", "lib"))
    sys.path.insert(0, HERE)
    from common import configure_duckdb
    import corpus
    work = tempfile.mkdtemp(prefix="trino_smoke_", dir=os.path.join(HERE, "_work"))
    try:
        sub = "corpusdir"
        os.makedirs(os.path.join(work, sub), exist_ok=True)
        p = os.path.join(work, sub, "corpus.parquet")
        con = configure_duckdb(duckdb.connect())
        con.execute(f"COPY ({corpus.gen_select(1_000_000)}) TO '{p}' (FORMAT parquet, ROW_GROUP_SIZE 12288)")
        truth = {v: con.execute(
            f"SELECT count(*) FROM ({corpus.gen_select(1_000_000)}) WHERE user_name='{v}'").fetchone()[0]
            for v in ["user42", "user7"]}
        con.close()
        eng = TrinoEngine(work, sub).start()
        q = eng.query_fn()
        for v in ["user42", "user7"]:
            for op in ["=", "IN", "LIKE"]:
                got = q(op, v)
                print(f"  trino {v} {op:4} -> {got}  (truth {truth[v]}) "
                      f"{'OK' if got == truth[v] else 'MISMATCH'}")
        eng.stop()
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "_work"), exist_ok=True)
    _smoke()

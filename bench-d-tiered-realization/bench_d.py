#!/usr/bin/env python3
"""BENCH-D — tiered-realization WRITE/COMMIT-FRESHNESS contract (achievable core).

Grounded by Gemini batch-2 DR #4, which asserted three hot-tier realization paradigms with distinct
freshness contracts: File-Write (Kafka->Flink->Iceberg, "1-5 min"), SQL/WAL (ClickHouse/Druid/Pinot,
"ms-sec"), Never-Write/Catalog-Inline (DuckLake, "sub-second"). The full streaming front (Kafka/Flink)
is out of scope without that infra; this measures the inherent STORAGE write->queryable contract that
each paradigm rests on, first-party, so the DR's asserted bands become measured numbers:

  - Catalog-inline  = DuckLake (DuckDB 1.5.3, local catalog + parquet data path)
  - SQL/WAL         = ClickHouse 26.5.1 native MergeTree INSERT
  - File-write      = Apache Iceberg append/commit (pyiceberg -> Nessie/MinIO)

Per paradigm x batch size: time write+commit (= freshness: when is the just-written data queryable)
and a follow-up count. Synthetic conn-like rows (structured; no adversarial text). Tier B, single
host. NOTE the file-write number is the raw Iceberg COMMIT cost, NOT the "1-5 min" — that band is a
Flink micro-batch checkpoint-interval CHOICE layered on top, not an inherent commit latency; this
bench isolates the commit cost to make that distinction measurable.

Run on host: /home/USER/sdw-lab-benchmarks/.venv/bin/python bench_d.py
"""
import json, os, random, statistics, time
from pathlib import Path
import pyarrow as pa

random.seed(7)
BATCHES = [1_000, 10_000, 100_000]
REPS = 3
OUT = Path(os.environ.get("OUT_DIR", str(Path(__file__).parent / "results")))
ARMS_TO_RUN = os.environ.get("ARMS", "ducklake,clickhouse,iceberg").split(",")
# default = host-mapped ports; in-container override via env to internal service names
S3 = {"s3.endpoint": os.environ.get("S3_ENDPOINT", "http://localhost:9300"), "s3.access-key-id": "ejsbench",
      "s3.secret-access-key": "ejsbench123", "s3.path-style-access": "true"}
NESSIE = os.environ.get("NESSIE_URI", "http://localhost:19320/iceberg/")
CH_HOST = os.environ.get("CH_HOST", "localhost")
CH_PORT = int(os.environ.get("CH_PORT", "8323"))


def gen_batch(n):
    return pa.table({
        "ts": pa.array([1.781e9 + random.random()*86400 for _ in range(n)], pa.float64()),
        "orig_h": [f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}" for _ in range(n)],
        "resp_h": [f"93.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}" for _ in range(n)],
        "resp_p": pa.array([random.choice([80,443,22,445,3389]) for _ in range(n)], pa.int32()),
        "proto": ["tcp"]*n,
        "orig_bytes": pa.array([random.randint(40,4000) for _ in range(n)], pa.int64()),
        "resp_bytes": pa.array([random.randint(40,8000) for _ in range(n)], pa.int64()),
    })


def med(xs): xs=sorted(xs); n=len(xs); return xs[n//2] if n%2 else (xs[n//2-1]+xs[n//2])/2


def arm_ducklake(batches):
    import duckdb
    import os, shutil
    for p in ("/tmp/benchd.ducklake", "/tmp/benchd_data"):
        try: (shutil.rmtree(p) if os.path.isdir(p) else os.remove(p))
        except Exception: pass
    con = duckdb.connect()
    con.execute("INSTALL ducklake; LOAD ducklake")
    con.execute("ATTACH 'ducklake:/tmp/benchd.ducklake' AS dl (DATA_PATH '/tmp/benchd_data')")
    con.execute("USE dl")
    con.execute("CREATE TABLE conn (ts DOUBLE, orig_h VARCHAR, resp_h VARCHAR, resp_p INTEGER, proto VARCHAR, orig_bytes BIGINT, resp_bytes BIGINT)")
    res={}
    for n in batches:
        wc=[]; q=[]
        for _ in range(REPS):
            df=gen_batch(n).to_pandas()
            t0=time.perf_counter(); con.execute("INSERT INTO conn SELECT * FROM df"); wc.append(time.perf_counter()-t0)
            t1=time.perf_counter(); con.execute("SELECT count(*) FROM conn").fetchall(); q.append(time.perf_counter()-t1)
        res[n]={"write_commit_s":round(med(wc),4),"query_s":round(med(q),4)}
    con.close()
    return res


def arm_clickhouse(batches):
    import clickhouse_connect
    c=clickhouse_connect.get_client(host=CH_HOST, port=CH_PORT, password="ejsbench123")
    c.command("DROP TABLE IF EXISTS benchd_freshness")
    c.command("""CREATE TABLE benchd_freshness (ts Float64, orig_h String, resp_h String, resp_p Int32,
                 proto String, orig_bytes Int64, resp_bytes Int64) ENGINE=MergeTree ORDER BY ts""")
    cols=["ts","orig_h","resp_h","resp_p","proto","orig_bytes","resp_bytes"]
    res={}
    for n in batches:
        wc=[]; q=[]
        for _ in range(REPS):
            b=gen_batch(n); data=[list(row) for row in zip(*[b.column(col).to_pylist() for col in cols])]
            t0=time.perf_counter(); c.insert("benchd_freshness", data, column_names=cols); wc.append(time.perf_counter()-t0)
            t1=time.perf_counter(); c.query("SELECT count() FROM benchd_freshness").result_rows; q.append(time.perf_counter()-t1)
        res[n]={"write_commit_s":round(med(wc),4),"query_s":round(med(q),4)}
    return res


def arm_iceberg(batches):
    from pyiceberg.catalog.rest import RestCatalog
    cat=RestCatalog("nessie", uri=NESSIE, warehouse="warehouse", **S3)
    cat.create_namespace_if_not_exists("soc")
    try: cat.drop_table("soc.benchd_freshness")
    except Exception: pass
    tbl=cat.create_table("soc.benchd_freshness", schema=gen_batch(1).schema)
    res={}
    for n in batches:
        wc=[]; q=[]
        for _ in range(REPS):
            b=gen_batch(n)
            t0=time.perf_counter(); tbl.append(b); wc.append(time.perf_counter()-t0)   # write data file + commit metadata
            t1=time.perf_counter(); sum(1 for _ in [tbl.scan().to_arrow()]); q.append(time.perf_counter()-t1)
        res[n]={"write_commit_s":round(med(wc),4),"query_s":round(med(q),4)}
    return res


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    p=OUT/"bench_d.json"
    out=json.loads(p.read_text()) if p.exists() else {
        "bench":"BENCH-D write/commit-freshness contract (achievable core; no Kafka/Flink front)",
        "tier":"B","host":"single host","batches":BATCHES,"reps":REPS,"arms":{}}
    out.setdefault("arms", {})
    candidates=[("ducklake","ducklake_catalog_inline", arm_ducklake),
                ("clickhouse","clickhouse_wal", arm_clickhouse),
                ("iceberg","iceberg_file_commit", arm_iceberg)]
    for key, name, fn in candidates:
        if key not in ARMS_TO_RUN: continue
        try:
            out["arms"][name]=fn(BATCHES)
            row=out["arms"][name]
            print(f"{name:26} " + " | ".join(f"{n//1000}k: wc {row[n]['write_commit_s']*1000:.0f}ms q {row[n]['query_s']*1000:.0f}ms" for n in BATCHES), flush=True)
        except Exception as e:
            out["arms"][name]={"error":str(e)[:300]}; print(f"{name:26} FAIL: {str(e)[:200]}", flush=True)
    p.write_text(json.dumps(out, indent=2))
    print(f"\n-> {p}")


if __name__ == "__main__":
    main()

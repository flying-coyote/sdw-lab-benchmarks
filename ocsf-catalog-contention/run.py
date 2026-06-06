"""T1.3 — concurrent-writer catalog contention: the adverse leg of H-DUCKLAKE-02 R6/R7 never tested.

R6 (planning) and R7 (streaming cadence) both ran a SINGLE writer. H-DUCKLAKE-02's original load-bearing
claim, though, is that DuckLake "loses advantage at enterprise scale due to catalog DB bottleneck" — a
*concurrent-write* failure mode that R0/R8 (reads) and R6/R7 (single writer) never exercised. This runs it.

N writer PROCESSES commit small batches concurrently to the SAME table, swept N ∈ {1,4,8,16}, on a
Postgres-backed catalog for BOTH engines (a single-file catalog only permits one writer, which would make
the test trivial; Postgres is the realistic concurrent backend and the one the vendor's bottleneck concern
is actually about). It is adverse to BOTH formats by construction:
  - Iceberg: optimistic concurrency on the table's metadata pointer -> concurrent appends conflict ->
    CommitFailedException -> refresh + retry. The retry rate IS the Iceberg contention cost.
  - DuckLake: every commit is a transaction against the shared SQL catalog -> the catalog is the
    serialization point. Latency growth / errors with writer count IS the bottleneck the hypothesis names.

Measured per (engine, N): aggregate throughput (rows/s), commit p50/p95 (ms, across all writers'
commits), retry count, hard-error count. Reports which degrades, and how, as concurrency rises.

    python run.py        # N in {1,4,8,16}, 20 commits/writer, 200 rows/commit, Postgres catalog on :5434
"""

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import BASE_EPOCH  # noqa: E402

# dedicated catalog databases per engine (reset each run); a DuckLake Postgres catalog stores ONE global
# data path, so all DuckLake trials share a fixed data path and differ only by table name.
PG = "host=localhost port=5434 user=postgres dbname=dlcat"
PG_SA = "postgresql+psycopg://postgres@localhost:5434/icecat"
PG_ADMIN = "host=localhost port=5434 user=postgres dbname=postgres"
WRITER_COUNTS = [1, 4, 8, 16]
COMMITS_PER_WRITER = 20
BATCH = 200
WORK = os.path.join(HERE, "_work")
DL_DATA = os.path.join(WORK, "dl_data")
ICE_WH = os.path.join(WORK, "ice_wh")


def _reset_catalogs():
    """Fresh Postgres catalog DBs + fresh data dirs, so each run starts clean and no stale DuckLake
    data-path registration lingers."""
    import shutil
    import psycopg
    cn = psycopg.connect(PG_ADMIN, autocommit=True)
    cur = cn.cursor()
    for db in ("dlcat", "icecat"):
        cur.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{db}'")
        cur.execute(f"DROP DATABASE IF EXISTS {db}")
        cur.execute(f"CREATE DATABASE {db}")
    cn.close()
    for d in (DL_DATA, ICE_WH):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)


def _pct(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return round(s[k], 2)


def _batch_sql(writer_id, ci, n):
    base = (writer_id * 10_000_000) + ci * n
    return (f"SELECT i AS id, {BASE_EPOCH*1000} + i AS time, {writer_id} AS writer, "
            f"(hash(i::VARCHAR)%5000000)::BIGINT AS bytes_out FROM range({base},{base+n}) t(i)")


# ----- workers (top-level so they pickle for ProcessPoolExecutor) -----
def _ducklake_writer(args):
    table, data_path, n_commits, batch, wid = args
    con = duckdb.connect()
    con.execute("LOAD ducklake; LOAD postgres")
    con.execute(f"ATTACH 'ducklake:postgres:{PG}' AS dl (DATA_PATH '{data_path}')")
    lat, retries, errors = [], 0, 0
    for ci in range(n_commits):
        ok = False
        for attempt in range(10):
            t0 = time.perf_counter()
            try:
                con.execute(f"INSERT INTO dl.{table} {_batch_sql(wid, ci, batch)}")
                lat.append((time.perf_counter() - t0) * 1000)
                ok = True
                break
            except Exception:  # noqa: BLE001 — catalog conflict / lock; back off and retry
                retries += 1
                time.sleep(0.01 * (attempt + 1))
        if not ok:
            errors += 1
    con.execute("DETACH dl")
    return {"lat": lat, "retries": retries, "errors": errors}


def _iceberg_writer(args):
    table, warehouse, n_commits, batch, wid = args
    from pyiceberg.catalog.sql import SqlCatalog
    import pyarrow as pa
    cat = SqlCatalog("ice", uri=PG_SA, warehouse=f"file://{warehouse}")
    tbl = cat.load_table(f"b.{table}")
    lat, retries, errors = [], 0, 0
    for ci in range(n_commits):
        base = (wid * 10_000_000) + ci * batch
        ab = pa.table({"id": list(range(base, base + batch)),
                       "time": [BASE_EPOCH * 1000 + i for i in range(base, base + batch)],
                       "writer": [wid] * batch,
                       "bytes_out": [(hash(str(i)) % 5_000_000) for i in range(base, base + batch)]})
        ok = False
        for attempt in range(10):
            t0 = time.perf_counter()
            try:
                tbl.append(ab)
                lat.append((time.perf_counter() - t0) * 1000)
                ok = True
                break
            except Exception:  # noqa: BLE001 — CommitFailedException on conflict: refresh + retry
                retries += 1
                time.sleep(0.01 * (attempt + 1))
                try:
                    tbl = cat.load_table(f"b.{table}")
                except Exception:
                    pass
        if not ok:
            errors += 1
    return {"lat": lat, "retries": retries, "errors": errors}


def _setup_table(engine, table, data_path, warehouse, con):
    """Create the empty target table before writers start (avoids a create-race)."""
    schema_cols = "id BIGINT, time BIGINT, writer INTEGER, bytes_out BIGINT"
    if engine == "ducklake":
        os.makedirs(data_path, exist_ok=True)
        con.execute(f"ATTACH 'ducklake:postgres:{PG}' AS dls (DATA_PATH '{data_path}')")
        con.execute(f"DROP TABLE IF EXISTS dls.{table}")
        con.execute(f"CREATE TABLE dls.{table} ({schema_cols})")
        con.execute("DETACH dls")
    else:
        from pyiceberg.catalog.sql import SqlCatalog
        import pyarrow as pa
        os.makedirs(warehouse, exist_ok=True)
        cat = SqlCatalog("ice", uri=PG_SA, warehouse=f"file://{warehouse}")
        try:
            cat.create_namespace("b")
        except Exception:
            pass
        try:
            cat.drop_table(f"b.{table}")
        except Exception:
            pass
        empty = pa.schema([("id", pa.int64()), ("time", pa.int64()),
                           ("writer", pa.int64()), ("bytes_out", pa.int64())])
        cat.create_table(f"b.{table}", schema=empty)


def trial(engine, n_writers):
    table = f"{engine}_w{n_writers}"
    data_path = DL_DATA      # fixed: DuckLake's PG catalog stores one global data path
    warehouse = ICE_WH
    con = duckdb.connect()
    con.execute("INSTALL ducklake; LOAD ducklake; INSTALL postgres; LOAD postgres")
    _setup_table(engine, table, data_path, warehouse, con)
    con.close()

    worker = _ducklake_writer if engine == "ducklake" else _iceberg_writer
    args = [(table, data_path if engine == "ducklake" else warehouse,
             COMMITS_PER_WRITER, BATCH, wid) for wid in range(n_writers)]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=n_writers) as ex:
        results = list(ex.map(worker, args))
    wall = time.perf_counter() - t0

    all_lat = [x for r in results for x in r["lat"]]
    total_commits = n_writers * COMMITS_PER_WRITER
    rows = total_commits * BATCH
    retries = sum(r["retries"] for r in results)
    errors = sum(r["errors"] for r in results)
    return {"engine": engine, "writers": n_writers, "commits": total_commits,
            "wall_s": round(wall, 2), "throughput_rows_s": round(rows / wall, 1) if wall else 0,
            "commit_p50_ms": _pct(all_lat, 50), "commit_p95_ms": _pct(all_lat, 95),
            "retries": retries, "errors": errors,
            "retry_per_commit": round(retries / total_commits, 3) if total_commits else 0}


def run():
    os.makedirs(WORK, exist_ok=True)
    _reset_catalogs()
    rows = []
    for nw in WRITER_COUNTS:
        for engine in ("ducklake", "iceberg"):
            r = trial(engine, nw)
            rows.append(r)
            print(f"  {engine:9} writers={nw:>2}  {r['throughput_rows_s']:>9.0f} rows/s  "
                  f"p50={r['commit_p50_ms']}ms p95={r['commit_p95_ms']}ms  "
                  f"retries={r['retries']} ({r['retry_per_commit']}/commit) errors={r['errors']}")

    def scaling(engine):
        rs = {r["writers"]: r for r in rows if r["engine"] == engine}
        base = rs[WRITER_COUNTS[0]]["commit_p95_ms"] or 0.01
        top = rs[WRITER_COUNTS[-1]]["commit_p95_ms"] or 0.01
        return {"p95_growth_x": round(top / base, 2),
                "throughput_at_max_writers": rs[WRITER_COUNTS[-1]]["throughput_rows_s"],
                "retries_at_max_writers": rs[WRITER_COUNTS[-1]]["retries"],
                "errors_total": sum(rs[w]["errors"] for w in WRITER_COUNTS)}
    result = {
        "benchmark": "ocsf-catalog-contention (T1.3) — concurrent writers, Postgres-backed catalog",
        "hypothesis": "H-DUCKLAKE-02 (the untested concurrent-write / catalog-bottleneck leg)",
        "evidence_tier": "B (single machine; concurrent processes; commit percentiles + retry counts)",
        "writer_counts": WRITER_COUNTS, "commits_per_writer": COMMITS_PER_WRITER, "batch_rows": BATCH,
        "catalog_backend": "PostgreSQL 17 (shared, port 5434) for both engines",
        "ducklake_scaling": scaling("ducklake"), "iceberg_scaling": scaling("iceberg"),
        "trials": rows,
    }
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(result, open(os.path.join(rdir, "results.json"), "w"), indent=2, sort_keys=True)
    open(os.path.join(rdir, "RESULTS.md"), "w").write(render_md(result))
    print(f"\nDuckLake p95 growth 1→{WRITER_COUNTS[-1]} writers: {result['ducklake_scaling']['p95_growth_x']}× | "
          f"Iceberg: {result['iceberg_scaling']['p95_growth_x']}×")
    print("wrote results/results.json + RESULTS.md")
    return result


def render_md(r):
    def block(rows, engine):
        return "\n".join(
            f"| {x['writers']} | {x['throughput_rows_s']:.0f} | {x['commit_p50_ms']} | {x['commit_p95_ms']} | "
            f"{x['retries']} ({x['retry_per_commit']}/commit) | {x['errors']} |"
            for x in rows if x["engine"] == engine)
    dl, ice = r["ducklake_scaling"], r["iceberg_scaling"]
    return f"""# Concurrent-writer catalog contention (T1.3) — H-DUCKLAKE-02's untested adverse leg

**Tier B · single machine · {r['catalog_backend']}.** N writer processes commit {r['commits_per_writer']}
batches of {r['batch_rows']} rows each, concurrently, to the SAME table, swept over writers
{r['writer_counts']}. R6/R7 only ran a single writer; the hypothesis's original "DuckLake loses at scale
because the catalog DB bottlenecks" claim is a *concurrent-write* mode, tested here for the first time.
Adverse to both: Iceberg's optimistic concurrency conflicts-and-retries; DuckLake's commits serialize on
the shared SQL catalog.

## DuckLake (catalog = Postgres)

| writers | rows/s | commit p50 (ms) | commit p95 (ms) | retries | hard errors |
|--:|--:|--:|--:|--:|--:|
{block(r['trials'], 'ducklake')}

## Iceberg (catalog = Postgres)

| writers | rows/s | commit p50 (ms) | commit p95 (ms) | retries | hard errors |
|--:|--:|--:|--:|--:|--:|
{block(r['trials'], 'iceberg')}

## Scaling 1 → {r['writer_counts'][-1]} writers

- **DuckLake**: commit p95 grows **{dl['p95_growth_x']}×**, throughput at max writers {dl['throughput_at_max_writers']:.0f} rows/s, {dl['retries_at_max_writers']} retries, {dl['errors_total']} hard errors total.
- **Iceberg**: commit p95 grows **{ice['p95_growth_x']}×**, throughput at max writers {ice['throughput_at_max_writers']:.0f} rows/s, {ice['retries_at_max_writers']} retries, {ice['errors_total']} hard errors total.

## Reading

This is the leg R6/R7 left open and the one the hypothesis's load-bearing claim actually rests on. The
table above is the honest adverse test of both formats under concurrency: whichever degrades — DuckLake by
catalog-commit serialization (p95 growth, eventually errors) or Iceberg by optimistic-concurrency conflicts
(retry storms) — is measured rather than assumed. Single machine, one catalog backend (Postgres), small
batches to maximise commit pressure; the transferable finding is the *shape of each format's degradation
as writers scale*, not the absolute rows/s on this host.
"""


if __name__ == "__main__":
    run()

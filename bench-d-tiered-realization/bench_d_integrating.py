#!/usr/bin/env python3
"""BENCH-D integrating run (H-TIERED-REALIZATION-01) — Window 1: the single-backend NULL baseline.

Pre-registered in PRE-REGISTRATION-integrating-2026-06-16.md (Platt strong inference; decision rule +
committed thresholds written before any number existed). This module establishes the two nulls the
multi-tier arm must beat to earn its complexity:

  Null-A = a single Iceberg table (Nessie/MinIO) holding the whole lifecycle, one DuckDB reader.
  Null-B = a single DuckLake table (DuckDB 1.5.3, catalog-inline, fully local) — the locality control.

Adversary fixes folded in (design panel wj6zv61h0, verdict FIX-FIRST):
  A  N-day corpus (the inherited gen_batch spanned one day -> no age axis). DAYS is swept.
  C  freshness is a no-warmup, fresh-commit-per-trial harness (NOT time_trials, whose warmup discards
     the cold first-read that IS freshness). Iceberg re-pins metadata + uses a fresh DuckDB connection
     per trial to defeat the metadata cache.
  D  plan_files() COUNT is deterministic (raw, no CV); EXPLAIN ANALYZE planning LATENCY is CV-gated.
  #5 metadata cache defeated per-trial for freshness; OS page cache NOT dropped (needs sudo) -> every
     timed number is labeled warm-cache, single-host, and the cold object-store regime is the named
     follow-up.

The multi-tier arm + watermark lifecycle + pinned-vs-naive correctness oracle + conservation invariant
(fix E) + degenerate all-Iceberg control are Window 2; this file leaves clearly-marked seams for them.

Run on host:  ~/sdw-lab-benchmarks/.venv/bin/python bench_d_integrating.py
"""
import json
import os
import shutil
import statistics
import sys
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from common import (  # noqa: E402
    BASE_EPOCH, new_rng, time_trials, logical_fingerprint, parquet_manifest, configure_duckdb,
)

# --- pre-registered config -------------------------------------------------------------------------
SUB_SEED = 4                       # BENCH-D sub-seed off lib.common MASTER_SEED
CV_BLOWOUT_PCT = 30.0              # committed: a timed dim with cv_pct > this invalidates the trial set
TRIALS = 7
FRESH_BATCH_ROWS = 10_000         # per-trial fresh-day batch for the freshness harness
# scale sweep: (rows, days) — base + one larger, per the chDB "don't trust one cheap scale" lesson
SCALES = [(700_000, 14), (2_800_000, 14)]
if os.environ.get("QUICK"):       # smoke mode
    SCALES = [(140_000, 14)]

OUT = Path(os.environ.get("OUT_DIR", str(Path(__file__).parent / "results")))
DUCKLAKE_CATALOG = "/tmp/benchd_int.ducklake"
DUCKLAKE_DATA = "/tmp/benchd_int_data"

S3 = {"s3.endpoint": os.environ.get("S3_ENDPOINT", "http://localhost:9300"),
      "s3.access-key-id": "ejsbench", "s3.secret-access-key": "ejsbench123",
      "s3.path-style-access": "true"}
NESSIE = os.environ.get("NESSIE_URI", "http://localhost:19320/iceberg/")
MINIO_HOST = os.environ.get("MINIO_HOST", "localhost:9300")

RESP_PORTS = [80, 443, 22, 445, 3389]


def _pct(xs):
    """median/min/max/cv summary for a list of ms samples (the no-warmup freshness reporter)."""
    xs = sorted(xs)
    n = len(xs)
    med = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
    mean = sum(xs) / n
    cv = (statistics.pstdev(xs) / mean * 100.0) if n > 1 and mean > 0 else 0.0
    return {"median_ms": round(med, 3), "min_ms": round(xs[0], 3), "max_ms": round(xs[-1], 3),
            "cv_pct": round(cv, 1), "trials": n, "warmup": 0}


def gen_day(day_index: int, n: int, rng) -> pa.Table:
    """One event-day's worth of conn-like rows. ts spans that day; event_day is the derived age axis.
    Fix A: ts = BASE_EPOCH + day_index*86400 + r*86400, so a corpus built from many days actually has
    many distinct event_day buckets (the inherited single-day generator could not)."""
    base = BASE_EPOCH + day_index * 86400
    ts = [base + rng.random() * 86400 for _ in range(n)]
    return pa.table({
        "ts": pa.array(ts, pa.float64()),
        "event_day": pa.array([day_index] * n, pa.int32()),
        "orig_h": [f"10.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}" for _ in range(n)],
        "resp_h": [f"93.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}" for _ in range(n)],
        "resp_p": pa.array([rng.choice(RESP_PORTS) for _ in range(n)], pa.int32()),
        "proto": ["tcp"] * n,
        "orig_bytes": pa.array([rng.randint(40, 4000) for _ in range(n)], pa.int64()),
        "resp_bytes": pa.array([rng.randint(40, 8000) for _ in range(n)], pa.int64()),
    })


def gen_corpus(n_rows: int, days: int):
    """The one corpus, generated once, fed to every arm. Even split across `days` event-days."""
    rng = new_rng(SUB_SEED)
    per = n_rows // days
    tables = []
    for d in range(days):
        k = per if d < days - 1 else (n_rows - per * (days - 1))
        tables.append(gen_day(d, k, rng))
    return pa.concat_tables(tables), rng


# --- the four pre-registered SOC-shaped workload queries (same text every arm) ---------------------
def workload(table_sql: str, max_day: int):
    return {
        "freshness_probe":  f"SELECT count(*) FROM {table_sql} WHERE event_day = {max_day}",
        "recent_window":    f"SELECT count(*) FROM {table_sql} WHERE event_day >= {max_day - 1}",
        "cold_aggregation": (f"SELECT resp_p, sum(orig_bytes + resp_bytes) b FROM {table_sql} "
                             f"GROUP BY resp_p ORDER BY b DESC"),
        "needle_lookup":    (f"SELECT count(*) FROM {table_sql} WHERE orig_h = '10.1.1.1'"),
    }


def scan_battery(con, table_sql: str, max_day: int):
    """CV-gated scan latency for the 4 queries (steady-state; time_trials is correct here)."""
    out = {}
    for name, q in workload(table_sql, max_day).items():
        out[name] = time_trials(lambda q=q: con.execute(q).fetchall(), warmup=2, trials=TRIALS)
        out[name]["cv_blown"] = out[name]["cv_pct"] > CV_BLOWOUT_PCT
    return out


def planning_latency(con, table_sql: str, max_day: int):
    """Fix D: EXPLAIN ANALYZE planning LATENCY only (CV-gated). The plan_files() COUNT is reported
    separately as deterministic. Measured on the boundary-crossing recent_window query."""
    q = workload(table_sql, max_day)["recent_window"]

    def plan_once():
        con.execute(f"EXPLAIN ANALYZE {q}").fetchall()
    res = time_trials(plan_once, warmup=2, trials=TRIALS)
    res["cv_blown"] = res["cv_pct"] > CV_BLOWOUT_PCT
    res["note"] = "EXPLAIN ANALYZE wall time (plan+exec instrument); steady-state, warm-cache"
    return res


# --- DuckDB / MinIO / Iceberg wiring ---------------------------------------------------------------
def duck():
    import duckdb
    con = configure_duckdb(duckdb.connect(database=":memory:"))
    con.execute("INSTALL iceberg; LOAD iceberg")
    con.execute("INSTALL httpfs; LOAD httpfs")
    con.execute(f"""CREATE OR REPLACE SECRET minio (TYPE s3, KEY_ID 'ejsbench', SECRET 'ejsbench123',
                    ENDPOINT '{MINIO_HOST}', URL_STYLE 'path', USE_SSL false, REGION 'us-east-1')""")
    return con


def iceberg_scan_sql(meta_location: str) -> str:
    # NB: pass the pinned metadata.json with NO allow_moved_paths — pyiceberg writes absolute s3://
    # manifest paths, and allow_moved_paths makes DuckDB re-resolve them against the metadata.json
    # path (doubling it -> 404). Plain form reads the absolute paths correctly (probed 2026-06-16).
    return f"iceberg_scan('{meta_location}')"


def iceberg_catalog():
    from pyiceberg.catalog.rest import RestCatalog
    return RestCatalog("nessie", uri=NESSIE, warehouse="warehouse", **S3)


def iceberg_total_bytes(tbl) -> dict:
    tasks = list(tbl.scan().plan_files())
    return {"n_data_files": len(tasks),
            "total_bytes": int(sum(t.file.file_size_in_bytes for t in tasks))}


# --- NULL-B: single DuckLake table ----------------------------------------------------------------
def null_b_ducklake(corpus: pa.Table, max_day: int) -> dict:
    import duckdb
    for p in (DUCKLAKE_CATALOG, DUCKLAKE_DATA):
        try:
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        except Exception:
            pass
    con = configure_duckdb(duckdb.connect())
    con.execute("INSTALL ducklake; LOAD ducklake")
    con.execute(f"ATTACH 'ducklake:{DUCKLAKE_CATALOG}' AS dl (DATA_PATH '{DUCKLAKE_DATA}')")
    con.execute("USE dl")
    con.execute("CREATE TABLE conn (ts DOUBLE, event_day INTEGER, orig_h VARCHAR, resp_h VARCHAR, "
                "resp_p INTEGER, proto VARCHAR, orig_bytes BIGINT, resp_bytes BIGINT)")
    con.register("corpus_rel", corpus)   # zero-copy Arrow -> DuckDB (no pandas in-container)
    con.execute("INSERT INTO conn SELECT * FROM corpus_rel")
    con.unregister("corpus_rel")

    fp = logical_fingerprint(con, "SELECT * FROM conn")
    scan = scan_battery(con, "conn", max_day)
    plan = planning_latency(con, "conn", max_day)

    # no-warmup freshness (fix C): each trial commits a brand-new day, times write+commit+first-read.
    def fresh_step(i):
        day = max_day + 1 + i
        batch = gen_day(day, FRESH_BATCH_ROWS, new_rng(SUB_SEED + 100 + i))
        con.register("fresh_rel", batch)
        t0 = time.perf_counter()
        con.execute("INSERT INTO conn SELECT * FROM fresh_rel")
        n = con.execute(f"SELECT count(*) FROM conn WHERE event_day = {day}").fetchone()[0]
        dt = (time.perf_counter() - t0) * 1000.0
        con.unregister("fresh_rel")
        assert n == FRESH_BATCH_ROWS, f"ducklake freshness read got {n}"
        return dt
    freshness = _pct([fresh_step(i) for i in range(TRIALS)])
    freshness["cv_blown"] = freshness["cv_pct"] > CV_BLOWOUT_PCT

    # storage (deterministic): sum DuckLake parquet bytes + a representative footer manifest
    files = [str(p) for p in Path(DUCKLAKE_DATA).rglob("*.parquet")]
    total = sum(os.path.getsize(f) for f in files)
    rep = parquet_manifest(con, max(files, key=os.path.getsize)) if files else {}
    storage = {"n_parquet_files": len(files), "total_bytes": int(total),
               "representative_footer": rep, "codec_note": "DuckLake default (Snappy / ~122,880 row-groups)"}
    con.close()
    return {"backend": "ducklake_single", "local": True,
            "logical_fingerprint": fp, "freshness_ingest": freshness,
            "scan_latency": scan, "planning_latency": plan, "storage": storage}


# --- NULL-A: single Iceberg table (Nessie/MinIO), per-day appends ----------------------------------
def null_a_iceberg(corpus: pa.Table, max_day: int) -> dict:
    cat = iceberg_catalog()
    cat.create_namespace_if_not_exists("soc")
    try:
        cat.drop_table("soc.benchd_int_null")
    except Exception:
        pass
    schema_tbl = corpus.slice(0, 1)
    tbl = cat.create_table("soc.benchd_int_null", schema=schema_tbl.schema)
    # per-day appends -> realistic freshly-tiered file accumulation (one data file per day)
    for d in range(max_day + 1):
        day_rows = corpus.filter(pc.equal(corpus["event_day"], d))
        if day_rows.num_rows:
            tbl.append(day_rows)
    tbl = cat.load_table("soc.benchd_int_null")
    meta = tbl.metadata_location
    plan_files_count = len(list(tbl.scan().plan_files()))  # fix D: deterministic, no CV
    bytes_info = iceberg_total_bytes(tbl)

    con = duck()
    scan_sql = iceberg_scan_sql(meta)
    fp = logical_fingerprint(con, f"SELECT * FROM {scan_sql}")
    scan = scan_battery(con, scan_sql, max_day)
    plan = planning_latency(con, scan_sql, max_day)

    # no-warmup freshness (fix C): append a fresh day, re-pin metadata, fresh DuckDB conn, first read.
    def fresh_step(i):
        day = max_day + 1 + i
        batch = gen_day(day, FRESH_BATCH_ROWS, new_rng(SUB_SEED + 200 + i))
        t0 = time.perf_counter()
        tbl.append(batch)                       # commit: data file + metadata
        tbl2 = cat.load_table("soc.benchd_int_null")   # re-pin new snapshot
        m2 = tbl2.metadata_location
        cfresh = duck()                         # fresh conn -> defeats DuckDB metadata cache
        n = cfresh.execute(
            f"SELECT count(*) FROM {iceberg_scan_sql(m2)} WHERE event_day = {day}").fetchone()[0]
        dt = (time.perf_counter() - t0) * 1000.0
        cfresh.close()
        assert n == FRESH_BATCH_ROWS, f"iceberg freshness read got {n}"
        return dt
    freshness = _pct([fresh_step(i) for i in range(TRIALS)])
    freshness["cv_blown"] = freshness["cv_pct"] > CV_BLOWOUT_PCT

    # footer of one Iceberg data file (read s3 parquet via the DuckDB secret)
    rep = {}
    try:
        first = list(tbl.scan().plan_files())[0].file.file_path
        rep = parquet_manifest(con, first.replace("s3://", "s3://"))
    except Exception as e:
        rep = {"footer_error": str(e)[:200]}
    storage = {"n_data_files": bytes_info["n_data_files"], "total_bytes": bytes_info["total_bytes"],
               "plan_files_count": plan_files_count, "representative_footer": rep,
               "codec_note": "pyiceberg default (ZSTD / ~1M row-groups)"}
    con.close()
    return {"backend": "iceberg_single", "local": False, "metadata_location": meta,
            "logical_fingerprint": fp, "freshness_ingest": freshness,
            "scan_latency": scan, "planning_latency": plan,
            "plan_files_count": plan_files_count, "storage": storage}


def run_scale(n_rows: int, days: int) -> dict:
    corpus, _ = gen_corpus(n_rows, days)
    max_day = days - 1
    label = f"{n_rows}rows_{days}days"
    print(f"\n=== scale {label}: {corpus.num_rows:,} rows over {days} days ===", flush=True)

    # corpus identity (fingerprint via a throwaway DuckDB over the in-memory arrow table)
    import duckdb
    c0 = configure_duckdb(duckdb.connect())
    c0.register("corpus_rel", corpus)
    corpus_fp = logical_fingerprint(c0, "SELECT * FROM corpus_rel")
    c0.close()

    print("  Null-B (DuckLake single, local) ...", flush=True)
    nb = null_b_ducklake(corpus, max_day)
    print(f"    freshness median {nb['freshness_ingest']['median_ms']:.1f}ms "
          f"(cv {nb['freshness_ingest']['cv_pct']}%)  storage {nb['storage']['total_bytes']:,}B", flush=True)

    print("  Null-A (Iceberg single, Nessie/MinIO) ...", flush=True)
    na = null_a_iceberg(corpus, max_day)
    print(f"    freshness median {na['freshness_ingest']['median_ms']:.1f}ms "
          f"(cv {na['freshness_ingest']['cv_pct']}%)  files {na['plan_files_count']} "
          f"storage {na['storage']['total_bytes']:,}B", flush=True)

    # gate-blocking: both nulls must return the identical corpus (answer-equality precondition)
    fps = {"corpus": corpus_fp, "null_b_ducklake": nb["logical_fingerprint"],
           "null_a_iceberg": na["logical_fingerprint"]}
    answer_equal = len(set(fps.values())) == 1
    print(f"    answer-equality (logical_fingerprint): {'PASS' if answer_equal else 'FAIL'}  {fps}", flush=True)

    return {"scale": label, "n_rows": corpus.num_rows, "days": days,
            "fingerprints": fps, "answer_equal": answer_equal,
            "null_b_ducklake": nb, "null_a_iceberg": na}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"bench": "BENCH-D integrating run — Window 1: single-backend NULL baseline",
           "hypothesis": "H-TIERED-REALIZATION-01", "tier": "B", "host": "single host",
           "cache_label": "warm-cache, single-host (OS page cache not dropped; cold object-store regime is the named follow-up)",
           "cv_blowout_pct": CV_BLOWOUT_PCT, "trials": TRIALS,
           "preregistration": "PRE-REGISTRATION-integrating-2026-06-16.md",
           "duckdb": __import__("duckdb").__version__, "pyiceberg": __import__("pyiceberg").__version__,
           "scales": []}
    for n_rows, days in SCALES:
        out["scales"].append(run_scale(n_rows, days))
    p = OUT / "bench_d_integrating_null.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"\n-> {p}")
    all_equal = all(s["answer_equal"] for s in out["scales"])
    print(f"answer-equality across all scales: {'PASS' if all_equal else 'FAIL — investigate before any latency claim'}")


if __name__ == "__main__":
    main()

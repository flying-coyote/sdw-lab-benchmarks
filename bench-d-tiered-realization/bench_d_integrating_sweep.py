#!/usr/bin/env python3
"""BENCH-D integrating run — Window 3: the planning-cliff file-accumulation sweep + storage at parity.

Settles the two SLO cards the head-to-head (Window 2) left open:

  1. PLANNING SLO (committed 200 ms). The breaking-points spine. Sweep a single Iceberg table to
     N small data files (N = 10/100/1,000/10,000), measure the metadata-planning latency (time to walk
     the manifest list, CV-gated — the COUNT is deterministic, reported raw per fix D) and a DuckDB scan,
     then COMPACT (overwrite -> few large files, the cold tier's mechanism) and re-measure. This finds
     whether monolithic fragmented Iceberg planning CLIFFS as files accumulate (the null's vulnerability)
     and whether compaction recovers it (tiering's separate-compaction-per-tier case). Cliff-vs-graceful
     is read off the planning-latency curve vs file count.

  2. STORAGE SLO (deterministic). Resolve the Window-1 codec confound: Iceberg looked smaller only
     because pyiceberg defaults ZSTD while DuckLake defaults Snappy. Write the SAME corpus via DuckDB at
     ZSTD and at Snappy and compare to the Iceberg ZSTD bytes — isolating codec from architecture, so the
     storage SLO is judged at parity.

ejs-network vantage. Run:
  docker cp bench-d-tiered-realization/bench_d_integrating_sweep.py ejs-lab:/work/bench-d-tiered-realization/
  docker exec -e S3_ENDPOINT=http://minio:9000 -e NESSIE_URI=http://nessie:19120/iceberg/ \
    -e MINIO_HOST=minio:9000 -e OUT_DIR=/work/results [-e NLIST=10,100,1000] \
    ejs-lab python3 /work/bench-d-tiered-realization/bench_d_integrating_sweep.py
"""
import json
import os
import statistics
import time
from pathlib import Path

import duckdb

import bench_d_integrating as B

CV_BLOWOUT_PCT = B.CV_BLOWOUT_PCT
NLIST = [int(x) for x in os.environ.get("NLIST", "10,100,1000,10000").split(",")]
SWEEP_ROWS = int(os.environ.get("SWEEP_ROWS", "700000"))
DAYS = 14
PLAN_TRIALS = int(os.environ.get("PLAN_TRIALS", "5"))
OUT = Path(os.environ.get("OUT_DIR", str(Path(__file__).parent / "results")))


def _pct(xs):
    xs = sorted(xs)
    n = len(xs)
    med = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
    mean = sum(xs) / n
    cv = (statistics.pstdev(xs) / mean * 100.0) if n > 1 and mean > 0 else 0.0
    r = {"median_ms": round(med, 3), "min_ms": round(xs[0], 3), "max_ms": round(xs[-1], 3),
         "cv_pct": round(cv, 1), "trials": n}
    r["cv_blown"] = r["cv_pct"] > CV_BLOWOUT_PCT
    return r


def time_plan_files(tbl):
    """Metadata-planning LATENCY (CV-gated): wall time to walk the manifest list and enumerate data
    files. The file COUNT this produces is deterministic and reported separately (fix D)."""
    samples = []
    for _ in range(PLAN_TRIALS):
        t0 = time.perf_counter()
        n = len(list(tbl.scan().plan_files()))
        samples.append((time.perf_counter() - t0) * 1000.0)
    return _pct(samples), n


def time_duck_scan(con, meta, max_day):
    q = f"SELECT count(*) FROM {B.iceberg_scan_sql(meta)} WHERE event_day >= {max_day - 1}"
    return B.time_trials(lambda: con.execute(q).fetchall(), warmup=2, trials=PLAN_TRIALS)


def sweep_one(corpus, max_day, N):
    cat = B.iceberg_catalog()
    cat.create_namespace_if_not_exists("soc")
    try:
        cat.drop_table("soc.benchd_sweep")
    except Exception:
        pass
    tbl = cat.create_table("soc.benchd_sweep", schema=corpus.slice(0, 1).schema)
    rows = corpus.num_rows
    per = max(1, rows // N)
    t0 = time.time()
    for i in range(N):
        start = i * per
        length = per if i < N - 1 else (rows - start)
        if length <= 0:
            break
        tbl.append(corpus.slice(start, length))
    build_s = round(time.time() - t0, 1)
    tbl = cat.load_table("soc.benchd_sweep")
    meta_frag = tbl.metadata_location
    plan_lat_frag, files_frag = time_plan_files(tbl)
    con = B.duck()
    scan_frag = time_duck_scan(con, meta_frag, max_day)

    # COMPACT — the cold tier's mechanism: overwrite into few large files + expire snapshots (assert it)
    t0 = time.time()
    tbl.overwrite(corpus)
    compact_s = round(time.time() - t0, 1)
    expire_ok = True
    try:
        tbl.maintenance.expire_snapshots().commit()
    except Exception as e:
        expire_ok = f"FAILED: {str(e)[:120]}"
    tbl = cat.load_table("soc.benchd_sweep")
    meta_comp = tbl.metadata_location
    plan_lat_comp, files_comp = time_plan_files(tbl)
    scan_comp = time_duck_scan(con, meta_comp, max_day)
    con.close()

    print(f"  N={N:>6}: frag {files_frag} files plan {plan_lat_frag['median_ms']:.1f}ms "
          f"scan {scan_frag['median_ms']:.1f}ms (build {build_s}s) -> compacted {files_comp} files "
          f"plan {plan_lat_comp['median_ms']:.1f}ms scan {scan_comp['median_ms']:.1f}ms (compact {compact_s}s)",
          flush=True)
    return {"N_appends": N,
            "fragmented": {"data_files": files_frag, "plan_latency": plan_lat_frag,
                           "scan_latency": scan_frag, "build_s": build_s},
            "compacted": {"data_files": files_comp, "plan_latency": plan_lat_comp,
                          "scan_latency": scan_comp, "compact_s": compact_s, "expire_ok": expire_ok}}


def storage_parity(corpus):
    """Isolate codec from architecture: same corpus, DuckDB ZSTD vs Snappy vs the Iceberg ZSTD bytes."""
    con = B.configure_duckdb(duckdb.connect())
    con.register("r", corpus)
    out = {}
    for codec in ("zstd", "snappy", "uncompressed"):
        p = f"/tmp/parity_{codec}.parquet"
        try:
            os.remove(p)
        except Exception:
            pass
        con.execute(f"COPY (SELECT {B_COLS} FROM r) TO '{p}' (FORMAT PARQUET, COMPRESSION '{codec}')")
        out[codec] = os.path.getsize(p)
    con.close()
    return out


B_COLS = "ts, event_day, orig_h, resp_h, resp_p, proto, orig_bytes, resp_bytes"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    corpus, _ = B.gen_corpus(SWEEP_ROWS, DAYS)
    max_day = DAYS - 1
    print(f"=== Window 3 sweep: {corpus.num_rows:,} rows, N in {NLIST} ===", flush=True)
    sweeps = [sweep_one(corpus, max_day, N) for N in NLIST]
    print("=== storage parity (codec isolated) ===", flush=True)
    parity = storage_parity(corpus)
    print(f"  DuckDB ZSTD {parity['zstd']:,}B | Snappy {parity['snappy']:,}B | "
          f"uncompressed {parity['uncompressed']:,}B", flush=True)
    out = {"bench": "BENCH-D integrating run — Window 3: planning-cliff sweep + storage parity",
           "hypothesis": "H-TIERED-REALIZATION-01", "tier": "B", "host": "single host",
           "cache_label": "warm-cache, single-host", "cv_blowout_pct": CV_BLOWOUT_PCT,
           "sweep_rows": SWEEP_ROWS, "planning_slo_ms": 200,
           "duckdb": duckdb.__version__, "pyiceberg": __import__("pyiceberg").__version__,
           "sweeps": sweeps, "storage_parity_bytes": parity}
    p = OUT / "bench_d_integrating_sweep.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"\n-> {p}")


if __name__ == "__main__":
    main()

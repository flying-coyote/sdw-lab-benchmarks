#!/usr/bin/env python3
"""§12 / H-EDGE-01 — resource-bounded detection on the edge: how tight can the box get before a
DuckDB hunting detection stops completing? Tests the constrained-inference / edge-analytics claim
that meaningful security detection runs under endpoint-class caps, and characterizes the FAILURE
SHAPE (graceful spill vs cliff) — the breaking-points framing the program favors, not a winner.

A representative multi-step hunting detection (per-host hourly volume Z-score — the UEBA two-level
aggregation: GROUP BY host,hour -> per-host mean/stddev -> flag Z>3) is run over a 10M-row synthetic
process/flow corpus under a swept DuckDB `memory_limit` (4G→2G→1G→512M→256M→128M) at endpoint thread
counts (4, 2, 1), with spill-to-disk enabled. For each (mem, threads) we record: completed?, latency,
and whether it spilled (temp files written). The floor = the tightest cap that still completes, and
whether it degrades gracefully (spills, slower) or cliffs (errors). Synthetic only. Tier B, single host.
"""
import os
import json, os, time, shutil, tempfile
import duckdb

N = int(os.environ.get("EDGE_N", "10000000"))
MEMS = ["4GB", "2GB", "1GB", "512MB", "256MB", "128MB"]
THREADS = [4, 2, 1]
OUT = os.path.expanduser("~/sdw-lab-benchmarks/duckdb-edge-floor/results/edge_floor.json")

# multi-step hunting detection (UEBA volume Z-score) — memory-intensive (two-level group + per-host stats)
DETECT = """
WITH hourly AS (
  SELECT host, (ts // 3600) AS hr, count(*) AS c FROM events GROUP BY host, (ts // 3600)
)
SELECT host, max(c) peak, avg(c) mean_c, stddev_pop(c) sd
FROM hourly GROUP BY host
HAVING count(*) >= 5 AND stddev_pop(c) > 0 AND (max(c)-avg(c))/stddev_pop(c) > 3
ORDER BY (max(c)-avg(c))/stddev_pop(c) DESC LIMIT 50
"""


def make_corpus(path):
    """Generate the corpus ONCE to a Parquet (so each capped run reads the same bytes)."""
    con = duckdb.connect()
    con.execute(f"""COPY (SELECT
        (1781000000 + (hash(i) % 604800))::BIGINT AS ts,
        'h' || ((hash(i) % 8000))::VARCHAR AS host,
        'u' || ((hash(i+11) % 20000))::VARCHAR AS user,
        ('proc' || (hash(i+1) % 200))::VARCHAR AS process,
        (hash(i+7) % 100000)::BIGINT AS bytes
        FROM range({N}) t(i)) TO '{path}' (FORMAT parquet, COMPRESSION zstd)""")
    con.close()


def run_capped(parquet, mem, threads):
    tmp = tempfile.mkdtemp(prefix=" duck_spill_".strip())
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{mem}'"); con.execute(f"SET threads={threads}")
    con.execute(f"SET temp_directory='{tmp}'"); con.execute("SET preserve_insertion_order=false")
    con.execute(f"CREATE VIEW events AS SELECT * FROM read_parquet('{parquet}')")
    rec = {"mem": mem, "threads": threads}
    try:
        # warm the file cache once (not timed) then time the detection
        con.execute("SELECT count(*) FROM events").fetchone()
        t0 = time.perf_counter()
        rows = con.execute(DETECT).fetchall()
        rec["latency_s"] = round(time.perf_counter() - t0, 2)
        rec["completed"] = True
        rec["flagged"] = len(rows)
        # spill detection: any temp files written?
        spilled = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(tmp) for f in fs)
        rec["spilled_bytes"] = spilled
        rec["spilled"] = spilled > 0
    except Exception as e:
        rec["completed"] = False
        rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        con.close(); shutil.rmtree(tmp, ignore_errors=True)
    return rec


def main():
    work = tempfile.mkdtemp(prefix="edge_")
    parquet = os.path.join(work, "events.parquet")
    print(f"generating {N:,}-row corpus...", flush=True)
    make_corpus(parquet)
    size_mb = os.path.getsize(parquet) / 1e6
    print(f"corpus {size_mb:.0f} MB parquet", flush=True)
    res = {"bench": "duckdb-edge-floor (H-EDGE-01 §12)", "tier": "B", "n_rows": N,
           "corpus_mb": round(size_mb, 1), "duckdb": duckdb.__version__, "runs": []}
    for threads in THREADS:
        for mem in MEMS:
            r = run_capped(parquet, mem, threads)
            res["runs"].append(r)
            status = (f"OK {r['latency_s']}s flagged={r['flagged']} spilled={r.get('spilled')}"
                      if r["completed"] else f"FAIL {r.get('error')}")
            print(f"  threads={threads} mem={mem:6} -> {status}", flush=True)
    # floor: tightest mem that completes at threads=1 (the most endpoint-like)
    t1 = [r for r in res["runs"] if r["threads"] == 1]
    completed_t1 = [r for r in t1 if r["completed"]]
    res["floor_mem_threads1"] = completed_t1[-1]["mem"] if completed_t1 else "none completed"
    res["graceful"] = any(r.get("spilled") and r["completed"] for r in res["runs"])
    res["any_cliff"] = any(not r["completed"] for r in res["runs"])
    json.dump(res, open(OUT, "w"), indent=2, default=str)
    shutil.rmtree(work, ignore_errors=True)
    print(f"\nedge floor (threads=1): completes down to {res['floor_mem_threads1']} | "
          f"graceful-spill seen={res['graceful']} | any hard-fail={res['any_cliff']}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()

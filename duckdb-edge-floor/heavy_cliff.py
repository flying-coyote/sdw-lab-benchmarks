#!/usr/bin/env python3
"""H-EDGE-01 cliff-finder — the memory-heavy detection the streaming UEBA agg didn't stress.
A high-cardinality group-by on (host,user,process,minute) over 10M rows builds a ~10M-entry hash
that must exceed tight caps, forcing DuckDB to spill (graceful) or fail (cliff). Sweeps memory_limit
at threads=1 (the most endpoint-like) to find the floor + the failure SHAPE. Synthetic. Tier B."""
import os
import json, os, time, shutil, tempfile
import duckdb

N = 10_000_000
MEMS = ["4GB", "2GB", "1GB", "512MB", "256MB", "128MB", "64MB"]
HEAVY = """SELECT host, usr, process, (ts//60) AS m, count(*) c
           FROM events GROUP BY host, usr, process, (ts//60) ORDER BY c DESC LIMIT 50"""


def make(path):
    con = duckdb.connect()
    con.execute(f"""COPY (SELECT (1781000000+(hash(i)%604800))::BIGINT ts, 'h'||((hash(i)%8000))::VARCHAR host,
        'u'||((hash(i+11)%20000))::VARCHAR usr, ('proc'||(hash(i+1)%200))::VARCHAR process
        FROM range({N}) t(i)) TO '{path}' (FORMAT parquet, COMPRESSION zstd)""")
    con.close()


def run(parquet, mem):
    tmp = tempfile.mkdtemp(prefix="cliff_"); con = duckdb.connect()
    con.execute(f"SET memory_limit='{mem}'"); con.execute("SET threads=1")
    con.execute(f"SET temp_directory='{tmp}'"); con.execute("SET preserve_insertion_order=false")
    con.execute(f"CREATE VIEW events AS SELECT * FROM read_parquet('{parquet}')")
    rec = {"mem": mem}
    try:
        t0 = time.perf_counter(); con.execute(HEAVY).fetchall()
        rec["latency_s"] = round(time.perf_counter()-t0, 2); rec["completed"] = True
        sp = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(tmp) for f in fs)
        rec["spilled_mb"] = round(sp/1e6, 1); rec["spilled"] = sp > 0
    except Exception as e:
        rec["completed"] = False; rec["error"] = f"{type(e).__name__}: {str(e)[:110]}"
    finally:
        con.close(); shutil.rmtree(tmp, ignore_errors=True)
    return rec


def main():
    work = tempfile.mkdtemp(prefix="cliff_corp_"); pq = os.path.join(work, "e.parquet")
    print(f"gen {N:,} rows...", flush=True); make(pq)
    res = {"bench": "duckdb-edge-floor / heavy cliff-finder", "tier": "B", "n_rows": N,
           "detection": "high-card group-by (host,user,process,minute) ~10M groups", "threads": 1, "runs": []}
    for mem in MEMS:
        r = run(pq, mem); res["runs"].append(r)
        print(f"  mem={mem:6} -> " + (f"OK {r['latency_s']}s spilled={r.get('spilled')} ({r.get('spilled_mb')}MB)"
              if r["completed"] else f"CLIFF {r.get('error')}"), flush=True)
    ok = [r for r in res["runs"] if r["completed"]]
    res["floor_mem"] = ok[-1]["mem"] if ok else "none"
    res["graceful_spill_seen"] = any(r.get("spilled") and r["completed"] for r in res["runs"])
    res["cliff_seen"] = any(not r["completed"] for r in res["runs"])
    res["cliff_at"] = next((r["mem"] for r in res["runs"] if not r["completed"]), None)
    json.dump(res, open(os.path.expanduser("~/sdw-lab-benchmarks/duckdb-edge-floor/results/heavy_cliff.json"), "w"), indent=2, default=str)
    shutil.rmtree(work, ignore_errors=True)
    print(f"\nheavy detection (threads=1): completes to {res['floor_mem']} | graceful-spill={res['graceful_spill_seen']} "
          f"| cliff={res['cliff_seen']}" + (f" at {res['cliff_at']}" if res['cliff_at'] else ""))


if __name__ == "__main__":
    main()

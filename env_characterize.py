"""Foundational: is this host a stable enough benchmark environment?

We cannot pin the CPU governor from inside WSL2 (the Windows host owns it), and DuckDB is an embedded
engine (in-process timing). Before trusting — or re-running — any latency comparison, measure the
environment's OWN noise rather than assume it. This runs a representative query many times back-to-back
and reports:
  - coefficient of variation (CV) — db-benchmarks' stability metric; a delta below the CV isn't real.
  - sustained drift — median of the last third vs the first third of the repeats, to catch thermal
    throttling (box heats up under load and downclocks) or a warm-up tail.
It runs two query classes:
  - in-memory table (pure CPU + memory scheduling): isolates governor/thermal/scheduler variance.
  - parquet-backed (adds I/O + decompression): the realistic bench path.
If both CVs are low and there's no upward drift, WSL2 + reporting CV is a defensible standard. If CV is
high or latency drifts up under sustained load, the environment must change (Windows High-Performance
power plan, native Linux boot, or a cloud fixed-frequency instance) before the numbers carry weight.

    python env_characterize.py --rows 50000000 --repeats 30
"""
import argparse
import os
import statistics
import sys
import tempfile
import time

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
from common import BASE_EPOCH, configure_duckdb  # noqa: E402

PORTS = "[80, 443, 22, 53, 3389, 445, 8080, 3306]"
HEAVY = ("SELECT split_part(src_ip,'.',2)::INT AS o2, dst_port, count(*) c, sum(bytes_out) b "
         "FROM {t} GROUP BY 1,2 ORDER BY c DESC, o2, dst_port LIMIT 50")
LIGHT = "SELECT count(*) FROM {t} WHERE dst_port = 443"


def gen_table(con, n):
    con.execute(f"""CREATE TABLE mem AS
        SELECT i AS id, {BASE_EPOCH*1000} + i AS time,
               '10.' || (hash(i::VARCHAR||'a')%256) || '.' || (hash(i::VARCHAR||'b')%256) || '.' || (hash(i::VARCHAR||'c')%256) AS src_ip,
               {PORTS}[(1 + hash(i::VARCHAR||'p')%8)::BIGINT]::INTEGER AS dst_port,
               (hash(i::VARCHAR||'bo')%5000000)::BIGINT AS bytes_out
        FROM range(0,{n}) t(i)""")


def stats(samples):
    mean = statistics.mean(samples)
    cv = statistics.pstdev(samples) / mean * 100 if mean > 0 and len(samples) > 1 else 0.0
    n = len(samples)
    third = max(1, n // 3)
    drift = (statistics.median(samples[-third:]) / statistics.median(samples[:third]) - 1) * 100
    return {"median_ms": round(statistics.median(samples), 1), "min_ms": round(min(samples), 1),
            "max_ms": round(max(samples), 1), "cv_pct": round(cv, 1),
            "drift_last_vs_first_pct": round(drift, 1), "n": n}


def hammer(con, sql, repeats, warmup):
    for _ in range(warmup):
        con.execute(sql).fetchall()
    out = []
    for _ in range(repeats):
        t0 = time.perf_counter(); con.execute(sql).fetchall(); out.append((time.perf_counter() - t0) * 1000)
    return out


def verdict(cv):
    return "GREEN (<5%)" if cv < 5 else "YELLOW (5-15%)" if cv < 15 else "RED (>15%)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=50_000_000)
    ap.add_argument("--repeats", type=int, default=30)
    ap.add_argument("--warmup", type=int, default=3)
    args = ap.parse_args()

    cpu_mhz = []
    try:
        for line in open("/proc/cpuinfo"):
            if line.lower().startswith("cpu mhz"):
                cpu_mhz.append(float(line.split(":")[1]))
    except Exception:
        pass

    work = tempfile.mkdtemp(prefix="envchar_")
    con = configure_duckdb(duckdb.connect())
    gen_table(con, args.rows)
    pqf = os.path.join(work, "data.parquet")
    con.execute(f"COPY mem TO '{pqf}' (FORMAT parquet, COMPRESSION zstd)")

    print(f"host: nproc={os.cpu_count()}  rows={args.rows:,}  repeats={args.repeats}  warmup={args.warmup}")
    if cpu_mhz:
        print(f"/proc/cpuinfo cpu MHz: min={min(cpu_mhz):.0f} max={max(cpu_mhz):.0f} "
              f"(WSL2 may report a static value)")
    print()
    runs = {
        "in-memory heavy": hammer(con, HEAVY.format(t="mem"), args.repeats, args.warmup),
        "in-memory light": hammer(con, LIGHT.format(t="mem"), args.repeats, args.warmup),
        "parquet heavy":   hammer(con, HEAVY.format(t=f"read_parquet('{pqf}')"), args.repeats, args.warmup),
        "parquet light":   hammer(con, LIGHT.format(t=f"read_parquet('{pqf}')"), args.repeats, args.warmup),
    }
    con.close()
    import shutil; shutil.rmtree(work, ignore_errors=True)

    print(f"{'query class':18} {'median':>9} {'min':>8} {'max':>8} {'CV%':>6} {'drift%':>7}  stability")
    for k, s in ((k, stats(v)) for k, v in runs.items()):
        print(f"{k:18} {s['median_ms']:>8.0f}m {s['min_ms']:>7.0f}m {s['max_ms']:>7.0f}m "
              f"{s['cv_pct']:>6.1f} {s['drift_last_vs_first_pct']:>7.1f}  {verdict(s['cv_pct'])}")
    print("\nReading: CV is run-to-run noise (db-benchmarks' stability metric); a measured speed delta "
          "below the CV is not a real difference. drift% > 0 under sustained load suggests thermal "
          "throttling; < 0 suggests a warm-up tail. Compare in-memory (pure CPU/scheduler) vs parquet "
          "(adds I/O+decompress) to localize the noise source.")


if __name__ == "__main__":
    main()

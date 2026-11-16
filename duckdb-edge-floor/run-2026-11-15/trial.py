#!/usr/bin/env python3
"""One trial of the 2026-11-15 enforced-cap run (duckdb-edge-floor). Runs INSIDE a fresh container whose
cgroup v2 memory.max is the cap; the driver (driver.py) launches it and reads the cgroup files afterwards.

Usage: trial.py SHAPE CORPUS MEMLIMIT_MB THREADS OUT_PREFIX
  SHAPE   one of null, S, H, J, probe (probe = mechanism check only, never a bench cell)
  CORPUS  path to the Parquet corpus (ignored for null/probe)
Writes OUT_PREFIX.samples.jsonl (one line per poll, flushed each line so the last sample survives a kill)
and OUT_PREFIX.json (final record) on completion or on a DuckDB exception.
"""
import hashlib, json, os, sys, threading, time

SHAPE, CORPUS, MEMLIMIT_MB, THREADS, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
TEMP = os.environ.get("EDGE_TEMP", "/spill/t")
POLL_S = 0.05

# The three detection shapes, frozen in PREREGISTRATION-2026-11-15.md.
QUERIES = {
    # S: streaming two-level UEBA volume z-score (June shape) with a deterministic tie-break added.
    "S": """
WITH hourly AS (
  SELECT host, (ts // 3600) AS hr, count(*) AS c FROM events GROUP BY host, (ts // 3600)
)
SELECT host, max(c) AS peak, round(avg(c), 6) AS mean_c, round(stddev_pop(c), 6) AS sd,
       round((max(c)-avg(c))/stddev_pop(c), 6) AS z
FROM hourly GROUP BY host
HAVING count(*) >= 5 AND stddev_pop(c) > 0 AND (max(c)-avg(c))/stddev_pop(c) > 3
ORDER BY z DESC, host LIMIT 50""",
    # H: high-cardinality group-by (June heavy shape) with a deterministic tie-break added.
    "H": """
SELECT host, usr, process, (ts // 60) AS m, count(*) AS c
FROM events GROUP BY host, usr, process, (ts // 60)
ORDER BY c DESC, host, usr, process, m LIMIT 50""",
    # J: self-join, process pairs co-occurring on one host in the same minute bucket, aggregated to
    # per-host pair counts; reports the rare pairs (seen in exactly one host-minute) as count + xor checksum.
    "J": """
WITH e AS (SELECT host, process, ts // 60 AS m FROM events),
pairs AS (
  SELECT a.host, a.process AS p1, b.process AS p2, count(*) AS c
  FROM e a JOIN e b ON a.host = b.host AND a.m = b.m AND a.process < b.process
  GROUP BY a.host, a.process, b.process
)
SELECT count(*) AS n_pairs, sum(c)::BIGINT AS n_cooccur,
       count(*) FILTER (WHERE c = 1) AS n_rare,
       bit_xor(hash(host, p1, p2)) FILTER (WHERE c = 1) AS rare_xor
FROM pairs""",
    "null": "SELECT 1",
    "probe": "SELECT count(*) FROM range(400000000) t(i) WHERE hash(i) % 7 = 0",
}


def read(path, default=None):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return default


def proc_status():
    out = {}
    for line in (read("/proc/self/status", "") or "").splitlines():
        k, _, v = line.partition(":")
        if k in ("VmRSS", "VmHWM", "RssAnon", "RssFile"):
            out[k] = int(v.split()[0]) * 1024
    return out


def cg_anon():
    for line in (read("/sys/fs/cgroup/memory.stat", "") or "").splitlines():
        if line.startswith("anon "):
            return int(line.split()[1])
    return None


def dir_bytes(p):
    tot = 0
    for dp, _, fs in os.walk(p):
        for f in fs:
            try:
                tot += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return tot


def main():
    rec = {"shape": SHAPE, "corpus": os.path.basename(CORPUS), "memory_limit_mb": MEMLIMIT_MB, "threads": THREADS}
    os.makedirs(TEMP, exist_ok=True)
    samples = open(OUT + ".samples.jsonl", "w", buffering=1)
    t_start = time.perf_counter()
    import duckdb  # import inside the measured process so the client baseline is part of the cell
    rec["duckdb"] = duckdb.__version__
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{MEMLIMIT_MB}MB'")
    con.execute(f"SET threads={THREADS}")
    con.execute(f"SET temp_directory='{TEMP}'")
    con.execute("SET preserve_insertion_order=false")
    if SHAPE not in ("null", "probe"):
        con.execute(f"CREATE VIEW events AS SELECT * FROM read_parquet('{CORPUS}')")
    peaks = {"tmpfiles_bytes": 0, "dir_bytes": 0, "bm_bytes": 0, "bm_temp_bytes": 0, "rss_anon": 0,
             "cg_anon": 0, "samples": 0, "poll_errors": 0}
    stop = threading.Event()
    poll_con = con.cursor()

    def poller():
        while not stop.is_set():
            s = {"t": round(time.perf_counter() - t_start, 3)}
            try:
                s["tmpfiles_bytes"] = poll_con.execute(
                    "SELECT coalesce(sum(size),0) FROM duckdb_temporary_files()").fetchone()[0]
                bm = poll_con.execute(
                    "SELECT coalesce(sum(memory_usage_bytes),0), coalesce(sum(temporary_storage_bytes),0) "
                    "FROM duckdb_memory()").fetchone()
                s["bm_bytes"], s["bm_temp_bytes"] = int(bm[0]), int(bm[1])
            except Exception as e:  # the poll itself may fail under pressure; count it, keep going
                peaks["poll_errors"] += 1
                s["poll_error"] = type(e).__name__
            s["dir_bytes"] = dir_bytes(TEMP)
            ps = proc_status()
            s["rss_anon"] = ps.get("RssAnon", 0)
            s["cg_anon"] = cg_anon() or 0
            for k in ("tmpfiles_bytes", "dir_bytes", "bm_bytes", "bm_temp_bytes", "rss_anon", "cg_anon"):
                if s.get(k) is not None and s.get(k, 0) > peaks[k]:
                    peaks[k] = int(s[k])
            peaks["samples"] += 1
            samples.write(json.dumps(s) + "\n")
            stop.wait(POLL_S)

    th = threading.Thread(target=poller, daemon=True)
    th.start()
    try:
        t0 = time.perf_counter()
        rows = con.execute(QUERIES[SHAPE]).fetchall()
        rec["latency_s"] = round(time.perf_counter() - t0, 4)
        rec["outcome"] = "completed"
        rec["n_rows"] = len(rows)
        rec["answer_sha256"] = hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest()
        if SHAPE == "J":
            rec["answer"] = [list(map(str, r)) for r in rows]
    except Exception as e:
        rec["latency_s"] = round(time.perf_counter() - t0, 4)
        name = type(e).__name__
        rec["outcome"] = "duckdb_oom_error" if "OutOfMemory" in name or "out of memory" in str(e).lower() else "error"
        rec["error"] = f"{name}: {str(e)[:300]}"
    stop.set()
    th.join(timeout=2)
    ps = proc_status()
    rec["vm_hwm_bytes"] = ps.get("VmHWM")
    rec["peaks"] = peaks
    rec["wall_in_process_s"] = round(time.perf_counter() - t_start, 4)
    with open(OUT + ".json", "w") as f:
        json.dump(rec, f, indent=1)


if __name__ == "__main__":
    main()

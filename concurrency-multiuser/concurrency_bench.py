#!/usr/bin/env python3
"""Multi-USER concurrency bench: closed-loop concurrency curve on the flagship
top-talkers scan-aggregation, one engine at a time, on soc.conn (10.3M rows).

Closes the single-USER -> multi-USER caveat the thesis names as "the honest open
extension." It does NOT test single-HOST -> distributed/cluster scaling (still one
host, one engine process). Each of N closed-loop clients models one interactive SOC
analyst: issue query, wait for the full result, immediately issue the next. We sweep
N and read p50/p95/p99 latency + aggregate QPS to find the saturation knee.

Structured-data only; aggregate output (top-10 source IPs by bytes). No raw event
rows enter the process [[feedback_security_telemetry_injection_surface]].

Invoke ONE engine per process (memory isolation; "one engine at a time"):
    python3 concurrency_bench.py <engine> <out.json>
  engine in {starrocks, clickhouse_iceberg, trino, dremio}  -> run inside ejs-lab
            opensearch (foil)                                -> run on host vs :9200

Env: LEVELS=1,2,4,8,16,32  WINDOW=20  MEM_FLOOR_KB=1200000
     OS_HOST=http://localhost:9200  OS_INDEX=zeek_conn  TABLE=soc.conn
"""
import os, sys, json, time, threading, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LEVELS = [int(x) for x in os.environ.get("LEVELS", "1,2,4,8,16,32").split(",")]
WINDOW = float(os.environ.get("WINDOW", "20"))
MEM_FLOOR_KB = int(os.environ.get("MEM_FLOOR_KB", "1200000"))   # abort a level below ~1.2 GB free
TABLE = os.environ.get("TABLE", "soc.conn")
OS_HOST = os.environ.get("OS_HOST", "http://localhost:9200")
OS_INDEX = os.environ.get("OS_INDEX", "zeek_conn")


def mem_available_kb():
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable"):
                return int(line.split()[1])
    return None


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    f = int(k); c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


# ---- per-engine client factory (each thread builds its OWN; pymysql/ch clients are not thread-safe) ----
def make_runner(engine):
    """Return (run_callable, label_of_first_result) — run_callable executes one query."""
    if engine == "opensearch":
        body = json.dumps({
            "size": 0, "track_total_hits": False,
            "aggs": {"by_src": {
                "terms": {"field": "orig_h", "size": 10, "order": {"tb": "desc"}},
                "aggs": {"tb": {"sum": {"script": {"source": "doc['orig_bytes'].value + doc['resp_bytes'].value"}}}}}}
        }).encode()
        # request_cache=false: force re-computation per query so the foil measures compute
        # under concurrency, not OpenSearch's shard request-cache memoizing the identical agg
        # (matches the SQL engines, which recompute each query; CH has use_query_cache=0).
        url = f"{OS_HOST}/{OS_INDEX}/_search?request_cache=false"

        def run():
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.load(r)
            if "error" in d:
                raise RuntimeError(str(d["error"])[:140])
            return d["aggregations"]["by_src"]["buckets"][0]["key"]
        return run

    from ejs_clients import StarRocks, ClickHouse, Trino, Dremio
    cls = {"starrocks": StarRocks, "clickhouse_iceberg": ClickHouse, "trino": Trino, "dremio": Dremio}[engine]
    c = cls()
    ref = c.ref(TABLE)
    sql = f"SELECT orig_h, SUM(orig_bytes + resp_bytes) AS b FROM {ref} GROUP BY orig_h ORDER BY b DESC LIMIT 10"

    def run():
        rows = c.run(sql)
        return rows[0][0] if rows else None
    return run


def run_level(engine, n):
    """N closed-loop clients hammer the query for WINDOW seconds. Returns metrics dict."""
    lat = [[] for _ in range(n)]
    err = [[] for _ in range(n)]
    ready = threading.Barrier(n + 1)
    stop = threading.Event()
    first_key = [None]

    def worker(i):
        try:
            run = make_runner(engine)
        except Exception as e:
            err[i].append(f"connect:{e}"[:160]); ready.wait(); return
        ready.wait()
        while not stop.is_set():
            t0 = time.perf_counter()
            try:
                k = run()
                lat[i].append(time.perf_counter() - t0)
                if first_key[0] is None:
                    first_key[0] = k
            except Exception as e:
                err[i].append(str(e)[:160])
                if stop.is_set():
                    break
                time.sleep(0.05)

    ths = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(n)]
    for t in ths:
        t.start()
    ready.wait()                 # all connected; start the clock together
    t_start = time.perf_counter()
    mem_min = mem_available_kb()
    aborted = None
    while time.perf_counter() - t_start < WINDOW:
        time.sleep(0.5)
        m = mem_available_kb()
        if m is not None:
            mem_min = min(mem_min, m)
            if m < MEM_FLOOR_KB:
                aborted = f"mem_floor:{m}"
                break
    elapsed = time.perf_counter() - t_start
    stop.set()
    for t in ths:
        t.join(timeout=130)

    all_lat = [x for sub in lat for x in sub]
    all_err = [x for sub in err for x in sub]
    return {
        "n_clients": n, "elapsed_s": round(elapsed, 3), "completed": len(all_lat),
        "qps": round(len(all_lat) / elapsed, 3) if elapsed else None,
        "p50_ms": round(pct(all_lat, 0.50) * 1000, 2) if all_lat else None,
        "p95_ms": round(pct(all_lat, 0.95) * 1000, 2) if all_lat else None,
        "p99_ms": round(pct(all_lat, 0.99) * 1000, 2) if all_lat else None,
        "mean_ms": round(sum(all_lat) / len(all_lat) * 1000, 2) if all_lat else None,
        "errors": len(all_err), "err_sample": all_err[:3],
        "mem_min_kb": mem_min, "aborted": aborted, "result_key": first_key[0],
    }


def main():
    engine, out = sys.argv[1], sys.argv[2]
    res = {"engine": engine, "table": TABLE, "window_s": WINDOW, "levels": []}
    # warmup once (page cache + planner); not timed
    try:
        make_runner(engine)() if engine == "opensearch" else None
        if engine != "opensearch":
            r = make_runner(engine); r()
        print(f"[{engine}] warmup ok", flush=True)
    except Exception as e:
        res["warmup_error"] = str(e)[:200]
        json.dump(res, open(out, "w"), indent=2)
        print(f"[{engine}] WARMUP FAILED: {e}", flush=True)
        return
    for n in LEVELS:
        avail = mem_available_kb()
        if avail is not None and avail < MEM_FLOOR_KB:
            res["levels"].append({"n_clients": n, "aborted": f"mem_floor_pre:{avail}"})
            print(f"[{engine}] N={n} skipped (mem {avail} < floor)", flush=True)
            break
        m = run_level(engine, n)
        res["levels"].append(m)
        print(f"[{engine}] N={n:>2} qps={m['qps']} p50={m['p50_ms']} p95={m['p95_ms']} "
              f"p99={m['p99_ms']} n={m['completed']} err={m['errors']} memMin={m['mem_min_kb']}"
              + (f" ABORT={m['aborted']}" if m["aborted"] else ""), flush=True)
        if m["aborted"]:
            break
    json.dump(res, open(out, "w"), indent=2)
    print(f"[{engine}] wrote {out}", flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""OpenSearch shard-count concurrency physics (backlog 1b) — is the foil's 6.73x
concurrency scaling (and the N=16 foil-ties-columnar convergence) a single-shard artifact?

The concurrency-multiuser foil used zeek_conn (1 shard). A single-shard index serves
concurrent queries via the search thread pool but cannot parallelize ONE query across
shards. This sweep reindexes the same 10M-doc corpus at S in {1,2,4,8} shards (force-merged
to 1 segment each, matching the single-segment foil discipline), then re-runs the SAME
closed-loop concurrency curve (concurrency_bench.py opensearch arm) against each, to measure
how shard count changes (a) the N=1 single-query latency and (b) the concurrency scaling.

Honest framing: more shards lowers N=1 latency (intra-query parallelism) but spends the
host's cores per query, so it should REDUCE concurrency headroom on a fixed-core single host
— the test quantifies that trade and tells us whether the published foil curve is shard-bound.

Structured/aggregate only; no raw rows enter the process. Tier B, single host.
Run (host, NOT in ejs-lab — the opensearch arm uses urllib vs :9200):
    python3 shard_sweep.py
Env: SHARDS=1,2,4,8  LEVELS=1,2,4,8,16  WINDOW=20  SRC=zeek_conn  OS_HOST=http://localhost:9200
"""
import json, os, subprocess, sys, time, urllib.request

OS_HOST = os.environ.get("OS_HOST", "http://localhost:9200")
SRC = os.environ.get("SRC", "zeek_conn")
SHARDS = [int(x) for x in os.environ.get("SHARDS", "1,2,4,8").split(",")]
LEVELS = os.environ.get("LEVELS", "1,2,4,8,16")
WINDOW = os.environ.get("WINDOW", "20")
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")


def req(method, path, body=None, timeout=600):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{OS_HOST}{path}", data=data, method=method,
                               headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.load(resp)


def ensure_index(shards):
    """Create zeek_conn_s{shards} from SRC's mapping (override shard count), reindex, force-merge to 1 seg."""
    idx = SRC if shards == 1 else f"{SRC}_s{shards}"
    if shards == 1:
        return idx  # use the existing single-shard index as-is
    # fresh build each run for determinism
    try:
        req("DELETE", f"/{idx}")
    except Exception:
        pass
    src_map = req("GET", f"/{SRC}/_mapping")[SRC]["mappings"]
    req("PUT", f"/{idx}", {"settings": {"index": {"number_of_shards": shards, "number_of_replicas": 0,
                                                  "refresh_interval": "-1"}},
                           "mappings": src_map})
    print(f"  [s{shards}] reindex {SRC} -> {idx} ...", flush=True)
    task = req("POST", "/_reindex?wait_for_completion=false&requests_per_second=-1",
               {"source": {"index": SRC, "size": 5000}, "dest": {"index": idx}})["task"]
    # poll the reindex task
    while True:
        time.sleep(5)
        st = req("GET", f"/_tasks/{task}")
        if st.get("completed"):
            d = st["response"]
            print(f"  [s{shards}] reindexed {d.get('total')} docs, failures={len(d.get('failures', []))}", flush=True)
            break
    req("POST", f"/{idx}/_refresh")
    print(f"  [s{shards}] force-merge -> 1 segment ...", flush=True)
    req("POST", f"/{idx}/_forcemerge?max_num_segments=1", timeout=1800)
    req("POST", f"/{idx}/_refresh")
    cnt = req("GET", f"/{idx}/_count")["count"]
    print(f"  [s{shards}] ready: {cnt} docs, {shards} shards, 1 segment/shard", flush=True)
    return idx


def run_curve(idx, shards):
    out = os.path.join(RESULTS, f"shardsweep_s{shards}.json")
    env = dict(os.environ, OS_INDEX=idx, LEVELS=LEVELS, WINDOW=WINDOW, OS_HOST=OS_HOST)
    print(f"  [s{shards}] concurrency curve on {idx} (LEVELS={LEVELS}) ...", flush=True)
    subprocess.run([sys.executable, os.path.join(HERE, "concurrency_bench.py"), "opensearch", out],
                   env=env, check=True)
    return json.load(open(out))


def main():
    os.makedirs(RESULTS, exist_ok=True)
    summary = {"benchmark": "opensearch shard-count concurrency (backlog 1b)",
               "evidence_tier": "B (single host, single node; synthetic 10M-doc Zeek conn; force-merged 1 seg)",
               "src_index": SRC, "shards_tested": SHARDS, "levels": LEVELS, "window_s": WINDOW,
               "host_cpus": os.cpu_count(), "by_shards": {}}
    for s in SHARDS:
        idx = ensure_index(s)
        res = run_curve(idx, s)
        lv = {x["n_clients"]: x for x in res["levels"] if "n_clients" in x and x.get("qps") is not None}
        n1 = lv.get(1, {})
        qmax = max((x["qps"] for x in lv.values()), default=None)
        summary["by_shards"][s] = {
            "n1_p50_ms": n1.get("p50_ms"), "n1_qps": n1.get("qps"),
            "qps_max": qmax, "scaling_x": round(qmax / n1["qps"], 2) if n1.get("qps") and qmax else None,
            "curve": {x["n_clients"]: {"qps": x["qps"], "p50_ms": x["p50_ms"], "p95_ms": x["p95_ms"]}
                      for x in lv.values()},
        }
        b = summary["by_shards"][s]
        print(f"== s{s}: N1 p50={b['n1_p50_ms']}ms qps={b['n1_qps']} | QPS_max={b['qps_max']} | scaling={b['scaling_x']}x\n", flush=True)
    json.dump(summary, open(os.path.join(RESULTS, "shard_sweep_summary.json"), "w"), indent=2, sort_keys=True)
    print("wrote results/shard_sweep_summary.json")


if __name__ == "__main__":
    main()

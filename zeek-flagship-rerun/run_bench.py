#!/usr/bin/env python3
"""Timed runs for one arm. Usage:
  run_bench.py --arm {opensearch|clickhouse_native|clickhouse_iceberg} [--trials 7] [--warmup 1] [--engine-cold]
  run_bench.py --compare        # answer-equality + CV-gated speedup report across all raw_*.json

Protocol (pre-registered in README.md): per query, --warmup discarded runs then
--trials timed runs; median + CV reported; a delta between arms is only claimable
when it exceeds the larger of the two CVs (methodology §4). All timing is
client-side wall time from THIS process over HTTP — the same client path for
every arm (the original timed ClickHouse via `docker exec` subprocess, which
inflates sub-second measurements; this is a declared improvement, not parity
with the original).

No OS-cold runs: the host has no passwordless sudo for drop_caches, so runs are
labelled hot/warm per methodology §3. --engine-cold restarts the engine
container and runs each query once (engine-cold / OS-warm), reported separately.
"""
import argparse
import json
import statistics
import subprocess
import time
from pathlib import Path

from queries import CH_NATIVE_TABLE, ICEBERG_TABLE_FN, OS_QUERIES, ch_queries, extract_ch, extract_os

WORK = Path(__file__).parent / "_work"
RESULTS = Path(__file__).parent / "results"

ARM_CONTAINER = {"opensearch": "zfr-opensearch", "clickhouse_native": "zfr-clickhouse",
                 "clickhouse_iceberg": "zfr-clickhouse"}


def os_runner():
    from opensearchpy import OpenSearch
    client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], http_compress=False,
                        use_ssl=False, verify_certs=False, timeout=600)

    def run(name):
        t0 = time.perf_counter()
        resp = client.search(index="zeek_conn", body=OS_QUERIES[name],
                             params={"request_cache": "false"})
        dt = time.perf_counter() - t0
        return dt, extract_os(name, resp)

    return list(OS_QUERIES.keys()), run


def ch_runner(table_expr):
    import clickhouse_connect
    client = clickhouse_connect.get_client(host="localhost", port=8123, password="zfrbench123",
                                           query_limit=0)
    qs = ch_queries(table_expr)

    def run(name):
        t0 = time.perf_counter()
        res = client.query(qs[name], settings={"use_query_cache": 0})
        dt = time.perf_counter() - t0
        return dt, extract_ch(name, res.result_rows)

    return list(qs.keys()), run


def get_runner(arm):
    if arm == "opensearch":
        return os_runner()
    if arm == "clickhouse_native":
        return ch_runner(CH_NATIVE_TABLE)
    if arm == "clickhouse_iceberg":
        return ch_runner(ICEBERG_TABLE_FN)
    raise SystemExit(f"unknown arm {arm}")


def wait_healthy(arm, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            # client creation itself fails while the engine is still booting,
            # so it must live inside the retry loop
            names, run = get_runner(arm)
            run("count_all")
            return
        except Exception:
            time.sleep(5)
    raise SystemExit(f"{arm} not healthy after {timeout}s")


def bench(arm, trials, warmup):
    names, run = get_runner(arm)
    out = {"arm": arm, "trials": trials, "warmup": warmup, "condition": "hot/warm",
           "started_unix": time.time(), "queries": {}}
    for name in names:
        for _ in range(warmup):
            run(name)
        durations, answer = [], None
        for _ in range(trials):
            dt, answer = run(name)
            durations.append(dt)
        med = statistics.median(durations)
        mean = statistics.fmean(durations)
        cv = (statistics.stdev(durations) / mean * 100) if len(durations) > 1 and mean > 0 else 0.0
        out["queries"][name] = {
            "durations_s": [round(d, 4) for d in durations],
            "median_s": round(med, 4), "mean_s": round(mean, 4), "cv_pct": round(cv, 1),
            "answer": answer,
        }
        print(f"  {arm} {name}: median {med:.3f}s  CV {cv:.1f}%", flush=True)
    return out


def engine_cold(arm):
    subprocess.run(["docker", "restart", ARM_CONTAINER[arm]], check=True, capture_output=True)
    wait_healthy(arm)
    names, run = get_runner(arm)
    cold = {}
    for name in names:
        dt, _ = run(name)
        cold[name] = round(dt, 4)
        print(f"  {arm} {name} [engine-cold]: {dt:.3f}s", flush=True)
    return cold


def compare():
    raws = {p.stem.replace("raw_", ""): json.loads(p.read_text()) for p in RESULTS.glob("raw_*.json")}
    report = {"answer_equality": {}, "speedups_cv_gated": {}}
    arms = sorted(raws)
    qnames = list(next(iter(raws.values()))["queries"].keys())
    for q in qnames:
        answers = {a: json.dumps(raws[a]["queries"][q]["answer"]) for a in arms}
        report["answer_equality"][q] = {
            "identical": len(set(answers.values())) == 1,
            "per_arm": {a: raws[a]["queries"][q]["answer"] for a in arms},
        }
    for q in qnames:
        for i, a in enumerate(arms):
            for b in arms[i + 1:]:
                ma, mb = raws[a]["queries"][q]["median_s"], raws[b]["queries"][q]["median_s"]
                cva, cvb = raws[a]["queries"][q]["cv_pct"], raws[b]["queries"][q]["cv_pct"]
                fast, slow = (a, b) if ma < mb else (b, a)
                ratio = max(ma, mb) / min(ma, mb)
                gap_pct = (ratio - 1) * 100
                gate = max(cva, cvb)
                report["speedups_cv_gated"][f"{q}: {fast} vs {slow}"] = {
                    "ratio": round(ratio, 2), "gap_pct": round(gap_pct, 1),
                    "gate_max_cv_pct": gate, "claimable": gap_pct > gate,
                }
    # arm-level summary: mean of per-query medians (the original's headline construction)
    report["avg_of_medians_s"] = {
        a: round(statistics.fmean(raws[a]["queries"][q]["median_s"] for q in qnames), 4) for a in arms
    }
    (RESULTS / "comparison.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("avg_of_medians_s",)}, indent=2))
    bad = [q for q, v in report["answer_equality"].items() if not v["identical"]]
    print(f"answer-equality: {'ALL IDENTICAL' if not bad else 'MISMATCH IN: ' + ', '.join(bad)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm")
    ap.add_argument("--trials", type=int, default=7)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--engine-cold", action="store_true")
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)

    if args.compare:
        compare()
        return
    if not args.arm:
        raise SystemExit("--arm required")
    out = bench(args.arm, args.trials, args.warmup)
    # persist the timed pass before the cold pass so a cold-pass failure can't lose it
    (RESULTS / f"raw_{args.arm}.json").write_text(json.dumps(out, indent=2))
    if args.engine_cold:
        out["engine_cold_s"] = engine_cold(args.arm)
        (RESULTS / f"raw_{args.arm}.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

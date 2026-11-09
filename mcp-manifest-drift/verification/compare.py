"""Compare the verifier's independent live re-run against the original live.json: H0 within the re-run,
cross-session manifest identity, and latency stats. Usage: python -I compare.py <orig live.json> <rerun live.json>"""
import json, statistics, sys, hashlib
orig, new = (json.load(open(p)) for p in sys.argv[1:3])
canon = lambda tools: hashlib.sha256(json.dumps(sorted(tools, key=lambda t: t["name"]), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
raw = lambda tools: hashlib.sha256(json.dumps(tools).encode()).hexdigest()
out = {}
for s in sorted({x["server"] for x in new}):
    o = [x for x in orig if x["server"] == s]; n = [x for x in new if x["server"] == s]
    xs = [x["list_ms"] for x in n]
    out[s] = {
        "n": len(n),
        "rerun_distinct_raw_manifests": len({raw(x["tools"]) for x in n}),
        "rerun_distinct_canon_manifests": len({canon(x["tools"]) for x in n}),
        "same_canon_as_original": {canon(x["tools"]) for x in n} == {canon(x["tools"]) for x in o},
        "same_raw_as_original": {raw(x["tools"]) for x in n} == {raw(x["tools"]) for x in o},
        "median_ms": round(statistics.median(xs), 3), "cv_pct": round(100 * statistics.stdev(xs) / statistics.mean(xs), 1),
        "min_ms": round(min(xs), 3), "max_ms": round(max(xs), 3),
        "per_run_median_ms": [round(statistics.median([x["list_ms"] for x in n if x["run"] == r]), 3) for r in (1, 2, 3)],
        "init_ms_per_run": [round(x["init_ms"], 1) for x in n if x["snapshot"] == 0],
        "serverInfo": n[0]["serverInfo"], "tools": len(n[0]["tools"]),
    }
print(json.dumps(out, indent=1))

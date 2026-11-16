#!/usr/bin/env python3
"""Pool the post-hoc example-2 timing passes (posthoc_ex2_timing.py) into medians, CVs, ratios and floors.
POST-HOC, NOT PRE-REGISTERED. Writes results/timing_ex2posthoc_summary.json and prints a markdown table."""
import glob, json, statistics
from pathlib import Path
HERE = Path(__file__).resolve().parent
files = sorted(glob.glob(str(HERE / "results" / "timing_ex2posthoc_n1000000_pass*.json")))
runs = [json.load(open(f)) for f in files]
lays = ["L1_typed", "L2_otel_map", "L3_aos_unmapped", "L3b_aos_ex2"]
out = {"passes": len(runs), "duckdb": sorted({r["duckdb"] for r in runs}), "pyarrow": sorted({r["pyarrow"] for r in runs}),
       "python": sorted({r["python"] for r in runs}), "loadavg": [[r["loadavg_start"][0], r["loadavg_end"][0]] for r in runs],
       "queries": {}}
print("| query | L1 ms (CV) | L2 ms | L3 ex1 ms | L3b ex2 ms | L3/L1 | L3b/L1 (floor) | L2/L1 | answer |")
print("|---|---|---|---|---|---|---|---|---|")
for q in runs[0]["queries"]:
    s = {l: [x for r in runs for x in r["queries"][q]["timings"][l]["samples_ms"]] for l in lays}
    med = {l: statistics.median(v) for l, v in s.items()}
    cv = {l: statistics.pstdev(v) / statistics.mean(v) for l, v in s.items()}
    eq = all(r["queries"][q]["answers_equal"] for r in runs)
    ans = runs[0]["queries"][q]["answer"]
    floor = min(s["L3b_aos_ex2"]) / max(s["L1_typed"])
    out["queries"][q] = {"n_samples": {l: len(v) for l, v in s.items()}, "median_ms": med, "cv": cv,
                         "L3_over_L1": med["L3_aos_unmapped"] / med["L1_typed"], "L3b_over_L1": med["L3b_aos_ex2"] / med["L1_typed"],
                         "L2_over_L1": med["L2_otel_map"] / med["L1_typed"], "L3b_floor": floor, "answers_equal": eq, "answer": ans}
    print(f"| {q} | {med['L1_typed']:.1f} ({cv['L1_typed']:.0%}) | {med['L2_otel_map']:.1f} | {med['L3_aos_unmapped']:.1f} | "
          f"{med['L3b_aos_ex2']:.1f} | {out['queries'][q]['L3_over_L1']:.1f}x | {out['queries'][q]['L3b_over_L1']:.2f}x ({floor:.2f}) | "
          f"{out['queries'][q]['L2_over_L1']:.1f}x | {str(ans)[:40]} {'equal' if eq else 'MISMATCH'} |")
(HERE / "results" / "timing_ex2posthoc_summary.json").write_text(json.dumps(out, indent=1))
print(out["loadavg"], out["duckdb"], out["pyarrow"], out["python"])

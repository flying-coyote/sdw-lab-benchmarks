#!/usr/bin/env python3
"""Pool the 3 passes x 7 trials per (scale, layout, query), compute median/CV/ratios, score H4/H4b/H5."""
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE / "results"
LAYOUTS = ["L1_typed", "L2_otel_map", "L3_aos_unmapped"]
out = {}
md = []
for n in (100000, 1000000):
    passes = [json.loads((R / f"timing_n{n}_pass{p}.json").read_text()) for p in range(3)]
    meta = json.loads((HERE / "data" / f"n{n}" / "corpus_meta.json").read_text())
    out[n] = {"sizes": {l: meta["layouts"][l]["bytes"] for l in LAYOUTS},
              "write_s": {l: meta["layouts"][l]["write_s"] for l in LAYOUTS}, "queries": {}}
    md.append(f"\n### {n:,} calls\n")
    md.append("| query | layout | pooled median ms | CV % | min–max ms | per-pass medians | ratio vs L1 | answers equal |")
    md.append("|---|---|---|---|---|---|---|---|")
    for q in passes[0]["queries"]:
        stats = {}
        for l in LAYOUTS:
            s = [x for p in passes for x in p["queries"][q]["timings"][l]["samples_ms"]]
            med = statistics.median(s)
            cv = statistics.pstdev(s) / statistics.mean(s) * 100
            stats[l] = {"median_ms": round(med, 2), "cv_pct": round(cv, 1), "min_ms": round(min(s), 2),
                        "max_ms": round(max(s), 2), "n": len(s),
                        "pass_medians": [p["queries"][q]["timings"][l]["median_ms"] for p in passes]}
        eq = all(p["queries"][q]["answers_equal"] for p in passes)
        base = stats["L1_typed"]
        for l in LAYOUTS:
            st = stats[l]
            st["ratio_vs_L1"] = round(st["median_ms"] / base["median_ms"], 1)
            # conservative bound: slowest-case L1 against fastest-case layout
            st["ratio_floor_vs_L1"] = round(st["min_ms"] / base["max_ms"], 2)
            md.append(f"| {q} | {l} | {st['median_ms']} | {st['cv_pct']} | {st['min_ms']}–{st['max_ms']} | "
                      f"{', '.join(str(x) for x in st['pass_medians'])} | {st['ratio_vs_L1']}x "
                      f"(floor {st['ratio_floor_vs_L1']}x) | {eq} |")
        out[n]["queries"][q] = {"answers_equal": eq, "answer": passes[0]["queries"][q]["answer"], "stats": stats}
    md.append(f"\nOn disk (ZSTD, row group 122880): " + ", ".join(
        f"{l} {out[n]['sizes'][l]/1e6:.1f} MB" for l in LAYOUTS) +
        f"; L3/L1 = {out[n]['sizes']['L3_aos_unmapped']/out[n]['sizes']['L1_typed']:.2f}x, "
        f"L2/L1 = {out[n]['sizes']['L2_otel_map']/out[n]['sizes']['L1_typed']:.2f}x. Write seconds: " +
        ", ".join(f"{l} {out[n]['write_s'][l]}" for l in LAYOUTS) + ".")

# Hypothesis scoring at the primary scale (1M)
P = out[1000000]["queries"]
h4 = {}
for q in ("Q1_tool_by_agent", "Q3_tool_breadth_errors", "Q4_failure_bursts", "Q5_off_allowlist"):
    st = P[q]["stats"]
    r = st["L3_aos_unmapped"]["ratio_vs_L1"]
    floor = st["L3_aos_unmapped"]["ratio_floor_vs_L1"]
    delta_pct = (st["L3_aos_unmapped"]["median_ms"] / st["L1_typed"]["median_ms"] - 1) * 100
    within_cv = delta_pct <= max(st["L1_typed"]["cv_pct"], st["L3_aos_unmapped"]["cv_pct"])
    h4[q] = {"ratio": r, "floor": floor, "meets_3x": r >= 3, "under_1_5x": r < 1.5, "within_cv": within_cv,
             "L2_between": st["L1_typed"]["median_ms"] < st["L2_otel_map"]["median_ms"] < st["L3_aos_unmapped"]["median_ms"]}
q2 = P["Q2_argument_hunt"]["stats"]
h4b = {l: q2[l]["ratio_vs_L1"] for l in LAYOUTS}
s = out[1000000]["sizes"]
verdicts = {
    "H4": "supported" if all(v["meets_3x"] and not v["within_cv"] for v in h4.values()) else
          ("refuted" if any(v["under_1_5x"] or v["within_cv"] for v in h4.values()) else "partial (1.5x-3x)"),
    "H4_L2_between": all(v["L2_between"] for v in h4.values()),
    "H4b": "supported" if max(h4b.values()) <= 1.5 else "refuted",
    "H5": "supported" if s["L3_aos_unmapped"] / s["L1_typed"] >= 1.3 else "refuted",
}
out["hypotheses"] = {"H4_detail": h4, "H4b_ratios": h4b, "H5_ratio": round(s["L3_aos_unmapped"] / s["L1_typed"], 3),
                     "verdicts": verdicts}
(R / "timing_summary.json").write_text(json.dumps(out, indent=1))
(R / "timing_summary.md").write_text("\n".join(md) + "\n")
print("\n".join(md))
print(json.dumps(out["hypotheses"], indent=1))

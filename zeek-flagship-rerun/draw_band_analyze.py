#!/usr/bin/env python3
"""Flagship triple-run band — fold the 3 independent draws into a per-arm latency band and a
per-ratio multiples band, so the 145×→two-regime headline is quoted as a 3-draw range, not a
single median. Draws:
  draw-1 = results/ (canonical published)
  draw-2 = results_revalidation_2026-06-14/
  draw-3 = results_revalidation3_2026-06-14/ (the corrected draw3_proper.sh run)
A multiple is "stable" if its 3-draw spread is modest and it is claimable in all 3.
Writes FLAGSHIP-TRIPLE-BAND-2026-06-14.{json,md}."""
import json
import statistics
from pathlib import Path

HERE = Path(__file__).parent
DRAWS = {
    "draw1_published": HERE / "results" / "comparison.json",
    "draw2_reval": HERE / "results_revalidation_2026-06-14" / "comparison.json",
    "draw3_reval": HERE / "results_revalidation3_2026-06-14" / "comparison.json",
}
HEADLINE = [
    "count_all: clickhouse_native vs dremio_iceberg",
    "count_all: clickhouse_iceberg vs dremio_iceberg",
    "count_all: opensearch vs clickhouse_iceberg",
    "count_all: clickhouse_native vs opensearch",
    "count_all: clickhouse_native vs clickhouse_iceberg",
]


def band(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    mean = sum(vals) / len(vals)
    cv = (statistics.pstdev(vals) / mean * 100) if len(vals) > 1 and mean else 0.0
    return {"min": round(min(vals), 4), "median": round(statistics.median(vals), 4),
            "max": round(max(vals), 4), "n": len(vals), "cv_pct": round(cv, 1)}


def main():
    loaded = {n: json.loads(p.read_text()) for n, p in DRAWS.items() if p.exists()}
    arms = ["clickhouse_native", "clickhouse_iceberg", "dremio_iceberg", "opensearch"]
    arm_band = {a: band([loaded[d].get("avg_of_medians_s", {}).get(a) for d in loaded]) for a in arms}
    ratio_band = {}
    for key in HEADLINE:
        per_draw, claim_all = [], True
        for d in loaded:
            e = loaded[d].get("speedups_cv_gated", {}).get(key)
            if e:
                per_draw.append(e.get("ratio")); claim_all = claim_all and bool(e.get("claimable"))
            else:
                claim_all = False
        ratio_band[key] = {"band": band(per_draw), "per_draw": per_draw, "claimable_all_draws": claim_all}

    out = {"bench": "zeek-flagship-rerun", "draws": list(loaded.keys()),
           "avg_of_medians_band_s": arm_band, "headline_ratio_band": ratio_band}
    (HERE / "FLAGSHIP-TRIPLE-BAND-2026-06-14.json").write_text(json.dumps(out, indent=2))
    md = ["# Flagship triple-run band (2026-06-14)", "",
          f"Three independent draws ({', '.join(loaded.keys())}). Tier B, single host. Headline "
          "quoted as a 3-draw range; low across-draw CV = the multiple is stable (ratios travel even "
          "when absolute ms drift with page-cache).", "",
          "## Per-arm avg-of-medians latency (s) — band across draws", "",
          "| arm | min | median | max | across-draw CV |", "|---|--:|--:|--:|--:|"]
    for a in arms:
        b = arm_band[a]
        if b: md.append(f"| {a} | {b['min']} | {b['median']} | {b['max']} | {b['cv_pct']}% |")
    md += ["", "## Headline multiples — band across draws", "",
           "| comparison | min× | median× | max× | across-draw CV | claimable all |",
           "|---|--:|--:|--:|--:|:--:|"]
    for key in HEADLINE:
        rb = ratio_band[key]; b = rb["band"]
        if b:
            md.append(f"| {key.replace('count_all: ','')} | {b['min']}× | {b['median']}× | {b['max']}× "
                      f"| {b['cv_pct']}% | {'yes' if rb['claimable_all_draws'] else 'NO'} |")
    md.append("")
    (HERE / "FLAGSHIP-TRIPLE-BAND-2026-06-14.md").write_text("\n".join(md))
    print(json.dumps(out, indent=2)); print("\nwrote FLAGSHIP-TRIPLE-BAND-2026-06-14.{json,md}")


if __name__ == "__main__":
    main()

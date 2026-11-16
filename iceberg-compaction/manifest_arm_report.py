#!/usr/bin/env python3
"""Print the markdown tables for RESULTS-MANIFEST-ARM-2026-11-16.md from the arm's raw JSON."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results", "manifest_arm_2026-11-16.json")
d = json.load(open(p))
C = ("default", "merge_on", "rewrite_manifests", "compacted")

print("### Shape A: planning sweep (700,000 rows, separate table per N)\n")
print("| N | condition | data files | manifests | plan median ms (CV%) | scan median ms (CV%) | answer = default |")
print("|---:|---|---:|---:|---:|---:|---|")
for r in d["shape_a_planning_sweep"]:
    for c in C:
        x = r[c]
        print(f"| {r['N_appends']:,} | {c} | {x['data_files']:,} | {x['manifests']:,} | "
              f"{x['plan']['median_ms']:.1f} ({x['plan']['cv_pct']}) | {x['scan']['median_ms']:.1f} ({x['scan']['cv_pct']}) | "
              f"{x['answer_matches_default']} |")
print("\nRatios against default (plan / scan):\n")
print("| N | merge_on | rewrite_manifests | compacted |")
print("|---:|---:|---:|---:|")
for r in d["shape_a_planning_sweep"]:
    a = r["default"]
    cells = []
    for c in C[1:]:
        x = r[c]
        cells.append(f"{a['plan']['median_ms'] / x['plan']['median_ms']:.1f}x / {a['scan']['median_ms'] / x['scan']['median_ms']:.1f}x")
    print(f"| {r['N_appends']:,} | " + " | ".join(cells) + " |")

b = d["shape_b_zeek_500"]
qs = list(b["default"]["battery"])
print(f"\n### Shape B: Zeek conn, {b['rows']:,} rows as {b['n_appends']} appends\n")
print("| condition | data files | manifests | plan ms | " + " | ".join(qs) + " |")
print("|---|---:|---:|---:|" + "---:|" * len(qs))
for c in C:
    x = b[c]
    print(f"| {c} | {x['data_files']} | {x['manifests']} | {x['plan']['median_ms']:.1f} | "
          + " | ".join(f"{x['battery'][q]['median_ms']:.1f} ({x['battery'][q]['cv_pct']})" for q in qs) + " |")
print("\nRecovery against default (default median / condition median):\n")
print("| condition | plan | " + " | ".join(qs) + " |")
print("|---|---:|" + "---:|" * len(qs))
for c in C[1:]:
    x = b[c]
    print(f"| {c} | {b['default']['plan']['median_ms'] / x['plan']['median_ms']:.1f}x | "
          + " | ".join(f"{b['default']['battery'][q]['median_ms'] / x['battery'][q]['median_ms']:.2f}x" for q in qs) + " |")
print("\nAnswer equality vs default:", {c: all(b[c]["battery"][q].get("answer_matches_default") for q in qs) for c in C[1:]})

import chartstyle as cs
import matplotlib.pyplot as plt

# Source: ocsf-format-planning/results/RESULTS.md
# 5M rows, commit ladder 10/50/200 (each commit = one data file), same engine (DuckDB).
# Native planning proxy (each format's own mechanism):
#   pyiceberg plan_files():  13.0 -> 59.0 -> 228.4 ms   (17.6x across the ladder)
#   DuckLake catalog query:  2.94 -> 3.57 -> 3.56 ms    (1.21x — flat)
commits = [10, 50, 200]
ice_plan = [13.0, 59.0, 228.4]
dl_plan  = [2.94, 3.57, 3.56]

fig, ax = cs.canvas(
    "Iceberg's planning cost climbs with file count; DuckLake's stays flat.",
    "Median time to resolve 'which files do I scan' as 5M rows fragment across more commits — the small-files tax Iceberg V4 targets.",
    source="sdw-lab-benchmarks/ocsf-format-planning",
    tier="Tier B · single-host · the SHAPE is the claim (each format's native planner; absolute ms not head-to-head)",
    figsize=(8.8, 4.6), bottom=0.17, top=0.80)

ax.plot(commits, ice_plan, "-o", color=cs.ACCENT, lw=2.4, markersize=7, zorder=3)
ax.plot(commits, dl_plan, "-o", color=cs.CONTEXT, lw=2.4, markersize=7, zorder=3)

# direct labels placed off the lines, in clear space
ax.text(95, 165, "Iceberg manifests  —  pyiceberg plan_files()\n17.6× across the ladder",
        ha="left", va="center", fontsize=11, color=cs.ACCENT, fontweight="bold")
ax.text(108, 22, "DuckLake SQL catalog  —  1.21× (stays flat)",
        ha="left", va="center", fontsize=11, color=cs.MUTED, fontweight="bold")

# per-point value labels for Iceberg (above the line)
for x, y in zip(commits, ice_plan):
    ax.text(x, y + 7, f"{y:.0f}", ha="center", va="bottom", fontsize=9.5, color=cs.ACCENT)
# DuckLake values (just above its low flat line)
for x, y in zip(commits, dl_plan):
    ax.text(x, y + 5, f"{y:.1f}", ha="center", va="bottom", fontsize=9, color=cs.MUTED)

ax.set_xlim(0, 215)
ax.set_ylim(0, 255)
ax.set_xticks(commits)
ax.set_xticklabels(["10 files", "50 files", "200 files"])
ax.set_ylabel("planning latency (ms)")
ax.grid(axis="y", color=cs.GRID)
ax.grid(axis="x", visible=False)
ax.set_axisbelow(True)
ax.tick_params(length=0)

ax.text(0, 1.02, "identical answers throughout — the difference is where the metadata lives (files vs a database)",
        transform=ax.transAxes, ha="left", va="bottom", fontsize=8.5, color=cs.MUTED, family=cs.MONO)

cs.direction_note(fig, "latency: lower is better")
cs.save(fig, "out/iceberg-manifests-vs-ducklake-sql-catalo.png")
print("rendered r07")

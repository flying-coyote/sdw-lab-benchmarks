import chartstyle as cs
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Source: bench-a-context-collapse/results/RESULTS.md  — SYNTHETIC testbed, one planted chain.
# Per-query Delta(N-F) for adversary-tail A1..A10, tagged by mechanism.
# A1 +1.000 grain | A2 +1.000 grain | A8 +1.000 grain | A10 +1.000 time | A4 +1.000 time
# A6 +0.993 structural | A5 +0.600 bounded | A9 +0.500 bounded | A3 +0.095 time | A7 +0.003 time
# Per-mechanism means: grain +1.000, structural +0.993, bounded-context +0.550, time +0.524
# Storage: Store F is 1.93x Store N (SYNTHETIC corpus — never cross with APT29 1.799x).
queries = [
    ("A1", 1.000, "grain"), ("A2", 1.000, "grain"), ("A8", 1.000, "grain"),
    ("A4", 1.000, "time"), ("A10", 1.000, "time"),
    ("A6", 0.993, "structural"),
    ("A5", 0.600, "bounded-context"), ("A9", 0.500, "bounded-context"),
    ("A3", 0.095, "time"), ("A7", 0.003, "time"),
]
MCOL = {"grain": cs.ACCENT, "structural": cs.BAD,
        "bounded-context": cs.ACCENT2, "time": cs.WARN}

# sort high->low so the survivors sit at the bottom
queries_sorted = sorted(queries, key=lambda t: t[1], reverse=True)
labels = [f"{q}" for q, _, _ in queries_sorted]
vals   = [v for _, v, _ in queries_sorted]
cols   = [MCOL[m] for _, _, m in queries_sorted]
y = list(range(len(queries_sorted)))[::-1]

fig, ax = cs.canvas(
    "Coarse normalization blinds the adversary tail — but not every query.",
    "Recall lost per adversary-tail query when the fidelity store is coarsened (Store N vs Store F). Five go fully blind; ordering (A3) and dwell (A7) survive.",
    source="sdw-lab-benchmarks/bench-a-context-collapse",
    tier="Tier B · single-host · SYNTHETIC one-chain testbed · mechanism-only (use de-gamed APT29 for public recall headlines)",
    figsize=(9.4, 5.4), bottom=0.15, top=0.76)

ax.barh(y, vals, color=cols, height=0.62, zorder=3)
for yi, v in zip(y, vals):
    if v >= 0.2:
        ax.text(v - 0.02, yi, f"+{v:.3f}", ha="right", va="center", color="white", fontweight="bold", fontsize=10)
    else:
        ax.text(v + 0.015, yi, f"+{v:.3f}", ha="left", va="center", color=cs.BODY, fontsize=10)

ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=11.5)
ax.set_xlim(0, 1.12)
ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
ax.set_xlabel("recall lost to coarsening  (delta = fidelity − coarse)")
cs.bare(ax)
ax.grid(axis="x", color=cs.GRID); ax.grid(axis="y", visible=False)
ax.set_axisbelow(True); ax.tick_params(length=0)

# mechanism legend with per-mechanism mean delta
order = ["grain", "structural", "bounded-context", "time"]
means = {"grain": 1.000, "structural": 0.993, "bounded-context": 0.550, "time": 0.524}
handles = [Patch(facecolor=MCOL[m], label=f"{m}  (mean delta +{means[m]:.3f})") for m in order]
ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=9.5,
          title="mechanism", title_fontsize=9.5, handlelength=1.2, labelspacing=0.5)

ax.text(0.0, 1.025,
        "headline delta(adversary − routine) = +0.719   ·   Store F = 1.93× Store N (synthetic corpus)",
        transform=ax.transAxes, ha="left", va="bottom", fontsize=8.8, color=cs.MUTED, family=cs.MONO)

cs.direction_note(fig, "recall lost: lower is better")
cs.save(fig, "out/per-mechanism-context-collapse-decomposi.png")
print("rendered r09")

import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: ocsf-zorder-pruning/results/RESULTS.md (FULL re-derivation incl. read-side pruning table)
# 2,000,000-row OCSF Network Activity, 50,000-row row groups (~40 rgs/file), DuckDB, zstd-3.
# Pruning (% row groups excluded by min/max footer stats):
#   query                        unordered  single_sort  zorder
#   Q1 src_ip AND time             0.0%       95.0%       72.5%
#   Q2 dst_port AND src_ip         0.0%       97.5%       65.0%
#   Q3 dst_endpoint AND port       0.0%        0.0%       15.0%
#   Q4 time-window only            0.0%        0.0%       65.0%
# Write cost ms: unordered 2656.6 · single_sort 2058.7 · zorder 11564.2  (zorder 5.62x single_sort)
# Answers identical across all three layouts.
queries = ["Q1\nsrc_ip AND time", "Q2\ndst_port AND src_ip",
           "Q3\ndst_endpoint AND port", "Q4\ntime-window only"]
unordered   = [0.0, 0.0, 0.0, 0.0]
single_sort = [95.0, 97.5, 0.0, 0.0]
zorder      = [72.5, 65.0, 15.0, 65.0]

fig, (axL, axR) = cs.canvas(
    "Z-order prunes the multi-dimension queries a single sort can't — at a write-time price.",
    "Share of Parquet row groups skipped by min/max footer stats, per query. Z-order is the only layout that prunes Q3 and Q4.",
    source="sdw-lab-benchmarks/ocsf-zorder-pruning · RESULTS.md · 2M rows, 50,000-row groups",
    tier="Tier B · single-host · DuckDB · answers identical across layouts · pruning = conservative footer lower bound",
    figsize=(10.4, 4.9), bottom=0.20, top=0.80, ncols=2,
    gridspec_kw={"width_ratios": [3.1, 1]})

x = np.arange(len(queries))
w = 0.26
bars = [
    (unordered,   -w, cs.CONTEXT, "unordered"),
    (single_sort,  0, cs.ACCENT2, "single sort"),
    (zorder,       w, cs.ACCENT,  "z-order"),
]
for vals, off, color, lab in bars:
    rects = axL.bar(x + off, vals, width=w, color=color, label=lab, zorder=3)
    for xi, v in zip(x + off, vals):
        if v > 0:
            axL.text(xi, v + 2, f"{v:.0f}", ha="center", va="bottom",
                     fontsize=9.5, color=cs.BODY,
                     fontweight="bold" if color == cs.ACCENT else "normal")
        else:
            axL.text(xi, 2, "0", ha="center", va="bottom", fontsize=8.5, color=cs.MUTED)

axL.set_ylim(0, 108)
axL.set_xticks(x)
axL.set_xticklabels(queries, fontsize=9.5)
axL.set_ylabel("Row groups pruned (%)")
axL.set_yticks([0, 25, 50, 75, 100])
axL.grid(axis="y", color=cs.GRID); axL.grid(axis="x", visible=False)
for s in ("top", "right"):
    axL.spines[s].set_visible(False)
# direct-labeled legend at top of left panel
axL.legend(loc="upper center", bbox_to_anchor=(0.5, 1.06), ncol=3, frameon=False,
           fontsize=10, handlelength=1.1, columnspacing=1.6, handletextpad=0.5)
# call out the Q3/Q4 single-sort blind spot
axL.annotate("single sort prunes\nnothing here",
             (2.0, 6), textcoords="offset points", xytext=(0, 40),
             ha="center", va="bottom", fontsize=8.5, color=cs.MUTED, family=cs.MONO,
             arrowprops=dict(arrowstyle="->", color=cs.MUTED, lw=1.0))

# --- right panel: write cost ---
wlabels = ["single\nsort", "unordered", "z-order"]
wvals   = [2058.7, 2656.6, 11564.2]
wcolors = [cs.ACCENT2, cs.CONTEXT, cs.ACCENT]
yb = np.arange(len(wlabels))
axR.barh(yb, wvals, color=wcolors, height=0.6, zorder=3)
for yi, v in zip(yb, wvals):
    axR.text(v + 250, yi, f"{v/1000:.1f}s", ha="left", va="center",
             fontsize=9.5, color=cs.BODY,
             fontweight="bold" if v > 10000 else "normal")
axR.set_yticks(yb); axR.set_yticklabels(wlabels, fontsize=9.5)
axR.invert_yaxis()
axR.set_xlim(0, 14500)
axR.set_xlabel("Write cost (s)")
axR.set_xticks([0, 5000, 10000]); axR.set_xticklabels(["0", "5", "10"])
axR.set_title("the price", fontsize=10.5, color=cs.MUTED, loc="left", pad=6)
axR.grid(axis="x", color=cs.GRID); axR.grid(axis="y", visible=False)
for s in ("top", "right", "left"):
    axR.spines[s].set_visible(False)
axR.tick_params(axis="y", length=0)
axR.annotate("5.6x the\nsingle sort", (11564, 2), textcoords="offset points",
             xytext=(-6, -26), ha="right", va="top", fontsize=8.5,
             color=cs.ACCENT, family=cs.MONO)

cs.direction_note(fig, "pruned %: higher is better", x=0.66, y=0.74)
cs.direction_note(fig, "write cost: lower is better", x=0.955, y=0.775)
cs.save(fig, "out/z-order-vs-single-sort-vs-unordered.png")
print("rendered r18")

import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: ocsf-zstd-dictionary/results/RESULTS.md
# 100,000 OCSF events (~221 bytes JSON each). Dictionary trained on disjoint held-out 50k.
# Compression ratio vs raw JSON, by events-per-block (zstd-3):
#   block:        1       10      100     1000
#   zstd-3 plain  1.33x   4.24x   6.3x    5.88x
#   zstd-3 +dict  3.57x   5.26x   5.89x   6.11x
# Columnar reference (large Parquet row group), zstd-3 no-dict: 9.45x  (block-independent)
blocks   = [1, 10, 100, 1000]
plain    = [1.33, 4.24, 6.30, 5.88]
dict_    = [3.57, 5.26, 5.89, 6.11]
columnar = 9.45
xpos = np.arange(len(blocks))   # even spacing for the categorical block sizes

fig, ax = cs.canvas(
    "A schema-trained ZSTD dictionary wins per-event, then fades as you batch.",
    "Compression ratio vs raw JSON for 100k OCSF events. The trained dictionary's edge is the gap between the two lines — widest at 1 event/block, gone by 100.",
    source="sdw-lab-benchmarks/ocsf-zstd-dictionary · RESULTS.md · dict trained on disjoint held-out 50k",
    tier="Tier B · single-host · ~221-byte JSON events · per-event ingest regime, NOT the lakehouse 8.2x Zeek number",
    figsize=(9.0, 4.9), bottom=0.16, top=0.80)

# columnar reference line (the ceiling the per-record codecs can't reach)
ax.axhline(columnar, color=cs.CONTEXT, linewidth=1.4, linestyle=(0, (5, 3)), zorder=2)
ax.text(xpos[-1], columnar + 0.18, f"columnar Parquet zstd-3 (no dict)  {columnar:.2f}x",
        ha="right", va="bottom", fontsize=9.5, color=cs.MUTED, family=cs.MONO)

ax.plot(xpos, dict_, "-o", color=cs.ACCENT, linewidth=2.4, markersize=8,
        zorder=5, markeredgecolor="white", markeredgewidth=1.3)
ax.plot(xpos, plain, "-o", color=cs.CONTEXT, linewidth=2.2, markersize=8,
        zorder=4, markeredgecolor="white", markeredgewidth=1.3)

# direct labels at line ends + the headline crossover point
ax.text(xpos[0] - 0.08, dict_[0], f"+dict {dict_[0]:.2f}x", ha="right", va="center",
        fontsize=10, color=cs.ACCENT, fontweight="bold")
ax.text(xpos[0] - 0.08, plain[0] - 0.15, f"plain zstd-3 {plain[0]:.2f}x", ha="right", va="top",
        fontsize=10, color=cs.MUTED)
ax.text(xpos[-1] + 0.06, dict_[-1] - 0.05, "+dict", ha="left", va="center",
        fontsize=9.5, color=cs.ACCENT, fontweight="bold")
ax.text(xpos[-1] + 0.06, plain[-1] + 0.05, "plain", ha="left", va="center",
        fontsize=9.5, color=cs.MUTED)

# mark where the dict edge is gone (block=100, plain 6.30 > dict 5.89)
ax.annotate("dict edge gone\nby 100 events/block",
            (xpos[2], (plain[2] + dict_[2]) / 2), textcoords="offset points",
            xytext=(0, -52), ha="center", va="top", fontsize=9, color=cs.BODY,
            family=cs.MONO, arrowprops=dict(arrowstyle="->", color=cs.BODY, lw=1.0))
# shade the per-event win
ax.annotate("the per-event hot path\nsecurity ingestion runs on",
            (xpos[0], dict_[0]), textcoords="offset points", xytext=(34, -6),
            ha="left", va="center", fontsize=9, color=cs.ACCENT, family=cs.MONO)

ax.set_xticks(xpos)
ax.set_xticklabels([f"{b}" for b in blocks])
ax.set_xlabel("Events per block  (per-record  to  batched)")
ax.set_ylabel("Compression ratio vs raw JSON")
ax.set_xlim(-0.65, len(blocks) - 0.35)
ax.set_ylim(0, 10.4)
ax.set_yticks([0, 2, 4, 6, 8, 10])
ax.grid(axis="y", color=cs.GRID); ax.grid(axis="x", visible=False)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)

cs.save(fig, "out/schema-trained-zstd-dictionary-compression.png")
print("rendered r20")

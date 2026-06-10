import chartstyle as cs
import matplotlib.pyplot as plt

# Source: ocsf-read-scan/results/WRITER-READ-LEVER.md
# 20M-row OCSF table, MATCHED codec (zstd-3) + row-group (122,880), SAME reader (DuckDB).
# Only variable = the writer's encoding strategy.
# size (MB):      duckdb 228.3 · pyarrow_default 365.1 · pyarrow_dict 365.1 · pyiceberg 212.4
# topn_src (ms):  duckdb 629   · pyarrow_default 708   · pyarrow_dict 669   · pyiceberg 381
# scan_sum (ms):  duckdb 37    · pyarrow_default 53    · pyarrow_dict 55    · pyiceberg 31
writers = [
    # label, size_MB, topn_ms, color, dx, dy, ha, va
    ("pyiceberg",        212.4, 381, cs.ACCENT,  6,  4, "left",  "bottom"),
    ("duckdb",           228.3, 629, cs.ACCENT2, 6, -2, "left",  "center"),
    ("pyarrow (dict)",   365.1, 669, cs.CONTEXT, 0, -14, "center", "top"),
    ("pyarrow (default)",365.1, 708, cs.CONTEXT, 0,  10, "center", "bottom"),
]

fig, ax = cs.canvas(
    "Pick the writer, not just the codec — it moves both size and read latency.",
    "20M OCSF rows, same zstd-3 codec and row-group, same DuckDB reader. Only the writer's encoding differs.",
    source="sdw-lab-benchmarks/ocsf-read-scan · WRITER-READ-LEVER.md",
    tier="Tier B · single-host · matched-codec control · topn_src query · ms are this host's",
    figsize=(8.8, 4.8), bottom=0.16, top=0.80)

for label, size, topn, color, dx, dy, ha, va in writers:
    ax.scatter(size, topn, s=240, color=color, zorder=5, edgecolor="white", linewidth=1.5)
    ax.annotate(f"{label}\n{size:.1f} MB · {topn} ms",
                (size, topn), textcoords="offset points", xytext=(dx, dy),
                ha=ha, va=va, fontsize=10, color=cs.BODY,
                fontweight="bold" if label == "pyiceberg" else "normal")

# guide: pyiceberg is both smallest AND fastest (lower-left = best)
ax.annotate("smallest file\nand fastest read",
            (212.4, 381), textcoords="offset points", xytext=(40, 34),
            ha="left", va="bottom", fontsize=9, color=cs.ACCENT, family=cs.MONO,
            arrowprops=dict(arrowstyle="->", color=cs.ACCENT, lw=1.2))
# the two pyarrow points: same bytes, different read -> size and read can diverge
ax.annotate("same bytes (365.1 MB),\ndifferent read latency",
            (365.1, 688), textcoords="offset points", xytext=(-12, 0),
            ha="right", va="center", fontsize=9, color=cs.MUTED, family=cs.MONO)

ax.set_xlim(195, 400)
ax.set_ylim(330, 760)
ax.set_xlabel("File size (MB) — smaller is better, left", color=cs.MUTED)
ax.set_ylabel("topn_src read (ms) — faster is lower")
ax.grid(True, color=cs.GRID)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
cs.save(fig, "out/parquet-writer-as-a-read-lever.png")
print("rendered r17")

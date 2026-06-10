import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: ocsf-read-scan/results/COLD-CACHE.md  (cold/warm ratio per query per format)
# 20M byte-identical rows; posix_fadvise(DONTNEED) cold reads, ext4.
#            full_count  filtered  topn_src  byte_rollup  subnet_rollup
# iceberg      1.09        1.55      1.23       1.43          1.01
# ducklake     0.99        1.32      0.97       1.46          1.21
queries = ["full_count", "filtered", "topn_src", "byte_rollup", "subnet_rollup"]
iceberg  = [1.09, 1.55, 1.23, 1.43, 1.01]
ducklake = [0.99, 1.32, 0.97, 1.46, 1.21]

fig, ax = cs.canvas(
    "Forensic reads run cold — the first scan pays a 1.0–1.55× page-cache penalty",
    "Cold / warm latency ratio per query (20M byte-identical rows). 1.0× = cache-insensitive; higher = depends on the OS page cache an IR query won't have.",
    source="sdw-lab-benchmarks/ocsf-read-scan",
    tier="Tier B · single-host · ext4 · byte-identical files in both catalogs · ratios transferable, ms this host's",
    figsize=(8.8, 5.0), bottom=0.18, top=0.78)

y = np.arange(len(queries))[::-1]
h = 0.36

# reference line at 1.0 (cache-insensitive)
ax.axvline(1.0, color=cs.MUTED, lw=1.0, ls=(0, (4, 3)), zorder=1)

b1 = ax.barh(y + h / 2, iceberg, height=h, color=cs.ACCENT, zorder=3,
             edgecolor="white", linewidth=0.8)
b2 = ax.barh(y - h / 2, ducklake, height=h, color=cs.CONTEXT, zorder=3,
             edgecolor="white", linewidth=0.8)

for yi, v in zip(y + h / 2, iceberg):
    ax.text(v + 0.015, yi, f"{v:.2f}×", ha="left", va="center",
            fontsize=10, color=cs.ACCENT, fontweight="bold")
for yi, v in zip(y - h / 2, ducklake):
    ax.text(v + 0.015, yi, f"{v:.2f}×", ha="left", va="center",
            fontsize=10, color=cs.MUTED)

ax.set_yticks(y)
ax.set_yticklabels(queries, fontsize=11)
ax.set_xlim(0, 1.78)
ax.set_ylim(y[-1] - 1.15, y[0] + 0.6)
ax.set_xlabel("cold / warm latency ratio")
cs.bare(ax)
ax.set_yticks(y)
ax.set_yticklabels(queries, fontsize=11)
ax.tick_params(axis="y", length=0)
ax.tick_params(axis="x", length=0)
ax.set_xticks([0, 0.5, 1.0, 1.5])
ax.set_xticklabels(["0", "0.5×", "1.0×", "1.5×"])
ax.grid(axis="x", color=cs.GRID)
ax.grid(axis="y", visible=False)
ax.set_axisbelow(True)

# compact legend in clear space (lower-right interior)
legx = 1.40
for i, (name, color) in enumerate([("Iceberg", cs.ACCENT), ("DuckLake", cs.CONTEXT)]):
    yk = y[-1] - 0.55 - i * 0.30
    ax.add_patch(plt.Rectangle((legx, yk - 0.10), 0.045, 0.20, color=color, clip_on=False, zorder=5))
    ax.text(legx + 0.075, yk, name, ha="left", va="center", fontsize=10,
            color=(cs.ACCENT if color == cs.ACCENT else cs.MUTED),
            fontweight=("bold" if color == cs.ACCENT else "normal"))

# annotate the cache-insensitive reference (under the baseline, clear of legend + axis)
ax.text(1.0, y[-1] - 0.85, "1.0× = cache-insensitive", ha="center", va="center",
        fontsize=8.5, color=cs.MUTED, family=cs.SANS)

cs.direction_note(fig, "cold penalty: lower is better", x=0.975, y=0.745)
cs.save(fig, "out/cold-vs-warm-read-penalty-per-query-iceberg.png")
print("rendered cold/warm")

import chartstyle as cs
import matplotlib.pyplot as plt

# Source: ocsf-vortex-format/results/results.json (1,000,000 OCSF rows)
#   footprint (bytes):  Parquet 11,847,345  Vortex 14,916,824   -> MB (decimal)
#   full_scan median:   Parquet 40.409 ms   Vortex 24.547 ms
#   needle  median:     Parquet 36.855 ms   Vortex 10.777 ms
#   write   ms:         Parquet 195 ms      Vortex 414 ms
# size_ratio parquet/vortex = 0.79 (Parquet smaller); Vortex faster on read.
pq_bytes, vx_bytes = 11847345, 14916824
pq_size = pq_bytes / 1e6   # 11.85 MB
vx_size = vx_bytes / 1e6   # 14.92 MB
pq_scan, vx_scan = 40.409, 24.547
pq_needle, vx_needle = 36.855, 10.777
pq_write, vx_write = 195, 414

# four panels: each (title, unit, parquet, vortex, "lower is better" winner annotation)
panels = [
    ("Footprint", "MB on disk", pq_size, vx_size,
     f"Parquet {pq_size/vx_size:.2f}× smaller"),
    ("Full scan", "ms (median)", pq_scan, vx_scan,
     f"Vortex {pq_scan/vx_scan:.2f}× faster"),
    ("Needle lookup", "ms (median)", pq_needle, vx_needle,
     f"Vortex {pq_needle/vx_needle:.2f}× faster"),
    ("Write", "ms", pq_write, vx_write,
     f"Parquet {vx_write/pq_write:.2f}× faster"),
]

fig, axes = cs.canvas(
    "Vortex trades a bigger file for faster reads; Parquet for cheaper writes",
    "Parquet vs Vortex on 1M OCSF rows, native reader each. Lower is better on every panel — note the per-panel scale.",
    source="sdw-lab-benchmarks/ocsf-vortex-format",
    tier="Tier B · single-host · 1M rows · emerging-format track (Vortex not yet an Iceberg data file)",
    figsize=(9.6, 4.9), bottom=0.12, top=0.66, ncols=4)
fig.subplots_adjust(wspace=0.55, left=0.06, right=0.98)

PQ, VX = cs.CONTEXT, cs.ACCENT

for ax, (title, unit, pv, vv, note) in zip(axes, panels):
    vals = [pv, vv]
    colors = [PQ, VX]
    bars = ax.bar([0, 1], vals, color=colors, width=0.66, edgecolor="white", linewidth=1.0, zorder=3)
    top = max(vals)
    for xi, v in zip([0, 1], vals):
        lbl = f"{v:.0f}" if v >= 100 else (f"{v:.1f}" if v >= 10 else f"{v:.1f}")
        ax.text(xi, v + top * 0.025, lbl, ha="center", va="bottom",
                fontsize=11, fontweight="bold", color=(cs.ACCENT if colors[xi] == VX else cs.BODY))
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Parquet", "Vortex"], fontsize=9.5)
    ax.set_ylim(0, top * 1.30)
    ax.set_title("")  # avoid mpl title; place our own
    ax.text(0.5, 1.13, title, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=11.5, fontweight="bold", color=cs.INK)
    ax.text(0.5, 1.02, note, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=9, color=cs.MUTED, family=cs.MONO)
    ax.set_ylabel(unit, fontsize=9.5)
    cs.bare(ax)
    ax.set_yticks([])
    ax.tick_params(axis="x", length=0)
    ax.grid(False)

cs.direction_note(fig, "Lower is better")
cs.save(fig, "out/vortex-vs-parquet-footprint-scan-needle-write.png")
print("rendered vortex")

import chartstyle as cs
import matplotlib.pyplot as plt

# Source: cost-to-serve-retention/results/RESULTS.md:24-25 (measured bytes/event, same 10M events:
# Iceberg Parquet pyiceberg zstd defaults 44.0, ClickHouse MergeTree blanket ZSTD(22) 41.5),
# :39-40 (priced at 1 TB/day raw, 365-day retention, storage only: CH ZSTD-22 on gp3 $3,234/mo,
# Iceberg zstd on S3 $988/mo), :30-33 (gp3 $0.08, S3 Standard $0.023 per GB-month), :56 (3.3x).
# 3234 / 988 = 3.27, shown as 3.3x.
# Lab chart-style redraw (2026-11-23) of an earlier grayscale figure of the same result.
engines = ["ClickHouse\nZSTD(22) on gp3", "Iceberg\nzstd default on S3"]
bytes_ev = [41.5, 44.0]
cost = [3234, 988]
colors = [cs.ACCENT, cs.CONTEXT]

fig, (a1, a2) = cs.canvas(
    "Better compression, higher bill.",
    "Tighter bytes on block storage still cost 3.3× more a month than looser bytes on object storage,\n"
    "because the storage class sets the price per byte.",
    source="sdw-lab-benchmarks/cost-to-serve-retention",
    tier="Tier B · single host · bytes measured, cost modelled at AWS us-east-1 list prices · storage only",
    figsize=(9.4, 5.2), ncols=2, bottom=0.20, top=0.70)

for ax, vals, fmt, ttl in [(a1, bytes_ev, "{:.1f}", "Measured footprint (bytes per event)"),
                           (a2, cost, "${:,.0f} / mo", "Monthly storage cost (1 TB/day, 365-day retention)")]:
    ax.bar([0, 1], vals, width=0.58, color=colors, zorder=3)
    for xi, v in zip([0, 1], vals):
        ax.text(xi, v * 1.02, fmt.format(v), ha="center", va="bottom", fontsize=12.5,
                fontweight="bold", color=cs.ACCENT if xi == 0 else cs.BODY)
    ax.set_xticks([0, 1]); ax.set_xticklabels(engines, fontsize=10)
    ax.set_title(ttl, fontsize=11, color=cs.INK, loc="left", pad=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(cs.GRID)
    ax.grid(axis="y", color=cs.GRID); ax.grid(axis="x", visible=False); ax.set_axisbelow(True)
    ax.tick_params(length=0)

a1.set_ylim(0, 55)
a1.text(0.5, 50, "ClickHouse is about 6% tighter", ha="center", va="bottom", fontsize=9.5, color=cs.MUTED)
a2.set_ylim(0, 3900)
a2.set_yticks([0, 1000, 2000, 3000]); a2.set_yticklabels(["$0", "$1,000", "$2,000", "$3,000"])
a2.annotate("", xy=(1, 1250), xytext=(1, 3150),
            arrowprops=dict(arrowstyle="<->", color=cs.BAD, lw=1.4))
a2.text(1.08, 2200, "3.3× the bill", ha="left", va="center", fontsize=11, fontweight="bold", color=cs.BAD)

cs.direction_note(fig, "cost: lower is better")
cs.save(fig, "out/storeclass-cost.png")
print("rendered r43")

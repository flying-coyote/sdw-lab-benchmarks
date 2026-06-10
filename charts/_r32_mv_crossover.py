import chartstyle as cs
import matplotlib.pyplot as plt

# Source: ocsf-mv-acceleration/results/CROSSOVER.md
# recompute/incremental ratio (>1 => incremental maintenance wins) vs base:batch,
# at a fixed 200,000-row batch.
#   bounded_high_card (user_name x dst_port, saturates 16,000 groups):
#     5:1 -> 0.95, 25:1 -> 1.9, 100:1 -> 5.57, 200:1 -> 8.49  (first wins ~25:1)
#   unbounded_high_card (src_ip, group count grows with base):
#     5:1 -> 0.64, 25:1 -> 0.71, 100:1 -> 0.74, 200:1 -> 0.78  (never wins in range)
ratios = [5, 25, 100, 200]
bounded = [0.95, 1.9, 5.57, 8.49]
unbounded = [0.64, 0.71, 0.74, 0.78]

fig, ax = cs.canvas(
    "Incremental MV maintenance pays only for bounded-cardinality panels",
    "Recompute / incremental cost ratio vs base:batch (fixed 200k batch). Above 1.0, an incremental merge beats a full recompute.",
    source="sdw-lab-benchmarks/ocsf-mv-acceleration",
    tier="Tier B · single-host · synthetic · the shape is the claim, the crossover ratio is this corpus's",
    figsize=(8.8, 4.8), bottom=0.16, top=0.78)

x = list(range(len(ratios)))

# break-even reference line
ax.axhline(1.0, color=cs.MUTED, lw=1.0, ls=(0, (4, 3)), zorder=1)
ax.text(1.5, 1.35, "break-even (1.0×)", ha="center", va="bottom",
        fontsize=9, color=cs.MUTED, family=cs.MONO)

# bounded = the point (accent), wins
ax.plot(x, bounded, "-o", color=cs.ACCENT, lw=2.6, ms=8, zorder=4,
        markeredgecolor="white", markeredgewidth=1.3)
# unbounded = context (grey), never wins
ax.plot(x, unbounded, "-o", color=cs.CONTEXT, lw=2.4, ms=7, zorder=3,
        markeredgecolor="white", markeredgewidth=1.3)

# direct labels at each point for bounded
for xi, yi in zip(x, bounded):
    ax.annotate(f"{yi:.2f}×", (xi, yi), textcoords="offset points",
                xytext=(0, 11), ha="center", fontsize=10.5, color=cs.ACCENT, fontweight="bold")
# unbounded labels below the markers (all clustered low)
for xi, yi in zip(x, unbounded):
    ax.annotate(f"{yi:.2f}×", (xi, yi), textcoords="offset points",
                xytext=(0, -18), ha="center", fontsize=9.5, color=cs.MUTED)

# series labels (direct, no legend)
ax.text(x[-1] + 0.06, bounded[-1], "bounded card.\n(user × dst_port)", ha="left", va="center",
        fontsize=10, color=cs.ACCENT, fontweight="bold")
ax.text(x[-1] + 0.06, unbounded[-1] + 0.30, "unbounded card.\n(src_ip) — never wins", ha="left", va="bottom",
        fontsize=10, color=cs.MUTED)

# mark the crossover (first win at ~25:1)
ax.annotate("incremental first wins\nhere (~25:1)", xy=(1, 1.9), xytext=(1.0, 4.4),
            ha="center", fontsize=9.5, color=cs.ACCENT,
            arrowprops=dict(arrowstyle="->", color=cs.ACCENT, lw=1.3))

ax.set_xticks(x)
ax.set_xticklabels([f"{r}:1" for r in ratios])
ax.set_xlabel("base : batch ratio")
ax.set_ylabel("recompute / incremental  (×)")
ax.set_xlim(-0.35, len(ratios) - 0.15 + 1.85)
ax.set_ylim(0, 9.7)
ax.grid(axis="y", color=cs.GRID)
ax.grid(axis="x", visible=False)
ax.set_axisbelow(True)
ax.tick_params(length=0)

cs.direction_note(fig, "higher = incremental wins", x=0.115, y=0.745, ha="left", va="top")
cs.save(fig, "out/mv-incremental-vs-recompute-crossover.png")
print("rendered mv crossover")

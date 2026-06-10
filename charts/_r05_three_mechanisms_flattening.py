import chartstyle as cs
import matplotlib.pyplot as plt

# Source: flattening-fidelity/results/RESULTS.md  (synthetic deterministic C2 corpus; SHIPPED public benchmark)
# 1. Absence-vs-NULL:  naive-flat recall 0.00 vs NULL-aware / preserved-JSON recall 1.00 (100% silent-miss, structural)
#    (holds at 1k/10k/100k events, byte-identical re-run)
# 2. Grain loss:       beacon-hunt atomic F1 1.00 vs coarse (5-min rollup) F1 0.50 ; routine query exact either way
# 3. Floating ts:      UTC correlation recall 1.00 vs floating 0.46 (200 chains) / 0.50 (1000 chains)
#    -> cross-zone chains lost; chart the 0.46 worst case and note the 0.46-0.50 range.

panels = [
    {
        "title": "1. Absence vs NULL",
        "mech": "CloudTrail 'no MFA' = an ABSENT field.\nFlattened, absent becomes NULL, so\nWHERE mfa='false' matches nothing.",
        "after_label": "naive\nflattened",
        "before_label": "preserved JSON /\nNULL-aware",
        "after": 0.00,
        "before": 1.00,
        "note": "100% silent miss\n(structural, not probabilistic)",
    },
    {
        "title": "2. Grain loss",
        "mech": "Beacons separable only on timing\njitter. A (src,dst,5-min) rollup\ndrops the discriminating feature.",
        "after_label": "coarse\n5-min rollup",
        "before_label": "atomic\ngrain",
        "after": 0.50,
        "before": 1.00,
        "note": "beacon-hunt F1 halves\n(routine volume query stays exact)",
    },
    {
        "title": "3. Floating timestamps",
        "mech": "Drop the UTC offset and compare\nlocal wall-clocks as if co-zoned;\ncross-zone chains scatter hours apart.",
        "after_label": "floating\nlocal time",
        "before_label": "UTC-\nnormalized",
        "after": 0.46,
        "before": 1.00,
        "note": "cross-zone correlation lost\n(recall 0.46-0.50; same-zone survives)",
    },
]

fig, axes = cs.canvas(
    "Three ways flattening silently drops a detection — same recall before, zero-to-half after.",
    "Recall (or F1) of a planted detection on the fidelity-preserving store vs the flattened store. Each "
    "mechanism is structural: the flattened query runs clean and fast and returns the wrong answer.",
    source="sdw-lab-benchmarks/flattening-fidelity",
    tier="Tier B · single host · SYNTHETIC deterministic corpus · shipped public benchmark (flying-coyote/ocsf-flattening-benchmark)",
    figsize=(12.0, 5.2), bottom=0.32, top=0.72, ncols=3)

for ax, p in zip(axes, panels):
    xs = [0, 1]
    vals = [p["before"], p["after"]]
    colors = [cs.ACCENT, cs.BAD]
    bars = ax.bar(xs, vals, color=colors, width=0.55, zorder=3)
    for x, v in zip(xs, vals):
        ax.text(x, v + 0.03, f"{v:.2f}", ha="center", va="bottom",
                fontsize=14, fontweight="bold", color=cs.BODY)
    ax.set_xticks(xs)
    ax.set_xticklabels([p["before_label"], p["after_label"]], fontsize=9.5)
    ax.set_ylim(0, 1.55)
    ax.set_xlim(-0.7, 1.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(cs.GRID)
    ax.grid(axis="y", color=cs.GRID); ax.grid(axis="x", visible=False)
    ax.tick_params(axis="both", length=0)
    ax.set_yticks([0, 0.5, 1.0])
    # panel title (top, above everything)
    ax.text(-0.7, 1.62, p["title"], ha="left", va="bottom",
            fontsize=11.5, fontweight="bold", color=cs.INK)
    # mechanism note below the axis
    ax.text(0.5, -0.42, p["mech"], ha="center", va="top", transform=ax.get_xaxis_transform(),
            fontsize=8.3, color=cs.MUTED)
    # the loss arrow, drawn between the two bar tops
    ax.annotate("", xy=(0.78, p["after"] + 0.05), xytext=(0.22, p["before"] - 0.05),
                arrowprops=dict(arrowstyle="->", color=cs.BAD, lw=1.3))
    # the loss callout sits in the clear band at the top of the panel
    ax.text(0.5, 1.42, p["note"], ha="center", va="top",
            fontsize=8.2, color=cs.BAD, fontweight="bold")

axes[0].set_ylabel("recall / F1 of the planted detection")

cs.save(fig, "out/three-mechanisms-of-silent-detection-loss.png")
print("rendered r05")

import chartstyle as cs
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Source: ocsf-nl2sql-silenterror/results/RESULTS.md
# (source header writes 'gemma4:26b'; the register + all cross-refs label it gemma3:26b — using gemma3:26b)
# columns per tier: (n, correct, silent, loud)
# phi3:latest   accuracy 0.36, silent-rate 0.09 (3 of 33 silent)
# gemma3:26b    accuracy 0.55, silent-rate 0.00 (15 loud, 0 silent)
tiers = ["simple_filter", "aggregation", "group_by", "time_window",
         "multi_condition", "join", "adversary_tail"]
phi3 = {  # correct, silent, loud
    "simple_filter": (3, 2, 0), "aggregation": (5, 0, 0), "group_by": (0, 1, 4),
    "time_window": (0, 0, 4), "multi_condition": (3, 0, 2), "join": (1, 0, 3),
    "adversary_tail": (0, 0, 5),
}
gemma = {
    "simple_filter": (5, 0, 0), "aggregation": (5, 0, 0), "group_by": (0, 0, 5),
    "time_window": (2, 0, 2), "multi_condition": (4, 0, 1), "join": (2, 0, 2),
    "adversary_tail": (0, 0, 5),
}
C_OK, C_SILENT, C_LOUD = cs.CONTEXT, cs.BAD, cs.ACCENT2

fig, axes = cs.canvas(
    "Silent wrong answers cluster mid-difficulty; the harder model fails loud.",
    "Per-tier outcomes for two local NL2SQL models, counts of correct / silent / loud answers.",
    source="sdw-lab-benchmarks/ocsf-nl2sql-silenterror",
    tier="Tier B · single-host · local models · one planted chain · n=4–5 per tier (directional, not a settled rate)",
    figsize=(10.0, 5.4), bottom=0.22, top=0.74, ncols=2)

ax1, ax2 = axes
y = list(range(len(tiers)))

def draw(ax, data, title, sub):
    for i, tier in enumerate(tiers):
        ok, sil, loud = data[tier]
        left = 0
        for val, col in [(ok, C_OK), (sil, C_SILENT), (loud, C_LOUD)]:
            if val > 0:
                ax.barh(i, val, left=left, color=col, height=0.66, zorder=3)
                tc = "white" if col != C_OK else cs.BODY
                ax.text(left + val / 2, i, str(val), ha="center", va="center",
                        color=tc, fontsize=9, fontweight="bold" if col == C_SILENT else "normal")
                left += val
    ax.set_xlim(0, 5.4)
    ax.set_ylim(-0.9, len(tiers) - 0.3)
    cs.bare(ax)
    ax.invert_yaxis()
    ax.grid(axis="x", visible=False); ax.grid(axis="y", visible=False)
    ax.set_xticks([]); ax.tick_params(length=0)
    # title + sub stacked above the plot, in the reserved top margin
    ax.text(0, 1.12, title, transform=ax.transAxes, fontsize=12.5,
            color=cs.BODY, fontweight="bold", ha="left", va="bottom")
    ax.text(0, 1.035, sub, transform=ax.transAxes, fontsize=9.3,
            color=cs.MUTED, ha="left", va="bottom", family=cs.MONO)

draw(ax1, phi3, "phi3:latest", "accuracy 0.36  ·  silent-rate 0.09  ·  3 silent")
ax1.set_yticks(y); ax1.set_yticklabels(tiers, fontsize=10)
draw(ax2, gemma, "gemma3:26b", "accuracy 0.55  ·  silent-rate 0.00  ·  0 silent")
ax2.set_yticks(y); ax2.set_yticklabels([])

handles = [
    Patch(facecolor=C_OK, label="correct"),
    Patch(facecolor=C_SILENT, label="silent (runs, returns a wrong answer)"),
    Patch(facecolor=C_LOUD, label="loud (errors / empty)"),
]
fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.085),
           ncol=3, frameon=False, fontsize=9.5, handlelength=1.2)

cs.save(fig, "out/nl2sql-silent-error-by-model-strength-an.png")
print("rendered r11")

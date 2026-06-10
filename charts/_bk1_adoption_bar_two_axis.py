"""Build #1 — adoption-bar-two-axis (MOAR book ch01, Executive Summary).

Conceptual two-axis framing diagram: a platform move has to win large on BOTH
the technical axis and the operational axis or the migration risk doesn't make
sense. FRAMING DIAGRAM — no measured data points, no evidence-tier claim.
Source framing sentence: ch01-why-cybersecurity-data-is-different-DRAFT.md line 7.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import chartstyle as cs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

OUT = os.path.join(_HERE, "out")
NAME = "adoption-bar-two-axis"
SANS_FB = [cs.SANS, "DejaVu Sans"]


def build(gray=False):
    ACCENT = "#3a3a3a" if gray else cs.ACCENT
    WARN = "#8a8a8a" if gray else cs.WARN
    WIN_FILL = "#d9d9d9" if gray else "#e7eef5"   # the wins-both region
    LOSE_FILL = "#f3f3f3" if gray else cs.SUBTLE

    fig, ax = cs.canvas(
        "The adoption bar: a move has to win large on BOTH axes,\n"
        "or the risk doesn't make sense.",
        "The scarcest resource is people fluent on both sides of the security/data-engineering bridge — scarcer than\n"
        "budget, and scarcer than any single technology gap. That scarcity is what sets the bar.",
        source="MOAR book ch01, Executive Summary — the adoption-bar framing",
        tier="framing diagram · illustrative — no measured data points",
        figsize=(8.8, 5.6), top=0.785, bottom=0.085)

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["left"].set_color(cs.MUTED)
    ax.spines["bottom"].set_color(cs.MUTED)

    BAR = 6.0  # the bar sits high on purpose: "win LARGE on both axes"

    # quadrant fills
    ax.add_patch(Rectangle((0, 0), 10, 10, facecolor=LOSE_FILL, edgecolor="none", zorder=0))
    ax.add_patch(Rectangle((BAR, BAR), 10 - BAR, 10 - BAR, facecolor=WIN_FILL,
                           edgecolor=ACCENT, linewidth=1.6, zorder=1))

    # the adoption bar (L-shaped threshold)
    ax.plot([BAR, BAR], [BAR, 10], color=ACCENT, lw=2.2, ls=(0, (5, 3)), zorder=2)
    ax.plot([BAR, 10], [BAR, BAR], color=ACCENT, lw=2.2, ls=(0, (5, 3)), zorder=2)
    ax.text(BAR - 0.15, 9.75, "the adoption bar", ha="right", va="top", fontsize=10,
            color=ACCENT, family=SANS_FB, fontweight="bold", rotation=0)

    # region labels
    ax.text((BAR + 10) / 2, (BAR + 10) / 2 + 0.35, "ADOPTION DEFENSIBLE",
            ha="center", va="center", fontsize=11.5, color=ACCENT,
            family=SANS_FB, fontweight="bold", zorder=3)
    ax.text((BAR + 10) / 2, (BAR + 10) / 2 - 0.55,
            "wins large on the benchmark AND\nyour team can actually run it",
            ha="center", va="center", fontsize=8.6, color=cs.BODY,
            family=SANS_FB, zorder=3, linespacing=1.5)

    ax.text(BAR / 2 + 0.4, 8.0,
            "Operational win without the\ntechnical case — easy to run,\n"
            "but no reason to take the\nmigration risk",
            ha="center", va="center", fontsize=9, color=cs.MUTED,
            family=SANS_FB, linespacing=1.6)

    ax.text((BAR + 10) / 2, 2.9,
            "Wins the benchmark while assuming\nspecialists you cannot hire —\n"
            "fails in operation no matter\nwhat the cost model says",
            ha="center", va="center", fontsize=9, color=WARN,
            family=SANS_FB, linespacing=1.6, fontweight="bold")

    ax.text(BAR / 2 + 0.4, 2.9, "No case on either axis —\nstay where you are",
            ha="center", va="center", fontsize=9, color=cs.MUTED,
            family=SANS_FB, linespacing=1.6)

    # axis arrows + labels
    ax.annotate("", xy=(10, 0), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color=cs.MUTED, lw=1.4))
    ax.annotate("", xy=(0, 10), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color=cs.MUTED, lw=1.4))
    ax.set_xlabel("Technical win  (benchmark, capability, cost model)",
                  fontsize=10.5, color=cs.BODY, family=SANS_FB)
    ax.set_ylabel("Operational win  (a team you can actually staff can run it)",
                  fontsize=10.5, color=cs.BODY, family=SANS_FB)

    return fig


def main():
    fig = build(gray=False)
    web = os.path.join(OUT, f"{NAME}.png")
    fig.savefig(web, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)

    fig = build(gray=True)
    prn = os.path.join(OUT, f"{NAME}-print.png")
    fig.savefig(prn, dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    from PIL import Image
    Image.open(prn).convert("L").save(prn)
    print("rendered", web, "and", prn)


if __name__ == "__main__":
    main()

"""Build #5 — three-journeys-comparison (MOAR book ch04 §4.5).

Extends the pb6 campaign graphic (_pb6_three_journeys.py) with the Marcus
Path-A → Path-B pivot. Every constraint phrase, platform name, cost, and
trade-off is carried character-exact from the ch04 §4.5 comparison table
(ch04-three-architect-journeys-DRAFT.md lines 418-423): $380K / $2.9M /
$12M / $1.8M, the $200K limited SIEM, the $9.1M/year premium, 60-90 sec,
<30 sec, 1.5-3×.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import chartstyle as cs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

OUT = os.path.join(_HERE, "out")
NAME = "three-journeys-comparison"
MONO_FB = [cs.MONO, "DejaVu Sans Mono"]
SANS_FB = [cs.SANS, "DejaVu Sans"]


def build(gray=False):
    ACCENT = "#3a3a3a" if gray else cs.ACCENT
    WARN = "#6e6e6e" if gray else cs.WARN
    WARN_TXT = "#3a3a3a" if gray else cs.WARN

    fig, ax = cs.canvas(
        "Same framework, three estates, three right answers — and re-run under\n"
        "changed constraints, the right answer was the $12M incumbent.",
        source="MOAR book ch04 §4.5 comparison table — composite journeys; costs carried exactly",
        tier="illustrative · composites, constraints kept faithful",
        figsize=(9.6, 6.4), top=0.845, bottom=0.075)

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis("off")
    ax.grid(False)

    def box(x, y, w, h, fc=cs.SUBTLE, ec=cs.GRID, lw=1.0):
        p = FancyBboxPatch((x, y), w, h,
                           boxstyle="round,pad=0.10,rounding_size=0.16",
                           facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3)
        ax.add_patch(p)
        return p

    # --- framework box across the top ---
    fx, fy, fw, fh = 0.40, 10.75, 9.20, 1.00
    box(fx, fy, fw, fh, fc=cs.WHITE, ec=ACCENT, lw=1.6)
    ax.text(fx + fw / 2, fy + fh / 2,
            "same Chapter 3 framework — mandatory filters → weighted scoring",
            ha="center", va="center", fontsize=9.5, color=ACCENT,
            family=MONO_FB, fontweight="bold", zorder=4)

    CW = 2.95
    con_y, con_h = 8.10, 1.90    # binding-constraint boxes
    ans_y, ans_h = 6.10, 1.30    # first-pass answer boxes

    cols = [
        (0.30, "Jennifer · healthcare",
         "HIPAA data sovereignty +\noperational simplicity\n(0-1 engineers)",
         "Dremio Cloud +\nOn-Prem Hybrid — $380K/yr",
         "trade-off: no real-time (<30 sec);\nkept a limited schema-on-read\nSIEM ($200K) for real-time"),
        (3.525, "Marcus · financial services",
         "AWS-native integration +\n7-year queryable retention",
         "Path A: AWS Athena +\nStarburst — $2.9M/yr",
         "trade-off: 60-90 sec latency\nvs real-time requirement"),
        (6.75, "Priya · multi-national",
         "multi-cloud data sovereignty +\nzero regional disruption",
         "Denodo Virtualization\nPlatform — $1.8M/yr",
         "trade-off: 1.5-3× performance\noverhead vs native queries"),
    ]

    for cx0, who, constraints, answer, trade in cols:
        cx = cx0 + CW / 2
        ax.text(cx, con_y + con_h + 0.55, who, ha="center", va="center",
                fontsize=9.3, color=cs.INK, family=SANS_FB, fontweight="bold",
                zorder=5, bbox=dict(facecolor=cs.WHITE, edgecolor="none", pad=1.6))
        ax.annotate("", xy=(cx, con_y + con_h + 0.10), xytext=(cx, fy - 0.12),
                    arrowprops=dict(arrowstyle="->", color=cs.MUTED, lw=1.1,
                                    shrinkA=0, shrinkB=0), zorder=2)
        box(cx0, con_y, CW, con_h, fc=cs.SUBTLE, ec=cs.GRID)
        ax.text(cx, con_y + con_h / 2, constraints, ha="center", va="center",
                fontsize=8.7, color=cs.BODY, family=SANS_FB, zorder=4,
                linespacing=1.55)
        ax.annotate("", xy=(cx, ans_y + ans_h + 0.10), xytext=(cx, con_y - 0.12),
                    arrowprops=dict(arrowstyle="->", color=cs.MUTED, lw=1.1,
                                    shrinkA=0, shrinkB=0), zorder=2)
        box(cx0, ans_y, CW, ans_h, fc=ACCENT, ec=ACCENT)
        ax.text(cx, ans_y + ans_h / 2, answer, ha="center", va="center",
                fontsize=8.8, color=cs.WHITE, family=MONO_FB,
                fontweight="bold", zorder=4, linespacing=1.45)
        ax.text(cx, ans_y - 0.30, trade, ha="center", va="top", fontsize=7.4,
                color=cs.MUTED, family=SANS_FB, zorder=4, linespacing=1.45)

    # --- the Marcus Path-A → Path-B pivot (middle column only) ---
    mx0 = 3.525
    mcx = mx0 + CW / 2
    piv_y, piv_h = 2.55, 1.75
    pb_y, pb_h = 0.85, 1.30

    ax.annotate("", xy=(mcx, piv_y + piv_h + 0.10), xytext=(mcx, ans_y - 1.32),
                arrowprops=dict(arrowstyle="->", color=WARN, lw=1.4,
                                shrinkA=0, shrinkB=0), zorder=2)
    ax.text(mcx + 0.16, piv_y + piv_h + 0.42, "constraints change →\nsame framework, second pass",
            ha="left", va="center", fontsize=7.2, color=WARN_TXT,
            family=SANS_FB, zorder=4, linespacing=1.4)
    box(mx0, piv_y, CW, piv_h, fc=cs.WHITE, ec=WARN, lw=1.5)
    ax.text(mcx, piv_y + piv_h / 2,
            "SEC real-time fraud mandate\n(<30 sec) + team capacity\nloss (1 engineer)",
            ha="center", va="center", fontsize=8.6, color=cs.BODY,
            family=SANS_FB, zorder=4, linespacing=1.55)
    ax.annotate("", xy=(mcx, pb_y + pb_h + 0.10), xytext=(mcx, piv_y - 0.12),
                arrowprops=dict(arrowstyle="->", color=WARN, lw=1.4,
                                shrinkA=0, shrinkB=0), zorder=2)
    box(mx0, pb_y, CW, pb_h, fc=WARN, ec=WARN)
    ax.text(mcx, pb_y + pb_h / 2, "Path B: Schema-on-read\nSIEM — $12M/yr",
            ha="center", va="center", fontsize=8.8, color=cs.WHITE,
            family=MONO_FB, fontweight="bold", zorder=4, linespacing=1.45)
    ax.text(mcx, pb_y - 0.28,
            "$9.1M/yr premium accepted for regulatory\ncompliance + operational simplicity",
            ha="center", va="top", fontsize=7.4, color=WARN_TXT,
            family=SANS_FB, zorder=4, linespacing=1.45)

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

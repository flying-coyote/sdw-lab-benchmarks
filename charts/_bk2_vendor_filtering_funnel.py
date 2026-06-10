"""Build #2 — vendor-filtering-funnel (MOAR book ch03 §3.1).

Funnel: 80-100 vendors -> Tier 1 mandatory filter -> 10-15 viable -> Tier 2
scoring -> 3-5 finalists -> Tier 3 tiebreaker -> 1 winner -> POC -> 1 selection.
Counts carried exactly from the "Vendor Landscape Reduction" table,
ch03-decision-framework-DRAFT.md lines 121-131 (incl. the ~87% / 80->10 note).
Framework-derived counts, not a measurement.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import chartstyle as cs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402

OUT = os.path.join(_HERE, "out")
NAME = "vendor-filtering-funnel"
SANS_FB = [cs.SANS, "DejaVu Sans"]

# (stage, count label, mechanism)  — ch03 §3.1 table, verbatim counts
STAGES = [
    ("Initial universe", "80-100 vendors", '"security data platform"\nmarket category'),
    ("After Tier 1 filters", "10-15 vendors", "mandatory requirements (SQL, retention,\nintegration, partitioning)"),
    ("After Tier 2 scoring", "3-5 finalists", "strongly preferred capabilities\n(open formats, OCSF, streaming)"),
    ("After Tier 3 tiebreaker", "1 winner", "nice-to-have features\n(ML, threat intel, templates)"),
    ("After POC validation", "1 selection", "proof-of-concept with real data\nconfirms claims"),
]
# midpoint counts drive the funnel widths (sqrt-scaled so the tail stays visible)
MIDS = [90, 12.5, 4, 1, 1]


def build(gray=False):
    band = ["#3a3a3a", "#5a5a5a", "#7a7a7a", "#999999", "#b3b3b3"] if gray else \
           [cs.ACCENT, cs.TEAL600, cs.ACCENT2, "#8db0d6", cs.CONTEXT]

    fig, ax = cs.canvas(
        "Twelve mandatory requirements do the heavy lifting: 80+ vendors\n"
        "down to 10-15 viable, then 3-5 finalists, then one validated selection.",
        "Tier 1 does most of the work — roughly an 87% reduction in the framework example (80 down to 10);\n"
        "Tiers 2 and 3 only refine the finalists from there.",
        source="MOAR book ch03 §3.1 — 'The Filtering Effect' vendor-landscape-reduction table",
        tier="framework-derived counts · not a measurement — your count depends on your Tier 1 list",
        figsize=(8.8, 5.6), top=0.775, bottom=0.08)

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.grid(False)

    n = len(STAGES)
    top_y, bot_y = 9.4, 0.6
    row_h = (top_y - bot_y) / n
    cx = 3.1                      # funnel center x
    max_w = 5.4                   # width of the widest band
    w = [max_w * (m / MIDS[0]) ** 0.5 for m in MIDS]
    w = [max(v, 0.55) for v in w]  # floor so the 1-vendor bands stay drawable

    for i, (stage, count, mech) in enumerate(STAGES):
        y1 = top_y - i * row_h          # top of this band
        y0 = y1 - row_h * 0.84          # bottom (gap between bands)
        w1 = w[i]
        w0 = w[i + 1] if i + 1 < n else w[i]
        poly = Polygon([(cx - w1 / 2, y1), (cx + w1 / 2, y1),
                        (cx + w0 / 2, y0), (cx - w0 / 2, y0)],
                       closed=True, facecolor=band[i], edgecolor="white",
                       linewidth=1.2, zorder=3)
        ax.add_patch(poly)
        # count inside (or beside, once the band gets narrow)
        if w1 > 1.6:
            ax.text(cx, (y0 + y1) / 2, count, ha="center", va="center",
                    fontsize=11, color=cs.WHITE, family=SANS_FB,
                    fontweight="bold", zorder=4)
        else:
            ax.text(cx + w1 / 2 + 0.18, (y0 + y1) / 2, count, ha="left",
                    va="center", fontsize=11, color=band[i], family=SANS_FB,
                    fontweight="bold", zorder=4)
        # stage label left, mechanism right
        ax.text(0.04, (y0 + y1) / 2, stage, ha="left", va="center",
                fontsize=9.5, color=cs.INK, family=SANS_FB, fontweight="bold")
        ax.text(6.35, (y0 + y1) / 2, mech, ha="left", va="center",
                fontsize=8.4, color=cs.MUTED, family=SANS_FB, linespacing=1.45)

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

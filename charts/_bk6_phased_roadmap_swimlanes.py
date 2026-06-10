"""Build #6 — phased-roadmap-swimlanes (MOAR book ch06 §6.3 + Appendix L.4).

Integrated-org vs federated-org implementation swimlanes. Integrated phase
spans carried exactly from the §6.3 headings (Pilot Months 1-3 / Production
Rollout Months 4-6 / Optimization & SIEM Sunset Months 7-9) with the month-3
GO/NO-GO and month-6 gates; the "12 months against the 6 to 9 an integrated
org would take" comparison and the seven staggered BU bars come from the
Appendix L.4 rollout table (§6.3 hands the federated walkthrough there).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import chartstyle as cs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

OUT = os.path.join(_HERE, "out")
NAME = "phased-roadmap-swimlanes"
SANS_FB = [cs.SANS, "DejaVu Sans"]

# Integrated phases: (label, month start, month end) — ch06 §6.3.1-6.3.3
PHASES = [
    ("Pilot — 5 sources, 10 analysts,\nparallel with the legacy SIEM", 0, 3),
    ("Production rollout — all 50 sources,\nfull SOC, 7-year retention", 3, 6),
    ("Optimization & SIEM sunset —\nfull retire or limited SIEM", 6, 9),
]
# Federated BU bars: (BU, onboard month, sunset month) — Appendix L.4 table
BUS = [
    ("BU-A (Pharma)", 1, 10),
    ("BU-D (Diagnostics)", 1, 10),
    ("BU-C (Consumer Health)", 4, 10),
    ("BU-E (Medical Devices)", 4, 11),
    ("BU-G (Clinical Research)", 6, 10),
    ("BU-H (Biologics)", 6, 11),
    ("BU-K (Vaccines)", 8, 12),
]


def build(gray=False):
    ACCENT = "#3a3a3a" if gray else cs.ACCENT
    ACCENT2 = "#6e6e6e" if gray else cs.ACCENT2
    PHASE_C = [ACCENT, "#555555" if gray else cs.TEAL600, ACCENT2]
    GATE = "#1f1f1f" if gray else cs.WARN
    BU_C = "#8c8c8c" if gray else cs.ACCENT2

    fig, ax = cs.canvas(
        "Gates fund each phase, never a big-bang cutover: 9 months for an\n"
        "integrated org — a federated estate runs 12, and that's the plan working.",
        source="MOAR book ch06 §6.3 phase spans + Appendix L.4 federated rollout table, carried exactly",
        tier="illustrative roadmap · durations as specified in §6.3 / L.4, not a measurement",
        figsize=(9.8, 6.2), top=0.85, bottom=0.09)

    ax.set_xlim(0, 12.6)
    ax.set_ylim(-0.6, 11.6)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=cs.GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_xticks(range(13))
    ax.set_xticklabels(["", *(f"M{m}" for m in range(1, 13))], fontsize=8.5)
    ax.set_yticks([])

    # ---- lane 1: integrated org (top) ----
    ax.text(0, 11.25, "INTEGRATED ORG — one decision-maker, synchronized timeline, corporate-funded pilot",
            ha="left", va="center", fontsize=9.0, color=cs.INK,
            family=SANS_FB, fontweight="bold")
    y_int = 9.9
    for (label, m0, m1), c in zip(PHASES, PHASE_C):
        ax.barh(y_int, m1 - m0, left=m0, height=0.85, color=c, zorder=3)
        ax.text((m0 + m1) / 2, y_int, label, ha="center", va="center",
                fontsize=7.4, color=cs.WHITE, family=SANS_FB, zorder=4,
                linespacing=1.4)
    # go/no-go gates (ch06 §6.3.1 month-1/2/3 reviews, §6.3.2 month-6 gate)
    for m, txt, big in [(1, "M1 review", False), (2, "M2 review", False),
                        (3, "GO / NO-GO\nto production", True),
                        (6, "GO to sunset, or\nextend parallel run", True)]:
        ax.plot(m, y_int - 0.62, marker="D", markersize=8 if big else 5,
                color=GATE, zorder=5, markeredgecolor="white", markeredgewidth=1.0)
        ax.text(m, y_int - 1.02, txt, ha="center", va="top",
                fontsize=7.2 if big else 6.6,
                color=cs.BODY if big else cs.MUTED, family=SANS_FB,
                linespacing=1.3, fontweight="bold" if big else "normal")
    ax.text(9.15, y_int,
            "M7-8: full sunset (cancel renewal,\n$800K/yr saved) or limited SIEM\n"
            "($800K→$200K/yr; $610K total, 24% under)\nM9: continuous improvement",
            ha="left", va="center", fontsize=6.8, color=cs.MUTED,
            family=SANS_FB, linespacing=1.45)

    # ---- lane 2: federated org (bottom) ----
    ax.text(0, 7.55, "FEDERATED ORG — 8-15 autonomous BUs, each controls its own cutover; coalition-funded",
            ha="left", va="center", fontsize=9.0, color=cs.INK,
            family=SANS_FB, fontweight="bold")
    for i, (bu, m0, m1) in enumerate(BUS):
        y = 6.6 - i * 0.95
        ax.barh(y, m1 - m0, left=m0, height=0.58, color=BU_C, zorder=3)
        ax.text(m0 - 0.12, y, bu, ha="right", va="center", fontsize=7.2,
                color=cs.BODY, family=SANS_FB)
        ax.plot(m1, y, marker="D", markersize=5, color=GATE, zorder=5,
                markeredgecolor="white", markeredgewidth=0.8)
        ax.text(m1 + 0.14, y, f"sunset M{m1}", ha="left", va="center",
                fontsize=6.6, color=cs.MUTED, family=SANS_FB)
    ax.text(0.15, -0.25,
            "Each bar runs data-onboarding → parallel operation → that BU's SIEM sunset; BU-controlled pacing, "
            "4-9 months per BU. \"The total program ran\n12 months against the 6 to 9 an integrated org would "
            "take\" (Appendix L.4) — roughly twice as long, by design, not by failure (§6.3.3).",
            ha="left", va="center", fontsize=7.6, color=cs.BODY,
            family=SANS_FB, linespacing=1.5)

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

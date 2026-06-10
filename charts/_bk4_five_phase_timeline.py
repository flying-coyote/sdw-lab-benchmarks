"""Build #4 — five-phase-decision-timeline (MOAR book ch03 §3.5).

Five phases over roughly seven weeks with the gate each phase has to clear.
Week spans carried exactly from the §3.5 phase headings (lines 436/462/489/
510/535); "roughly seven weeks" from line 432; phase outputs from lines
458 (requirements doc), 485 (10-25 vendors), 491/506 (2-4 finalists),
531 (clear winner or top two), 547 (decision documented, approved, underway);
POC week-by-week split from line 518; the reality-check note from line 545.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import chartstyle as cs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

OUT = os.path.join(_HERE, "out")
NAME = "five-phase-decision-timeline"
SANS_FB = [cs.SANS, "DejaVu Sans"]

# (phase label, week start, week end, gate text at phase end)
PHASES = [
    ("Phase 1 · Requirements gathering", 0, 1,
     "requirements doc:\nTier 1 / 2 / 3 + constraints"),
    ("Phase 2 · Vendor landscape filtering", 0, 2,
     "10-25 vendors clear\nevery mandatory gate"),
    ("Phase 3 · Tier 2 scoring & finalists", 1, 2,
     "2-4 finalists\ncarried into the POC"),
    ("Phase 4 · Proof-of-concept evaluation", 2, 6,
     "a clear winner —\nor a top two"),
    ("Phase 5 · Decision documentation", 6, 7,
     "ADR approved;\nimplementation begins"),
]
POC_WEEKS = ["wk 3 · setup", "wk 4 · performance", "wk 5 · operations", "wk 6 · cost"]


def build(gray=False):
    ACCENT = "#3a3a3a" if gray else cs.ACCENT
    ACCENT2 = "#6e6e6e" if gray else cs.ACCENT2
    GATE = "#1f1f1f" if gray else cs.WARN
    bar_c = [ACCENT, ACCENT2, ACCENT2, ACCENT, ACCENT2]

    fig, ax = cs.canvas(
        "Requirements to a documented decision in roughly seven weeks —\n"
        "and four of those weeks belong to the proof-of-concept.",
        source="MOAR book ch03 §3.5 — phase headings and week spans, carried exactly",
        tier="process timeline · mid-market baseline (2-5 TB/day) — see the per-phase reality check",
        figsize=(9.6, 5.4), top=0.83, bottom=0.10)

    n = len(PHASES)
    ax.set_xlim(0, 7.0)
    ax.set_ylim(-1.35, n)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=cs.GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_xticks(range(8))
    ax.set_xticklabels([f"wk {w}" for w in range(8)], fontsize=9)
    ax.set_yticks([])

    # gate-text placement per phase: (dx, dy, ha) relative to the gate diamond
    gate_pos = [(0.12, -0.07, "left"), (0.12, -0.07, "left"),
                (0.12, -0.07, "left"), (0.12, 0.42, "left"),
                (0.0, -0.50, "right")]
    for i, (label, w0, w1, gate) in enumerate(PHASES):
        y = n - 1 - i
        ax.barh(y, w1 - w0, left=w0, height=0.52, color=bar_c[i], zorder=3)
        ax.text(w0 + 0.07, y + 0.42, label, ha="left", va="center",
                fontsize=9.3, color=cs.INK, family=SANS_FB, fontweight="bold")
        # gate diamond + output at the phase end
        ax.plot(w1, y, marker="D", markersize=7, color=GATE, zorder=4,
                markeredgecolor="white", markeredgewidth=1.0)
        dx, dy, ha = gate_pos[i]
        ax.text(w1 + dx, y + dy, gate, ha=ha, va="center", fontsize=7.6,
                color=cs.BODY, family=SANS_FB, linespacing=1.35, zorder=4)

    # POC week-by-week split inside the Phase 4 bar
    y4 = n - 1 - 3
    for k, wk in enumerate(POC_WEEKS):
        ax.text(2.5 + k, y4, wk.split(" · ")[1], ha="center", va="center",
                fontsize=7.6, color=cs.WHITE, family=SANS_FB, zorder=4)
        if k:
            ax.plot([2 + k, 2 + k], [y4 - 0.26, y4 + 0.26], color="white",
                    lw=1.0, zorder=4)

    # reality-check note (§3.5, Phase 5 timeline reality check)
    ax.text(0, -1.05,
            "Reality check (§3.5): this is the mid-market baseline (2-5 TB/day, single cloud, 3-5 sources). "
            "Enterprise / multi-cloud / federated:\n12-16 weeks per phase (9-12 months total). "
            "Small greenfield teams: 3-4 weeks per phase (2-3 months total).",
            ha="left", va="center", fontsize=8.0, color=cs.MUTED,
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

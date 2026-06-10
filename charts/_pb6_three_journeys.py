import chartstyle as cs
from matplotlib.patches import FancyBboxPatch

# Diagram: one decision framework, three estates, three different right answers
# (and one reversal when the constraints changed). Composites, not a measurement.

MONO_FB = [cs.MONO, "DejaVu Sans Mono"]   # fallback for → (not in brand fonts)
SANS_FB = [cs.SANS, "DejaVu Sans"]

fig, ax = cs.canvas(
    "Same framework, three estates, three different right answers.",
    "The constraints pick the platform — and when one estate's constraints changed,\n"
    "the same framework sent it back to the SIEM.",
    source="MOAR book ch05 — composite journeys from real engagements",
    tier="illustrative · composites, constraints kept faithful",
    figsize=(8.8, 4.8), top=0.76, bottom=0.10)

ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis("off")
ax.grid(False)

def box(x, y, w, h, fc=cs.SUBTLE, ec=cs.GRID, lw=1.0):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.10,rounding_size=0.16",
                       facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3)
    ax.add_patch(p)
    return p

# --- framework box across the top (accent-edged) ---
fx, fy, fw, fh = 0.40, 8.55, 9.20, 1.15
box(fx, fy, fw, fh, fc=cs.WHITE, ec=cs.ACCENT, lw=1.6)
ax.text(fx + fw / 2, fy + fh / 2,
        "same decision framework — mandatory filters → weighted scoring",
        ha="center", va="center", fontsize=9.5, color=cs.ACCENT,
        family=MONO_FB, fontweight="bold", zorder=4)

# --- three columns ---
CW = 2.95
cols = [
    (0.30,  "PHI stays on-prem ·\n~no data-engineering staff", "Dremio hybrid", None),
    (3.525, "AWS-committed ·\n7-year queryable retention",     "Athena + Starburst",
            "→ back to the SIEM when a real-time\nmandate + staffing loss rewrote\nthe constraints"),
    (6.75,  "EU data stays in the EU ·\nChina data stays in China", "Denodo virtualization", None),
]
con_y, con_h = 5.45, 2.05   # constraints boxes
ans_y, ans_h = 3.25, 1.15   # answer boxes
for cx0, constraints, answer, note in cols:
    cx = cx0 + CW / 2
    # framework -> constraints
    ax.annotate("", xy=(cx, con_y + con_h + 0.06), xytext=(cx, fy - 0.10),
                arrowprops=dict(arrowstyle="->", color=cs.MUTED, lw=1.1,
                                shrinkA=0, shrinkB=0), zorder=2)
    # constraints box (grey)
    box(cx0, con_y, CW, con_h, fc=cs.SUBTLE, ec=cs.GRID)
    ax.text(cx, con_y + con_h / 2, constraints, ha="center", va="center",
            fontsize=9.3, color=cs.BODY, family=cs.SANS, zorder=4, linespacing=1.6)
    # constraints -> answer
    ax.annotate("", xy=(cx, ans_y + ans_h + 0.06), xytext=(cx, con_y - 0.10),
                arrowprops=dict(arrowstyle="->", color=cs.MUTED, lw=1.1,
                                shrinkA=0, shrinkB=0), zorder=2)
    # answer box (accent)
    box(cx0, ans_y, CW, ans_h, fc=cs.ACCENT, ec=cs.ACCENT)
    ax.text(cx, ans_y + ans_h / 2, answer, ha="center", va="center",
            fontsize=10, color=cs.WHITE, family=cs.MONO, fontweight="bold", zorder=4)
    # warn note (col 2 reversal)
    if note:
        ax.text(cx, ans_y - 0.45, note, ha="center", va="top", fontsize=8,
                color=cs.WARN, family=SANS_FB, zorder=4, linespacing=1.5)

cs.save(fig, "out/three-architect-journeys.png")
print("rendered pb6")

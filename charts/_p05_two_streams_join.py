import chartstyle as cs
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# Diagram: two context streams join on source IP into one detection.
# Mechanism illustration, not a measurement.

fig, ax = cs.canvas(
    "Neither signal is an incident; the join on source IP is.",
    "A handful of failed logins from an internal IP, and that same IP opening RDP sessions —\n"
    "brute force walking into lateral movement, visible only in the join.",
    source="security-data-that-works/docker (auth + network streams)",
    tier="illustrative · mechanism, not a measurement",
    figsize=(8.8, 4.0), top=0.74, bottom=0.11)

ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis("off")

def box(x, y, w, h, fc=cs.SUBTLE, ec=cs.GRID, lw=1.0):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12,rounding_size=0.18",
                       facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3)
    ax.add_patch(p)
    return p

# --- two stream boxes (grey context), left ---
sw, sh = 2.85, 2.2
sx = 0.40
streams = [("auth stream", "failed logins", 7.45), ("network stream", "RDP sessions", 0.95)]
for name, detail, sy in streams:
    box(sx, sy, sw, sh, fc=cs.SUBTLE, ec=cs.GRID)
    ax.text(sx + sw/2, sy + sh * 0.64, name, ha="center", va="center",
            fontsize=11, color=cs.BODY, family=cs.SANS, zorder=4)
    ax.text(sx + sw/2, sy + sh * 0.30, detail, ha="center", va="center",
            fontsize=9.5, color=cs.MUTED, family=cs.SANS, zorder=4)

# --- join node (small, accent) ---
jw, jh = 2.0, 1.15
jx, jy = 4.45, 5.30 - jh/2
box(jx, jy, jw, jh, fc=cs.WHITE, ec=cs.ACCENT, lw=1.6)
ax.text(jx + jw/2, jy + jh/2, "JOIN ON src_ip", ha="center", va="center",
        fontsize=10, color=cs.ACCENT, family=cs.MONO, fontweight="bold", zorder=4)

# --- arrows: streams -> join node ---
for _, _, sy in streams:
    ax.annotate("", xy=(jx - 0.18, 5.30 + (0.35 if sy > 5 else -0.35)),
                xytext=(sx + sw + 0.18, sy + sh/2),
                arrowprops=dict(arrowstyle="->", color=cs.MUTED, lw=1.2,
                                shrinkA=0, shrinkB=0), zorder=2)

# --- arrow: join -> detection ---
ax.annotate("", xy=(7.05, 5.30), xytext=(jx + jw + 0.18, 5.30),
            arrowprops=dict(arrowstyle="->", color=cs.MUTED, lw=1.3,
                            shrinkA=0, shrinkB=0), zorder=2)

# --- detection box (accent fill), right ---
dw, dh = 2.45, 2.0
dx, dy = 7.25, 5.30 - dh/2
box(dx, dy, dw, dh, fc=cs.ACCENT, ec=cs.ACCENT)
ax.text(dx + dw/2, dy + dh * 0.74, "brute force", ha="center", va="center",
        fontsize=11, color=cs.WHITE, family=cs.SANS, fontweight="bold", zorder=4)
ax.annotate("", xy=(dx + dw/2, dy + dh * 0.38), xytext=(dx + dw/2, dy + dh * 0.62),
            arrowprops=dict(arrowstyle="->", color=cs.WHITE, lw=1.3,
                            shrinkA=0, shrinkB=0), zorder=4)
ax.text(dx + dw/2, dy + dh * 0.24, "lateral movement", ha="center", va="center",
        fontsize=11, color=cs.WHITE, family=cs.SANS, fontweight="bold", zorder=4)

cs.save(fig, "out/two-streams-join.png")
print("rendered p05")

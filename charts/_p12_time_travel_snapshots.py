import chartstyle as cs
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# Diagram: Iceberg snapshot time travel — three writes, three immutable snapshots,
# each still queryable. Mechanism illustration, not a measurement.

fig, ax = cs.canvas(
    "Three writes, three snapshots — each still queryable as it stood.",
    "Iceberg snapshots are immutable. A mutable index updates in place, so \"what did this\n"
    "look like before the reindex\" has no answer there.",
    source="security-data-that-works/docker · Iceberg snapshot time travel",
    tier="illustrative · mechanism, not a measurement",
    figsize=(8.8, 3.8), top=0.72, bottom=0.12)

ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis("off")

def box(x, y, w, h, fc=cs.SUBTLE, ec=cs.GRID, lw=1.0):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12,rounding_size=0.18",
                       facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3)
    ax.add_patch(p)
    return p

# --- time arrow under the panels ---
ay = 5.55
ax.annotate("", xy=(9.75, ay), xytext=(0.25, ay),
            arrowprops=dict(arrowstyle="->", color=cs.MUTED, lw=1.2,
                            shrinkA=0, shrinkB=0), zorder=2)
ax.text(9.75, ay - 0.75, "time", ha="right", va="top",
        fontsize=8.5, color=cs.MUTED, family=cs.SANS, zorder=4)

# --- three snapshot panels on the time arrow ---
pw, ph = 2.55, 2.6
xs = [0.75, 3.85, 6.95]
for i, x in enumerate(xs, start=1):
    box(x, ay + 0.55, pw, ph, fc=cs.SUBTLE, ec=cs.GRID, lw=1.0)
    ax.text(x + pw/2, ay + 0.55 + ph * 0.66, f"write {i}", ha="center", va="center",
            fontsize=10.5, color=cs.BODY, family=cs.SANS, zorder=4)
    ax.text(x + pw/2, ay + 0.55 + ph * 0.30, f"-> snapshot s{i}", ha="center", va="center",
            fontsize=10, color=cs.ACCENT, family=cs.MONO, zorder=4)
    # tick where the panel sits on the time arrow
    ax.plot([x + pw/2, x + pw/2], [ay - 0.18, ay + 0.18], color=cs.MUTED, lw=1.2, zorder=2)

# --- accent callout: the time-travel query, in mono ---
ax.text(5.0, 3.0, "SELECT … FOR VERSION AS OF s1 | s2 | s3",
        ha="center", va="center", fontsize=11.5, color=cs.ACCENT,
        family=cs.MONO, fontweight="bold", zorder=4)

# --- greyed contrast line ---
ax.text(5.0, 1.0, "mutable index: prior state overwritten",
        ha="center", va="center", fontsize=9, color=cs.CONTEXT,
        family=cs.SANS, zorder=4)

cs.save(fig, "out/time-travel-snapshots.png")
print("rendered p12")

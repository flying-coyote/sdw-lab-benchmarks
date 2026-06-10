import chartstyle as cs
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# Diagram: five engines -> one OCSF Iceberg table -> one identical answer.
# Verified numbers: 1,000 rows / 125 RDP, 5 engines, 3 catalogs, 2 table formats.

fig, ax = cs.canvas(
    "Five engines, one table, one answer.",
    "DuckDB, Trino, ClickHouse, StarRocks and Dremio all return the identical 1,000 rows / 125 RDP\n"
    "from the same OCSF table — across 3 catalogs and 2 table formats.",
    source="security-data-that-works/docker · ./moar verify",
    tier="Tier B · single-host · reproducible",
    figsize=(8.8, 4.6), top=0.76, bottom=0.10)

ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis("off")

def box(x, y, w, h, fc=cs.SUBTLE, ec=cs.GRID, lw=1.0):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12,rounding_size=0.18",
                       facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3)
    ax.add_patch(p)
    return p

# --- five engine boxes, column on the left ---
engines = ["DuckDB", "Trino", "ClickHouse", "StarRocks", "Dremio"]
ew, eh = 2.0, 1.15
ex = 0.45
eys = [8.35, 6.55, 4.75, 2.95, 1.15]
for name, ey in zip(engines, eys):
    box(ex, ey, ew, eh)
    ax.text(ex + ew/2, ey + eh/2, name, ha="center", va="center",
            fontsize=11, color=cs.BODY, family=cs.SANS, zorder=4)

# --- central table box (accent-edged) ---
cw, ch = 2.45, 1.9
cx, cy = 4.15, 5.30 - ch/2
box(cx, cy, cw, ch, fc=cs.WHITE, ec=cs.ACCENT, lw=1.6)
ax.text(cx + cw/2, cy + ch/2, "one OCSF\nIceberg table", ha="center", va="center",
        fontsize=11.5, color=cs.INK, family=cs.SANS, fontweight="bold", zorder=4)
ax.text(cx + cw/2, cy - 0.55, "3 catalogs · 2 formats", ha="center", va="center",
        fontsize=8.5, color=cs.MUTED, family=cs.MONO, zorder=4)

# --- converging arrows: engines -> table ---
for ey in eys:
    ax.annotate("", xy=(cx - 0.18, 5.30 + 0.32 * (ey + eh/2 - 5.30) / 3.6),
                xytext=(ex + ew + 0.18, ey + eh/2),
                arrowprops=dict(arrowstyle="->", color=cs.MUTED, lw=1.1,
                                shrinkA=0, shrinkB=0), zorder=2)

# --- single arrow: table -> answer ---
ax.annotate("", xy=(7.10, 5.30), xytext=(cx + cw + 0.18, 5.30),
            arrowprops=dict(arrowstyle="->", color=cs.MUTED, lw=1.3,
                            shrinkA=0, shrinkB=0), zorder=2)

# --- answer box (accent fill) ---
aw, ah = 2.50, 1.9
axx, ayy = 7.28, 5.30 - ah/2
box(axx, ayy, aw, ah, fc=cs.ACCENT, ec=cs.ACCENT, lw=1.0)
ax.text(axx + aw/2, ayy + ah/2, "1,000 rows · 125 RDP", ha="center", va="center",
        fontsize=10, color=cs.WHITE, family=cs.MONO, fontweight="bold", zorder=4)
ax.text(axx + aw/2, ayy - 0.55, "identical, every engine", ha="center", va="center",
        fontsize=9, color=cs.MUTED, family=cs.SANS, zorder=4)

cs.save(fig, "out/five-engines-one-answer.png")
print("rendered p06")

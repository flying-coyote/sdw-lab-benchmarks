import chartstyle as cs
from matplotlib.patches import FancyBboxPatch

# Diagram: the open-stack layer diagram — four open/swappable layers,
# lock-in concentrated in the pipeline layer. Mechanism, not a measurement.

MONO_FB = [cs.MONO, "DejaVu Sans Mono"]   # fallback for ✓ ← → (not in brand fonts)

fig, ax = cs.canvas(
    "Open formats don't remove lock-in; they move it to the pipeline.",
    "Storage, table format, catalog and engine are open or swappable now — the remaining dependency\n"
    "is the transformation layer, and a raw copy in Iceberg is the escape hatch.",
    source="MOAR book ch04 §4.4 — pipeline lock-in",
    tier="illustrative · mechanism, not a measurement",
    figsize=(8.8, 4.6), top=0.76, bottom=0.10)

ax.set_xlim(0, 10)
ax.set_ylim(0, 8.3)
ax.axis("off")
ax.grid(False)

def box(x, y, w, h, fc=cs.SUBTLE, ec=cs.GRID, lw=1.0):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.10,rounding_size=0.16",
                       facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3)
    ax.add_patch(p)
    return p

# --- five layer bars, bottom to top ---
BX, BW, BH, GAP = 0.40, 4.20, 1.30, 0.27
layers = [  # (bar label, status tag, tag color, is_pipeline)
    ("Storage — object store (S3)",      "open ✓",                   cs.GOOD, False),
    ("Table format — Iceberg",           "open ✓",                   cs.GOOD, False),
    ("Catalog — REST",                   "open ✓",                   cs.GOOD, False),
    ("Engine — SQL",                     "swappable ✓",              cs.GOOD, False),
    ("Pipeline — transformation logic",  "← the lock-in lives here", cs.WARN, True),
]
for i, (label, tag, tagcolor, is_pipe) in enumerate(layers):
    y = 0.35 + i * (BH + GAP)
    cy = y + BH / 2
    if is_pipe:
        box(BX, y, BW, BH, fc=cs.SUBTLE, ec=cs.ACCENT, lw=1.8)
        ax.text(BX + 0.30, cy, label, ha="left", va="center", fontsize=10.5,
                color=cs.INK, family=cs.SANS, fontweight="bold", zorder=4)
    else:
        box(BX, y, BW, BH, fc=cs.SUBTLE, ec=cs.GRID)
        ax.text(BX + 0.30, cy, label, ha="left", va="center", fontsize=10.5,
                color=cs.BODY, family=cs.SANS, zorder=4)
    ax.text(BX + BW + 0.35, cy, tag, ha="left", va="center", fontsize=9.5,
            color=tagcolor, family=MONO_FB,
            fontweight="bold" if is_pipe else "normal", zorder=4)

# --- escape-hatch callout (mono), tucked under the pipeline row's warn tag ---
co_x, co_y, co_w, co_h = 6.35, 4.85, 3.50, 1.60
box(co_x, co_y, co_w, co_h, fc=cs.WHITE, ec=cs.GRID, lw=1.0)
ax.text(co_x + co_w / 2, co_y + co_h / 2,
        "escape hatch: split-write\nraw → Iceberg, replay\nthrough the next pipeline",
        ha="center", va="center", fontsize=8.2, color=cs.BODY,
        family=MONO_FB, zorder=4, linespacing=1.55)

cs.save(fig, "out/pipeline-lockin-stack.png")
print("rendered pb2")

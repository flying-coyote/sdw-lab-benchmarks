import chartstyle as cs
import matplotlib.pyplot as plt

# Source: security-data-that-works/docker · ./moar compare
# 200,000 OCSF events: 11.5 MB as an OpenSearch index vs 1.6 MB as
# columnar Parquet in the open lakehouse — query answers identical.

OPENSEARCH = 11.5
LAKEHOUSE = 1.6

fig, ax = cs.canvas(
    "Same data, same answers, about a seventh of the storage.",
    "200,000 OCSF events: 1.6 MB as columnar Parquet in the open lakehouse vs 11.5 MB as an\n"
    "OpenSearch index — query answers identical.",
    source="security-data-that-works/docker · ./moar compare",
    tier="Tier B · single-host · reproducible",
    figsize=(8.8, 3.6), top=0.72, bottom=0.20)
fig.subplots_adjust(left=0.245)  # room for the category labels

labels = ["OpenSearch index", "Open lakehouse (Parquet)"]
vals = [OPENSEARCH, LAKEHOUSE]
colors = [cs.CONTEXT, cs.ACCENT]
ypos = [1, 0]

ax.barh(ypos, vals, color=colors, height=0.58, zorder=3)
for y, v in zip(ypos, vals):
    ax.text(v + 0.18, y, f"{v} MB", ha="left", va="center",
            fontsize=13, fontweight="bold", color=cs.BODY)

# the gap, annotated once, plainly
ax.text(7.2, 0, "~7×", ha="left", va="center", fontsize=15,
        fontweight="bold", color=cs.ACCENT)
ax.text(7.2, -0.30, "smaller on disk", ha="left", va="center",
        fontsize=9.5, color=cs.MUTED)

ax.set_yticks(ypos)
ax.set_yticklabels(labels, fontsize=12)
ax.set_xlim(0, 13.2)
ax.set_xlabel("storage footprint (MB)")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.spines["left"].set_color(cs.GRID)
ax.grid(axis="x", color=cs.GRID)
ax.grid(axis="y", visible=False)
ax.tick_params(axis="both", length=0)

cs.direction_note(fig, "storage: lower is better")

cs.save(fig, "out/storage-footprint-7x.png")
print("rendered p10")

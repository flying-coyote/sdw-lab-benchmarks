"""
needle-where-the-index-wins.png — the OTHER regime (the index's home turf), measured honestly.

Pairs with benchmark-8-engine.png (columnar wins scan-heavy aggregation). This one shows the
point-lookup regime where the inverted index wins — and the honest finding that a lakehouse
store SORTED on the looked-up column ties it, so the lakehouse's point-lookup weakness is a
layout choice, not a fundamental limit.

Data: zeek-flagship-rerun needle arm (NEEDLE-FINDINGS-2026-06-14.md), random high-cardinality
point lookup `uid = <one row>` that defeats Parquet min/max pruning. 1 warmup + 7 trials,
answer-equality verified, OpenSearch 3.7 foil. Tier B, single host.
BM25 fuzzy full-text (the index's other home-turf half) is NOT yet measured (no rich text field
in the Zeek conn corpus) — named in the subtitle as future work so the chart doesn't overclaim.
"""
import chartstyle as cs
import matplotlib.pyplot as plt

# (label, latency ms, color) — lower is faster
ARMS = [
    ("ClickHouse · Iceberg (unsorted)",      145.0, cs.WARN),     # the avoidable slow case
    ("OpenSearch · inverted index",            3.5, cs.CONTEXT),  # the index reference
    ("ClickHouse · native (sorted on uid)",    3.5, cs.ACCENT),   # the lakehouse that ties the index
]

fig, ax = cs.canvas(
    "On point lookups, sort the lakehouse and it matches the index",
    sub=("A random high-cardinality point lookup (uid) that defeats Parquet min/max pruning — the index's "
         "home turf. The inverted index beats an UNSORTED lakehouse table 41×, but a lakehouse store SORTED "
         "on the looked-up column ties it (3.5 ms each). The weakness is a layout choice, not a limit. "
         "(BM25 full-text — the index's other home turf — not yet measured.)"),
    source="sdw-lab zeek-flagship-rerun needle arm · 2026-06-14 · OpenSearch 3.7 foil · answer-equality verified",
    tier="Tier B · single host · reproducible",
    figsize=(9.4, 4.6), bottom=0.20, top=0.72,
)

labels = [a[0] for a in ARMS]
lat    = [a[1] for a in ARMS]
colors = [a[2] for a in ARMS]
y = list(range(len(ARMS)))

ax.barh(y, lat, color=colors, height=0.60, zorder=3)
ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=10.5)
ax.set_xlim(0, 165)
ax.set_xlabel("point-lookup latency, ms  (lower is faster)")
ax.spines["left"].set_visible(False)
ax.tick_params(axis="y", length=0)

for yi, v in enumerate(lat):
    note = "  ← 41× slower than the index" if v > 100 else "  ← ties the index" if (yi == 2) else ""
    ax.text(v + 2.5, yi, f"{v:.1f} ms{note}", va="center", ha="left", fontsize=10, color=cs.BODY, zorder=4)

cs.direction_note(fig, "Lower is faster")
cs.save(fig, "out/needle-where-the-index-wins.png")
print("wrote out/needle-where-the-index-wins.png")

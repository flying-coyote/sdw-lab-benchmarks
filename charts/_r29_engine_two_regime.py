"""
benchmark-8-engine.png — the engine two-regime chart (replaces the stale 145×/Splunk table).

Data: zeek-flagship-rerun, draw-1 (canonical published draw), triple-validated 2026-06-14.
Average of per-query medians across the 5 standardized scan/aggregate queries, vs the
OpenSearch schema-on-read foil (best_compression, 1 segment). Dremio = Reflections OFF
(the honest apples-to-apples baseline), 2-draw validated (draw-3 hit a Dremio-26 auth race).

This is the SCAN-HEAVY AGGREGATION regime (the hunting workload). On point-lookups the
inverted index wins — that is the other half of the two-regime split (NEEDLE-FINDINGS),
which the subtitle names so the chart does not overclaim "columnar always wins".

Kept filename `benchmark-8-engine.png` so the deck + campaign references don't break, even
though the honest current foil-comparison suite is 4 arms (StarRocks/Trino were a separate
join workload, never re-measured against this foil — including them would mix foils).
"""
import chartstyle as cs
import matplotlib.pyplot as plt

# (label, avg-of-medians seconds, x faster than foil, bar color)
ARMS = [
    ("Schema-on-read SIEM\ninverted index",        2.854, 1.0,  cs.CONTEXT),  # baseline
    ("Dremio\nIceberg · Reflections off",          0.787, 3.6,  cs.ACCENT2),  # open format
    ("ClickHouse\nIceberg · zstd Parquet",         0.282, 10.1, cs.ACCENT),   # open-format hero
    ("ClickHouse\nnative MergeTree",               0.061, 46.8, cs.TEAL600),  # proprietary ceiling
]

fig, ax = cs.canvas(
    "Columnar engines win the hunting workload on open Iceberg",
    sub=("Average of 5 scan/aggregate queries vs a schema-on-read inverted-index foil (10M-event Zeek). "
         "The open Iceberg arms clear the foil 3.6–10.1×; the ~4.6× gap to native is the open-format tax. "
         "On point-lookups the index wins — the other regime."),
    source="sdw-lab zeek-flagship-rerun · triple-validated 2026-06-14 · OpenSearch 3.7 foil (best_compression, 1 seg)",
    tier="Tier B · single host · reproducible",
    figsize=(9.4, 5.0), bottom=0.21, top=0.74,
)

labels = [a[0] for a in ARMS]
speed  = [a[2] for a in ARMS]
lat    = [a[1] for a in ARMS]
colors = [a[3] for a in ARMS]
y = list(range(len(ARMS)))

ax.barh(y, speed, color=colors, height=0.62, zorder=3)
ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=10.5)
ax.set_xlim(0, 60)
ax.set_xlabel("× faster than the schema-on-read foil  (scan-heavy aggregation)")
ax.spines["left"].set_visible(False)
ax.tick_params(axis="y", length=0)

for yi, (v, s) in enumerate(zip(speed, lat)):
    tag = "1× baseline" if v == 1.0 else f"{v:.1f}×"
    ax.text(v + 0.7, yi, f"{tag}   ·   {s:.2f} s avg", va="center", ha="left",
            fontsize=10, color=cs.BODY, zorder=4)

cs.direction_note(fig, "Higher is faster")
cs.save(fig, "out/benchmark-8-engine.png")
print("wrote out/benchmark-8-engine.png")

"""Build #3 — workload-engine-grid (MOAR book ch03 §3.3).

One grid replacing the five per-workload capability matrices. Every rated cell
is traceable to ch03 §3.3: the worked threat-hunting Capability Assessment
Matrix (lines 249-255) plus the per-workload decision-implication prose
(real-time line 226, threat hunting line 257, forensic line 271, compliance
line 287, pipeline lines 299-301). Cells §3.3 does not rate are shown as
"not assessed" — nothing is invented. The compliance ✓s apply §3.3's
"you need a lakehouse with tiered queryability" to the three Iceberg columns.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import chartstyle as cs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

OUT = os.path.join(_HERE, "out")
NAME = "workload-engine-grid"
SANS_FB = [cs.SANS, "DejaVu Sans"]

PLATFORMS = ["Trino +\nIceberg", "Dremio +\nIceberg", "Splunk",
             "PostgreSQL", "AWS Athena\n+ Iceberg"]

# verdict codes: Y = meets, P = partial/conditional, N = disqualified when
# the workload is Tier 1, U = not assessed in ch03 §3.3
ROWS = [
    ("Real-time detection",
     "streaming ingest · windowed aggregation ·\nstateful processing · low-latency alerting",
     [("U", "not assessed\nin §3.3"),
      ("P", "needs Flink / Spark\nStreaming supplement"),
      ("Y", "the retained real-time\npath (“Splunk for alerts”)"),
      ("U", "not assessed\nin §3.3"),
      ("N", "batch querying —\ndisqualified if Tier 1")]),
    ("Threat hunting",
     "columnar storage · partition pruning ·\npredicate pushdown · distributed MPP",
     [("Y", "all four capabilities\n(worked matrix)"),
      ("Y", "all four capabilities\n(worked matrix)"),
      ("P", "tsidx not columnar;\nlimited pushdown"),
      ("N", "no columnar, no MPP —\n20-45 min queries"),
      ("Y", "all four capabilities\n(worked matrix)")]),
    ("Forensic deep-dive",
     "indexed point queries · row retrieval ·\ntime-travel · hot-tier optimization",
     None),  # merged band — §3.3 rates the requirement, not these five engines
    ("Compliance retention",
     "tiered lifecycle · cold-tier queryability ·\nimmutable format · compression",
     [("Y", "Iceberg lakehouse —\ntiered queryability"),
      ("Y", "Iceberg lakehouse —\ntiered queryability"),
      ("N", "“archive to offline” —\ndisqualified for 7-yr queryable"),
      ("U", "not assessed\nin §3.3"),
      ("Y", "Iceberg lakehouse —\ntiered queryability")]),
    ("Pipeline & data routing",
     "route-by-value · multi-destination ·\nreal-time transform · OCSF",
     None),  # merged band — lives in the pipeline layer (§3.4)
]

BAND_TEXT = {
    "Forensic deep-dive":
        "§3.3 rates this at requirement level, not per engine: you need indexed retrieval AND time-travel "
        "(rules out Elasticsearch unless a custom\nsnapshot workflow is acceptable); sub-second hot-tier queries "
        "need SSD/NVMe or S3 Standard. Rate your candidates with Worksheet A.3.",
    "Pipeline & data routing":
        "Lives in the pipeline layer, not these engines: if route-by-value is Tier 1, Logstash/Fluentd basic "
        "filtering is insufficient — you need Cribl or\nTenzir; if OCSF portability is Tier 2, OCSF transforms "
        "keep the logic portable across pipeline vendors. Full lock-in analysis: §3.4.",
}


def build(gray=False):
    if gray:
        FILL = {"Y": "#e2e2e2", "P": "#cfcfcf", "N": "#aaaaaa", "U": "#f2f2f2"}
        MARK = {"Y": "#1f1f1f", "P": "#1f1f1f", "N": "#000000", "U": "#8a8a8a"}
        BAND = "#f2f2f2"
        HEADC = "#3a3a3a"
    else:
        FILL = {"Y": "#e9f1e4", "P": "#f8ecdf", "N": "#f5e2e2", "U": cs.SUBTLE}
        MARK = {"Y": cs.GOOD, "P": cs.WARN, "N": cs.BAD, "U": cs.MUTED}
        BAND = cs.SUBTLE
        HEADC = cs.ACCENT
    GLYPH = {"Y": "✓", "P": "⚠", "N": "✗", "U": "—"}

    fig, ax = cs.canvas(
        "Every Tier 1 workload disqualifies someone: real-time rules out Athena,\n"
        "hunting rules out PostgreSQL, 7-year queryable retention rules out Splunk.",
        source="MOAR book ch03 §3.3 — worked threat-hunting matrix + per-workload decision implications",
        tier="framework assessment · capabilities as characterized in ch03, not a benchmark",
        figsize=(11.4, 6.6), top=0.845, bottom=0.075)

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.grid(False)

    LEFT = 2.55                       # workload-label column width
    col_w = (10 - LEFT) / len(PLATFORMS)
    top_y = 9.05
    row_h = (top_y - 0.85) / len(ROWS)

    # column headers
    for j, p in enumerate(PLATFORMS):
        ax.text(LEFT + (j + 0.5) * col_w, top_y + 0.42, p, ha="center",
                va="center", fontsize=9.5, color=HEADC, family=SANS_FB,
                fontweight="bold", linespacing=1.25)

    for i, (wl, caps, cells) in enumerate(ROWS):
        y1 = top_y - i * row_h
        y0 = y1 - row_h * 0.92
        cy = (y0 + y1) / 2
        # workload label + required capabilities
        ax.text(0.02, cy + 0.22, f"{i + 1} · {wl}", ha="left", va="center",
                fontsize=9.8, color=cs.INK, family=SANS_FB, fontweight="bold")
        ax.text(0.02, cy - 0.42, caps, ha="left", va="center", fontsize=7.0,
                color=cs.MUTED, family=SANS_FB, linespacing=1.35)
        if cells is None:
            # merged band across all five platform columns
            ax.add_patch(FancyBboxPatch(
                (LEFT + 0.04, y0), 10 - LEFT - 0.12, y1 - y0,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor=BAND, edgecolor=cs.GRID, linewidth=0.9, zorder=2))
            ax.text(LEFT + (10 - LEFT) / 2, cy, BAND_TEXT[wl], ha="center",
                    va="center", fontsize=7.4, color=cs.BODY, family=SANS_FB,
                    linespacing=1.5, zorder=3, style="italic")
            continue
        for j, (code, why) in enumerate(cells):
            x0 = LEFT + j * col_w + 0.05
            ax.add_patch(FancyBboxPatch(
                (x0, y0), col_w - 0.12, y1 - y0,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor=FILL[code], edgecolor=cs.GRID, linewidth=0.9, zorder=2))
            cxx = x0 + (col_w - 0.12) / 2
            ax.text(cxx, cy + 0.30, GLYPH[code], ha="center", va="center",
                    fontsize=13, color=MARK[code], family=SANS_FB,
                    fontweight="bold", zorder=3)
            ax.text(cxx, cy - 0.33, why, ha="center", va="center", fontsize=6.6,
                    color=cs.BODY, family=SANS_FB, linespacing=1.35, zorder=3)

    # legend
    ax.text(0.02, 0.22,
            "✓ meets (per ch03 §3.3)   ·   ⚠ conditional / partial   ·   "
            "✗ disqualified when the workload is Tier 1   ·   "
            "— not assessed in §3.3 (fill in Worksheet A.3)",
            ha="left", va="center", fontsize=8.2, color=cs.MUTED, family=SANS_FB)

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

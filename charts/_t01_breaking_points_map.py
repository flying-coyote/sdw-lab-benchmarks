"""Transition build #1 — the breaking-points map (program §7, task #30).

One 2D map: x = hot data scale (measured marks), y = concurrent demand.
Three architecture regions, edges as boundary bands carrying a shape glyph
(slope = graceful/warning, step = cliff/no warning), the one-line signal,
and a one-host coordinate anchor. The join cliff is drawn as a hazard
INSIDE the OLAP region (cliffs are layout decisions, not scale thresholds);
retention/ingest ride as right-rail chips; the schema-on-read SIEM is drawn
as the reader's likely origin, not a destination.

Every coordinate is from the transition-point program's measured atlas
(project1 transition-point-program-2026-06-10.md §2–§3, each number
spot-checked against its source RESULTS file):
- 10M: index hunt-shape crosses 10 s (port_scan 13.07 s vs 0.93 s Iceberg, 62×)
  while index-shaped lookups stay ms — zeek-flagship-rerun/results/RESULTS.md
- 100M: per-workload winner crossover on the 4-engine matrix; Trino
  high-cardinality distinct hard-error (988.80 MB per-node default ceiling);
  chDB 4.1.8 silent undercount (49 rows short, no error, chdb-io/chdb#587)
  — H-ARCH-02-evidence.md, clickhouse-vs-duckdb CORRECTNESS-DIVERGENCE.md
- 1B (DuckDB over Iceberg/DuckLake): filtered scan 407–445 ms; subnet_rollup
  19.4–21.4 s; topn_src 79–91 s (graceful crossing, engine spills + finishes)
  — ocsf-read-scan/results/LARGE-SCAN.md
- C1–C16 at 10M scan-aggregate: no arm crosses 10 s; DuckDB p95 57→689 ms
  graceful-linear — H-ARCH-02-evidence.md
- ch_native q5: stats-less layout + 6-table join → DNF >300 s; same engine
  over Iceberg 1.35 s — engine-join-specialization/results/RESULTS.md
- Retention: no knee — 14.8× compounded gap (4.2× bytes × 3.5× $/byte),
  ~$95K/mo per TB/day at 7 yr — cost-to-serve-retention/results/RESULTS.md
- Ingest: Iceberg ~133 ms/commit floor (~7.5 commits/s); DuckLake 3.9× at
  5-row commits — ocsf-streaming-cadence/results/RESULTS.md
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import chartstyle as cs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

OUT = os.path.join(_HERE, "out")
SANS_FB = [cs.SANS, "DejaVu Sans"]


def _slope_glyph(ax, x, y, color, scale=1.0):
    """Graceful edge: a rising-tail glyph (the curve gives warning)."""
    xs = np.array([0, 0.35, 0.7, 1.0]) * 0.055 * scale
    ys = np.array([0, 0.08, 0.35, 1.0]) * 1.6 * scale
    ax.plot(10 ** (np.log10(x) + xs * 4), y + ys, color=color, lw=2.2,
            solid_capstyle="round", zorder=6, clip_on=False)


def _step_glyph(ax, x, y, color, scale=1.0):
    """Cliff edge: a step glyph (no warning curve)."""
    dx = 0.10 * scale
    ax.plot([x, 10 ** (np.log10(x) + dx)], [y, y], color=color, lw=2.2, zorder=6)
    ax.plot([10 ** (np.log10(x) + dx)] * 2, [y, y + 2.4 * scale], color=color,
            lw=2.2, zorder=6)


def build_map():
    fig, ax = cs.canvas(
        "Architectures fail at an edge, not at a row count",
        "Every measured edge except the cliffs gives warning — the signal to watch is on each edge. "
        "One host; what travels is ordering and shape.",
        source="transition-point program 2026-06-10 · sdw-lab-benchmarks: zeek-flagship-rerun, H-ARCH-02, "
               "ocsf-read-scan, engine-join-specialization, cost-to-serve-retention, ocsf-streaming-cadence",
        figsize=(12.5, 6.6), top=0.85, bottom=0.12,
    )
    fig.subplots_adjust(left=0.065, right=0.775)

    ax.set_xscale("log")
    ax.set_xlim(8e5, 4e9)
    ax.set_ylim(0, 21)
    ax.set_xticks([1e6, 1e7, 1e8, 1e9])
    ax.set_xticklabels(["1M", "10M", "100M", "1B"], family=SANS_FB)
    ax.set_yticks([1, 4, 8, 16])
    ax.set_yticklabels(["C1", "C4", "C8", "C16"], family=SANS_FB)
    ax.set_xlabel("hot data scale (events, log)", family=SANS_FB)
    ax.set_ylabel("concurrent demand (clients)", family=SANS_FB)
    ax.grid(True, which="major", alpha=0.55)

    # ---- regions -----------------------------------------------------------
    ax.axvspan(8e5, 1e8, color=cs.SUBTLE, zorder=0)
    ax.text(3.5e6, 20.5, "EMBEDDED SINGLE-NODE", fontsize=8.5, family=cs.MONO,
            color=cs.MUTED, ha="center", va="top", fontweight="bold")
    ax.text(3.5e6, 19.4, "DuckDB-class · wins most shapes below the crossover",
            fontsize=8, color=cs.MUTED, ha="center", va="top", family=SANS_FB)

    # Edge 1 — the single-node ceiling band, shape-dependent 100M -> 1B
    ax.axvspan(1e8, 1e9, color=cs.ACCENT2, alpha=0.16, zorder=0)
    ax.text(2.9e8, 20.5, "EDGE — SINGLE-NODE CEILING", fontsize=8.5, family=cs.MONO,
            color=cs.ACCENT, ha="center", va="top", fontweight="bold")
    ax.text(2.9e8, 19.4, "shape-dependent, 100M→1B", fontsize=8, color=cs.BODY,
            ha="center", va="top", family=SANS_FB)
    _slope_glyph(ax, 1.6e8, 12.2, cs.ACCENT)
    ax.text(3.4e8, 11.8, "graceful — the tail\ngrows first (quarters)", fontsize=8,
            color=cs.ACCENT, ha="center", va="top", family=SANS_FB, style="italic")

    ax.text(1.8e9, 20.5, "SINGLE-HOST OLAP", fontsize=8.5, family=cs.MONO,
            color=cs.MUTED, ha="center", va="top", fontweight="bold")
    ax.text(1.8e9, 19.4, "ClickHouse · StarRocks\nTrino · Dremio", fontsize=8,
            color=cs.MUTED, ha="center", va="top", family=SANS_FB)

    # Distributed lane — honestly unmeasured (dashed right edge)
    ax.axvline(3.4e9, color=cs.MUTED, lw=1.4, ls=(0, (4, 4)), zorder=2)
    ax.text(3.05e9, 13.0, "distributed cluster —\nzero lab data by design;\nthe map ends honestly",
            fontsize=8, color=cs.MUTED, ha="right", va="center", style="italic", family=SANS_FB)

    # Edge 2 — concurrency knee (top band): beyond C16 at this per-query weight
    ax.axhspan(16, 21, color=cs.ACCENT2, alpha=0.10, zorder=0)
    ax.plot([8e5, 4e9], [16, 16], color=cs.ACCENT2, lw=1.2, ls=(0, (5, 3)))
    _slope_glyph(ax, 1.15e6, 16.3, cs.ACCENT, scale=0.7)
    ax.text(2.6e6, 17.9, "EDGE — concurrency knee: beyond C16 at this per-query weight\n"
                         "(DuckDB p95 57→689 ms with throughput flat — no arm crosses 10 s in range)",
            fontsize=8, color=cs.BODY, ha="left", va="top", family=SANS_FB)

    # ---- measured marks ----------------------------------------------------
    ax.plot(1e7, 1.0, marker="o", ms=11, mfc="white", mec=cs.BAD, mew=2.2, zorder=7)
    ax.annotate("your likely origin:\nschema-on-read index —\nhunt-shaped aggregation crosses\n"
                "10 s at 10M (13.07 s, 62× vs\nIceberg); lookups stay ms",
                (1e7, 1.0), xytext=(1.15e6, 4.2), fontsize=8, color=cs.BAD,
                family=SANS_FB, ha="left", va="bottom",
                arrowprops=dict(arrowstyle="-", color=cs.BAD, lw=0.9, alpha=0.7))

    ax.plot(1e8, 2.6, marker="o", ms=7, color=cs.ACCENT, zorder=7)
    ax.annotate("100M crossover: per-workload winner flips to the\nservers; Trino distinct hard-errors (config ceiling)",
                (1e8, 2.6), xytext=(1.5e8, 0.6), fontsize=8, color=cs.BODY,
                family=SANS_FB, ha="left", va="bottom",
                arrowprops=dict(arrowstyle="-", color=cs.MUTED, lw=0.8, alpha=0.7))

    ax.plot(1e9, 1.0, marker="o", ms=7, color=cs.ACCENT, zorder=7)
    ax.annotate("1B DuckDB: filtered scan 407–445 ms · top-N 79–91 s\n(spills and finishes — graceful)",
                (1e9, 1.0), xytext=(8e8, 3.6), fontsize=8, color=cs.BODY,
                family=SANS_FB, ha="center", va="bottom",
                arrowprops=dict(arrowstyle="-", color=cs.MUTED, lw=0.8, alpha=0.7))

    # ---- hazards inside regions (cliffs are layout decisions) --------------
    ax.plot(4e7, 10.6, marker="X", ms=12, color=cs.BAD, zorder=8)
    _step_glyph(ax, 5.3e7, 10.0, cs.BAD, scale=0.9)
    ax.text(3.2e7, 11.6, "CLIFF — a layout decision, not a scale threshold:\n"
                         "stats-less native layout + 6-table join → DNF >300 s;\n"
                         "the same engine over Iceberg answers in 1.35 s. No warning.",
            fontsize=8, color=cs.BAD, ha="center", va="bottom", family=SANS_FB)

    ax.plot(1.1e8, 7.4, marker="X", ms=9, color=cs.WARN, zorder=8)
    ax.text(1.35e8, 8.6, "SILENT-WRONG — chDB 4.1.8 returns a count\n"
                         "49 rows short at 100M, no error raised;\n"
                         "only an answer-equality gate sees it",
            fontsize=8, color=cs.WARN, ha="left", va="top", family=SANS_FB)

    # ---- right-rail chips (retention / ingest are budget-line edges) -------
    chips = [
        ("RETENTION", "no knee in the curve — the edge is\n"
                      "where the linear gap crosses your\n"
                      "budget: index-on-gp3 vs warm-Iceberg-\n"
                      "on-S3 is 14.8× compounded\n"
                      "(~$95K/mo per TB/day at 7 yr)"),
        ("INGEST", "commit-path floor, not a curve:\n"
                   "Iceberg ~133 ms fixed per-commit\n"
                   "(~7.5 commits/s); DuckLake inlines\n"
                   "3.9× more at 5-row commits. Lag vs\n"
                   "detection SLO: unmeasured (§6 next)"),
        ("ONE-HOST ANCHOR", "all coordinates: Beelink 5800H,\n"
                            "WSL2 48 GB/14t, Tier B.\n"
                            "What travels is ordering and\n"
                            "shape — locate yourself with\n"
                            "your own numbers"),
    ]
    y0 = 0.78
    for title, body in chips:
        col = cs.ACCENT if title != "ONE-HOST ANCHOR" else cs.MUTED
        fig.text(0.793, y0, title, fontsize=9, family=cs.MONO, color=col,
                 fontweight="bold", ha="left", va="top")
        fig.text(0.793, y0 - 0.038, body, fontsize=8, color=cs.BODY,
                 ha="left", va="top", family=SANS_FB, linespacing=1.45)
        y0 -= 0.245

    return fig


def build_ribbon():
    """1D degradation ribbon for deck slide 16 + the campaign feed crop."""
    _s = cs.FEED_SCALE if cs.FEED_SCALE > 0 else 1.0
    fig, ax = cs.canvas(
        "Where it breaks — the measured edges, in order",
        "Slope glyph = graceful (the tail warns you, quarters ahead) · step glyph = cliff (no warning). One host, Tier B.",
        source="transition-point program 2026-06-10 · sdw-lab-benchmarks (six suites; every coordinate source-cited)",
        figsize=(11.2, 3.4), top=0.76, bottom=0.30,
    )
    fig.subplots_adjust(left=0.045, right=0.975)
    ax.set_xscale("log")
    ax.set_xlim(8e5, 9e9)
    ax.set_ylim(0, 10)
    ax.set_yticks([])
    ax.set_xticks([1e6, 1e7, 1e8, 1e9])
    ax.set_xticklabels(["1M", "10M", "100M", "1B"], family=SANS_FB)
    ax.set_xlabel("hot data scale (events, log) — concurrency, retention, and ingest edges ride the rail below",
                  family=SANS_FB, fontsize=10 * _s)
    ax.grid(False)
    for s in ("left", "top", "right"):
        ax.spines[s].set_visible(False)

    # the rail
    ax.plot([8e5, 9e9], [5, 5], color=cs.GRID, lw=5, solid_capstyle="round", zorder=1)

    events = [
        (1e7, "10M — index hunt-edge", "hunting-shaped aggregation crosses 10 s\n(13.07 s vs 0.93 s Iceberg, 62×);\nlookup-shaped work stays ms", cs.BAD, "slope"),
        (1e8, "100M — crossover + hazards", "per-workload winner flips to the servers;\nTrino distinct hard-errors (config ceiling);\nchDB counts 49 rows short, silently", cs.ACCENT, "slope"),
        (1e9, "1B — single-node ceiling", "DuckDB top-N 79–91 s (graceful);\nfilters still 407–445 ms —\nshape-dependent edge", cs.ACCENT, "slope"),
        (6.5e9, "beyond — unmeasured", "zero lab data by design;\nthe ribbon ends honestly", cs.MUTED, None),
    ]
    for x, head, body, col, glyph in events:
        ax.plot([x, x], [4.0, 6.0], color=col, lw=2.4, zorder=3)
        ax.plot(x, 5, marker="o", ms=8, mfc="white", mec=col, mew=2.0, zorder=4)
        ax.text(x, 7.0, head, fontsize=9.5 * _s, fontweight="bold", color=col,
                ha="center", va="bottom", family=SANS_FB)
        ax.text(x, 3.4, body, fontsize=7.8 * _s, color=cs.BODY, ha="center", va="top",
                family=SANS_FB, linespacing=1.3)
        if glyph == "slope":
            _slope_glyph(ax, x * 1.12, 5.4, col, scale=0.55)

    # the cliff caveat box (layout, not scale — it can ambush anywhere on the rail)
    ax.text(1.65e6, 9.6, "and one CLIFF that is a layout decision, not a scale threshold: "
            "stats-less layout + 6-table join → DNF; same engine over Iceberg, 1.35 s",
            fontsize=8 * _s, color=cs.BAD, ha="left", va="top", family=SANS_FB, style="italic")

    return fig


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    from PIL import Image

    for name, builder in [("breaking-points-map", build_map),
                          ("breaking-points-ribbon", build_ribbon)]:
        fig = builder()
        web = os.path.join(OUT, f"{name}.png")
        web = cs.save(fig, web)
        print("wrote", web)
        fig = builder()
        prn = os.path.join(OUT, f"{name}-print.png")
        if cs.FEED_SCALE > 0:
            prn = os.path.join(OUT, "feed", f"{name}-print.png")
        fig.savefig(prn, dpi=300, bbox_inches="tight", pad_inches=0.12)
        plt.close(fig)
        Image.open(prn).convert("L").save(prn)
        print("wrote", prn)

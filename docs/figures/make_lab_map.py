#!/usr/bin/env python3
"""Draw docs/figures/lab-map.svg: the lab's bench folders in five clusters, the shared
planted-chain testbed and the benches built on it, and one highlight for the folders
that hold no scored result yet.

Standard library only. Cluster and status come from each folder's bench.yaml when it
has one; until then they come from the fallback tables below, which record the
2026-11-17 audit's unit split and the statuses the folders' own docs gave on that date.
Re-run after the bench.yaml files change, then render the PNG with sharp:

    python3 docs/figures/make_lab_map.py
    node -e 'require("<path>/sharp")("docs/figures/lab-map.svg",{density:144}).resize(1800).flatten({background:"#ffffff"}).png().toFile("docs/figures/lab-map.png")'

Palette: SDW Diagram standard (Harbor Haze), with the azure feed focal highlight
as the single highlight. Output is deterministic.
"""

from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "lab-map.svg"

# Same headings as scripts/bench_index.py CLUSTERS, so the map and the index read alike.
CLUSTERS = [
    ("detection", "Detection and the planted-chain testbed"),
    ("mapping-and-models", "Mapping, schema fidelity and model arms"),
    ("formats-and-lakehouse", "Formats, readers and lakehouse read/write paths"),
    ("catalogs-engines-cost", "Catalogs, engines, routing and cost"),
    ("ai-security", "AI security"),
]
LABEL_CHARS = 24  # wrap width for the cluster headings, in characters

# Fallback cluster per folder (the 2026-11-17 audit's unit split), used only where bench.yaml is absent.
FALLBACK_CLUSTER = {}
for c, names in {
    "detection": "ocsf-semantic-testbed bench-a-context-collapse ocsf-context-collapse-apt29 ocsf-sigma-detection ocsf-attack-coverage sigma-portability flattening-fidelity ocsf-data-health security-context-graph ocsf-marimo-hunt ocsf-fsi-compliance soc-query-shapes text-search-regex edr-two-regime",
    "mapping-and-models": "ontology-vs-schema-gate ocsf-mapping-fidelity ocsf-mapping-oracle ocsf-deterministic-mapper ocsf-1.9-rescore pipeline-normalization-fidelity spec-vs-emitted-integrity d3fend-ocsf-ai-alignment atlas-ocsf-observables m1-r1-blind-regrade ai-analyst-preregs ocsf-semantic-query ocsf-nl2sql-silenterror ocsf-airgap-agent sdpp-ingest-throughput stream-complexity",
    "formats-and-lakehouse": "clickhouse-vs-duckdb parquet-checksum-integrity parquet-determinism-encryption parquet-library-matrix ocsf-parquet-determinism ocsf-pruning-correctness ocsf-zorder-pruning ocsf-zstd-dictionary ocsf-vortex-format ocsf-nested-type-fidelity ocsf-temporal-null-coercion ocsf-arrow-transport ocsf-iceberg-metadata iceberg-compaction ocsf-read-scan ocsf-write-contract ocsf-write-inlining ocsf-storage-endurance",
    "catalogs-engines-cost": "ocsf-catalog-contention ocsf-format-planning ocsf-streaming-cadence ducklake-catalog-failuremodes polaris-catalog-dryrun ocsf-rls-overhead cost-to-serve-retention bench-d-tiered-realization concurrency-multiuser engine-join-specialization deterministic-routing-sim deterministic-routing-noncircular duckdb-edge-floor mv-rewrite-freshness ocsf-mv-acceleration workload-interference zeek-flagship-rerun",
    "ai-security": "t1-shadow-ai-discovery t2-platform-telemetry t3-guardrail-adaptive t4-interdiction t5-model-artifact-scanning t6-finetune-memorization t7-idp-delegation-logging t8a-mcp-before-after t8b-telemetry-injection t8c-trifecta-detection t9-pretooluse-hook-enforcement agent-telemetry-retention agent-toolcall-schemas ai-artifact-sbom delegation-chain-query mcp-manifest-drift",
}.items():
    for n in names.split():
        FALLBACK_CLUSTER[n] = c

# Fallback status, only for folders whose own docs on 2026-11-17 said they hold no scored result.
FALLBACK_STATUS = {
    "ocsf-semantic-testbed": "foundation",
    "ontology-vs-schema-gate": "frozen-design",
    "ocsf-fsi-compliance": "scaffold",
}
NOT_SCORED = {"scaffold", "spec", "foundation", "frozen-design"}

TESTBED = "ocsf-semantic-testbed"
# Folders whose code reads the testbed corpus (grep of their .py files, 2026-11-17).
DEPENDANTS = ["bench-a-context-collapse", "ocsf-attack-coverage", "ocsf-marimo-hunt",
              "ocsf-sigma-detection", "ocsf-nl2sql-silenterror", "ocsf-semantic-query"]

SKIP = {"lib", "charts", "scripts", "workloads", "docs"}

# Harbor Haze
NAVY, SLATE, DEEP, TINT, RULE, MUTED, BG = "#2c4f74", "#5c8dc5", "#36608f", "#eef3f9", "#e2e6ea", "#5b6878", "#f4f6f8"
FOCAL, FOCAL_EDGE = "#1f8fe0", "#0f5f9e"
FONT = "'DM Sans Variable','DM Sans',Helvetica,Arial,sans-serif"

W = 1800
MX, GAP = 40, 18
TOP = 190
COL_W = (W - 2 * MX - 4 * GAP) / 5
CHIP_H, CHIP_GAP = 38, 6


def read_yaml(path):
    d = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and ":" in line:
            k, _, v = line.partition(":")
            d[k.strip()] = v.strip()
    return d


def folders():
    out = []
    for p in sorted(ROOT.iterdir()):
        if not p.is_dir() or p.name.startswith((".", "_")) or p.name in SKIP:
            continue
        y = p / "bench.yaml"
        d = read_yaml(y) if y.is_file() else {}
        cluster = d.get("cluster") or FALLBACK_CLUSTER.get(p.name)
        status = d.get("status") or FALLBACK_STATUS.get(p.name, "")
        out.append((p.name, cluster, status))
    return out


def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + [cur]


def main():
    rows = folders()
    by = {k: [] for k, _ in CLUSTERS}
    for name, cluster, status in rows:
        by.setdefault(cluster or "unassigned", []).append((name, status))
    # testbed first in its column, its dependants next, then the rest alphabetically
    def order(item):
        n = item[0]
        return (0 if n == TESTBED else 1 if n in DEPENDANTS else 2, n)
    for k in by:
        by[k].sort(key=order)
    n_total = len(rows)
    n_hi = sum(1 for _, _, s in rows if s in NOT_SCORED)
    labels = {k: wrap(f"{lbl} ({len(by.get(k, []))})", LABEL_CHARS) for k, lbl in CLUSTERS}
    head_h = 30 + 28 * max(len(v) for v in labels.values())
    tallest = max(len(by.get(k, [])) for k, _ in CLUSTERS)
    H = TOP + head_h + tallest * (CHIP_H + CHIP_GAP) + 10 + 70

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="lm-title lm-desc">',
           f'<title id="lm-title">{n_total} lab folders in five clusters; {n_hi} hold no scored result yet</title>',
           f'<desc id="lm-desc">Each column is one cluster of bench folders. The shared planted-chain testbed is connected to the {len(DEPENDANTS)} benches whose code reads its corpus. Folders highlighted in blue have a status of foundation, scaffold, spec or frozen design, so they hold no scored result to cite.</desc>',
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
           f'<text x="{MX}" y="78" font-family="{FONT}" font-size="46" font-weight="700" fill="{NAVY}">{n_total} lab folders, five clusters: the {n_hi} in blue hold no scored result yet</text>',
           f'<text x="{MX}" y="128" font-family="{FONT}" font-size="26" fill="{MUTED}">Lines join the shared planted-chain testbed to the {len(DEPENDANTS)} benches built on its corpus.</text>']
    pos = {}
    for i, (key, label) in enumerate(CLUSTERS):
        x = MX + i * (COL_W + GAP)
        items = by.get(key, [])
        col_h = head_h + len(items) * (CHIP_H + CHIP_GAP) + 10
        svg.append(f'<rect x="{x:.1f}" y="{TOP}" width="{COL_W:.1f}" height="{col_h}" rx="12" fill="{BG}" stroke="{RULE}" stroke-width="2"/>')
        for li, line in enumerate(labels[key]):
            svg.append(f'<text x="{x + 16:.1f}" y="{TOP + 36 + 28 * li}" font-family="{FONT}" font-size="22" font-weight="700" fill="{NAVY}">{escape(line)}</text>')
        for j, (name, status) in enumerate(items):
            cy = TOP + head_h + j * (CHIP_H + CHIP_GAP)
            cx = x + 30
            cw = COL_W - 44
            hi = status in NOT_SCORED
            fill, stroke, txt = (FOCAL, FOCAL_EDGE, "#ffffff") if hi else ("#ffffff", "#c9d3de", NAVY)
            weight = "700" if (hi or name == TESTBED) else "400"
            svg.append(f'<rect x="{cx:.1f}" y="{cy}" width="{cw:.1f}" height="{CHIP_H}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
            svg.append(f'<text x="{cx + 10:.1f}" y="{cy + 26}" font-family="{FONT}" font-size="17" font-weight="{weight}" fill="{txt}">{escape(name)}</text>')
            pos[name] = (cx, cy, cw)
    # testbed connectors: an elbow along each dependant's left gutter
    if TESTBED in pos:
        tx, ty, tw = pos[TESTBED]
        sy = ty + CHIP_H / 2
        for dep in DEPENDANTS:
            if dep not in pos:
                continue
            dx, dy, _ = pos[dep]
            ey = dy + CHIP_H / 2
            if abs(dx - tx) < 1:
                gx = tx - 14
                svg.append(f'<path d="M{tx:.1f},{sy:.1f} H{gx:.1f} V{ey:.1f} H{dx:.1f}" fill="none" stroke="{SLATE}" stroke-width="2.5"/>')
            else:
                gx = dx - 14
                svg.append(f'<path d="M{tx + tw:.1f},{sy:.1f} H{gx:.1f} V{ey:.1f} H{dx:.1f}" fill="none" stroke="{SLATE}" stroke-width="2.5"/>')
            svg.append(f'<circle cx="{dx:.1f}" cy="{ey:.1f}" r="4" fill="{SLATE}"/>')
    svg.append(f'<text x="{MX}" y="{H - 24}" font-family="{FONT}" font-size="20" fill="{MUTED}">Source: bench.yaml in each folder.</text>')
    svg.append("</svg>")
    OUT.write_text("\n".join(svg) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {n_total} folders, {n_hi} highlighted")


if __name__ == "__main__":
    main()

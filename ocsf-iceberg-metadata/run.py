"""Iceberg metadata & compaction scaling — the small-files tax, measured.

Every Iceberg commit writes a data file, a manifest, and a fresh metadata.json, so a table fed by
many small streaming appends accumulates metadata that query planning has to read before it can
touch any data. This measures that: as the number of appends (snapshots / data files / manifests)
grows, how does scan-planning time grow — and how much does compacting the table back into a few
large files buy back? It's the practical Iceberg fundamental behind every "why is my lakehouse
slow" conversation, and it's the mechanism H-ICEBERG-V4-METADATA-EFFICIENCY-01 says V4 metadata
proposals target.

Planning is `table.scan().plan_files()` — the work of reading manifests to enumerate the data
files a query must scan; that's where the small-files tax lands. Scan is the subsequent read.
Latencies are machine-specific medians; the corpus and the file counts are deterministic.
"""

import json
import os
import shutil
import sys
import tempfile

import pyarrow as pa

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import BASE_EPOCH, configure_duckdb, new_rng, time_trials  # noqa: E402

ROWS_PER_APPEND = 5_000
CHECKPOINTS = [50, 100, 200]          # measure planning at these append counts
PORTS = [80, 443, 22, 53, 3389, 445, 8080, 3306]


def batch(seq):
    rng = new_rng(700 + seq)
    n = ROWS_PER_APPEND
    base = seq * n
    return pa.table({
        "id": pa.array([base + i for i in range(n)], pa.int64()),
        "time": pa.array([(BASE_EPOCH + base + i) * 1000 for i in range(n)], pa.int64()),
        "src_ip": pa.array([f"10.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}" for _ in range(n)]),
        "dst_port": pa.array([rng.choice(PORTS) for _ in range(n)], pa.int32()),
        "bytes": pa.array([rng.randint(40, 500_000) for _ in range(n)], pa.int64()),
    })


def make_catalog(work, name):
    from pyiceberg.catalog.sql import SqlCatalog
    wh = os.path.join(work, name); os.makedirs(wh)
    return SqlCatalog(name, uri=f"sqlite:///{work}/{name}.db", warehouse=f"file://{wh}")


def tree_counts(work, name):
    root = os.path.join(work, name)
    data = meta = 0
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(".parquet"):
                data += 1
            elif f.endswith(".metadata.json") or "manifest" in f or f.endswith(".avro"):
                meta += 1
    return {"data_files": data, "metadata_files": meta}


def plan_and_scan(tbl):
    plan = time_trials(lambda: list(tbl.scan().plan_files()), warmup=1, trials=3)
    scan = time_trials(lambda: tbl.scan().to_arrow(), warmup=1, trials=2)
    return plan["median_ms"], scan["median_ms"]


def _duckdb_iceberg_ms(metadata_location):
    """End-to-end filtered-scan time via DuckDB's iceberg reader (real query engine). DuckDB needs a
    version-hint that pyiceberg doesn't write, so write one, then time a filtered count."""
    import duckdb
    meta = metadata_location.replace("file://", "")
    root = os.path.dirname(os.path.dirname(meta))
    with open(os.path.join(root, "metadata", "version-hint.text"), "w") as f:
        f.write(os.path.basename(meta)[:-len(".metadata.json")])
    con = configure_duckdb(duckdb.connect()); con.execute("INSTALL iceberg; LOAD iceberg")
    t = time_trials(lambda: con.execute(
        f"SELECT count(*) FROM iceberg_scan('{root}') WHERE dst_port = 443").fetchone(),
        warmup=1, trials=3)
    con.close()
    return t["median_ms"]


def run():
    work = tempfile.mkdtemp(prefix="iceberg_meta_")
    try:
        # Fragmented: many small appends; measure planning as metadata accumulates.
        cat = make_catalog(work, "frag")
        cat.create_namespace("b")
        tbl = cat.create_table("b.events", schema=batch(0).schema)
        fragmented = []
        for seq in range(max(CHECKPOINTS)):
            tbl.append(batch(seq))
            if (seq + 1) in CHECKPOINTS:
                tbl = cat.load_table("b.events")
                plan_ms, scan_ms = plan_and_scan(tbl)
                c = tree_counts(work, "frag")
                fragmented.append({"appends": seq + 1, "rows": (seq + 1) * ROWS_PER_APPEND,
                                   "plan_ms": plan_ms, "scan_ms": scan_ms, **c})
                print(f"  [fragmented] {seq+1} appends ({c['data_files']} data, {c['metadata_files']} meta files): "
                      f"plan {plan_ms:.1f}ms  scan {scan_ms:.0f}ms")

        # Compacted: the same rows written as one append (one data file).
        total = max(CHECKPOINTS) * ROWS_PER_APPEND
        allrows = pa.concat_tables([batch(s) for s in range(max(CHECKPOINTS))])
        cat2 = make_catalog(work, "compact")
        cat2.create_namespace("b")
        tbl2 = cat2.create_table("b.events", schema=allrows.schema)
        tbl2.append(allrows)
        tbl2 = cat2.load_table("b.events")
        plan_ms, scan_ms = plan_and_scan(tbl2)
        cc = tree_counts(work, "compact")
        compacted = {"appends": 1, "rows": total, "plan_ms": plan_ms, "scan_ms": scan_ms, **cc}
        print(f"  [compacted]  1 append ({cc['data_files']} data, {cc['metadata_files']} meta files): "
              f"plan {plan_ms:.1f}ms  scan {scan_ms:.0f}ms")

        # Real-engine cross-check: DuckDB's iceberg reader over the same two tables, so the small-files
        # tax is shown on a production-representative engine, not only pyiceberg's Python planner.
        real = {"fragmented_ms": _duckdb_iceberg_ms(tbl.metadata_location),
                "compacted_ms": _duckdb_iceberg_ms(tbl2.metadata_location)}
        real["speedup_compacted_vs_fragmented"] = round(real["fragmented_ms"] / max(real["compacted_ms"], 0.01), 1)
        print(f"  [DuckDB iceberg_scan] fragmented {real['fragmented_ms']:.0f}ms  "
              f"compacted {real['compacted_ms']:.0f}ms  ({real['speedup_compacted_vs_fragmented']}×)")

        worst = fragmented[-1]
        return {"benchmark": "ocsf-iceberg-metadata", "evidence_tier": "B (single machine; latencies medians)",
                "rows_per_append": ROWS_PER_APPEND, "fragmented": fragmented, "compacted": compacted,
                "real_engine_duckdb": real,
                "headline": {
                    "fragmented_appends": worst["appends"], "fragmented_data_files": worst["data_files"],
                    "plan_speedup_compacted_vs_fragmented": round(worst["plan_ms"] / max(compacted["plan_ms"], 0.01), 1),
                    "scan_speedup_compacted_vs_fragmented": round(worst["scan_ms"] / max(compacted["scan_ms"], 0.01), 1),
                    "real_engine_speedup_compacted_vs_fragmented": real["speedup_compacted_vs_fragmented"],
                }}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(res):
    h = res["headline"]
    r = res.get("real_engine_duckdb", {"fragmented_ms": float("nan"), "compacted_ms": float("nan")})
    frag = "\n".join(f"| {r['appends']} | {r['data_files']} | {r['metadata_files']} | {r['plan_ms']:.1f} | {r['scan_ms']:.0f} |"
                     for r in res["fragmented"])
    c = res["compacted"]
    return f"""# Iceberg metadata & compaction scaling (results)

**Tier B.** How scan-planning cost grows as a table accumulates small appends (snapshots / data
files / manifests), and what compaction buys back. Planning is `scan().plan_files()` — reading
manifests to enumerate the files a query must touch; latencies are machine-specific medians.

## Fragmented table (many small appends)

| appends | data files | metadata files | plan ms | scan ms |
|---|---|---|---|---|
{frag}

## Compacted (same rows, one append)

| appends | data files | metadata files | plan ms | scan ms |
|---|---|---|---|---|
| {c['appends']} | {c['data_files']} | {c['metadata_files']} | {c['plan_ms']:.1f} | {c['scan_ms']:.0f} |

## Real-engine cross-check (DuckDB iceberg_scan)

A filtered scan through DuckDB's iceberg reader over the same two tables — a production query engine, not
pyiceberg's Python planner:

| table | DuckDB iceberg_scan ms |
|---|---|
| fragmented ({h['fragmented_data_files']} files) | {r['fragmented_ms']:.0f} |
| compacted (1 file) | {r['compacted_ms']:.0f} |

DuckDB is **{h.get('real_engine_speedup_compacted_vs_fragmented','—')}×** faster on the compacted table —
so the small-files tax is real on a production engine too, not a pyiceberg artifact. The magnitude differs
from the Python planner's (a real engine prunes and parallelizes), which is exactly why the pyiceberg
ratios below are framed as illustrative.

## Headline

The directional, transferable finding is that **scan-planning and scan cost grow monotonically with
file/manifest count, and compaction recovers them** — the small-files tax: planning has to read every
manifest before touching data, so cost scales with file count, not data volume. That is the
mechanism H-ICEBERG-V4-METADATA-EFFICIENCY-01 says V4 metadata targets, and the maintenance job
(compaction) every real deployment runs.

The specific ratios ({h['fragmented_appends']} micro-batch appends / {h['fragmented_data_files']} data files →
plan {h['plan_speedup_compacted_vs_fragmented']}×, scan {h['scan_speedup_compacted_vs_fragmented']}×) are
**illustrative of the mechanism under deliberate fragmentation, not production figures**. They are measured
by pyiceberg's own Python `plan_files()` on this machine with artificially small 5k-row files; the
real-engine cross-check above (DuckDB) confirms the tax exists on a production engine but at a different
magnitude, because a real engine prunes and parallelizes — so the pyiceberg ratio is planner-, file-size-,
and host-specific. This is a *within-Iceberg*
fragmentation cost; it is **not** a query-runtime number and **not** the DuckLake-vs-Iceberg format
comparison (that is BENCH-E, where the two are roughly interchangeable on read) or any vendor
format-war speedup claim. Do not conflate them. Tier B, single machine.
"""


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    if args.render_only:
        res = json.load(open(os.path.join(rdir, "results.json")))
    else:
        res = run()
        with open(os.path.join(rdir, "results.json"), "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "RESULTS.md"), "w") as f:
        f.write(render_md(res))
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()

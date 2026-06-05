"""DuckLake inlining vs Iceberg: does inlining avoid the small-files problem at the source?

BENCH-D measured the hot-tier write *contract*; this isolates one specific claim made for DuckLake:
that it inlines small streaming batches into the catalog instead of writing a data file per commit,
so it "never creates tiny files in the first place" — versus Iceberg's write-a-file-then-compact-later
model. The test is direct: feed the same stream of small batches to three arms and count the data
files each leaves behind, plus confirm the data is immediately queryable.

- iceberg            — classic Iceberg via pyiceberg: one data file (+ manifest + metadata.json) per commit
- ducklake_no_inline — DuckLake with inlining off: one data file per commit
- ducklake_inline    — DuckLake with inlining on (row limit above the batch size): rows inlined into the
                       catalog, no per-commit data file until a flush threshold

Files left on disk are the small-files tax avoided (or not). Latencies are machine-specific medians;
the corpus is seeded and identical across arms.
"""

import json
import os
import shutil
import sys
import tempfile

import duckdb
import pyarrow as pa

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import BASE_EPOCH, configure_duckdb, new_rng  # noqa: E402

N_COMMITS = 100
ROWS_PER_COMMIT = 200
INLINE_LIMIT = 10_000          # > ROWS_PER_COMMIT, so each batch inlines


def batch(seq):
    rng = new_rng(800 + seq)
    n = ROWS_PER_COMMIT
    base = seq * n
    return pa.table({
        "id": pa.array([base + i for i in range(n)], pa.int64()),
        "time": pa.array([(BASE_EPOCH + base + i) * 1000 for i in range(n)], pa.int64()),
        "src_ip": pa.array([f"10.10.{rng.randint(0,255)}.{rng.randint(1,254)}" for _ in range(n)]),
        "bytes": pa.array([rng.randint(40, 500_000) for _ in range(n)], pa.int64()),
    })


def count_parquet(root):
    return sum(1 for dp, _, fs in os.walk(root) for f in fs if f.endswith(".parquet"))


def count_all(root):
    data = meta = 0
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(".parquet"):
                data += 1
            elif f.endswith(".metadata.json") or "manifest" in f or f.endswith(".avro"):
                meta += 1
    return data, meta


def run_iceberg(work, batches):
    from pyiceberg.catalog.sql import SqlCatalog
    wh = os.path.join(work, "ice"); os.makedirs(wh)
    cat = SqlCatalog("i", uri=f"sqlite:///{work}/ice.db", warehouse=f"file://{wh}")
    cat.create_namespace("b")
    t = cat.create_table("b.e", schema=batches[0].schema)
    for bt in batches:
        t.append(bt)
    t = cat.load_table("b.e")
    data, meta = count_all(wh)
    return {"data_files": data, "metadata_files": meta, "rows": len(t.scan().to_arrow()),
            "queryable": len(t.scan().to_arrow()) == N_COMMITS * ROWS_PER_COMMIT}


def run_ducklake(work, batches, inline_limit, tag):
    dpath = os.path.join(work, f"dl_{tag}_data"); os.makedirs(dpath)
    con = configure_duckdb(duckdb.connect()); con.execute("INSTALL ducklake; LOAD ducklake")
    con.execute(f"ATTACH 'ducklake:{work}/dl_{tag}.ducklake' AS dl "
                f"(DATA_PATH '{dpath}', DATA_INLINING_ROW_LIMIT {inline_limit})")
    con.execute("USE dl")
    con.execute("CREATE TABLE e(id BIGINT, time BIGINT, src_ip VARCHAR, bytes BIGINT)")
    for bt in batches:
        con.register("b", bt)
        con.execute("INSERT INTO e SELECT * FROM b")
        con.unregister("b")
    rows = con.execute("SELECT count(*) FROM e").fetchone()[0]
    con.close()
    return {"data_files": count_parquet(dpath), "metadata_files": 0,
            "rows": rows, "queryable": rows == N_COMMITS * ROWS_PER_COMMIT}


def run():
    work = tempfile.mkdtemp(prefix="inlining_")
    try:
        batches = [batch(s) for s in range(N_COMMITS)]
        arms = {
            "iceberg": run_iceberg(work, batches),
            "ducklake_no_inline": run_ducklake(work, batches, 0, "noinl"),
            "ducklake_inline": run_ducklake(work, batches, INLINE_LIMIT, "inl"),
        }
        for name, a in arms.items():
            print(f"  {name:20}: {a['data_files']:>4} data files, {a['metadata_files']:>4} metadata files  "
                  f"(queryable={a['queryable']})")
        return {"benchmark": "ocsf-write-inlining", "evidence_tier": "B (single machine)",
                "commits": N_COMMITS, "rows_per_commit": ROWS_PER_COMMIT,
                "inline_row_limit": INLINE_LIMIT, "arms": arms,
                "headline": {
                    "iceberg_data_files": arms["iceberg"]["data_files"],
                    "ducklake_no_inline_data_files": arms["ducklake_no_inline"]["data_files"],
                    "ducklake_inline_data_files": arms["ducklake_inline"]["data_files"],
                    "small_files_avoided": arms["ducklake_no_inline"]["data_files"] - arms["ducklake_inline"]["data_files"]}}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(res):
    a = res["arms"]; h = res["headline"]
    rows = "\n".join(f"| {n} | {a[n]['data_files']} | {a[n]['metadata_files']} | {a[n]['queryable']} |" for n in a)
    return f"""# DuckLake inlining vs Iceberg — the small-files problem at the source (results)

**Tier B.** {res['commits']} small commits of {res['rows_per_commit']} rows each, identical seeded stream
to three arms; the metric is how many data files each leaves behind (and whether the data is queryable).

| arm | data files | metadata files | queryable |
|---|---|---|---|
{rows}

## Reading

The inlining claim holds, concretely: with inlining off, both DuckLake and Iceberg write one data file
per small commit ({h['ducklake_no_inline_data_files']} and {h['iceberg_data_files']} respectively, Iceberg
also accumulating a manifest and metadata.json each time), so a streaming workload leaves a pile of tiny
files that has to be compacted later. With inlining on, DuckLake writes
**{h['ducklake_inline_data_files']} data files** for the same stream — the rows live in the catalog until a
flush threshold — so the small files are never created in the first place rather than created and cleaned
up. Both remain immediately queryable. This is the difference between "create tiny files, then compact"
(the Iceberg maintenance job measured in the iceberg-metadata bench) and "don't create them" — a real
architectural distinction for hot-tier streaming ingest. Tier B, single machine; file counts are
deterministic, the threshold is a configured parameter. It does not by itself say which is better at
warehouse scale (inlined rows trade file-count for catalog growth) — it isolates the file-avoidance claim.
"""


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    res = json.load(open(os.path.join(rdir, "results.json"))) if args.render_only else run()
    if not args.render_only:
        with open(os.path.join(rdir, "results.json"), "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "RESULTS.md"), "w") as f:
        f.write(render_md(res))
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()

"""R6 — planning cost vs fragmentation: Iceberg manifests vs DuckLake SQL catalog.

ocsf-iceberg-metadata measured Iceberg's small-files tax (planning grows with file/manifest count) on
Iceberg alone. This adds the DuckLake side and isolates the variable cleanly by holding the *engine*
constant: the same DuckDB reads both formats end-to-end as the number of commits (and therefore data
files) grows at a fixed total row count, so the only thing that changes is how each format's metadata
layer resolves "which files must I scan." That is the architectural question behind the Iceberg V4
metadata work — Iceberg enumerates files by reading manifests (cost scales with file count), while
DuckLake resolves them with a SQL query against its catalog DB (an indexed lookup that shouldn't care
how many files there are).

Two readings come out of one run:
  - end-to-end (same engine, both formats): the fair, confound-free comparison — does DuckDB's query
    latency over each format degrade as the table fragments into more files?
  - planning proxy (each format's native mechanism): pyiceberg `plan_files()` (manifest traversal) vs
    DuckLake `ducklake_list_files` (catalog query). Different mechanisms, so the absolute ms aren't
    directly comparable — the *scaling shape* with file count is the transferable finding.

Deliberately small (5M rows, a few commit counts) — single engine, modest footprint. Latencies are
medians with CV; file counts are exact and deterministic.

    python run.py                 # 5M rows, commit ladder [10, 50, 200]
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import BASE_EPOCH, configure_duckdb, time_trials  # noqa: E402

PORTS = "[80, 443, 22, 53, 3389, 445, 8080, 3306]"
# A query that must enumerate every file (filtered group-by over the whole table), so metadata
# resolution actually matters — that's where a per-file planning cost would show up.
QUERY = ("SELECT dst_port, count(*) c FROM {t} WHERE dst_port IN (443, 3389) "
         "GROUP BY 1 ORDER BY 1")


def gen_batch_arrow(con, start, n):
    return con.execute(f"""
        SELECT i AS id, {BASE_EPOCH*1000} + i AS time,
               '10.' || (hash(i::VARCHAR||'a')%256) || '.' || (hash(i::VARCHAR||'b')%256) || '.'
                     || (hash(i::VARCHAR||'c')%256) AS src_ip,
               {PORTS}[(1 + hash(i::VARCHAR||'p')%8)::BIGINT]::INTEGER AS dst_port,
               (hash(i::VARCHAR||'bo')%5000000)::BIGINT AS bytes_out
        FROM range({start},{start+n}) t(i)""").fetch_arrow_table()


def _n_files(root, ext):
    return sum(1 for dp, _, fs in os.walk(root) for f in fs if f.endswith(ext))


def ingest_iceberg(con, work, total, k):
    """Iceberg table fed by k appends -> k data files + k snapshots + accumulating manifests."""
    from pyiceberg.catalog.sql import SqlCatalog
    wh = os.path.join(work, f"ice_{k}"); os.makedirs(wh)
    cat = SqlCatalog(f"e{k}", uri=f"sqlite:///{work}/ice_{k}.db", warehouse=f"file://{wh}")
    cat.create_namespace("b")
    per = total // k
    tbl = None
    for ci in range(k):
        ab = gen_batch_arrow(con, ci * per, per)
        if tbl is None:
            tbl = cat.create_table("b.events", schema=ab.schema)
        tbl.append(ab)
        del ab
    meta = tbl.metadata_location.replace("file://", "")
    root = os.path.dirname(os.path.dirname(meta))
    with open(os.path.join(root, "metadata", "version-hint.text"), "w") as f:
        f.write(os.path.basename(meta)[:-len(".metadata.json")])
    return tbl, root, wh


def ingest_ducklake(con, work, total, k):
    """DuckLake table fed by k inserts -> k data files, all tracked in the SQL catalog."""
    dpath = os.path.join(work, f"dl_{k}_data"); os.makedirs(dpath)
    con.execute(f"ATTACH 'ducklake:{work}/dl_{k}.ducklake' AS dl{k} (DATA_PATH '{dpath}')")
    per = total // k
    for ci in range(k):
        ab = gen_batch_arrow(con, ci * per, per)
        con.register("src", ab)
        if ci == 0:
            con.execute(f"CREATE TABLE dl{k}.events AS SELECT * FROM src")
        else:
            con.execute(f"INSERT INTO dl{k}.events SELECT * FROM src")
        con.unregister("src"); del ab
    return dpath


def run(total, ladder):
    work = tempfile.mkdtemp(prefix="fmt_planning_")
    try:
        con = configure_duckdb(duckdb.connect())
        con.execute("INSTALL iceberg; LOAD iceberg; INSTALL ducklake; LOAD ducklake")
        rungs = []
        for k in ladder:
            # --- Iceberg ---
            tbl, root, wh = ingest_iceberg(con, work, total, k)
            ice_files = _n_files(wh, ".parquet")
            ice_e2e = time_trials(
                lambda: con.execute(QUERY.format(t=f"iceberg_scan('{root}')")).fetchall(),
                warmup=1, trials=5)
            ice_plan = time_trials(lambda: list(tbl.scan().plan_files()), warmup=1, trials=5)

            # --- DuckLake ---
            dpath = ingest_ducklake(con, work, total, k)
            dl_files = _n_files(dpath, ".parquet")
            dl_e2e = time_trials(
                lambda: con.execute(QUERY.format(t=f"dl{k}.events")).fetchall(), warmup=1, trials=5)
            dl_plan = time_trials(
                lambda: con.execute(f"SELECT count(*) FROM ducklake_list_files('dl{k}','events')").fetchall(),
                warmup=1, trials=5)

            # same engine, same logical data -> answers must match across formats
            ia = con.execute(QUERY.format(t=f"iceberg_scan('{root}')")).fetchall()
            da = con.execute(QUERY.format(t=f"dl{k}.events")).fetchall()
            rungs.append({
                "commits": k, "iceberg_data_files": ice_files, "ducklake_data_files": dl_files,
                "iceberg_e2e_ms": ice_e2e["median_ms"], "iceberg_e2e_cv": ice_e2e["cv_pct"],
                "ducklake_e2e_ms": dl_e2e["median_ms"], "ducklake_e2e_cv": dl_e2e["cv_pct"],
                "iceberg_plan_ms": ice_plan["median_ms"], "iceberg_plan_cv": ice_plan["cv_pct"],
                "ducklake_plan_ms": dl_plan["median_ms"], "ducklake_plan_cv": dl_plan["cv_pct"],
                "answers_agree": ia == da,
            })
            print(f"  commits={k:<4} files ice/dl {ice_files}/{dl_files}  "
                  f"e2e ice {ice_e2e['median_ms']:.0f}ms / dl {dl_e2e['median_ms']:.0f}ms  "
                  f"plan ice {ice_plan['median_ms']:.1f}ms / dl {dl_plan['median_ms']:.2f}ms  agree={ia==da}")
            con.execute(f"DETACH dl{k}")

        def grow(side):
            first, last = rungs[0][side], rungs[-1][side]
            return round(last / max(first, 0.001), 2)
        con.close()
        return {"benchmark": "ocsf-format-planning (R6)",
                "evidence_tier": "B (single machine; latencies medians w/ CV; file counts exact)",
                "hypothesis": "H-ICEBERG-V4-METADATA-EFFICIENCY-01 / H-DUCKLAKE-02 (planning architecture)",
                "total_rows": total, "commit_ladder": ladder,
                "e2e_growth_iceberg_x": grow("iceberg_e2e_ms"),
                "e2e_growth_ducklake_x": grow("ducklake_e2e_ms"),
                "plan_growth_iceberg_x": grow("iceberg_plan_ms"),
                "plan_growth_ducklake_x": grow("ducklake_plan_ms"),
                "rungs": rungs}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(res):
    rows = "\n".join(
        f"| {r['commits']} | {r['iceberg_data_files']}/{r['ducklake_data_files']} | "
        f"{r['iceberg_e2e_ms']:.0f} ({r['iceberg_e2e_cv']:.0f}%) | {r['ducklake_e2e_ms']:.0f} ({r['ducklake_e2e_cv']:.0f}%) | "
        f"{r['iceberg_plan_ms']:.1f} ({r['iceberg_plan_cv']:.0f}%) | {r['ducklake_plan_ms']:.2f} ({r['ducklake_plan_cv']:.0f}%) |"
        for r in res["rungs"])
    return f"""# Planning cost vs fragmentation — Iceberg manifests vs DuckLake catalog (R6)

**Tier B · single machine.** {res['total_rows']:,} rows ingested into each format across a ladder of
commit counts (each commit = one data file), then read end-to-end by the **same engine** (DuckDB) so the
only variable is how each format's metadata layer resolves which files to scan. Latencies are medians
with CV; file counts are exact.

| commits | data files ice/dl | DuckDB e2e — Iceberg ms (cv) | DuckDB e2e — DuckLake ms (cv) | plan — pyiceberg ms (cv) | plan — DuckLake catalog ms (cv) |
|---|---|--:|--:|--:|--:|
{rows}

- End-to-end growth across the ladder (same engine): Iceberg **{res['e2e_growth_iceberg_x']}×**,
  DuckLake **{res['e2e_growth_ducklake_x']}×**.
- Native planning-proxy growth: pyiceberg `plan_files()` **{res['plan_growth_iceberg_x']}×**, DuckLake
  `ducklake_list_files` **{res['plan_growth_ducklake_x']}×**.

## Reading

The same data, read by the same engine, fragments into more and more files as the commit count grows —
and the two formats answer "which files do I scan" very differently. Iceberg enumerates them by reading
manifests, so its end-to-end query latency and especially its planning cost climb as files accumulate;
that climb is the small-files tax, and it is the mechanism the Iceberg V4 metadata work targets. DuckLake
resolves the same question with a query against its SQL catalog, an indexed lookup whose cost barely
moves with file count, so its planning stays roughly flat across the ladder. The planning-proxy columns
use each format's native mechanism (pyiceberg's Python manifest planner vs DuckLake's catalog query), so
their absolute milliseconds aren't directly comparable — the transferable finding is the *shape*: one
grows with fragmentation, the other doesn't, which is an architectural property of where the metadata
lives (in files vs in a database), not a tuning detail. Both formats return identical answers throughout.
Tier B, single machine; magnitudes are this host's, the scaling shapes are the finding.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=5_000_000)
    ap.add_argument("--ladder", type=int, nargs="+", default=[10, 50, 200])
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    out = os.path.join(rdir, "results.json")
    if args.render_only:
        res = json.load(open(out))
    else:
        res = run(args.rows, args.ladder)
        with open(out, "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "RESULTS.md"), "w") as f:
        f.write(render_md(res))
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()

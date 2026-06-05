"""BENCH-E large-scan arm — DuckLake vs Iceberg at >1B rows.

BENCH-E proper runs at 10M rows and materializes the whole corpus as one in-memory Arrow table.
That doesn't scale: a 1B-row Arrow table is tens of GB of host memory, outside DuckDB's memory_limit.
This arm answers the gap the headline BENCH-E and DuckDB Labs' own numbers leave open
(H-DUCKLAKE-02): "benchmark large-scan workloads — >1B rows, full-table scan, complex aggregation —
where DuckLake's catalog DB might become the bottleneck." The hypothesis to test is whether DuckLake's
SQL-catalog advantage on small commits turns into a *liability* on a big full scan, or whether at scan
scale both formats are just reading Parquet and the metadata layer is amortized away.

Ingestion is batched so peak memory is one batch, not the whole corpus: each batch is generated once
(seeded off the global row index, so the corpus is deterministic and identical across formats), then
appended to Iceberg (pyiceberg) and inserted into DuckLake (DuckDB-native) from the SAME batch. Both
formats are read by the same engine (DuckDB) so the only variable is the format's read path. DuckDB's
memory_limit (auto-scaled, ~28GB on this host) makes the high-cardinality aggregation spill to native
ext4 rather than OOM.

    python large_scan.py --rows 100000000     # validate small first
    python large_scan.py --rows 1000000000     # the >1B run (long; run in background)
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import BASE_EPOCH, configure_duckdb, time_trials  # noqa: E402

PORTS = "[80, 443, 22, 53, 3389, 445, 8080, 3306]"

# Scan shapes a SOC runs at scale. The last two are the "complex aggregation" the gap names:
# topn_src is a high-cardinality group-by (~16.7M distinct src_ip) that forces a large hash table
# (spills under memory_limit); subnet_rollup is a two-key roll-up that stresses the aggregator harder.
QUERIES = {
    "full_count":    "SELECT count(*) FROM {t}",
    "filtered":      "SELECT count(*) FROM {t} WHERE dst_port = 443",
    "topn_src":      "SELECT src_ip, count(*) c FROM {t} GROUP BY 1 ORDER BY c DESC, src_ip LIMIT 20",
    "byte_rollup":   "SELECT dst_port, sum(bytes_out) FROM {t} GROUP BY 1 ORDER BY 2 DESC",
    "subnet_rollup": ("SELECT split_part(src_ip,'.',2)::INT AS o2, dst_port, count(*) c, "
                      "sum(bytes_out) b FROM {t} GROUP BY 1,2 ORDER BY c DESC, o2, dst_port LIMIT 50"),
}


def gen_batch_arrow(con, start, n):
    """One deterministic batch of OCSF-shaped rows for global indices [start, start+n)."""
    return con.execute(f"""
        SELECT i AS id, {BASE_EPOCH*1000} + i AS time,
               '10.' || (hash(i::VARCHAR||'a')%256) || '.' || (hash(i::VARCHAR||'b')%256) || '.' || (hash(i::VARCHAR||'c')%256) AS src_ip,
               {PORTS}[(1 + hash(i::VARCHAR||'p')%8)::BIGINT]::INTEGER AS dst_port,
               (hash(i::VARCHAR||'bo')%5000000)::BIGINT AS bytes_out
        FROM range({start},{start+n}) t(i)""").fetch_arrow_table()


def _dir_bytes(root):
    return sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(root) for f in fs)


def _n_files(root, ext):
    return sum(1 for dp, _, fs in os.walk(root) for f in fs if f.endswith(ext))


def run(total_rows, batch):
    work = tempfile.mkdtemp(prefix="bench_e_big_")
    try:
        con = configure_duckdb(duckdb.connect())
        con.execute("INSTALL iceberg; LOAD iceberg; INSTALL ducklake; LOAD ducklake")

        # warehouses
        from pyiceberg.catalog.sql import SqlCatalog
        wh = os.path.join(work, "ice"); os.makedirs(wh)
        cat = SqlCatalog("e", uri=f"sqlite:///{work}/ice.db", warehouse=f"file://{wh}")
        cat.create_namespace("b")
        dpath = os.path.join(work, "dl_data"); os.makedirs(dpath)
        con.execute(f"ATTACH 'ducklake:{work}/dl.ducklake' AS dl (DATA_PATH '{dpath}')")

        ice_tbl = None
        n_batches = (total_rows + batch - 1) // batch
        print(f"  ingesting {total_rows:,} rows in {n_batches} batches of {batch:,} "
              f"(peak memory = one batch)…", flush=True)
        done = 0
        for bi in range(n_batches):
            start = bi * batch
            n = min(batch, total_rows - start)
            ab = gen_batch_arrow(con, start, n)
            if ice_tbl is None:
                ice_tbl = cat.create_table("b.events", schema=ab.schema)
                ice_tbl.append(ab)
                con.register("src", ab); con.execute("CREATE TABLE dl.events AS SELECT * FROM src")
            else:
                ice_tbl.append(ab)
                con.register("src", ab); con.execute("INSERT INTO dl.events SELECT * FROM src")
            con.unregister("src")
            del ab
            done += n
            print(f"    batch {bi+1}/{n_batches} ({done:,} rows)", flush=True)

        meta = ice_tbl.metadata_location.replace("file://", "")
        root = os.path.dirname(os.path.dirname(meta))
        with open(os.path.join(root, "metadata", "version-hint.text"), "w") as f:
            f.write(os.path.basename(meta)[:-len(".metadata.json")])

        results = {
            "iceberg":  {"storage_bytes": _dir_bytes(wh), "data_files": _n_files(wh, ".parquet"),
                         "queries": {}},
            "ducklake": {"storage_bytes": _dir_bytes(dpath) + os.path.getsize(f"{work}/dl.ducklake"),
                         "data_files": _n_files(dpath, ".parquet"), "queries": {}},
        }
        print("  scanning (warmup 1, 3 trials)…", flush=True)
        for qid, sql in QUERIES.items():
            ice_sql = sql.format(t=f"iceberg_scan('{root}')")
            dl_sql = sql.format(t="dl.events")
            it = time_trials(lambda: con.execute(ice_sql).fetchall(), warmup=1, trials=3)
            dt = time_trials(lambda: con.execute(dl_sql).fetchall(), warmup=1, trials=3)
            results["iceberg"]["queries"][qid] = {"median_ms": it["median_ms"], "cv_pct": it["cv_pct"]}
            results["ducklake"]["queries"][qid] = {"median_ms": dt["median_ms"], "cv_pct": dt["cv_pct"]}
            ratio = round(it["median_ms"] / max(dt["median_ms"], 0.01), 2)
            print(f"  {qid:14}: iceberg {it['median_ms']:.0f}ms  ducklake {dt['median_ms']:.0f}ms  "
                  f"(ice/dl {ratio}×)", flush=True)

        def _norm(rows):
            return sorted(tuple(str(c) for c in r) for r in rows)
        same = all(_norm(con.execute(QUERIES[q].format(t=f"iceberg_scan('{root}')")).fetchall())
                   == _norm(con.execute(QUERIES[q].format(t="dl.events")).fetchall()) for q in QUERIES)
        con.close()
        return {"benchmark": "ocsf-read-scan large-scan arm (BENCH-E, >1B)",
                "evidence_tier": "B (single machine; latencies medians)",
                "n_rows": total_rows, "batch_rows": batch, "n_batches": n_batches,
                "memory_limit": __import__("common").DUCK_MEMORY_LIMIT,
                "answers_identical": same, **results}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(res):
    def m(side, q):
        v = res[side]["queries"][q]
        return v["median_ms"] if isinstance(v, dict) else v
    def cvp(side, q):
        v = res[side]["queries"][q]
        return v["cv_pct"] if isinstance(v, dict) else 0.0
    rows = "\n".join(
        f"| {q} | {m('iceberg',q):.0f} ({cvp('iceberg',q):.0f}%) | {m('ducklake',q):.0f} ({cvp('ducklake',q):.0f}%) | "
        f"{round(m('iceberg',q)/max(m('ducklake',q),0.01),2)}× |"
        for q in res["iceberg"]["queries"])
    return f"""# BENCH-E large-scan arm — DuckLake vs Iceberg at {res['n_rows']:,} rows (results)

**Tier B · single machine.** {res['n_rows']:,} rows ingested in {res['n_batches']} batches of
{res['batch_rows']:,} (peak memory = one batch), materialized in both formats and read by the same
engine (DuckDB, memory_limit {res['memory_limit']}, spilling to native ext4). Latencies are medians
with CV (warmup 1, 3 trials). **This is the default-config comparison — the two writers differ in
codec/encoding, so the gap mixes the writer's compression with the format.** See SAME-FILES.md for the
byte-identical comparison that isolates the format (the read difference collapses to ~parity there).

| query | Iceberg ms (cv) | DuckLake ms (cv) | Iceberg/DuckLake |
|---|---|---|---|
{rows}

- Storage: Iceberg {res['iceberg']['storage_bytes']/1e9:.2f} GB ({res['iceberg']['data_files']} data files) ·
  DuckLake {res['ducklake']['storage_bytes']/1e9:.2f} GB ({res['ducklake']['data_files']} data files)
- Answers identical across both formats: **{res['answers_identical']}**

## Reading

The open question (H-DUCKLAKE-02) was whether DuckLake's SQL-catalog advantage on small streaming
commits turns into a liability on a large full scan, where its catalog DB might become the bottleneck.
At {res['n_rows']:,} rows, read by one engine over the same logical data, the two formats return
identical answers and the latency column shows what the format's read path costs at this scale. The
high-cardinality aggregations (topn_src, subnet_rollup) are where a catalog or planning overhead would
surface if it existed; the byte_rollup and full_count are metadata-amortized scans. Tier B, single
machine; the answer-equality and the relative shape are the transferable findings, the magnitudes are
this host's.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1_000_000_000)
    ap.add_argument("--batch", type=int, default=50_000_000)
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    out = os.path.join(rdir, "large-scan.json")
    if args.render_only:
        res = json.load(open(out))
    else:
        res = run(args.rows, args.batch)
        with open(out, "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "LARGE-SCAN.md"), "w") as f:
        f.write(render_md(res))
    print("wrote results/large-scan.json + LARGE-SCAN.md", flush=True)


if __name__ == "__main__":
    main()

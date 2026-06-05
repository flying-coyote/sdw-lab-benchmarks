"""BENCH-E — DuckLake vs Iceberg large-scan read performance.

The read-side sibling to BENCH-D (which measured the write contract). Same large OCSF corpus
materialized in both formats, read by the SAME engine (DuckDB) so the variable is the table
format's read path, not the engine: DuckLake (catalog-backed, DuckDB-native) vs Iceberg (read via
DuckDB's iceberg extension). Four scan shapes a SOC actually runs — full count, a filtered scan, a
top-N aggregation, a byte rollup — at scale.

This is the top format-war tracking question (H-DUCKLAKE-02): are the two interchangeable on read,
and what does the format cost in scan latency? Latencies are machine-specific medians; the corpus
is seeded and identical across both formats.
"""

import json
import os
import shutil
import sys
import tempfile

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import BASE_EPOCH, configure_duckdb, time_trials  # noqa: E402

N_ROWS = 10_000_000
PORTS = "[80, 443, 22, 53, 3389, 445, 8080, 3306]"

QUERIES = {
    "full_count":   "SELECT count(*) FROM {t}",
    "filtered":     "SELECT count(*) FROM {t} WHERE dst_port = 443",
    "topn_src":     "SELECT src_ip, count(*) c FROM {t} GROUP BY 1 ORDER BY c DESC, src_ip LIMIT 20",
    "byte_rollup":  "SELECT dst_port, sum(bytes_out) FROM {t} GROUP BY 1 ORDER BY 2 DESC",
}


def gen_arrow(con, n):
    return con.execute(f"""
        SELECT i AS id, {BASE_EPOCH*1000} + i AS time,
               '10.' || (hash(i::VARCHAR||'a')%256) || '.' || (hash(i::VARCHAR||'b')%256) || '.' || (hash(i::VARCHAR||'c')%256) AS src_ip,
               {PORTS}[(1 + hash(i::VARCHAR||'p')%8)::BIGINT]::INTEGER AS dst_port,
               (hash(i::VARCHAR||'bo')%5000000)::BIGINT AS bytes_out
        FROM range(0,{n}) t(i)""").fetch_arrow_table()


def _dir_bytes(root):
    return sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(root) for f in fs)


def setup_iceberg(work, tbl_arrow):
    from pyiceberg.catalog.sql import SqlCatalog
    wh = os.path.join(work, "ice"); os.makedirs(wh)
    cat = SqlCatalog("e", uri=f"sqlite:///{work}/ice.db", warehouse=f"file://{wh}")
    cat.create_namespace("b")
    t = cat.create_table("b.events", schema=tbl_arrow.schema)
    t.append(tbl_arrow)
    meta = t.metadata_location.replace("file://", "")
    root = os.path.dirname(os.path.dirname(meta))
    with open(os.path.join(root, "metadata", "version-hint.text"), "w") as f:
        f.write(os.path.basename(meta)[:-len(".metadata.json")])     # DuckDB iceberg reader needs this
    return root, _dir_bytes(wh)


def setup_ducklake(work, con, tbl_arrow):
    dpath = os.path.join(work, "dl_data"); os.makedirs(dpath)
    con.execute("INSTALL ducklake; LOAD ducklake")
    con.execute(f"ATTACH 'ducklake:{work}/dl.ducklake' AS dl (DATA_PATH '{dpath}')")
    con.register("src", tbl_arrow)
    con.execute("CREATE TABLE dl.events AS SELECT * FROM src")
    con.unregister("src")
    size = _dir_bytes(dpath) + (os.path.getsize(f"{work}/dl.ducklake") if os.path.exists(f"{work}/dl.ducklake") else 0)
    return size


def run():
    work = tempfile.mkdtemp(prefix="bench_e_")
    try:
        con = configure_duckdb(duckdb.connect())
        con.execute("INSTALL iceberg; LOAD iceberg")
        print(f"  generating {N_ROWS:,}-row OCSF corpus…")
        arrow = gen_arrow(con, N_ROWS)
        ice_root, ice_bytes = setup_iceberg(work, arrow)
        dl_bytes = setup_ducklake(work, con, arrow)

        results = {"iceberg": {"storage_bytes": ice_bytes, "queries": {}},
                   "ducklake": {"storage_bytes": dl_bytes, "queries": {}}}
        for qid, sql in QUERIES.items():
            ice_sql = sql.format(t=f"iceberg_scan('{ice_root}')")
            dl_sql = sql.format(t="dl.events")
            it = time_trials(lambda: con.execute(ice_sql).fetchall(), warmup=1, trials=3)
            dt = time_trials(lambda: con.execute(dl_sql).fetchall(), warmup=1, trials=3)
            results["iceberg"]["queries"][qid] = {"median_ms": it["median_ms"], "cv_pct": it["cv_pct"]}
            results["ducklake"]["queries"][qid] = {"median_ms": dt["median_ms"], "cv_pct": dt["cv_pct"]}
            ratio = round(it["median_ms"] / max(dt["median_ms"], 0.01), 2)
            print(f"  {qid:12}: iceberg {it['median_ms']:.0f}ms  ducklake {dt['median_ms']:.0f}ms  (ice/dl {ratio}×)")

        # correctness: both formats must return the same answer for the same logical data,
        # compared order-insensitively (every query has a deterministic ordering, but compare as
        # a sorted multiset so a tie-stable re-order can't masquerade as a discrepancy)
        def _norm(rows):
            return sorted(tuple(str(c) for c in r) for r in rows)
        same = all(_norm(con.execute(QUERIES[q].format(t=f"iceberg_scan('{ice_root}')")).fetchall())
                   == _norm(con.execute(QUERIES[q].format(t="dl.events")).fetchall()) for q in QUERIES)
        con.close()
        return {"benchmark": "ocsf-read-scan (BENCH-E)", "evidence_tier": "B (single machine; latencies medians)",
                "n_rows": N_ROWS, "answers_identical": same, **results}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(res):
    def m(side, q):
        return res[side]["queries"][q]["median_ms"]
    def cvp(side, q):
        return res[side]["queries"][q]["cv_pct"]
    rows = "\n".join(
        f"| {q} | {m('iceberg',q):.0f} ({cvp('iceberg',q):.0f}%) | {m('ducklake',q):.0f} ({cvp('ducklake',q):.0f}%) | "
        f"{round(m('iceberg',q)/max(m('ducklake',q),0.01),2)}× |"
        for q in res["iceberg"]["queries"])
    return f"""# BENCH-E — DuckLake vs Iceberg large-scan reads (results)

**Tier B.** {res['n_rows']:,}-row OCSF corpus materialized in both formats and read by the same
engine (DuckDB). Latencies are medians with coefficient of variation. **This is the default-config
comparison and is confounded**: the two writers differ in codec and per-column encoding (pyiceberg
ZSTD/dictionary vs DuckDB ZSTD/PLAIN), so the gap mixes the writer's compression with the format. See
[PARITY.md](PARITY.md) (matched codec) and [SAME-FILES.md](SAME-FILES.md) (byte-identical data) for the
controlled result that isolates the format — where the read difference collapses to ~parity.

| query | Iceberg ms (cv) | DuckLake ms (cv) | Iceberg/DuckLake |
|---|---|---|---|
{rows}

- Storage: Iceberg {res['iceberg']['storage_bytes']/1e6:.0f} MB · DuckLake {res['ducklake']['storage_bytes']/1e6:.0f} MB
- Answers identical across both formats: **{res['answers_identical']}**

## Reading

Read by one engine over the same logical data, the two formats return identical answers — they are
interchangeable on *correctness*. The latency column is where the format's read path shows: the
ratio is the cost (or saving) of the format on each scan shape at this scale, not an engine
difference. That is the read-side complement to BENCH-D's write-contract finding, and the pairing is
the H-DUCKLAKE-02 trade-off: which format you reach for depends on the write pattern (BENCH-D) and
the read latency here, not on one being universally better. Tier B, single machine; the magnitudes
are this host's, the answer-equality and the relative shape are the transferable findings.
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

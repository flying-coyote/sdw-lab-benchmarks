"""R5 — materialized-view acceleration for SOC dashboards, with its true cost.

A SOC wall refreshes the same handful of aggregates every few seconds — events per class, the
5-minute time-series, the failed-auth-by-user panel — over a table that streaming ingest keeps growing.
Serving those from a base-table scan on every refresh re-reads the whole corpus each time; a materialized
view serves them from a tiny pre-aggregated table instead. The acceleration is real and large, but it is
not free, and the honest accounting is three numbers, not one:

  - read speedup: how much faster the dashboard refresh is off the MV vs a base scan,
  - maintenance cost: incremental upkeep (merge each ingest batch's partial aggregate) vs the naive
    full-recompute-per-refresh that has the same read speedup but throws the compute saving away, and
  - storage + write-amplification: the extra bytes the MV costs and the extra writes to maintain it.

The catch the number hides: an MV only accelerates the aggregates you decided in advance; an ad-hoc query
still pays the base scan. So an MV trades flexibility and write cost for read latency on a fixed question
set — quantified here rather than asserted. H-MV-SECURITY-01.

The panels are additive count/sum group-bys, which is what lets a streaming MV be maintained by merging
each batch's partial aggregate into the running MV (cost ∝ MV size + batch, not a full base rescan) rather
than recomputing — and which is itself the design constraint: MVs fit additive panels, not arbitrary
analytics.

    python run.py                 # default 20M events, 20 streaming batches
"""

import argparse
import json
import os
import sys
import tempfile
import time

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, os.path.join(HERE, "..", "clickhouse-vs-duckdb"))
from common import BASE_EPOCH, configure_duckdb, time_trials  # noqa: E402
import corpus  # noqa: E402

BASE_MS = BASE_EPOCH * 1000

# Each panel as an additive aggregate: key columns (output name -> base-row expression) and sum columns
# (output name -> base-row aggregate). The base query, the per-batch partial, the incremental merge, and
# the MV serve are all derived from these so they're guaranteed consistent. `order_limit` is appended to
# both base and serve so their row order matches for the answer-equality check.
PANELS = {
    "class_rollup": {
        "keys": [("class_uid", "class_uid"), ("activity_id", "activity_id")],
        "sums": [("n", "count(*)"), ("bin", "sum(bytes_in)"), ("bout", "sum(bytes_out)")],
        "where": "", "order_limit": "ORDER BY class_uid, activity_id",
    },
    "time_series_5m": {
        "keys": [("bucket", f"(time - {BASE_MS}) // 300000")],
        "sums": [("n", "count(*)"), ("bout", "sum(bytes_out)")],
        "where": "", "order_limit": "ORDER BY bucket",
    },
    "failed_auth_by_user": {
        "keys": [("user_name", "user_name")],
        "sums": [("n", "count(*)")],
        "where": "WHERE status_id = 2", "order_limit": "ORDER BY n DESC, user_name LIMIT 50",
    },
}


def _key_names(cfg):
    return [k for k, _ in cfg["keys"]]


def _sum_names(cfg):
    return [s for s, _ in cfg["sums"]]


def base_query(cfg, src):
    keys = ", ".join(f"{e} AS {n}" for n, e in cfg["keys"])
    sums = ", ".join(f"{e} AS {n}" for n, e in cfg["sums"])
    gb = ", ".join(str(i + 1) for i in range(len(cfg["keys"])))
    return (f"SELECT {keys}, {sums} FROM {src} {cfg['where']} GROUP BY {gb} {cfg['order_limit']}")


def serve_query(cfg, mv):
    cols = ", ".join(_key_names(cfg) + _sum_names(cfg))
    return f"SELECT {cols} FROM {mv} {cfg['order_limit']}"


def partial_query(cfg, batch_sel):
    """This batch's partial aggregate (same shape as the MV), to be merged into the running MV."""
    keys = ", ".join(f"{e} AS {n}" for n, e in cfg["keys"])
    sums = ", ".join(f"{e} AS {n}" for n, e in cfg["sums"])
    gb = ", ".join(str(i + 1) for i in range(len(cfg["keys"])))
    return f"SELECT {keys}, {sums} FROM ({batch_sel}) {cfg['where']} GROUP BY {gb}"


def _dir_bytes(path):
    return os.path.getsize(path) if os.path.isfile(path) else \
        sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(path) for f in fs)


def run(total_rows, n_batches):
    work = tempfile.mkdtemp(prefix="mv_accel_")
    try:
        con = configure_duckdb(duckdb.connect())
        batch = total_rows // n_batches

        con.execute("CREATE TABLE base (row_id BIGINT, time BIGINT, activity_id INT, class_uid INT, "
                    "severity_id INT, src_ip VARCHAR, dst_ip VARCHAR, dst_port INT, user_name VARCHAR, "
                    "bytes_in BIGINT, bytes_out BIGINT, status_id INT)")
        # MV starts empty with exactly the panel's (keys, sums) schema.
        for p, cfg in PANELS.items():
            con.execute(f"CREATE TABLE mv_{p} AS {partial_query(cfg, corpus.gen_select(1))} LIMIT 0")

        maint = {p: 0.0 for p in PANELS}
        for bi in range(n_batches):
            start = bi * batch
            sel = corpus.gen_select(batch).replace("FROM range(0, {n})".format(n=batch),
                                                    f"FROM range({start}, {start + batch})")
            # generate the micro-batch ONCE, into memory; insert it, then aggregate the SAME in-hand
            # batch for the MV partial — so maintenance measures aggregation, not row regeneration.
            ab = con.execute(sel).fetch_arrow_table()
            con.register("batch_rows", ab)
            con.execute("INSERT INTO base SELECT * FROM batch_rows")
            for p, cfg in PANELS.items():
                keys = _key_names(cfg)
                sums = _sum_names(cfg)
                resum = ", ".join(f"sum({s}) AS {s}" for s in sums)
                gb = ", ".join(str(i + 1) for i in range(len(keys)))
                t0 = time.perf_counter()
                # merge: re-aggregate (current MV ∪ this batch's partial). Cost ∝ MV rows + the
                # arriving batch's rows, NOT the full base table — that's what makes it incremental.
                con.execute(f"""CREATE OR REPLACE TABLE mv_{p} AS
                    SELECT {', '.join(keys)}, {resum} FROM (
                        SELECT * FROM mv_{p}
                        UNION ALL
                        {partial_query(cfg, 'SELECT * FROM batch_rows')}
                    ) GROUP BY {gb}""")
                maint[p] += (time.perf_counter() - t0) * 1000
            con.unregister("batch_rows")
            del ab

        con.execute(f"COPY base TO '{work}/base.parquet' (FORMAT parquet)")
        base_bytes = _dir_bytes(f"{work}/base.parquet")

        panels = {}
        for p, cfg in PANELS.items():
            con.execute(f"COPY mv_{p} TO '{work}/mv_{p}.parquet' (FORMAT parquet)")
            mv_bytes = _dir_bytes(f"{work}/mv_{p}.parquet")
            bq, sq = base_query(cfg, "base"), serve_query(cfg, f"mv_{p}")
            base_t = time_trials(lambda: con.execute(bq).fetchall(), warmup=1, trials=5)
            serve_t = time_trials(lambda: con.execute(sq).fetchall(), warmup=1, trials=5)
            # naive alternative with the same read speedup: full recompute of the MV from base each
            # refresh (uses the key EXPRESSIONS, since e.g. `bucket` is derived, not a base column).
            recompute = (f"SELECT " + ", ".join(f"{e} AS {n}" for n, e in cfg["keys"]) + ", " +
                         ", ".join(f"{e} AS {n}" for n, e in cfg["sums"]) +
                         f" FROM base {cfg['where']} GROUP BY " +
                         ", ".join(str(i + 1) for i in range(len(cfg["keys"]))))
            recompute_t = time_trials(lambda: con.execute(recompute).fetchall(), warmup=1, trials=3)
            agree = _norm(con.execute(bq).fetchall()) == _norm(con.execute(sq).fetchall())
            mv_rows = con.execute(f"SELECT count(*) FROM mv_{p}").fetchone()[0]
            per_batch = maint[p] / n_batches
            panels[p] = {
                "base_scan_ms": base_t["median_ms"], "base_scan_cv": base_t["cv_pct"],
                "mv_serve_ms": serve_t["median_ms"], "mv_serve_cv": serve_t["cv_pct"],
                "read_speedup": round(base_t["median_ms"] / max(serve_t["median_ms"], 0.001), 1),
                "incremental_maintenance_total_ms": round(maint[p], 1),
                "incremental_maintenance_per_batch_ms": round(per_batch, 2),
                "full_recompute_ms": recompute_t["median_ms"],
                "incremental_vs_recompute_x": round(recompute_t["median_ms"] / max(per_batch, 0.001), 1),
                "mv_rows": mv_rows, "mv_bytes": mv_bytes,
                "storage_overhead_pct": round(100 * mv_bytes / base_bytes, 3),
                "answers_agree": agree,
            }
            print(f"  {p:20} read {base_t['median_ms']:.0f}->{serve_t['median_ms']:.1f}ms "
                  f"({panels[p]['read_speedup']}x)  maint {per_batch:.1f}ms/batch "
                  f"(recompute {recompute_t['median_ms']:.0f}ms, {panels[p]['incremental_vs_recompute_x']}x cheaper)  "
                  f"MV +{panels[p]['storage_overhead_pct']}%  agree={agree}")
        con.close()
        return {"benchmark": "ocsf-mv-acceleration (R5)",
                "evidence_tier": "B (single machine; latencies medians w/ CV; sizes exact)",
                "hypothesis": "H-MV-SECURITY-01",
                "n_rows": total_rows, "n_batches": n_batches, "base_bytes": base_bytes,
                "panels": panels}
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def _norm(rows):
    return sorted(tuple(str(c) for c in r) for r in rows)


def render_md(res):
    rows = "\n".join(
        f"| {p} | {v['base_scan_ms']:.0f} ({v['base_scan_cv']:.0f}%) | {v['mv_serve_ms']:.1f} ({v['mv_serve_cv']:.0f}%) | "
        f"{v['read_speedup']}× | {v['incremental_maintenance_per_batch_ms']} | {v['full_recompute_ms']:.0f} | "
        f"{v['incremental_vs_recompute_x']}× | +{v['storage_overhead_pct']}% |"
        for p, v in res["panels"].items())
    return f"""# Materialized-view acceleration for SOC dashboards — with its cost (R5)

**Tier B · single machine.** {res['n_rows']:,} OCSF events ingested in {res['n_batches']} streaming
batches; three SOC-dashboard panels served two ways — a base-table scan on every refresh vs a tiny
additive materialized view maintained incrementally per batch. Read latencies are medians with CV;
storage is exact on-disk Parquet bytes. H-MV-SECURITY-01.

| panel | base scan ms (cv) | MV serve ms (cv) | read speedup | MV maint ms/batch | full-recompute ms | incremental vs recompute | MV storage overhead |
|---|--:|--:|--:|--:|--:|--:|--:|
{rows}

Base table: {res['base_bytes']/1e6:.0f} MB.

## Reading

The read speedup is the headline a dashboard owner sees: serving a panel from the pre-aggregated MV
collapses a full-corpus scan to a read of a few hundred rows. But the cost is in the other columns. The
MV has to be maintained, and the maintenance strategy is where the real engineering choice sits:
recomputing the aggregate from the base table on every refresh delivers the same read speedup while
throwing the compute saving away (it re-scans the whole corpus each time), whereas merging each ingest
batch's partial aggregate keeps the MV current for a small per-batch cost — the `incremental vs recompute`
column is how much cheaper the streaming-correct path is. The storage overhead is small here because these
panels collapse to few groups, but it scales with the aggregate's cardinality, not the base table's.

The constraint the speedup hides is that an MV only answers the questions you pre-decided: all three
panels here are additive count/sum group-bys, which is exactly what lets them be maintained incrementally,
and an ad-hoc query — a new pivot, a different filter, a hunt — still pays the base scan. So a
materialized view is a bet that a fixed set of questions is worth paying storage and per-batch maintenance
to answer fast, and it's the right bet precisely for the always-on SOC dashboard whose question set is
stable, not for exploratory analysis. Tier B, single machine; the speedup/maintenance/storage trade is the
transferable finding, the magnitudes are this corpus's.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=20_000_000)
    ap.add_argument("--batches", type=int, default=20)
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    out = os.path.join(rdir, "results.json")
    if args.render_only:
        res = json.load(open(out))
    else:
        res = run(args.rows, args.batches)
        with open(out, "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "RESULTS.md"), "w") as f:
        f.write(render_md(res))
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()

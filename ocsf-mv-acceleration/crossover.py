"""T2.4 — where does incremental MV maintenance beat full recompute? The base:batch crossover.

R5 reported incremental-vs-recompute at ONE base size and found it "break-even for high-cardinality at this
base." That's a point, not a curve. The maintenance economics are a ratio: a full recompute costs ∝ the
BASE table it rescans, while an incremental merge costs ∝ (MV rows + the arriving BATCH). So:
  - for a BOUNDED-cardinality MV (group count saturates), incremental per-batch cost goes ~flat while
    recompute grows with the base, so incremental wins once base:batch is large enough — there's a crossover.
  - for an UNBOUNDED-cardinality MV (groups grow with the base), the MV is ~as big as the base, so the merge
    re-aggregates almost everything every batch and incremental never pulls ahead.

This sweeps the base size at a fixed batch for one bounded and one unbounded high-cardinality panel, and
reports the base:batch ratio where incremental crosses recompute. H-MV-SECURITY-01 (the maintenance leg).

    python crossover.py        # base in {1M,5M,20M,40M}, batch 200k
"""

import argparse
import json
import os
import sys
import tempfile

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, os.path.join(HERE, "..", "clickhouse-vs-duckdb"))
from common import configure_duckdb, time_trials  # noqa: E402
import corpus  # noqa: E402

BATCH = 200_000
BASE_SIZES = [1_000_000, 5_000_000, 20_000_000, 40_000_000]

# Two high-cardinality panels (additive count/sum group-bys), differing in whether the group count is bounded.
PANELS = {
    "bounded_high_card (user_name × dst_port)": {
        "keys": ["user_name", "dst_port"],           # 2000 users × 8 ports = 16,000 groups (saturates)
    },
    "unbounded_high_card (src_ip)": {
        "keys": ["src_ip"],                           # distinct src_ip grows with the base (no saturation)
    },
}


def _agg_sql(keys, src):
    k = ", ".join(keys)
    gb = ", ".join(str(i + 1) for i in range(len(keys)))
    return f"SELECT {k}, count(*) AS n, sum(bytes_out) AS bout FROM {src} GROUP BY {gb}"


def _batch_select(start, n):
    return corpus.gen_select(n).replace("FROM range(0, {n})".format(n=n),
                                         f"FROM range({start}, {start + n})")


def run(base_sizes, batch):
    work = tempfile.mkdtemp(prefix="mv_crossover_")
    try:
        con = configure_duckdb(duckdb.connect())
        rows = []
        for S in base_sizes:
            # base table at size S (one shot)
            con.execute(f"CREATE OR REPLACE TABLE base AS {_batch_select(0, S)}")
            # one disjoint arriving batch (rows the base doesn't already contain)
            con.execute(f"CREATE OR REPLACE TABLE batch_rows AS {_batch_select(S, batch)}")
            for label, cfg in PANELS.items():
                keys = cfg["keys"]
                # steady-state MV = full aggregate of the base
                con.execute(f"CREATE OR REPLACE TABLE mv AS {_agg_sql(keys, 'base')}")
                mv_rows = con.execute("SELECT count(*) FROM mv").fetchone()[0]
                # full recompute: re-aggregate the whole base (cost ∝ base)
                recompute = _agg_sql(keys, "base")
                rt = time_trials(lambda: con.execute(recompute).fetchall(), warmup=1, trials=3)
                # incremental merge: re-aggregate (MV ∪ this batch's partial) -> cost ∝ MV rows + batch
                resum = "sum(n) AS n, sum(bout) AS bout"
                gb = ", ".join(str(i + 1) for i in range(len(keys)))
                merge = (f"SELECT {', '.join(keys)}, {resum} FROM "
                         f"(SELECT * FROM mv UNION ALL {_agg_sql(keys, 'batch_rows')}) GROUP BY {gb}")
                it = time_trials(lambda: con.execute(merge).fetchall(), warmup=1, trials=3)
                ratio = round(rt["median_ms"] / max(it["median_ms"], 0.001), 2)  # >1 ⇒ incremental wins
                rows.append({
                    "panel": label, "base_rows": S, "batch_rows": batch,
                    "base_to_batch_ratio": S // batch, "mv_rows": mv_rows,
                    "recompute_ms": rt["median_ms"], "recompute_cv": rt["cv_pct"],
                    "incremental_ms": it["median_ms"], "incremental_cv": it["cv_pct"],
                    "recompute_over_incremental": ratio, "incremental_wins": ratio > 1.0,
                })
                print(f"  {label:34} base={S//1_000_000}M (ratio {S//batch:>4}:1)  "
                      f"mv_rows={mv_rows:>8}  recompute={rt['median_ms']:.1f}ms  "
                      f"incremental={it['median_ms']:.1f}ms  →{ratio}× {'WIN' if ratio>1 else 'lose'}")
        con.close()

        # crossover: lowest base:batch ratio at which incremental first wins, per panel
        crossover = {}
        for label in PANELS:
            wins = [r for r in rows if r["panel"] == label and r["incremental_wins"]]
            crossover[label] = min((r["base_to_batch_ratio"] for r in wins), default=None)
        return {"benchmark": "ocsf-mv-acceleration crossover (T2.4)",
                "evidence_tier": "B (single machine; latency medians w/ CV)",
                "hypothesis": "H-MV-SECURITY-01 (maintenance leg)",
                "batch_rows": batch, "base_sizes": base_sizes,
                "crossover_base_to_batch_ratio": crossover, "rows": rows}
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def render_md(res):
    def block(label):
        return "\n".join(
            f"| {r['base_to_batch_ratio']}:1 | {r['base_rows']//1_000_000}M | {r['mv_rows']:,} | "
            f"{r['recompute_ms']:.1f} | {r['incremental_ms']:.1f} | {r['recompute_over_incremental']}× | "
            f"{'✅ incremental' if r['incremental_wins'] else '❌ recompute'} |"
            for r in res["rows"] if r["panel"] == label)
    blocks = "\n\n".join(
        f"### {label}\n\n| base:batch | base | MV rows | recompute ms | incremental ms | "
        f"recompute/incremental | winner |\n|--:|--:|--:|--:|--:|--:|---|\n{block(label)}"
        for label in PANELS)
    cx = res["crossover_base_to_batch_ratio"]
    cx_lines = "\n".join(
        f"- **{label}**: " + (f"incremental first wins at **base:batch ≈ {v}:1**"
                              if v else "incremental **never wins** in the swept range (MV grows with base)")
        for label, v in cx.items())
    return f"""# MV maintenance: the base:batch crossover (T2.4)

**Tier B · single machine.** R5 gave incremental-vs-recompute at one base size; this sweeps the base at a
fixed batch ({res['batch_rows']:,} rows) to find the ratio where incremental maintenance overtakes full
recompute, for a bounded- and an unbounded-cardinality high-card MV. `recompute/incremental > 1` ⇒
incremental wins (a full recompute costs ∝ base; an incremental merge costs ∝ MV rows + batch).

{blocks}

## Crossover

{cx_lines}

## Reading

The maintenance economics are a ratio, not a verdict. For a **bounded**-cardinality MV (here user_name ×
dst_port, which saturates at 16,000 groups), the incremental merge re-aggregates a roughly fixed MV plus
the arriving batch, so its cost is ~flat in the base size, while a full recompute rescans the whole base —
so once the base is large enough relative to the batch, incremental wins, and the crossover above is where.
That is the regime a streaming SOC lives in (a huge, growing base table and small frequent batches), which
is exactly where incremental maintenance pays. For an **unbounded**-cardinality MV (src_ip, whose group
count grows with the base), the MV is nearly as large as the base, the merge re-aggregates almost
everything every batch, and incremental never pulls ahead — so the honest design rule is: incremental
maintenance is the right call for **bounded-cardinality** panels at high base:batch, and an
unbounded-cardinality "MV" is really just a recompute wearing a hat. Tier B, single machine; the crossover
ratio is this corpus's, the shape (bounded saturates → wins; unbounded doesn't) is the transferable finding.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=BATCH)
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    out = os.path.join(rdir, "crossover.json")
    if args.render_only:
        res = json.load(open(out))
    else:
        res = run(BASE_SIZES, args.batch)
        json.dump(res, open(out, "w"), indent=2, sort_keys=True)
    open(os.path.join(rdir, "CROSSOVER.md"), "w").write(render_md(res))
    print(f"\ncrossover (base:batch where incremental wins): {res['crossover_base_to_batch_ratio']}")
    print("wrote results/crossover.json + CROSSOVER.md")


if __name__ == "__main__":
    main()

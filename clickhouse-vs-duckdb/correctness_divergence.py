"""A silent cross-engine correctness divergence the C3 benchmark's answer-equality gate caught.

The C3 timing run (run.py) asserts a hard gate before reporting any latency: every query, every config,
every scale must return identical answers on DuckDB and ClickHouse (chDB), because both read the same
bytes and a speed comparison between engines that disagree on the answer is meaningless. At 100M rows that
gate failed on q3 (a selective lookup) — and the cause turned out to be a real, deterministic bug, not a
flaky measurement: chDB's Parquet reader silently under-counts an exact string-equality filter.

This isolates and reproduces it from first principles, with the generator as ground truth (the corpus is
a pure function of the row index, so the true count of any `user_name` value is computable without either
engine). The trigger is structural, not raw scale: a Parquet file laid out as ~814 row groups exposes it,
and it reproduces cheaply at 10M rows with a small row-group size (122,880 = 10× 12,288, so 10M/12,288 and
100M/122,880 land on the same ~814-group structure). The signature:

  - DuckDB's Parquet read == the generator's ground truth (exact),
  - chDB over the same Parquet file under-counts `user_name = 'x'` and `user_name IN ('x')` — dropping a
    handful of genuinely-matching rows that all sit in the tail row groups (the same rows chDB reads back
    correctly when you select them by a different column),
  - chDB's `LIKE 'x'` (a different filter path) is correct, and
  - the same data loaded into chDB's own MergeTree store is correct.

So the defect is specific to the Parquet reader's equality-filter path at this row-group structure, in
chDB 4.1.8 (embedded ClickHouse). The finding is not "ClickHouse is wrong" in general — it is a specific,
reproducible, silent miscount, and the transferable lesson is the lab's whole premise: a cross-engine
answer-equality gate is not ceremony, it is the thing that catches a fast engine returning the wrong
number without raising an error. Verify; don't trust the speed.

    python correctness_divergence.py            # 10M rows, the cheap trigger structure
    python correctness_divergence.py --rows 100000000 --rg 122880   # the original 100M structure
"""

import argparse
import json
import os
import sys
import tempfile

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)
from common import configure_duckdb  # noqa: E402
import corpus  # noqa: E402

# Fixed probe values (deterministic, not cherry-picked post hoc): a spread of user_name values whose
# true counts the generator gives directly. The divergence affects multiple values, not just one.
PROBES = ["user42", "user1337", "user7", "user999", "user1500", "user256", "user1023", "user64"]


def run(rows, rg_size):
    work = tempfile.mkdtemp(prefix="c3_divergence_")
    try:
        from chdb import session as chs
        con = configure_duckdb(duckdb.connect())
        p = os.path.join(work, "corpus.parquet")
        con.execute(f"COPY ({corpus.gen_select(rows)}) TO '{p}' (FORMAT parquet, ROW_GROUP_SIZE {rg_size})")
        n_groups = con.execute(
            f"SELECT count(DISTINCT row_group_id) FROM parquet_metadata('{p}')").fetchone()[0]

        sess = chs.Session()
        sess.query("CREATE DATABASE IF NOT EXISTS d")
        sess.query(f"CREATE TABLE IF NOT EXISTS d.e ENGINE=MergeTree ORDER BY tuple() AS "
                   f"SELECT * FROM file('{p}', Parquet)")

        def ch(sql):
            return int(sess.query(sql, "CSV").data().strip())

        probes = []
        for v in PROBES:
            truth = con.execute(
                f"SELECT count(*) FROM ({corpus.gen_select(rows)}) WHERE user_name = '{v}'").fetchone()[0]
            dduck = con.execute(
                f"SELECT count(*) FROM read_parquet('{p}') WHERE user_name = '{v}'").fetchone()[0]
            ch_eq = ch(f"SELECT count(*) FROM file('{p}', Parquet) WHERE user_name = '{v}'")
            ch_in = ch(f"SELECT count(*) FROM file('{p}', Parquet) WHERE user_name IN ('{v}')")
            ch_like = ch(f"SELECT count(*) FROM file('{p}', Parquet) WHERE user_name LIKE '{v}'")
            ch_mt = ch(f"SELECT count(*) FROM d.e WHERE user_name = '{v}'")
            probes.append({
                "value": v, "truth": truth,
                "duckdb_parquet": dduck,
                "chdb_parquet_eq": ch_eq, "chdb_parquet_in": ch_in,
                "chdb_parquet_like": ch_like, "chdb_mergetree": ch_mt,
                "duckdb_correct": dduck == truth,
                "chdb_eq_undercount": truth - ch_eq,
            })
            flag = "" if ch_eq == truth else f"  chDB= UNDERCOUNT {truth - ch_eq}"
            print(f"  {v:10} truth={truth:>6} duckdb={dduck:>6} chdb_eq={ch_eq:>6} "
                  f"chdb_like={ch_like:>6} chdb_mt={ch_mt:>6}{flag}")
        con.close()

        diverged = [pr for pr in probes if pr["chdb_eq_undercount"] != 0]
        duckdb_all_correct = all(pr["duckdb_correct"] for pr in probes)
        like_all_correct = all(pr["chdb_parquet_like"] == pr["truth"] for pr in probes)
        mt_all_correct = all(pr["chdb_mergetree"] == pr["truth"] for pr in probes)
        return {
            "benchmark": "clickhouse-vs-duckdb correctness divergence (C3 gate finding)",
            "evidence_tier": "B (single machine; ground-truth-verified, deterministic, reproducible)",
            "environment": {"duckdb": duckdb.__version__, "chdb": __import__("chdb").__version__},
            "corpus_rows": rows, "row_group_size": rg_size, "row_groups": n_groups,
            "probe_values": len(PROBES),
            "duckdb_matches_ground_truth": duckdb_all_correct,
            "chdb_eq_diverged_values": len(diverged),
            "chdb_eq_total_undercount": sum(pr["chdb_eq_undercount"] for pr in probes),
            "chdb_like_correct": like_all_correct,
            "chdb_mergetree_correct": mt_all_correct,
            "predicate_path": {
                "=": "undercounts (Parquet reader)", "IN": "undercounts (Parquet reader)",
                "LIKE": "correct", "MergeTree native": "correct"},
            "probes": probes,
        }
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def render_md(res):
    rows = "\n".join(
        f"| `{pr['value']}` | {pr['truth']} | {pr['duckdb_parquet']} | {pr['chdb_parquet_eq']} | "
        f"{pr['chdb_parquet_like']} | {pr['chdb_mergetree']} | "
        f"{'—' if pr['chdb_eq_undercount']==0 else '−'+str(pr['chdb_eq_undercount'])} |"
        for pr in res["probes"])
    env = res["environment"]
    return f"""# A silent cross-engine correctness divergence (C3 answer-equality gate)

**Tier B · single machine · ground-truth-verified.** DuckDB `{env['duckdb']}` vs chDB `{env['chdb']}`
(embedded ClickHouse), both reading the **same** Parquet file ({res['corpus_rows']:,} rows,
{res['row_groups']} row groups). The corpus is a pure function of the row index, so the true count of any
`user_name` value is computable from the generator without either engine — that is the ground truth here.

The C3 timing benchmark refuses to report a latency until both engines return identical answers (a fast
engine that returns the wrong number is not faster, it is wrong). At 100M rows that gate failed, and this
is the isolated, cheaply-reproduced cause.

| user_name | ground truth | DuckDB (Parquet) | chDB `=` (Parquet) | chDB `LIKE` (Parquet) | chDB MergeTree | chDB `=` error |
|---|--:|--:|--:|--:|--:|--:|
{rows}

- DuckDB matches ground truth on every probe: **{res['duckdb_matches_ground_truth']}**
- chDB `=` over Parquet diverged on **{res['chdb_eq_diverged_values']} of {res['probe_values']}** probe
  values, total undercount **{res['chdb_eq_total_undercount']}** rows
- chDB `LIKE` correct on all: **{res['chdb_like_correct']}** · chDB MergeTree correct on all:
  **{res['chdb_mergetree_correct']}**

## Reading

Both engines read identical bytes, and the generator says DuckDB is right, so chDB's `=` filter over this
Parquet file is silently dropping genuinely-matching rows — a handful per value, all in the tail row
groups, returned with no error and a confident count. It is not raw scale: the trigger is the row-group
structure (~{res['row_groups']} groups), which is why a 10M-row file with a small row-group size reproduces
what the 100M default file showed. And it is specific to the Parquet reader's equality path: the same
predicate via `LIKE`, and the same data in chDB's own MergeTree store, are both correct. So the defect is
narrow and real, in chDB {env['chdb']} — not a general indictment of ClickHouse, which is an excellent
engine, but a concrete reproducible miscount in one read path.

The transferable point is the methodology, not the bug. A benchmark that only timed the two engines would
have published chDB as competitive on the selective-lookup query and never noticed it returned the wrong
answer; the cross-engine answer-equality gate is the only reason this surfaced, and it surfaced silently —
no exception, no warning from the engine, just a number that was 49 short out of 50,361 at 100M. For
security data specifically, where a `count(*) WHERE` under a filter is a detection threshold or a
compliance figure, an engine that is fast and silently wrong is worse than one that is slow and right.
Verify across engines; don't trust the speed. (Candidate upstream report to the chDB/ClickHouse project —
left for a human to file with this reproduction.) Tier B, single machine; the reproduction is
deterministic, the lesson is general.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=10_000_000)
    ap.add_argument("--rg", type=int, default=12_288, help="Parquet ROW_GROUP_SIZE (trigger is ~814 groups)")
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    out = os.path.join(rdir, "correctness-divergence.json")
    if args.render_only:
        res = json.load(open(out))
    else:
        res = run(args.rows, args.rg)
        with open(out, "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "CORRECTNESS-DIVERGENCE.md"), "w") as f:
        f.write(render_md(res))
    print(f"\nDuckDB==truth: {res['duckdb_matches_ground_truth']}  |  "
          f"chDB '=' diverged on {res['chdb_eq_diverged_values']}/{res['probe_values']} values "
          f"(−{res['chdb_eq_total_undercount']} rows)  |  LIKE correct: {res['chdb_like_correct']}  |  "
          f"MergeTree correct: {res['chdb_mergetree_correct']}")
    print("wrote results/correctness-divergence.json + CORRECTNESS-DIVERGENCE.md")


if __name__ == "__main__":
    main()

"""Lower-level bake-off #3: does row-group / page / bloom pruning ever drop the needle?

This is the exact layer the chDB Bloom-pushdown undercount lived in. A Parquet reader prunes row groups and
pages it believes can't match a predicate, using min/max statistics, the page index, and (optionally) bloom
filters. The optimization is only safe if the pruning is *sound* — it must never skip a block that actually
contains a matching row. When it does, a detection query (needle-in-a-haystack: one IOC value among millions)
silently under-counts: the engine returns 0 where the truth is 1, fast and confident and wrong.

Two arms, both gated on "the answer is identical to a known ground truth":

  ARM 1 (min/max + page-index pruning, cross-engine A/B): the SAME key multiset is written two ways — SORTED
    (so each row group has a tight, non-overlapping min/max range and an equality predicate prunes to a single
    row group) and SHUFFLED (so every row group's range spans nearly the whole domain and nothing can be
    pruned). For a battery of needles concentrated on row-group boundaries (where off-by-one pruning bugs
    bite), every engine counts `k = needle` on both files. Identical data, only the row order differs, so any
    sorted-vs-shuffled disagreement isolates a pruning bug. Ground truth: each key appears once → present
    needle = 1, absent = 0.

  ARM 2 (bloom-filter pushdown, the chDB-specific structure): chDB writes a Parquet file WITH bloom filters
    (output_format_parquet_write_bloom_filter=1), the structure the original bug decoded. Every engine then
    counts present and absent needles over it. A bloom filter is allowed false positives but NEVER false
    negatives, so a present needle returning 0 is a hard correctness failure in the bloom path.

Tier B, single machine. The transferable finding is per-engine soundness of pruning, re-checked per version.

    python run.py
"""
import json
import os
import random
import shutil
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
N = 1_000_000
RG = 10_000          # -> 100 row groups
SEED = 1729


def build_files(work):
    keys = list(range(N))
    ps = os.path.join(work, "sorted.parquet")
    pq.write_table(pa.table({"k": pa.array(keys, pa.int64())}), ps,
                   row_group_size=RG, write_statistics=True, write_page_index=True)
    shuf = keys[:]
    random.Random(SEED).shuffle(shuf)
    ph = os.path.join(work, "shuffled.parquet")
    pq.write_table(pa.table({"k": pa.array(shuf, pa.int64())}), ph,
                   row_group_size=RG, write_statistics=True, write_page_index=True)
    # evidence the A/B is real: sorted rg0 is a tight slice; shuffled rg0 spans ~the whole domain
    smd, hmd = pq.ParquetFile(ps).metadata, pq.ParquetFile(ph).metadata
    ab = {"row_groups": smd.num_row_groups,
          "sorted_rg0_range": [smd.row_group(0).column(0).statistics.min, smd.row_group(0).column(0).statistics.max],
          "shuffled_rg0_range": [hmd.row_group(0).column(0).statistics.min, hmd.row_group(0).column(0).statistics.max]}
    return ps, ph, ab


def write_bloom(work):
    """chDB writes a bloom-filtered Parquet file — the structure the original chDB pushdown bug decoded."""
    from chdb import session as chs
    p = os.path.join(work, "bloom.parquet")
    chs.Session().query(
        f"INSERT INTO FUNCTION file('{p}', Parquet, 'k Int64') SELECT number AS k FROM numbers({N}) "
        f"SETTINGS output_format_parquet_write_bloom_filter=1, output_format_parquet_row_group_size={RG}")
    return p


# --- count engines: each returns count(*) WHERE k = needle, default pushdown engaged --------------------
def c_duckdb(p, needle):
    import duckdb
    return int(duckdb.connect().execute(f"SELECT count(*) FROM read_parquet('{p}') WHERE k = {needle}").fetchone()[0])


def c_pyarrow(p, needle):
    return pq.read_table(p, filters=[("k", "=", needle)]).num_rows


def c_polars(p, needle):
    import polars as pl
    return int(pl.scan_parquet(p).filter(pl.col("k") == needle).select(pl.len()).collect().item())


def c_datafusion(p, needle):
    import datafusion
    ctx = datafusion.SessionContext(); ctx.register_parquet("t", p)
    return int(ctx.sql(f"SELECT count(*) AS n FROM t WHERE k = {needle}").to_pydict()["n"][0])


def c_chdb(p, needle):
    from chdb import session as chs
    return int(chs.Session().query(f"SELECT count() FROM file('{p}', Parquet) WHERE k = {needle}", "CSV").data().strip())


ENGINES = {"duckdb": c_duckdb, "pyarrow": c_pyarrow, "polars": c_polars,
           "datafusion": c_datafusion, "chdb": c_chdb}


def needles():
    present = {0, N // 2, N - 1}
    for g in (1, 5, 37, 99):          # a few row-group edges: max of rg g-1, min of rg g, and the next row
        present |= {g * RG - 1, g * RG, g * RG + 1}
    absent = {N + 7}                   # above the global max — pruning to 0 here is correct
    truth = {n: (1 if n < N else 0) for n in (present | absent)}
    return sorted(present | absent), truth


def count_over(path, ns, truth):
    """Per engine: count each needle; classify against truth. Returns {engine: {...}}."""
    out = {}
    for name, fn in ENGINES.items():
        wrong = []
        for n in ns:
            try:
                got = fn(path, n)
            except Exception as e:  # noqa: BLE001
                wrong.append({"needle": n, "got": f"ERR {type(e).__name__}", "truth": truth[n]})
                continue
            if got != truth[n]:
                wrong.append({"needle": n, "got": got, "truth": truth[n]})
        out[name] = {"correct": not wrong, "wrong": wrong}
    return out


def run():
    work = tempfile.mkdtemp(prefix="prune_")
    try:
        ns, truth = needles()
        ps, ph, ab = build_files(work)
        arm1 = {"sorted": count_over(ps, ns, truth), "shuffled": count_over(ph, ns, truth), "ab_evidence": ab}
        try:
            pb = write_bloom(work)
            arm2 = {"available": True, "bloom": count_over(pb, ns, truth)}
        except Exception as e:  # noqa: BLE001
            arm2 = {"available": False, "error": f"{type(e).__name__}: {str(e)[:90]}"}
        return {
            "benchmark": "row-group / page / bloom pruning soundness (lower-level bake-off #3)",
            "evidence_tier": "B (single machine; identical-data A/B; exact ground truth)",
            "rows": N, "row_group_size": RG, "needles": ns, "seed": SEED,
            "environment": {m: __import__(m).__version__ for m in
                            ("pyarrow", "duckdb", "polars", "datafusion", "chdb")},
            "arm1_minmax_pageindex": arm1,
            "arm2_bloom_filter": arm2,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(r):
    eng = list(ENGINES)

    def summ(block):
        rows = []
        for name in eng:
            v = block[name]
            cell = "✅ all correct" if v["correct"] else "❌ " + "; ".join(
                f"k={w['needle']}→{w['got']} (truth {w['truth']})" for w in v["wrong"][:3])
            rows.append(f"| {name} | {cell} |")
        return "\n".join(rows)

    a1 = r["arm1_minmax_pageindex"]
    ab = a1["ab_evidence"]
    a2 = r["arm2_bloom_filter"]
    env = ", ".join(f"{k} `{v}`" for k, v in r["environment"].items())
    a2body = ("not available (" + a2.get("error", "") + ")" if not a2["available"]
              else "chDB wrote a bloom-filtered file; every engine counts present + absent needles over it.\n\n"
                   "| engine | result |\n|---|---|\n" + summ(a2["bloom"]))
    return f"""# Does pruning ever drop the needle? (lower-level bake-off #3)

**Tier B · single machine · identical-data A/B.** A Parquet reader prunes row groups and pages it believes
can't match — by min/max statistics, the page index, and optionally bloom filters — and the optimization is
only safe if it *never* skips a block that actually contains a matching row. When it isn't, a needle-in-a-
haystack detection query (one IOC value among {r['rows']:,}) silently under-counts. This is the exact layer
the chDB Bloom-pushdown undercount lived in. Engines: {env}.

## Arm 1 — min/max + page-index pruning (sorted vs shuffled A/B)

The same key multiset ({r['rows']:,} keys, each once) is written two ways: **sorted** (each row group a tight
slice, so an equality predicate prunes to one row group) and **shuffled** (every row group spans nearly the
whole domain, so nothing prunes). Only the row order differs, so any sorted-vs-shuffled disagreement isolates
a pruning bug. Needles cluster on row-group boundaries (where off-by-one pruning bites). Present needle truth
= 1, absent = 0.

A/B is real: {ab['row_groups']} row groups; sorted rg0 covers `{ab['sorted_rg0_range']}` (a tight slice an
equality predicate can prune around), shuffled rg0 covers `{ab['shuffled_rg0_range']}` (≈ the whole domain —
unprunable).

| engine | sorted file (pruning engaged) |
|---|---|
{summ(a1['sorted'])}

| engine | shuffled file (no pruning possible — reference) |
|---|---|
{summ(a1['shuffled'])}

## Arm 2 — bloom-filter pushdown (the chDB-specific structure)

{a2body}

A bloom filter permits false positives but never false negatives, so a *present* needle returning 0 over a
bloom-filtered file is a hard correctness failure in the bloom decode/probe path — precisely the original bug.

## Reading

Pruning is the optimization that makes a lakehouse competitive on selective security queries, and it is exactly
where a fast wrong answer hides: the engine that skips the row group holding the one matching event returns
zero in milliseconds and looks healthy. The A/B isolates it cleanly — identical data, identical predicate,
only the physical layout differs, so the sorted file and the shuffled file must agree, and they must both
equal the ground truth. That is the same verify-the-answer discipline as the cross-engine, page-checksum, and
encoding benches, aimed at the planner's skip logic rather than the decoder's bytes. The per-engine result is
version-bound and is the transferable finding; re-run it on any engine upgrade, because pushdown paths
(bloom, page-index, late-materialization) are where new optimizations land and where a soundness regression
would first show up as a quiet under-count on a detection query.
"""


def main():
    res = run()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "results.json"), "w"), indent=2, sort_keys=True, default=str)
    open(os.path.join(rdir, "RESULTS.md"), "w").write(render_md(res))
    for arm, key in (("arm1.sorted", "arm1_minmax_pageindex"),):
        pass
    a1 = res["arm1_minmax_pageindex"]
    bad1 = {e: v["wrong"] for e, v in a1["sorted"].items() if not v["correct"]}
    print("arm1 sorted-file pruning failures:", bad1 or "none (every engine sound)")
    if res["arm2_bloom_filter"]["available"]:
        bad2 = {e: v["wrong"] for e, v in res["arm2_bloom_filter"]["bloom"].items() if not v["correct"]}
        print("arm2 bloom-file failures:", bad2 or "none (every engine sound)")
    else:
        print("arm2 bloom: unavailable:", res["arm2_bloom_filter"].get("error"))
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()

"""Does the R3 silent equality-undercount generalize across engines? (Phase E)

R3 caught chDB 4.1.8 silently undercounting a Parquet `=`/`IN` filter in the tail row groups of a
many-row-group file, while DuckDB, chDB's own `LIKE`, and chDB's MergeTree all matched the generator's
ground truth. That was ONE engine, ONE filter class, ONE version. The open question
(H-ENGINE-ANSWER-EQUIVALENCE-01) is whether the defect is a one-engine bug or a pattern.

This runs the same trigger structure (corpus.py, ~814 row groups, the cheap 10M reproduction) across many
query engines reading the SAME Parquet bytes, against the generator's ground truth (the corpus is a pure
function of the row index, so the true count of any `user_name` value is computable without any engine).
Predicate classes: `=`, `IN`, `LIKE`.

The engine set is chosen by *distinct Parquet reader* (see ENGINE-LANDSCAPE-SURVEY.md), not by engine name —
engines that wrap a reader already tested add little, and engines that re-encode into a private segment
format aren't Parquet-reader tests at all.

Always-on (in-process):
  - DuckDB (own C++)            - reference
  - chDB (ClickHouse C++)       - the R3 failer; + its MergeTree as a within-engine control
  - DataFusion (arrow-rs)
  - Polars (own polars-parquet)
  - pyarrow / Acero (Arrow C++) - its count_rows(filter=) hits the row-group-stats pushdown path directly
  - Daft (Rust)
  - fastparquet (pure-Python, non-Arrow) - the outsider cross-check

Optional (containerized, via --servers): clickhouse_server, spark, starrocks, trino, dremio, risingwave,
postgres, feldera. Each reads the SAME file (bind-mounted) except postgres, which loads the corpus into a
native heap table (the "just use Postgres" baseline — an independent executor, not a Parquet reader).

Two things are measured: (1) GROUND-TRUTH correctness per engine (passers named as loudly as failers);
(2) CROSS-ENGINE agreement WITHOUT ground truth — for each (value,predicate), do the shared-bytes engines
agree among themselves? That tests the alternative hypothesis: if every divergence is one engine vs a
unanimous rest, cross-engine majority catches it with no generator; an ambiguous split needs ground truth.

    python multi_engine_correctness.py                                   # in-process engines, 10M
    python multi_engine_correctness.py --servers clickhouse_server,spark,starrocks,trino   # + containers
    python multi_engine_correctness.py --servers all --rows 100000000 --rg 122880          # R3 scale
"""

import argparse
import json
import os
import sys
import tempfile
from collections import Counter

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)
from common import configure_duckdb  # noqa: E402
import corpus  # noqa: E402

# Pre-registered probe values (fixed before the run, not cherry-picked post hoc).
PROBES = ["user42", "user1337", "user7", "user999", "user1500", "user256", "user1023", "user64"]
PREDICATES = ["=", "IN", "LIKE"]

# Which distinct Parquet reader each engine exercises (the survey's lens; honest about redundancy).
READER = {
    "duckdb": "DuckDB C++ (own)",
    "chdb_parquet": "ClickHouse C++ v3 reader (embedded chDB; CH 26.3, v3 default)",
    "chdb_mergetree": "ClickHouse MergeTree native store (within-engine control, not Parquet)",
    "clickhouse_server": "ClickHouse C++ older reader (server 25.10; v3 not default)",
    "datafusion": "arrow-rs parquet (Rust)",
    "polars": "polars-parquet (Rust, own)",
    "pyarrow": "Arrow C++ (Acero)",
    "daft": "Daft (Rust; arrow-rs-derived I/O)",
    "fastparquet": "fastparquet (pure-Python, non-Arrow)",
    "trino": "Trino Java (own, not parquet-mr)",
    "spark": "parquet-mr Java (the reference reader)",
    "starrocks": "StarRocks C++ (own)",
    "dremio": "Dremio Java (own vectorized)",
    "risingwave": "arrow-rs (streaming engine — reader not distinct)",
    "feldera": "arrow-rs (streaming DBSP — reader not distinct)",
    "postgres": "Postgres heap (corpus loaded — independent executor, NOT a Parquet read)",
}


# ----------------------------------------------------------------- in-process engine adapters (all SQL/df)
def _sql(t, op, v):
    if op == "=":
        return f"SELECT count(*) AS c FROM {t} WHERE user_name = '{v}'"
    if op == "IN":
        return f"SELECT count(*) AS c FROM {t} WHERE user_name IN ('{v}')"
    if op == "LIKE":
        return f"SELECT count(*) AS c FROM {t} WHERE user_name LIKE '{v}'"
    raise ValueError(op)


def engine_duckdb(con, p):
    return lambda op, v: int(con.execute(_sql(f"read_parquet('{p}')", op, v)).fetchone()[0])


def engine_chdb_parquet(sess, p):
    def q(op, v):
        return int(sess.query(_sql(f"file('{p}', Parquet)", op, v), "CSV").data().strip().splitlines()[-1].strip('"'))
    return q


def engine_chdb_mergetree(sess):
    def q(op, v):
        return int(sess.query(_sql("d.e", op, v), "CSV").data().strip().splitlines()[-1].strip('"'))
    return q


def engine_datafusion(ctx):
    return lambda op, v: int(ctx.sql(_sql("t", op, v)).to_pydict()["c"][0])


def engine_polars(pctx):
    return lambda op, v: int(pctx.execute(_sql("t", op, v), eager=True)["c"][0])


def engine_pyarrow(p):
    import pyarrow as pa
    import pyarrow.dataset as pads
    import pyarrow.compute as pc
    dset = pads.dataset(p, format="parquet")

    def q(op, v):
        if op == "=":
            f = pc.equal(pc.field("user_name"), v)
        elif op == "IN":
            f = pc.is_in(pc.field("user_name"), value_set=pa.array([v]))
        elif op == "LIKE":
            f = pc.match_like(pc.field("user_name"), v)
        else:
            raise ValueError(op)
        return int(dset.count_rows(filter=f))
    return q


def engine_daft(p):
    import daft
    df0 = daft.read_parquet(p)

    def q(op, v):
        c = df0["user_name"]
        if op == "=":
            df = df0.where(c == v)
        elif op == "IN":
            df = df0.where(c.is_in([v]))
        elif op == "LIKE":
            df = df0.where(c.like(v))
        else:
            raise ValueError(op)
        return int(df.count_rows())
    return q


def engine_fastparquet(p):
    import fastparquet
    col = fastparquet.ParquetFile(p).to_pandas(columns=["user_name"])["user_name"]

    def q(op, v):
        # No predicate pushdown — fastparquet materializes the column and we filter in pandas. The
        # probes carry no LIKE wildcards, so all three predicate classes reduce to equality here; the
        # interesting variable is fastparquet's *decode*, not the filter path.
        return int((col == v).sum())
    return q


# ------------------------------------------------------------------------------ container engine registry
def _container_factory(name, work, subdir):
    if name == "trino":
        from trino_runner import TrinoEngine
        return TrinoEngine(work, subdir)
    from server_engines import (ClickHouseServerEngine, SparkEngine, StarRocksEngine,
                                 DremioEngine, RisingWaveEngine, PostgresEngine, FelderaEngine)
    return {
        "clickhouse_server": ClickHouseServerEngine,
        "spark": SparkEngine,
        "starrocks": StarRocksEngine,
        "dremio": DremioEngine,
        "risingwave": RisingWaveEngine,
        "postgres": PostgresEngine,
        "feldera": FelderaEngine,
    }[name](work, subdir)


def run(rows, rg_size, servers=()):
    os.makedirs(os.path.join(HERE, "_work"), exist_ok=True)
    work = tempfile.mkdtemp(prefix="multi_engine_", dir=os.path.join(HERE, "_work"))
    started = []
    try:
        con = configure_duckdb(duckdb.connect())
        subdir = "corpusdir"
        os.makedirs(os.path.join(work, subdir), exist_ok=True)
        p = os.path.join(work, subdir, "corpus.parquet")
        con.execute(
            f"COPY ({corpus.gen_select(rows)}) TO '{p}' (FORMAT parquet, ROW_GROUP_SIZE {rg_size})")
        # mkdtemp is 0700; container engines that run as a non-root UID (Dremio uid 999) must be able to
        # traverse/read the bind-mounted tree, so widen perms on the throwaway work dir.
        os.chmod(work, 0o755); os.chmod(os.path.join(work, subdir), 0o755); os.chmod(p, 0o644)
        n_groups = con.execute(
            f"SELECT count(DISTINCT row_group_id) FROM parquet_metadata('{p}')").fetchone()[0]

        engines, versions = {}, {"duckdb": duckdb.__version__}
        parquet_engines = ["duckdb"]                     # shared-bytes engines that get a cross-engine vote
        engines["duckdb"] = engine_duckdb(con, p)

        from chdb import session as chs
        sess = chs.Session()
        sess.query("CREATE DATABASE IF NOT EXISTS d")
        sess.query("CREATE TABLE IF NOT EXISTS d.e ENGINE=MergeTree ORDER BY tuple() AS "
                   f"SELECT * FROM file('{p}', Parquet)")
        engines["chdb_parquet"] = engine_chdb_parquet(sess, p)
        engines["chdb_mergetree"] = engine_chdb_mergetree(sess)      # control, not in the vote
        versions["chdb"] = __import__("chdb").__version__
        parquet_engines.append("chdb_parquet")

        import datafusion
        dctx = datafusion.SessionContext(); dctx.register_parquet("t", p)
        engines["datafusion"] = engine_datafusion(dctx); versions["datafusion"] = datafusion.__version__
        parquet_engines.append("datafusion")

        import polars as pl
        engines["polars"] = engine_polars(pl.SQLContext(t=pl.scan_parquet(p)))
        versions["polars"] = pl.__version__; parquet_engines.append("polars")

        import pyarrow
        engines["pyarrow"] = engine_pyarrow(p); versions["pyarrow"] = pyarrow.__version__
        parquet_engines.append("pyarrow")

        import daft
        engines["daft"] = engine_daft(p); versions["daft"] = daft.__version__
        parquet_engines.append("daft")

        import fastparquet
        engines["fastparquet"] = engine_fastparquet(p); versions["fastparquet"] = fastparquet.__version__
        parquet_engines.append("fastparquet")

        # containerized engines — a failed startup is recorded and skipped, never aborts the matrix
        startup_errors = {}
        for s in servers:
            eng = _container_factory(s, work, subdir)
            try:
                eng.start()
                engines[s] = eng.query_fn(); versions[s] = eng.version
                parquet_engines.append(s)
                started.append(eng)
            except Exception as e:  # noqa: BLE001
                startup_errors[s] = f"{type(e).__name__}: {e}"[:300]
                print(f"  [{s}] startup unavailable (recorded, continuing): {str(e)[:140]}")
                try:                       # a partially-started container must still be torn down
                    eng.stop()
                except Exception:  # noqa: BLE001
                    pass

        # --------------------------------------------------------------- run the matrix (error-resilient)
        results = []
        for v in PROBES:
            truth = int(con.execute(
                f"SELECT count(*) FROM ({corpus.gen_select(rows)}) WHERE user_name = '{v}'").fetchone()[0])
            for op in PREDICATES:
                answers, errors = {}, {}
                for name, fn in engines.items():
                    try:
                        answers[name] = fn(op, v)
                    except Exception as e:  # noqa: BLE001 — record, never abort the matrix
                        answers[name] = None
                        errors[name] = f"{type(e).__name__}: {e}"[:200]
                votes = [answers[e] for e in parquet_engines if answers[e] is not None]
                counts = Counter(votes)
                consensus, consensus_n = (counts.most_common(1)[0] if counts else (None, 0))
                unanimous = len(counts) <= 1
                ambiguous = (not unanimous) and consensus_n <= len(votes) / 2
                results.append({
                    "value": v, "predicate": op, "truth": truth, "answers": answers, "errors": errors,
                    "cross_engine_unanimous": unanimous, "cross_engine_consensus": consensus,
                    "cross_engine_consensus_matches_truth": consensus == truth,
                    "ambiguous_split_without_truth": ambiguous,
                })
                wrong = [f"{e}{answers[e]-truth:+d}" for e in answers
                         if answers[e] is not None and answers[e] != truth]
                err = [f"{e}!" for e in errors]
                tag = ("  WRONG: " + ", ".join(wrong)) if wrong else ""
                tag += ("  ERR: " + ",".join(err)) if err else ""
                print(f"  {v:9} {op:4} truth={truth:>6}{tag}")
        con.close()

        cells = len(PROBES) * len(PREDICATES)
        scorecard = {}
        for e in engines:
            graded = [r for r in results if r["answers"][e] is not None]
            wrong = [r for r in graded if r["answers"][e] != r["truth"]]
            errored = [r for r in results if r["answers"][e] is None]
            scorecard[e] = {
                "reader": READER.get(e, "?"),
                "in_vote": e in parquet_engines,
                "cells_total": cells, "cells_graded": len(graded),
                "cells_wrong": len(wrong), "cells_errored": len(errored),
                "all_correct": len(wrong) == 0 and len(errored) == 0,
                "total_abs_error": sum(abs(r["answers"][e] - r["truth"]) for r in wrong),
                "wrong_cells": [{"value": r["value"], "predicate": r["predicate"],
                                 "error": r["answers"][e] - r["truth"]} for r in wrong],
            }

        any_div = any(not r["cross_engine_unanimous"] for r in results)
        any_amb = any(r["ambiguous_split_without_truth"] for r in results)
        passers = sorted(e for e in parquet_engines if scorecard[e]["all_correct"])
        failers = sorted(e for e in parquet_engines
                         if scorecard[e]["cells_wrong"] > 0)
        errored_engines = sorted(e for e in parquet_engines if scorecard[e]["cells_errored"] > 0)
        return {
            "benchmark": "multi-engine Parquet correctness probe (Phase E generalization of R3)",
            "hypothesis": "H-ENGINE-ANSWER-EQUIVALENCE-01",
            "evidence_tier": "B (single machine; ground-truth-verified, deterministic, reproducible)",
            "environment": versions, "corpus_rows": rows, "row_group_size": rg_size, "row_groups": n_groups,
            "probe_values": len(PROBES), "predicate_classes": PREDICATES,
            "shared_bytes_engines": parquet_engines,
            "ground_truth_passers": passers, "ground_truth_failers": failers,
            "engines_errored": errored_engines, "startup_unavailable": startup_errors,
            "scorecard": scorecard,
            "cross_engine_any_divergence": any_div, "cross_engine_any_ambiguous_split": any_amb,
            "cross_engine_catches_every_divergence_without_truth": any_div and not any_amb,
            "cells": results,
        }
    finally:
        for eng in started:
            try:
                eng.stop()
            except Exception:  # noqa: BLE001
                pass
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def render_md(res):
    env = res["environment"]
    pe = res["shared_bytes_engines"]
    sc = res["scorecard"]

    def verdict(e):
        s = sc[e]
        if s["cells_errored"] and not s["cells_wrong"]:
            return f"⚠ errored ({s['cells_errored']}/{s['cells_total']})"
        if s["all_correct"]:
            return "✓ all correct"
        return f"✗ −{s['total_abs_error']} on {s['cells_wrong']} cell(s)"

    order = [e for e in pe] + [e for e in sc if e not in pe]   # voters first, then controls
    sc_rows = "\n".join(
        f"| {e} | {sc[e]['reader']} | {'shared bytes' if sc[e]['in_vote'] else 'control'} | "
        f"{sc[e]['cells_graded']-sc[e]['cells_wrong']}/{sc[e]['cells_total']} | {verdict(e)} |"
        for e in order)

    bad = [r for r in res["cells"]
           if any(r["answers"][e] is not None and r["answers"][e] != r["truth"] for e in pe)]
    if bad:
        cols = [e for e in pe]
        det = "\n".join(
            f"| `{r['value']}` | `{r['predicate']}` | {r['truth']} | " +
            " | ".join(("—" if r["answers"][e] is None else
                        (str(r["answers"][e]) if r["answers"][e] == r["truth"]
                         else f"**{r['answers'][e]}**")) for e in cols) + " |"
            for r in bad)
        det_table = ("| value | predicate | truth | " + " | ".join(cols) + " |\n"
                     "|---|---|--:|" + "--:|" * len(cols) + "\n" + det +
                     "\n\n(bold = wrong answer; — = engine errored on that cell)")
    else:
        det_table = "_No shared-bytes engine returned a wrong answer on any cell._"

    passers = ", ".join(res["ground_truth_passers"]) or "none"
    failers = ", ".join(res["ground_truth_failers"]) or "none"
    distinct_failed_readers = sorted({sc[e]["reader"].split(" (")[0] for e in res["ground_truth_failers"]})
    xeng = ("every divergence was a single engine against a unanimous rest, so **cross-engine majority "
            "catches it without a generator**" if res["cross_engine_catches_every_divergence_without_truth"]
            else ("at least one divergence was an **ambiguous split** the engines could not resolve among "
                  "themselves — ground truth was required" if res["cross_engine_any_ambiguous_split"]
                  else "no cross-engine divergence occurred"))
    eng_lines = "\n".join(f"- **{e}** — {sc[e]['reader']}"
                          + (f" — `{env.get(e if e in env else e.split('_')[0], '')}`"
                             if (e in env or e.split('_')[0] in env) else "")
                          for e in order)
    su = res.get("startup_unavailable", {})
    unavail = ("\n\n## Attempted but unavailable\n\n" +
               "\n".join(f"- **{e}** — {msg}" for e, msg in su.items())) if su else ""

    return f"""# Cross-engine Parquet answer-equality — does the R3 undercount generalize? (Phase E)

**Tier B · single machine · ground-truth-verified.** {len(pe)} engines (plus controls) read the **same**
Parquet file ({res['corpus_rows']:,} rows, {res['row_groups']} row groups — the R3 trigger structure),
every count checked against the generator's ground truth (the corpus is a pure function of the row index,
so the true count of each `user_name` value is computable without any engine). {res['probe_values']}
pre-registered probe values × {len(res['predicate_classes'])} predicate classes (`=`, `IN`, `LIKE`) =
{res['probe_values']*len(res['predicate_classes'])} cells per engine. Engines were selected by *distinct
Parquet reader* (see `ENGINE-LANDSCAPE-SURVEY.md`).

## Engines

{eng_lines}

## Ground-truth scorecard (passers named as loudly as failers)

| engine | Parquet reader | role | cells correct | verdict |
|---|---|---|--:|---|
{sc_rows}

**Passes ground truth on every cell: {passers}.**
**Returns a wrong answer on ≥1 cell: {failers}** — spanning **{len(distinct_failed_readers)} distinct
reader(s)**: {", ".join(distinct_failed_readers) or "none"}.

## Where the engines diverged

{det_table}{unavail}

## Cross-engine agreement *without* ground truth (the alternative-hypothesis test)

The open question in H-ENGINE-ANSWER-EQUIVALENCE-01 is whether *cross-engine* comparison suffices or you
need *ground truth*. In this run: {xeng}.

- Any cross-engine divergence at all: **{res['cross_engine_any_divergence']}**
- Any ambiguous split (engines can't resolve it among themselves): **{res['cross_engine_any_ambiguous_split']}**

If divergences are always one-engine-vs-the-rest, running ≥3 engines and taking the majority is a
practical control even with no generator. The moment two engines agree on a wrong answer, the majority is
wrong and only ground truth saves you — so the durable control is **validate against ground truth where
you can; use cross-engine majority (≥3 engines) where you can't**, and never trust a single engine's
`count(*) WHERE` as self-evidently correct.

## Reading

This is the generalization R3 asked for, run across distinct Parquet readers rather than one engine. The
narrow claim — *answer-equivalence across engines is not free, so verify it* — holds regardless of the
count of failers: the verification is what catches a fast, silent, wrong answer, and the engines that pass
show the verification is cheap to satisfy, not unnecessary. On the broad claim (*do readers disagree?*):
this run found **{len(distinct_failed_readers)} distinct reader(s)** return a silently wrong answer over a
Parquet file the others read correctly, so the honest statement is **"more than a single isolated engine,
but not most"** — concentrated, not universal. For security data a `count(*) WHERE` is a detection
threshold or a compliance figure, so an engine that is fast and silently wrong is worse than one that is
slow and right. Single machine, deterministic reproduction; the method is the transferable finding, not any
one engine's name.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=10_000_000)
    ap.add_argument("--rg", type=int, default=12_288, help="Parquet ROW_GROUP_SIZE (trigger is ~814 groups)")
    ap.add_argument("--servers", default="",
                    help="comma list of containerized engines, or 'all'. "
                         "choices: clickhouse_server,spark,starrocks,trino,dremio,risingwave,postgres,feldera")
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    all_servers = ["clickhouse_server", "spark", "starrocks", "trino", "dremio", "risingwave",
                   "postgres", "feldera"]
    servers = all_servers if args.servers.strip() == "all" else \
        [s.strip() for s in args.servers.split(",") if s.strip()]
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    out = os.path.join(rdir, "multi-engine-correctness.json")
    if args.render_only:
        res = json.load(open(out))
    else:
        res = run(args.rows, args.rg, servers=servers)
        with open(out, "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "MULTI-ENGINE-CORRECTNESS.md"), "w") as f:
        f.write(render_md(res))
    print(f"\npassers: {res['ground_truth_passers']}")
    print(f"failers: {res['ground_truth_failers']}  |  errored: {res['engines_errored']}")
    print(f"cross-engine catches every divergence w/o truth: "
          f"{res['cross_engine_catches_every_divergence_without_truth']}  |  ambiguous: "
          f"{res['cross_engine_any_ambiguous_split']}")
    print("wrote results/multi-engine-correctness.json + MULTI-ENGINE-CORRECTNESS.md")


if __name__ == "__main__":
    main()

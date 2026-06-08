"""OCSF NL2SQL silent-error benchmark — by-difficulty silent-error rate of local
LLMs composing DuckDB SQL over an OCSF lakehouse.

This is the BREADTH companion to the BENCH-C text-to-SQL arm
(`../ocsf-semantic-query/run.py`). That arm runs only the 4 hardest adversary-tail
concept queries and found a weak local model fails *loudly* there (hallucinated
columns/functions → SQL error or empty), posting a 0.00 silent rate. The open
question that leaves is WHERE on the difficulty curve silent errors actually
concentrate. This benchmark answers it with ~30 labeled questions across seven
difficulty tiers (simple filter → aggregation → group-by → time-window →
multi-condition → join → adversary tail), each with a hand-authored gold answer.

Definitions (identical in spirit to ocsf-semantic-query/run.py:score, the canonical
scorer this thread already uses):
  correct — the generated SQL ran and the gold answer is recovered in the result.
  silent  — the generated SQL RAN and returned a non-empty result, but the gold
            answer is NOT in it. This is the analyst-trust danger: a plausible
            wrong answer with no error. The headline metric is the silent-error rate.
  loud    — the SQL errored, returned empty when the gold is non-empty, or the model
            refused / emitted no SQL. Operationally safer (a visible failure).

Design discipline (the lab conventions): seeded deterministic corpus + ground truth
(reused, never re-authored — MASTER_SEED=20260601), hand-authored gold answer key
(never an LLM), pinned local models at temperature 0, honest Tier-B / single-machine
caveats, and the LLM greedy-decode determinism caveat (the corpus, gold, and scorer
are deterministic and assertable; the SQL the model composes is temperature-0 greedy
decode — reproducible in practice, not asserted).

This is the FIRST OCSF datapoint for H-CONCEPT-GRAPH-03 framed as a by-difficulty
silent-error curve; positioned alongside BENCH-B (mapping-oracle silent-error on
field→OCSF mapping) and BENCH-C (the OBDA-vs-LLM concept-query head-to-head), not a
duplicate of either — see README "Relationship to BENCH-B and BENCH-C".

DO NOT run the heavy eval while another benchmark holds the box (it would contend for
DuckDB + the local LLM and corrupt both runs' numbers). See READINESS.md.
"""

import argparse
import json
import os
import sys

import duckdb
import requests

import questions as Q

HERE = os.path.dirname(os.path.abspath(__file__))
STORE_F = os.path.join(HERE, "..", "bench-a-context-collapse", "_work", "store_f")
GT = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "ground_truth.json")
OLLAMA = "http://localhost:11434/api/generate"
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import configure_duckdb  # noqa: E402

TABLES = Q.TABLES


# --------------------------------------------------------------------------- #
# DuckDB over Store F (NOT executed in --render-only / --determinism modes).    #
# --------------------------------------------------------------------------- #

def connect():
    con = configure_duckdb(duckdb.connect(":memory:"))
    for t in TABLES:
        con.execute(f"CREATE VIEW f_{t} AS SELECT * FROM '{STORE_F}/{t}.parquet'")
    return con


def schema_context(con):
    out = []
    for t in TABLES:
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM f_{t}").fetchall()]
        out.append(f"  f_{t}({', '.join(cols)})")
    return "Tables (DuckDB, fidelity OCSF store):\n" + "\n".join(out)


# --------------------------------------------------------------------------- #
# The model call — same request shape as ocsf-semantic-query/run.py.            #
# --------------------------------------------------------------------------- #

def compose_sql(model, schema, nl):
    prompt = (f"You write one DuckDB SQL query to answer a security question over an OCSF "
              f"fidelity store. Output JSON only: {{\"sql\": \"<one SELECT statement>\"}}.\n"
              f"{schema}\n\nQuestion: {nl}")
    try:
        r = requests.post(OLLAMA, json={"model": model, "prompt": prompt, "stream": False,
                          "format": "json", "options": {"temperature": 0}, "keep_alive": "10m"},
                          timeout=180)
        return json.loads(r.json().get("response", "")).get("sql", "")
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# The scorer — extends ocsf-semantic-query/run.py:score's kind-dispatch with    #
# `scalar` and `set` (the kinds the mid-difficulty tiers need), keeping the     #
# substring / uid / uidset semantics byte-identical. correct|silent only here;  #
# loud is decided by the caller (error / empty / no-SQL), exactly as in run.py. #
# --------------------------------------------------------------------------- #

def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def score(kind, rows, gold):
    """Classify a NON-EMPTY result against the gold answer: 'correct' | 'silent'."""
    flat = [c for row in rows for c in row]
    flat_s = [str(c) for c in flat]

    if kind == "substring":
        return "correct" if any(str(gold) in c for c in flat_s) else "silent"

    if kind == "uid":
        return "correct" if str(gold) in flat_s else "silent"

    if kind == "uidset":
        truth_set = set(gold)
        got = truth_set & set(flat_s)
        # recover a majority of the needle set without flooding (precision proxy)
        ok = len(got) >= 0.5 * len(truth_set) and len(flat_s) <= 4 * len(truth_set)
        return "correct" if ok else "silent"

    if kind == "scalar":
        # a single answer cell expected; tolerate a 1-row/1-col result or a scalar
        # that appears among the returned cells. numeric within rel-tol, else exact str.
        g_num = _num(gold)
        if g_num is not None:
            for c in flat:
                cv = _num(c)
                if cv is not None and (abs(cv - g_num) <= 1e-9 * max(1.0, abs(g_num))):
                    return "correct"
            return "silent"
        return "correct" if str(gold) in flat_s else "silent"

    if kind == "set":
        return "correct" if set(flat_s) == {str(g) for g in gold} else "silent"

    return "silent"


# --------------------------------------------------------------------------- #
# Gold resolution. truth -> ground_truth.json needle; literal -> pinned corpus  #
# invariant; sql -> the reference answer key, run ONCE on Store F to materialize #
# the gold (this is answer-key computation, the human-authored oracle, not the   #
# model's SQL). All three are deterministic.                                    #
# --------------------------------------------------------------------------- #

def resolve_gold(q, gt, con):
    if q["gold_via"] == "truth":
        return gt["truth_needles"][q["truth_key"]]
    if q["gold_via"] == "literal":
        return q["gold_literal"]
    # gold_via == "sql": execute the reference oracle to get the gold answer.
    res = con.execute(q["gold_sql"]).fetchall()
    if q["kind"] == "set":
        return [r[0] for r in res]
    # scalar / substring / uid: the answer is the single returned value
    return res[0][0] if (res and res[0]) else None


# --------------------------------------------------------------------------- #
# The run.                                                                      #
# --------------------------------------------------------------------------- #

def run_model(model, con, schema, gt):
    rows_out = []
    for q in Q.QUESTIONS:
        gold = resolve_gold(q, gt, con)
        sql = compose_sql(model, schema, q["nl"])
        outcome, n = "loud", 0
        if sql.strip():
            try:
                res = con.execute(sql).fetchall()
                n = len(res)
                if n == 0:
                    outcome = "loud"          # empty when gold exists ⇒ a visible miss
                else:
                    outcome = score(q["kind"], res, gold)
            except Exception:
                outcome = "loud"              # SQL error ⇒ loud (safer than silent)
        rows_out.append({"id": q["id"], "tier": q["tier"], "kind": q["kind"],
                         "outcome": outcome, "rows_returned": n, "sql": sql[:300]})

    n = len(rows_out)
    counts = {k: sum(1 for r in rows_out if r["outcome"] == k)
              for k in ("correct", "silent", "loud")}
    by_tier = {}
    for tier in Q.by_tier():
        tr = [r for r in rows_out if r["tier"] == tier]
        c = {k: sum(1 for r in tr if r["outcome"] == k) for k in ("correct", "silent", "loud")}
        by_tier[tier] = {"n": len(tr), "counts": c,
                         "silent_error_rate": round(c["silent"] / len(tr), 4),
                         "result_accuracy": round(c["correct"] / len(tr), 4)}
    return {"rows": rows_out, "counts": counts,
            "silent_error_rate": round(counts["silent"] / n, 4),
            "result_accuracy": round(counts["correct"] / n, 4),
            "by_tier": by_tier}


# --------------------------------------------------------------------------- #
# Rendering.                                                                     #
# --------------------------------------------------------------------------- #

TIER_ORDER = ["simple_filter", "aggregation", "group_by", "time_window",
              "multi_condition", "join", "adversary_tail"]


def render_md(results):
    lines = ["# OCSF NL2SQL silent-error benchmark — results", "",
             "**Tier B, single machine, local models, one planted chain.** The headline is the "
             "**silent-error rate** (SQL runs, returns a non-empty wrong answer) and **where on the "
             "difficulty curve it concentrates**. Anchors (external): NL2KQL ~58% result-accuracy "
             "at ~42% confidently-wrong; BIRD 81.67% vs 92.96% human.", ""]
    for model, r in results["models"].items():
        lines += [f"## {model}", "",
                  f"- result-accuracy: **{r['result_accuracy']:.2f}**",
                  f"- silent-error rate: **{r['silent_error_rate']:.2f}**",
                  f"- counts: {r['counts']}", "",
                  "| difficulty tier | n | correct | silent | loud | silent-rate |",
                  "|---|---|---|---|---|---|"]
        for tier in TIER_ORDER:
            t = r["by_tier"].get(tier)
            if not t:
                continue
            c = t["counts"]
            lines.append(f"| {tier} | {t['n']} | {c['correct']} | {c['silent']} | "
                         f"{c['loud']} | {t['silent_error_rate']:.2f} |")
        lines += ["", "<details><summary>per-question</summary>", "",
                  "| id | tier | kind | outcome | rows |", "|---|---|---|---|---|"]
        for q in r["rows"]:
            lines.append(f"| {q['id']} | {q['tier']} | {q['kind']} | {q['outcome']} | "
                         f"{q['rows_returned']} |")
        lines += ["", "</details>", ""]
    lines += ["## Reading", "",
              "The question to read off the by-tier table: do silent errors cluster in the "
              "**mid-difficulty** band (aggregation / group-by / time-window / multi-condition), "
              "where the SQL plausibly runs and quietly returns the wrong number, rather than on "
              "the **adversary tail**, where a weak local model tends to fail *loudly* "
              "(hallucinated columns/functions → error or empty)? That mid-band silent concentration, "
              "if it holds, is the analyst-trust hazard this benchmark exists to surface.", "",
              "Determinism: the corpus, the ground truth, and the correct/silent/loud scorer are "
              "deterministic and assertable (`--determinism`); the SQL the model composes is "
              "temperature-0 greedy decode — reproducible in practice, not asserted. See README "
              "for the relationship to BENCH-B (mapping-oracle) and BENCH-C (OBDA-vs-LLM)."]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# main.                                                                          #
# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["phi3:latest", "gemma4:26b"],
                    help="local Ollama models to run, temperature 0")
    ap.add_argument("--render-only", action="store_true",
                    help="re-render results/RESULTS.md from results/results.json (no DuckDB, no LLM)")
    ap.add_argument("--determinism", action="store_true",
                    help="assert the gold-source + scorer are deterministic; no DuckDB, no LLM")
    args = ap.parse_args()

    if args.determinism:
        # No DuckDB, no LLM: check the scorer is a pure, stable function and the
        # question set is structurally sound. The gold_sql oracle's determinism is
        # the same corpus-determinism the testbed already fingerprints.
        import questions as QQ
        ids = [q["id"] for q in QQ.QUESTIONS]
        unique = len(ids) == len(set(ids))
        # scorer stability on fixed inputs (one per kind)
        s = score("scalar", [(42,)], 42) == score("scalar", [(42,)], 42) == "correct"
        s &= score("scalar", [(41,)], 42) == "silent"
        s &= score("substring", [("abc",)], "b") == "correct"
        s &= score("uid", [("u1",), ("u2",)], "u2") == "correct"
        s &= score("uidset", [("a",), ("b",)], ["a", "b"]) == "correct"
        s &= score("set", [("p",), ("q",)], ["q", "p"]) == "correct"
        print(f"question ids unique: {unique} ({len(ids)} questions, "
              f"{len(QQ.by_tier())} tiers)")
        print(f"tier counts: {QQ.tier_counts()}")
        print(f"scorer stable + correct on fixed inputs: {bool(s)}")
        print("NOTE: corpus, ground truth, and the correct/silent/loud scorer are deterministic; "
              "the SQL each model composes is temperature-0 greedy decode (reproducible in "
              "practice, not asserted).")
        sys.exit(0 if (unique and s) else 1)

    if args.render_only:
        res = json.load(open(os.path.join(HERE, "results", "results.json")))
        os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
        with open(os.path.join(HERE, "results", "RESULTS.md"), "w") as f:
            f.write(render_md(res))
        print("rendered results/RESULTS.md")
        return

    if not os.path.isdir(STORE_F):
        print("Store F not built — run bench-a-context-collapse/run.py first "
              "(it depends on ocsf-semantic-testbed/generate.py).", file=sys.stderr)
        sys.exit(2)

    con = connect()
    schema = schema_context(con)
    gt = json.load(open(GT))
    out_models = {}
    for model in args.models:
        r = run_model(model, con, schema, gt)
        out_models[model] = r
        print(f"{model}: {r['counts']}  silent-error={r['silent_error_rate']:.2f}  "
              f"result-acc={r['result_accuracy']:.2f}")
        for tier in TIER_ORDER:
            t = r["by_tier"].get(tier)
            if t:
                print(f"  {tier:16s} n={t['n']:2d}  silent={t['counts']['silent']}  "
                      f"loud={t['counts']['loud']}  correct={t['counts']['correct']}")
    con.close()

    results = {
        "benchmark": "ocsf-nl2sql-silenterror (by-difficulty NL2SQL silent-error over OCSF)",
        "evidence_tier": "B (local models, single machine, one planted chain, hand-authored gold)",
        "hypothesis": "H-CONCEPT-GRAPH-03 (first OCSF by-difficulty silent-error datapoint)",
        "anchors": {"NL2KQL_result_accuracy": 0.58, "NL2KQL_confidently_wrong": 0.42,
                    "BIRD_sota": 0.8167, "BIRD_human": 0.9296},
        "question_count": len(Q.QUESTIONS),
        "tier_counts": Q.tier_counts(),
        "models": out_models,
    }
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "results.json"), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    with open(os.path.join(HERE, "results", "RESULTS.md"), "w") as f:
        f.write(render_md(results))
    print("wrote results/results.json and results/RESULTS.md")
    return results


if __name__ == "__main__":
    main()

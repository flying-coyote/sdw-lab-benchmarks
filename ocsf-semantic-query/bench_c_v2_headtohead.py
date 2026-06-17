#!/usr/bin/env python3
"""BENCH-C v2 — the integrated head-to-head harness (addendum §6 / pre-reg reporting order).

Registers every arm, scores each through the ONE shared scorer (scoring.classify, byte-identical),
applies the addendum §6 trial rule (8 trials for LLM-generation arms, 1 for deterministic arms), and
reports in the pre-registered order: retrieval-recall FIRST for the lookup class (A2/A6/A8), then the
tail (A3/A4/A7/A9) as compute-correctness across the four compute paths. A4 is EXCLUDED everywhere as
ill-posed (addendum §1).

Arms registered:
  1. text-to-SQL                (LLM SQL over RAW tables)          -- 8 trials  [run.py / v1 predictions]
  2. OBDA-deterministic         (curated/templated SPARQL)         -- 1 trial   [run_obda.py]
  3. structured-graph-query     (LLM-authored SPARQL, det. exec)   -- 8 trials  [run_structured_query.py]
  4. metrics-layer              (hand-curated plain SQL views)     -- 1 trial   [run_metrics_layer.py]
  +  graphrag flat / structured (entity-seeded retrieval; v2 hybrid on lookup) -- 8 trials [run_graphrag.py]

This harness does NOT call the LLM. The LLM-generation arms consume a predictions JSON produced by the
generation workflow (text-to-SQL SQL, structured-query SPARQL, graphrag answers), exactly as
bench_c_headtohead_score.py consumes its predictions. The deterministic arms (OBDA / metrics-layer /
structured-query EXECUTION on a hand-written query) are run in-process here for the smoke path.

Usage:
  # smoke (NO LLM): deterministic arms only, on the enlarged corpus, prove shapes score cleanly
  python3 bench_c_v2_headtohead.py --smoke
  # full scored run (after the generation workflow writes predictions):
  python3 bench_c_v2_headtohead.py --predictions _frontier/v2_predictions.json
"""
import argparse
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench_c_v2_config as CFG  # noqa: E402
from scoring import classify  # noqa: E402  (THE shared scorer — byte-identical, untouched)
import run_graphrag as R  # noqa: E402
import run_metrics_layer as ML  # noqa: E402
import run_structured_query as SQ  # noqa: E402
import run_obda as OBDA  # noqa: E402

LOOKUP = sorted(CFG.LOOKUP_CLASS)        # A2 A6 A8 (recall-first)
TAIL = sorted(CFG.TAIL_CLASS)            # A3 A4 A7 A9 (compute-correctness)
EXCLUDE = {"A4"} if CFG.A4_EXCLUDED_ILL_POSED else set()

# kind/truth_key per qid, read off run_graphrag.QUERIES (single source so kinds don't drift).
QMETA = {q["id"]: {"kind": q["kind"], "truth_key": q["truth_key"], "nl": q["nl"]} for q in R.QUERIES}


def load_truth_v2():
    gt = json.load(open(CFG.GT_V2))
    t = dict(gt["truth_needles"])
    t["truth_event_order"] = gt["truth_event_order"]
    t["truth_identity_links"] = gt["truth_identity_links"]
    return t


# --------------------------------------------------------------------- scoring helpers
def score_outcome(qid, cells, truth):
    """The ONE scoring entry point all arms route through. loud decided here (empty), else classify."""
    if not cells:
        return "loud"
    return classify(QMETA[qid]["kind"], cells, truth[QMETA[qid]["truth_key"]])


def aggregate_trials(by_trial):
    """by_trial: {trial: {correct,silent,loud}} -> mean/min/max/stdev per outcome (variance band)."""
    trials = sorted(by_trial)
    out = {}
    for oc in ("correct", "silent", "loud"):
        rates = []
        for t in trials:
            c = by_trial[t]
            n = sum(c.values()) or 1
            rates.append(c[oc] / n)
        out[oc] = {"mean": round(statistics.mean(rates), 4) if rates else 0.0,
                   "min": round(min(rates), 4) if rates else 0.0,
                   "max": round(max(rates), 4) if rates else 0.0,
                   "stdev": round(statistics.pstdev(rates), 4) if len(rates) > 1 else 0.0,
                   "n_trials": len(trials)}
    return out


def score_llm_arm(preds, truth, get_cells, *, qids):
    """preds: list of {qid, trial, ...}. 8-trial LLM arm. A4 excluded. Returns trial aggregate +
    per-query stability."""
    by_trial, by_query = {}, {}
    for p in preds:
        qid = p["qid"]
        if qid not in qids or qid in EXCLUDE:
            continue
        cells = get_cells(p)
        oc = score_outcome(qid, cells, truth)
        t = p.get("trial", 0)
        by_trial.setdefault(t, {"correct": 0, "silent": 0, "loud": 0})[oc] += 1
        by_query.setdefault(qid, {})[t] = oc
    stability = {q: {"majority": max(set(tr.values()), key=list(tr.values()).count),
                     "distinct_outcomes": len(set(tr.values()))} for q, tr in by_query.items()}
    return {"trials": CFG.TRIALS_LLM, "trial_rates": aggregate_trials(by_trial),
            "per_query_stability": stability, "n_queries": len(by_query)}


def score_det_arm(per_query, *, qids):
    """1-trial deterministic arm (variance zero by construction). per_query: {qid: outcome}."""
    counts = {"correct": 0, "silent": 0, "loud": 0}
    kept = {}
    for qid in qids:
        if qid in EXCLUDE:
            continue
        oc = per_query.get(qid, "loud")
        if oc not in counts:        # excluded / out-of-scope sentinels are not scored outcomes
            continue
        counts[oc] += 1
        kept[qid] = oc
    n = sum(counts.values()) or 1
    return {"trials": CFG.TRIALS_DETERMINISTIC, "deterministic": True, "counts": counts,
            "rates": {k: round(v / n, 4) for k, v in counts.items()}, "per_query": kept}


# --------------------------------------------------------------------- deterministic arms (in-process)
def run_metrics_layer_arm(truth):
    arm = ML.run()
    pq = {q: r["outcome"] for q, r in arm["per_query"].items()}
    return {
        "lookup": score_det_arm(pq, qids=LOOKUP),
        "tail": score_det_arm(pq, qids=TAIL),
        "raw_per_query": arm["per_query"], "excluded": arm["excluded"],
    }


def run_obda_arm():
    """OBDA-deterministic. Requires Ontop; if absent we record the dependency gap rather than fake it."""
    if not os.path.isdir(OBDA.ONTOP):
        return {"status": "blocked", "blocker": f"Ontop CLI absent at {OBDA.ONTOP}",
                "note": "OBDA arm needs Ontop; run run_obda.py with ONTOP_HOME set for the real result."}
    OBDA.main()   # merges into results.json; per-query is read back from there
    res = json.load(open(os.path.join(HERE, "results", "results.json")))
    o = res["arms"]["obda_ontop"]
    pq = {q: r["outcome"] for q, r in o["per_query"].items()}
    return {"lookup": score_det_arm(pq, qids=LOOKUP), "tail": score_det_arm(pq, qids=TAIL),
            "raw_per_query": o["per_query"], "excluded": o.get("excluded_ill_posed", [])}


def run_structured_query_exec_smoke(use_fallback):
    """Structured-query EXECUTION on a HAND-WRITTEN SPARQL (no LLM) — proves the deterministic
    execution+scoring path runs on the enlarged corpus for the smoke test."""
    props = None
    if not use_fallback:
        props = OBDA.write_props(OBDA.build_duckdb())
    # A6-shaped hand-written SPARQL (OWL2QL-expressible, NO gold constant): the no-MFA event uid.
    hand = ('PREFIX : <http://sdw.example/ocsf#>\n'
            'SELECT ?e WHERE { ?x a :ApiEvent ; :operation "AttachUserPolicy" ; '
            ':mfaPresent ?m ; :eventUid ?e . FILTER(?m = false) }')
    cells = SQ.execute(hand, props=props, use_fallback=use_fallback)
    truth = load_truth_v2()
    oc = score_outcome("A6", cells, truth)   # scorer accepts the shape
    path = "rdflib-fallback (Ontop absent)" if use_fallback else "Ontop"
    return {"exec_path": path, "hand_written_A6_outcome": oc, "cells": (cells or [])[:5],
            "scorer_accepted_shape": oc in ("correct", "silent", "loud")}


def smoke(report_path=None):
    truth = load_truth_v2()
    ontop_present = os.path.isdir(OBDA.ONTOP)
    use_fallback = not ontop_present

    out = {
        "bench": "BENCH-C v2 head-to-head SMOKE (deterministic arms only; NO LLM)",
        "corpus": {"shared_store_f": CFG.STORE_F, "v2_asset_overlay": CFG.STORE_F_V2_ASSET,
                   "v2_truth": CFG.GT_V2},
        "a4_excluded_ill_posed": CFG.A4_EXCLUDED_ILL_POSED,
        "lookup_class": LOOKUP, "tail_class": TAIL,
        "scorer": "scoring.classify (shared, byte-identical)",
        "arms": {},
    }
    # metrics-layer (deterministic)
    out["arms"]["metrics_layer"] = run_metrics_layer_arm(truth)
    # OBDA (deterministic; blocked if Ontop absent — recorded, not faked)
    out["arms"]["obda_deterministic"] = run_obda_arm()
    # structured-query EXECUTION on a hand-written SPARQL (deterministic exec path)
    out["arms"]["structured_query_exec_smoke"] = run_structured_query_exec_smoke(use_fallback)

    # console
    print("=== BENCH-C v2 SMOKE (deterministic arms, NO LLM) ===")
    print(f"corpus: v2 asset overlay = {CFG.STORE_F_V2_ASSET}")
    ml = out["arms"]["metrics_layer"]
    print(f"metrics-layer  lookup(A2/A6/A8): {ml['lookup']['counts']}   "
          f"tail(A3/A7/A9, A4 excluded): {ml['tail']['counts']}   excluded={ml['excluded']}")
    ob = out["arms"]["obda_deterministic"]
    if ob.get("status") == "blocked":
        print(f"OBDA           BLOCKED: {ob['blocker']}")
    else:
        print(f"OBDA           lookup: {ob['lookup']['counts']}   tail: {ob['tail']['counts']}   "
              f"excluded={ob['excluded']}")
    sq = out["arms"]["structured_query_exec_smoke"]
    print(f"structured-query EXEC ({sq['exec_path']}): hand-written A6 -> {sq['hand_written_A6_outcome']}  "
          f"scorer_accepted_shape={sq['scorer_accepted_shape']}")

    if report_path:
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        json.dump(out, open(report_path, "w"), indent=2, sort_keys=True, default=str)
        print(f"\n-> {report_path}")
    return out


def full(predictions_path, report_path):
    """Full scored run. predictions JSON shape (produced by the generation workflow):
      { "trials": 8,
        "text2sql":  [{qid, trial, sql}],          # executed against RAW tables
        "structured":[{qid, trial, sparql}],       # LLM-authored SPARQL, executed via Ontop/OBDA
        "graphrag":  [{qid, mode, trial, answer}] } # mode in {structured, flat}; v2 hybrid on lookup
    Deterministic arms (OBDA / metrics-layer) are run in-process. A4 excluded throughout."""
    truth = load_truth_v2()
    preds = json.load(open(predictions_path))
    ontop_present = os.path.isdir(OBDA.ONTOP)
    use_fallback = not ontop_present

    import duckdb

    def duck_raw():
        c = duckdb.connect()
        for t in ("auth", "session", "network", "dns", "process", "api"):
            c.execute(f"CREATE VIEW f_{t} AS SELECT * FROM read_parquet('{CFG.STORE_F}/{t}.parquet')")
        c.execute(f"CREATE VIEW f_asset AS SELECT * FROM read_parquet('{CFG.STORE_F_V2_ASSET}')")
        return c

    con = duck_raw()

    def t2s_cells(p):
        sql = p.get("sql", "")
        if not sql.strip():
            return None
        try:
            rows = con.execute(sql).fetchall()
        except Exception:
            return None
        return [str(c) for r in rows for c in r]

    def sparql_cells(p):
        return SQ.execute(p.get("sparql", ""), props=(None if use_fallback else _props_cache()),
                          use_fallback=use_fallback)

    def ans_cells(p):
        a = p.get("answer")
        if isinstance(a, list):
            return [str(x) for x in a]
        return [] if a in (None, "") else [str(a)]

    report = {
        "bench": "BENCH-C v2 head-to-head (integrated, shared scorer)",
        "hypotheses": ["H-CONCEPT-GRAPH-02", "H-CONCEPT-GRAPH-03"], "tier": "B",
        "a4_excluded_ill_posed": True, "lookup_class": LOOKUP, "tail_class": TAIL,
        "scorer": "scoring.classify (shared, byte-identical)",
        "reporting_order": ["lookup-recall-first (A2/A6/A8)", "tail-as-compute-correctness (A3/A7/A9)"],
        "arms": {},
    }
    # LLM arms (8 trials): split lookup vs tail per the pre-reg reporting order
    gr_struct = [p for p in preds.get("graphrag", []) if p.get("mode") == "structured"]
    gr_flat = [p for p in preds.get("graphrag", []) if p.get("mode") == "flat"]
    report["arms"]["text_to_sql"] = {
        "lookup": score_llm_arm(preds.get("text2sql", []), truth, t2s_cells, qids=set(LOOKUP)),
        "tail": score_llm_arm(preds.get("text2sql", []), truth, t2s_cells, qids=set(TAIL))}
    report["arms"]["structured_graph_query"] = {
        "lookup": score_llm_arm(preds.get("structured", []), truth, sparql_cells, qids=set(LOOKUP)),
        "tail": score_llm_arm(preds.get("structured", []), truth, sparql_cells, qids=set(TAIL))}
    report["arms"]["graphrag_structured"] = {
        "lookup": score_llm_arm(gr_struct, truth, ans_cells, qids=set(LOOKUP)),
        "tail": score_llm_arm(gr_struct, truth, ans_cells, qids=set(TAIL))}
    report["arms"]["graphrag_flat"] = {
        "lookup": score_llm_arm(gr_flat, truth, ans_cells, qids=set(LOOKUP)),
        "tail": score_llm_arm(gr_flat, truth, ans_cells, qids=set(TAIL))}
    # deterministic arms (1 trial)
    report["arms"]["metrics_layer"] = run_metrics_layer_arm(truth)
    report["arms"]["obda_deterministic"] = run_obda_arm()
    con.close()

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    json.dump(report, open(report_path, "w"), indent=2, sort_keys=True, default=str)
    print(f"-> {report_path}")
    return report


_PROPS = {}


def _props_cache():
    if "p" not in _PROPS:
        _PROPS["p"] = OBDA.write_props(OBDA.build_duckdb())
    return _PROPS["p"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="deterministic arms only; NO LLM")
    ap.add_argument("--predictions", help="LLM predictions JSON for the full scored run")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "v2_headtohead.json"))
    args = ap.parse_args()
    if args.smoke:
        smoke(report_path=os.path.join(HERE, "results", "v2_smoke.json"))
        return
    if args.predictions:
        full(args.predictions, args.out)
        return
    ap.print_help()


if __name__ == "__main__":
    main()

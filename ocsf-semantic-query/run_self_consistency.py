#!/usr/bin/env python3
"""BENCH-C v2.1 Arm #2 — self-consistency (N-of-8 majority-vote-or-abstain).

Pre-registered in BENCH-C-PREREGISTRATION-v2.1-arm-extension.md (committed BEFORE this run).
DERIVED from the trials ALREADY collected in the v2 predictions JSONs — NO new generation.

For each (arm, qid, tier) with 8 trials:
  - canonicalize each trial's ANSWER to a per-kind key that mirrors the shared scorer's salient
    extraction (so two trials cluster iff they agree under `scoring.classify`'s notion of the kind,
    NOT raw string identity — per the pre-reg);
  - take the MAJORITY answer (the key with the most trials) as the arm's answer;
  - ABSTAIN (a CAUGHT / loud-equivalent outcome, never correct) when no key reaches >= 5/8.
The majority answer is then scored through the ONE shared scorer (scoring.classify, byte-identical),
exactly as every other arm. A4 is excluded throughout (ill-posed, addendum sec.1).

Two pre-registered questions:
  (a) does majority-vote raise the CORRECT rate vs the per-trial mean?
  (b) does abstain-on-disagreement CATCH the silent errors — i.e. are the silent-wrong cells the ones
      that fail to reach majority? Pre-registered prediction: NO for the graphRAG tail, because the v2
      run already shows it is silent 1.0 with zero variance (unanimous), so it clears 5/8 and emits a
      confident silent error; self-consistency catches silent errors ONLY where the model is
      *inconsistently* wrong.

This script does NOT call an LLM. SPARQL execution (the `structured` arm) needs Ontop:
  ONTOP_HOME=~/tools/ontop-cli python3 run_self_consistency.py
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench_c_v2_config as CFG  # noqa: E402
import scoring  # noqa: E402  (THE shared scorer + its helpers — byte-identical, untouched)
from scoring import classify  # noqa: E402
import run_graphrag as R  # noqa: E402
import run_structured_query as SQ  # noqa: E402
import run_obda as OBDA  # noqa: E402

LOOKUP = sorted(CFG.LOOKUP_CLASS)             # A2 A6 A8
TAIL = [q for q in sorted(CFG.TAIL_CLASS) if q != "A4"]  # A3 A7 A9 (A4 excluded ill-posed)
SCORED = LOOKUP + TAIL
QMETA = {q["id"]: {"kind": q["kind"], "truth_key": q["truth_key"]} for q in R.QUERIES}

TIERS = {
    "haiku": "_frontier/v2/v2_predictions_haiku.json",
    "sonnet": "_frontier/v2/v2_predictions.json",
    "opus": "_frontier/v2/v2_predictions_opus.json",
}
MAJORITY = 5   # >= 5/8 (locked, pre-reg)


def load_truth():
    gt = json.load(open(CFG.GT_V2))
    t = dict(gt["truth_needles"])
    t["truth_event_order"] = gt["truth_event_order"]
    t["truth_identity_links"] = gt["truth_identity_links"]
    return t


def _norm_set(cells):
    return frozenset(str(c).strip().lower() for c in cells)


def canonical_key(kind, cells):
    """A hashable key reflecting the shared scorer's salient features for `kind`. Two answers share a
    key iff classify would treat them equivalently for that kind (mirrors scoring.classify)."""
    if not cells:
        return ("EMPTY",)
    if kind in ("substring", "uid", "uidset", "set"):
        return ("set", _norm_set(cells))
    if kind in ("count", "scalar", "exact_scalar"):
        nums = tuple(sorted(set(scoring._numbers(cells))))
        return ("num", nums) if nums else ("rows", len(cells))
    if kind == "order":
        text = " ".join(str(c) for c in cells).lower()
        seq = [kw for kw in (scoring.STAGE_KEYWORDS[s] for s in
                             ["stage0_oauth", "stage1_powershell", "stage2_beacon",
                              "stage3_lateral_conn", "stage4_nomfa", "stage5_assumerole",
                              "stage6_exfil"]) if text.find(kw) >= 0]
        seq.sort(key=lambda kw: text.find(kw))
        return ("order", tuple(seq))
    return ("set", _norm_set(cells))


def score_outcome(qid, cells, truth):
    if not cells:
        return "loud"
    return classify(QMETA[qid]["kind"], cells, truth[QMETA[qid]["truth_key"]])


# ----- per-tier execution (mirrors bench_c_v2_headtohead.full; scorer imported, not re-implemented)
def build_cell_getters():
    import duckdb
    con = duckdb.connect()
    for t in ("auth", "session", "network", "dns", "process", "api"):
        con.execute(f"CREATE VIEW f_{t} AS SELECT * FROM read_parquet('{CFG.STORE_F}/{t}.parquet')")
    con.execute(f"CREATE VIEW f_asset AS SELECT * FROM read_parquet('{CFG.STORE_F_V2_ASSET}')")
    use_fallback = not os.path.isdir(OBDA.ONTOP)
    props = None if use_fallback else OBDA.write_props(OBDA.build_duckdb())

    def t2s(p):
        sql = p.get("sql", "")
        if not sql.strip():
            return None
        try:
            rows = con.execute(sql).fetchall()
        except Exception:
            return None
        return [str(c) for r in rows for c in r]

    def sparql(p):
        return SQ.execute(p.get("sparql", ""), props=props, use_fallback=use_fallback)

    def ans(p):
        a = p.get("answer")
        if isinstance(a, list):
            return [str(x) for x in a]
        return [] if a in (None, "") else [str(a)]

    return con, t2s, sparql, ans, ("rdflib-fallback" if use_fallback else "Ontop")


def self_consistency_for_arm(preds, get_cells, qids, truth):
    """Returns per-qid: per-trial outcomes, the majority decision, and the SC outcome."""
    by_q = {}
    for p in preds:
        qid = p["qid"]
        if qid not in qids:
            continue
        by_q.setdefault(qid, []).append(p)
    out = {}
    for qid, plist in by_q.items():
        plist = sorted(plist, key=lambda p: p.get("trial", 0))
        per_trial = []           # (trial, outcome, key, cells)
        for p in plist:
            cells = get_cells(p)
            oc = score_outcome(qid, cells, truth)
            per_trial.append((p.get("trial", 0), oc, canonical_key(QMETA[qid]["kind"], cells), cells))
        keys = Counter(k for _, _, k, _ in per_trial)
        top_key, top_n = keys.most_common(1)[0]
        if top_n >= MAJORITY:
            # outcome of the majority answer = outcome of any trial carrying that key (key determines
            # the salient features classify uses, so all same-key trials share the outcome).
            sc_outcome = next(oc for _, oc, k, _ in per_trial if k == top_key)
            decision = "majority"
        else:
            sc_outcome = "abstain"   # caught (loud-equivalent), never correct
            decision = "abstain"
        per_trial_counts = Counter(oc for _, oc, _, _ in per_trial)
        out[qid] = {
            "kind": QMETA[qid]["kind"],
            "per_trial_outcomes": {oc: per_trial_counts.get(oc, 0) for oc in ("correct", "silent", "loud")},
            "n_distinct_answers": len(keys),
            "top_answer_agreement": f"{top_n}/8",
            "decision": decision,
            "sc_outcome": sc_outcome,
            # crux: was the per-trial MAJORITY outcome silent, and did SC abstain or emit it?
            "per_trial_majority_outcome": per_trial_counts.most_common(1)[0][0],
        }
    return out


def aggregate(arm_qid_results, qids):
    """Per-trial mean (correct/silent/loud) vs self-consistency (correct/silent/caught) over `qids`."""
    pt = {"correct": 0.0, "silent": 0.0, "loud": 0.0}
    sc = {"correct": 0, "silent": 0, "caught": 0}
    n = 0
    for qid in qids:
        if qid not in arm_qid_results:
            continue
        n += 1
        c = arm_qid_results[qid]["per_trial_outcomes"]
        tot = sum(c.values()) or 1
        for k in pt:
            pt[k] += c[k] / tot
        o = arm_qid_results[qid]["sc_outcome"]
        sc["caught" if o in ("abstain", "loud") else o] += 1
    if n:
        pt = {k: round(v / n, 4) for k, v in pt.items()}
    return {"n_queries": n, "per_trial_mean": pt, "self_consistency_counts": sc}


def main():
    truth = load_truth()
    report = {
        "bench": "BENCH-C v2.1 Arm #2 — self-consistency (5/8 majority-or-abstain; derived, NO new generation)",
        "hypotheses": ["H-CONCEPT-GRAPH-03", "H-CONCEPT-GRAPH-02"],
        "tier": "B", "majority_threshold": "5/8", "a4_excluded_ill_posed": True,
        "scorer": "scoring.classify (shared, byte-identical); clustering via per-kind canonical_key mirroring it",
        "tiers": {},
    }
    exec_path = None
    for tier, path in TIERS.items():
        preds = json.load(open(os.path.join(HERE, path)))
        con, t2s, sparql, ans, exec_path = build_cell_getters()
        gr_struct = [p for p in preds.get("graphrag", []) if p.get("mode") == "structured"]
        gr_flat = [p for p in preds.get("graphrag", []) if p.get("mode") == "flat"]
        arms = {
            "text_to_sql": (preds.get("text2sql", []), t2s, SCORED),
            "structured_graph_query": (preds.get("structured", []), sparql, TAIL),
            "graphrag_structured": (gr_struct, ans, SCORED),
            "graphrag_flat": (gr_flat, ans, SCORED),
        }
        tier_out = {}
        for arm, (plist, getter, qids) in arms.items():
            per_q = self_consistency_for_arm(plist, getter, set(qids), truth)
            tier_out[arm] = {
                "per_query": per_q,
                "lookup": aggregate(per_q, [q for q in qids if q in LOOKUP]),
                "tail": aggregate(per_q, [q for q in qids if q in TAIL]),
            }
        report["tiers"][tier] = tier_out
        con.close()
    report["exec_path"] = exec_path

    out_path = os.path.join(HERE, "results", "v2_1_self_consistency.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json.dump(report, open(out_path, "w"), indent=2, sort_keys=True, default=str)

    # console summary — the crux: graphRAG tail unanimous-silent -> SC emits silent (NOT caught)
    print("=== BENCH-C v2.1 Arm #2 self-consistency (exec:", exec_path, ") ===")
    for tier in TIERS:
        print(f"\n--- {tier} ---")
        for arm in ("text_to_sql", "structured_graph_query", "graphrag_structured", "graphrag_flat"):
            tail = report["tiers"][tier][arm]["tail"]
            ptm = tail["per_trial_mean"]
            scc = tail["self_consistency_counts"]
            print(f"  {arm:24s} TAIL  per-trial-mean(c/s/l)={ptm}  SC(correct/silent/caught)={scc}")
    print(f"\n-> {out_path}")
    return report


if __name__ == "__main__":
    main()

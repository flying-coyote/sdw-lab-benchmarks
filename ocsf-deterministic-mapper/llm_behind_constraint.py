"""Does the model add value BEHIND the schema constraint? (deterministic-mapper maturity)

The deterministic-mapper result showed a schema-constrained alias mapper has silent-error 0 by
construction. The honest follow-up the write-up promised: a model is only safe behind the same
constraint — so put phi3 behind it and see whether the model then beats the alias rules on coverage and
correctness while keeping silent-error 0.

Runs phi3 once (schema condition) over the 141 gold fields, caches the raw predictions, then scores:
  - raw phi3            (the BENCH-B baseline: invents paths)
  - phi3 + reject       (invalid prediction -> unmapped; silent-error 0)
  - phi3 + snap         (invalid prediction -> nearest valid path by string match; silent-error 0)
against the deterministic alias mapper. phi3 is 3.8B (safe to run); predictions are cached so
--render-only re-scores without calling the model.
"""

import difflib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ocsf-mapping-oracle"))
import run as bench_b  # noqa: E402

MODEL = "phi3:latest"
PRED_CACHE = os.path.join(HERE, "results", "llm_predictions.json")


def capture_predictions():
    valid = bench_b.load_valid_paths()
    items = bench_b.gold_fields(0)
    preds = []
    for it in items:
        raw = bench_b.ask(MODEL, bench_b.prompt_for(it, "schema", valid))
        preds.append({"field": it["field"], "source": it["source"], "class": it["class"],
                      "gold": it["gold"], "raw_pred": raw})
    os.makedirs(os.path.dirname(PRED_CACHE), exist_ok=True)
    json.dump(preds, open(PRED_CACHE, "w"), indent=2, sort_keys=True)
    return preds


def score(preds, valid):
    def tally(mapper):
        n = correct = silent = mapped = 0
        for p in preds:
            cls = p["class"]
            pred = mapper(p, valid)
            n += 1
            if pred is None or pred == "unmapped":
                continue
            mapped += 1
            if bench_b.normalize(pred, cls) not in valid[cls]:
                silent += 1
            if bench_b.normalize(pred, cls) == bench_b.normalize(p["gold"], cls):
                correct += 1
        return {"silent_error_rate": round(silent / n, 4), "path_correct": round(correct / n, 4),
                "coverage": round(mapped / n, 4)}

    def raw(p, valid):
        return p["raw_pred"]

    def reject(p, valid):
        if not p["raw_pred"]:
            return "unmapped"
        return p["raw_pred"] if bench_b.normalize(p["raw_pred"], p["class"]) in valid[p["class"]] else "unmapped"

    def snap(p, valid):
        if not p["raw_pred"]:
            return "unmapped"
        nrm = bench_b.normalize(p["raw_pred"], p["class"])
        if nrm in valid[p["class"]]:
            return p["raw_pred"]
        m = difflib.get_close_matches(nrm, list(valid[p["class"]]), n=1, cutoff=0.6)
        return m[0] if m else "unmapped"

    return {"raw_phi3": tally(raw), "phi3_reject": tally(reject), "phi3_snap": tally(snap)}


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    valid = bench_b.load_valid_paths()
    if args.render_only or os.path.exists(PRED_CACHE):
        preds = json.load(open(PRED_CACHE)) if os.path.exists(PRED_CACHE) else capture_predictions()
    else:
        preds = capture_predictions()
    arms = score(preds, valid)
    # the deterministic alias mapper, for comparison
    det = json.load(open(os.path.join(HERE, "results", "results.json")))["deterministic"]
    out = {"benchmark": "ocsf-deterministic-mapper / LLM-behind-constraint", "model": MODEL,
           "n_fields": len(preds), "arms": arms,
           "deterministic_alias_mapper": {"silent_error_rate": det["silent_error_rate"],
                                          "path_correct": det["path_correct"], "coverage": det["coverage_mapped"]}}
    json.dump(out, open(os.path.join(HERE, "results", "results-constrained.json"), "w"), indent=2, sort_keys=True)
    for name, a in {**arms, "deterministic_alias": out["deterministic_alias_mapper"]}.items():
        print(f"  {name:16}: silent-error {a['silent_error_rate']:.2f}  path-correct {a['path_correct']:.2f}  coverage {a['coverage']:.2f}")
    print("wrote results/results-constrained.json")


if __name__ == "__main__":
    main()

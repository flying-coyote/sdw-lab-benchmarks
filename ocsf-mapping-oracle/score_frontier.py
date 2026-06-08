#!/usr/bin/env python3
"""Score the frontier-leg predictions (claude-opus-4-8 subagents as the model) with the EXACT
benchmark scorer (run.py normalize + OCSF-1.8.0 valid-path closure), and merge the result into
results/results.json under a frontier-proxy model key. Then re-render RESULTS.md.

Usage: python3 score_frontier.py _frontier/predictions.json
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run as R  # noqa: E402

MODEL_KEY = "claude-opus-4-8 (frontier proxy)"


def main():
    preds_path = sys.argv[1]
    raw = json.load(open(preds_path))
    preds = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            preds[int(k)] = v
    else:
        for e in raw:
            preds[int(e["gidx"])] = e.get("path")

    prompts = {e["gidx"]: e for e in
               json.load(open(os.path.join(HERE, "_frontier", "frontier_prompts.json")))}
    valid = R.load_valid_paths()

    cells = {}
    missing = 0
    for cond in R.CONDITIONS:
        n = correct = silent = 0
        by_source = {}
        for gidx, e in prompts.items():
            if e["condition"] != cond:
                continue
            cls, src, gold = e["cls"], e["source"], e["gold"]
            bs = by_source.setdefault(src, {"n": 0, "silent": 0, "correct": 0})
            pred = preds.get(gidx)
            n += 1
            bs["n"] += 1
            if not pred:
                silent += 1
                bs["silent"] += 1
                missing += 1
                continue
            norm = R.normalize(pred, cls)
            if norm not in valid[cls]:
                silent += 1
                bs["silent"] += 1
            if norm == R.normalize(gold, cls):
                correct += 1
                bs["correct"] += 1
        cells[cond] = {
            "n": n,
            "path_correct": round(correct / n, 4) if n else 0,
            "silent_error_rate": round(silent / n, 4) if n else 0,
            "by_source": {s: {"n": v["n"], "silent_rate": round(v["silent"] / v["n"], 4),
                              "path_correct": round(v["correct"] / v["n"], 4)}
                          for s, v in by_source.items()},
        }
    lifts = {
        "silent_schema_minus_none": round(cells["schema"]["silent_error_rate"] - cells["none"]["silent_error_rate"], 4),
        "silent_skill_minus_none": round(cells["skill"]["silent_error_rate"] - cells["none"]["silent_error_rate"], 4),
        "silent_formal_minus_none": round(cells["formal"]["silent_error_rate"] - cells["none"]["silent_error_rate"], 4),
        "silent_formal_minus_wrong": round(cells["formal"]["silent_error_rate"] - cells["wrong_grounding"]["silent_error_rate"], 4),
        "pathcorrect_skill_minus_schema": round(cells["skill"]["path_correct"] - cells["schema"]["path_correct"], 4),
    }

    rpath = os.path.join(HERE, "results", "results.json")
    res = json.load(open(rpath))
    res.setdefault("models", {})[MODEL_KEY] = {"cells": cells, "lifts": lifts}
    res["evidence_tier"] = ("B (local model ladder + claude-opus-4-8 frontier proxy run via subagents; "
                            "a fair stand-in for a paid-SaaS-API frontier model — same prompts, model swapped)")
    json.dump(res, open(rpath, "w"), indent=2, sort_keys=True)
    open(os.path.join(HERE, "results", "RESULTS.md"), "w").write(R.render_md(res))

    print(f"missing predictions (scored as silent): {missing}/{len(prompts)}")
    print(f"{MODEL_KEY}:")
    for c in R.CONDITIONS:
        print(f"  {c:14s} silent_error={cells[c]['silent_error_rate']:.3f}  path_correct={cells[c]['path_correct']:.3f}")
    print(f"  LIFT formal-minus-wrong (isolates correct grounding): {lifts['silent_formal_minus_wrong']:+.3f}")
    print(f"  LIFT schema-minus-none: {lifts['silent_schema_minus_none']:+.3f}   skill-minus-none: {lifts['silent_skill_minus_none']:+.3f}")
    print("merged into results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()

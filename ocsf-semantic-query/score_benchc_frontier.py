#!/usr/bin/env python3
"""Score the frontier BENCH-C GraphRAG-vs-flat_retrieval comparison and merge two arms into
results.json: graphrag_opus (structured context) and flat_retrieval_opus (same facts, no structure).
Uses the shared correct/silent/loud scorer. If structured ~= flat, graph structure adds nothing over
plain retrieval of the same facts — the pre-registered null.

Usage: python3 score_benchc_frontier.py _frontier/benchc_predictions.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_graphrag as R  # noqa: E402

NAMEMAP = {"structured": "graphrag_opus", "flat": "flat_retrieval_opus"}


def cells_of(ans):
    if isinstance(ans, list):
        return [str(x) for x in ans]
    if ans in (None, ""):
        return []
    return [str(ans)]


def main():
    preds = json.load(open(sys.argv[1]))
    truth = R.load_truth()
    ctx = {e["qid"]: e for e in
           json.load(open(os.path.join(HERE, "_frontier", "benchc_contexts.json")))}

    by_mode = {}
    for p in preds:
        qid, mode = p["qid"], p["mode"]
        cells = cells_of(p.get("answer"))
        kind, tk = ctx[qid]["kind"], ctx[qid]["truth_key"]
        outcome = "loud" if not cells else R.classify(kind, cells, truth[tk])
        m = by_mode.setdefault(mode, {"per_query": {}, "counts": {"correct": 0, "silent": 0, "loud": 0}})
        m["per_query"][qid] = {"outcome": outcome, "kind": kind, "cells": len(cells), "sample": cells[:5]}
        m["counts"][outcome] += 1

    rpath = os.path.join(HERE, "results", "results.json")
    full = json.load(open(rpath))
    for mode, m in by_mode.items():
        n = sum(m["counts"].values()) or 1
        full.setdefault("arms", {})[NAMEMAP[mode]] = {
            "status": "measured (frontier proxy: claude-opus-4-8 subagents)",
            "engine": f"BENCH-C {mode} context (entity-seeded retrieval, "
                      f"{'facts+relationships' if mode == 'structured' else 'same facts, NO relationships'}) "
                      f"answered by claude-opus-4-8",
            "retrieval_mode": mode,
            "counts": m["counts"],
            "silent_error_rate": round(m["counts"]["silent"] / n, 4),
            "result_accuracy": round(m["counts"]["correct"] / n, 4),
            "per_query": m["per_query"],
        }
    json.dump(full, open(rpath, "w"), indent=2, sort_keys=True)

    s = by_mode.get("structured", {}).get("counts", {})
    f = by_mode.get("flat", {}).get("counts", {})
    print("=== BENCH-C frontier (claude-opus-4-8) ===")
    for mode in ("structured", "flat"):
        m = by_mode.get(mode)
        if m:
            print(f"  {mode:11s} {m['counts']}  acc={m['counts']['correct']/9:.2f}  "
                  f"{ {k: v['outcome'] for k, v in m['per_query'].items()} }")
    delta = s.get("correct", 0) - f.get("correct", 0)
    print(f"\n  GRAPH-STRUCTURE VALUE (correct_structured - correct_flat): {delta:+d} of 9")
    print("  -> if ~0, the pre-registered null holds: structure adds nothing over the same retrieved facts.")
    print("merged arms graphrag_opus + flat_retrieval_opus into results.json")


if __name__ == "__main__":
    main()

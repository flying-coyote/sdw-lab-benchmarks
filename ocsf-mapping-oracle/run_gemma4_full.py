"""Full 141-item gemma4:26b leg for BENCH-B — RESUMABLE.

Runs every gold-path item (no stratified cap) across all 6 sources x 5 conditions
(~705 inferences, ~8h on the local WSL2 host). Every (source, field, condition)
result is appended to a JSONL checkpoint immediately, so an interruption resumes
where it stopped instead of restarting. The aggregate is written incrementally
(after each condition) to results.json under a SEPARATE key 'gemma4:26b-full141'
so the committed 20-item 'gemma4:26b' sample is never clobbered until the full run
is complete. RESULTS.md is left untouched (regenerated after completion).

Reuses the inference path (prompt construction, ollama call, scoring, valid-path
closure) from run_gemma4.py verbatim — same model, same temperature 0, same conditions.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_gemma4 as g  # noqa: E402  reuse SOURCES/CONDITIONS/ask/prompt_for/normalize/load_valid_paths

CKPT = os.path.join(HERE, "results", "gemma4_full_checkpoint.jsonl")
RESULTS = os.path.join(HERE, "results", "results.json")
KEY = "gemma4:26b"  # canonical full-run result (the 20-item preview is gemma4:26b-sample20)


def build_full():
    """Every source field whose gold mapping is a real dotted OCSF path (no catch-alls)."""
    items = []
    for source, (mp, cls, uid) in g.SOURCES.items():
        for field, rec in mp.items():
            path = rec.get("ocsf", "")
            if path in g.CATCH_ALLS or "." not in path:
                continue
            items.append({"source": source, "field": field, "class": cls, "uid": uid,
                          "gold": path, "status": rec.get("status")})
    items.sort(key=lambda x: (x["source"], x["field"]))
    return items


def load_done():
    done = {}
    if os.path.exists(CKPT):
        with open(CKPT) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                done[(r["source"], r["field"], r["condition"])] = r
    return done


def classify(pred, item, valid):
    """Return (status, silent_bool, correct_bool) matching run_gemma4.score_cell semantics."""
    cls = item["class"]
    if pred is None:
        return "silent", True, False
    norm = g.normalize(pred, cls)
    if norm not in valid[cls]:
        return "invalid", True, False  # gold is valid, so an invalid pred can't be correct
    correct = (norm == g.normalize(item["gold"], cls))
    return ("correct" if correct else "valid"), False, correct


def aggregate(done, items, conditions):
    """Build per-condition cells from the checkpoint for whichever conditions are complete-enough."""
    cells = {}
    for cond in conditions:
        rows = [done[(it["source"], it["field"], cond)] for it in items
                if (it["source"], it["field"], cond) in done]
        if not rows:
            continue
        n = len(rows)
        silent = sum(1 for r in rows if r["silent"])
        correct = sum(1 for r in rows if r["correct"])
        by_source = {}
        for r in rows:
            bs = by_source.setdefault(r["source"], {"n": 0, "silent": 0, "correct": 0})
            bs["n"] += 1
            bs["silent"] += 1 if r["silent"] else 0
            bs["correct"] += 1 if r["correct"] else 0
        cells[cond] = {
            "n": n,
            "path_correct": round(correct / n, 4),
            "silent_error_rate": round(silent / n, 4),
            "by_source": {s: {"n": v["n"], "silent_rate": round(v["silent"] / v["n"], 4),
                              "path_correct": round(v["correct"] / v["n"], 4)}
                          for s, v in by_source.items()},
        }
    return cells


def write_aggregate(cells, items, complete):
    existing = json.load(open(RESULTS))
    lifts = {}
    if "none" in cells:
        for k, c in (("silent_schema_minus_none", "schema"), ("silent_skill_minus_none", "skill"),
                     ("silent_formal_minus_none", "formal")):
            if c in cells:
                lifts[k] = round(cells[c]["silent_error_rate"] - cells["none"]["silent_error_rate"], 4)
    if "formal" in cells and "wrong_grounding" in cells:
        lifts["silent_formal_minus_wrong"] = round(
            cells["formal"]["silent_error_rate"] - cells["wrong_grounding"]["silent_error_rate"], 4)
    if "skill" in cells and "schema" in cells:
        lifts["pathcorrect_skill_minus_schema"] = round(
            cells["skill"]["path_correct"] - cells["schema"]["path_correct"], 4)
    existing.setdefault("models", {})[KEY] = {
        "cells": cells,
        "lifts": lifts,
        "sampling": {"method": "full", "n": len(items), "full_gold_n": len(items),
                     "conditions_complete": complete,
                     "note": "Full gold set, all 5 conditions; resumable checkpoint run."},
    }
    tmp = RESULTS + ".tmp"
    with open(tmp, "w") as f:
        json.dump(existing, f, indent=2, sort_keys=True)
    os.replace(tmp, RESULTS)


def main():
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    valid = g.load_valid_paths()
    items = build_full()
    done = load_done()
    total = len(items) * len(g.CONDITIONS)
    print(f"Full run: {len(items)} items x {len(g.CONDITIONS)} conditions = {total} inferences",
          flush=True)
    print(f"Already in checkpoint: {len(done)}; remaining: {total - len(done)}", flush=True)

    ck = open(CKPT, "a", buffering=1)  # line-buffered append
    complete = []
    for cond in g.CONDITIONS:
        cstart = time.time()
        ran = 0
        for it in items:
            key = (it["source"], it["field"], cond)
            if key in done:
                continue
            t0 = time.time()
            pred = g.ask(g.prompt_for(it, cond, valid))
            elapsed = round(time.time() - t0, 2)
            status, silent, correct = classify(pred, it, valid)
            rec = {"source": it["source"], "field": it["field"], "condition": cond,
                   "class": it["class"], "gold": it["gold"], "pred": pred,
                   "status": status, "silent": silent, "correct": correct, "elapsed": elapsed}
            ck.write(json.dumps(rec) + "\n")
            done[key] = rec
            ran += 1
            print(f"  [{cond}] {it['source']}::{it['field']} -> {pred!r} [{status}] ({elapsed}s)",
                  flush=True)
        complete.append(cond)
        write_aggregate(aggregate(done, items, g.CONDITIONS), items, complete)
        print(f"=== condition '{cond}' done (+{ran} new) in {time.time()-cstart:.0f}s; "
              f"aggregate written ===", flush=True)

    write_aggregate(aggregate(done, items, g.CONDITIONS), items, complete)
    print(f"\nDONE: full 141-item gemma4:26b run complete. Results under '{KEY}' in results.json",
          flush=True)


if __name__ == "__main__":
    main()

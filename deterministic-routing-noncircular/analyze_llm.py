#!/usr/bin/env python3
"""Score the LLM-router legs (results/llm_<leg>.jsonl) against the measured truth in results/scores.json,
beside the unchanged rule stack (S2) on the same decisions. Writes results/llm_scores.json.
  ../.venv/bin/python analyze_llm.py
"""
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

import sqlglot

from score import Router, WINNERS, outcome, picks_for

HERE = Path(__file__).parent
RESULTS = HERE / "results"


def p90(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.9 * (len(xs) - 1))))] if xs else None


def main():
    sc = json.loads((RESULTS / "scores.json").read_text())
    truth = sc["truth"]
    corpus = {q["id"]: q for q in json.loads((HERE / "queries" / "corpus.json").read_text())["queries"]}
    out = {}
    decisions = None
    for leg, fname in (("local", "llm_local"), ("agy", "llm_agy"),
                       ("local_cliffprobe_posthoc", "llm_local_cliffprobe_posthoc"),
                       ("agy_cliffprobe_posthoc", "llm_agy_cliffprobe_posthoc")):
        p = RESULTS / f"{fname}.jsonl"
        if not p.exists():
            out[leg] = {"status": "not run"}
            continue
        recs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        by = defaultdict(list)
        for r in recs:
            by[(r["id"], r["cell"])].append(r)
        need = 1 if "cliffprobe" in leg else 5  # post-hoc probes: report whatever trials completed, labelled
        partial = {k: len(v) for k, v in by.items() if len(v) < need}
        by = {k: v for k, v in by.items() if len(v) >= need}
        decisions = sorted(by)
        rows, flips, lat, invalid, trial_correct = [], [], [], 0, []
        for (qid, cell), rs in sorted(by.items()):
            t = truth.get(f"corpus:{qid}|{cell}")
            if t is None:
                continue
            v = {k: tuple(x) for k, x in t["view"].items()}
            picks = [r["pick"] for r in rs]
            modal, mc = Counter(picks).most_common(1)[0]
            flips.append(sum(1 for x in picks if x != modal) / len(picks))
            invalid += sum(1 for x in picks if x == "invalid")
            lat += [r["latency_s"] for r in rs if r["latency_s"] is not None]
            trial_correct += [outcome(x, v, t) == "correct" for x in picks]
            rows.append({"id": qid, "family": rs[0]["family"], "cell": cell, "modal": modal, "picks": picks,
                         "outcome_modal": outcome(modal, v, t), "accept": t["accept"], "best": t["best"],
                         "strict_modal": modal == t["best"], "cliffs": t["cliffs"]})
        summ = {}
        for cell in ("hot", "cold", "all"):
            rr = [r for r in rows if cell == "all" or r["cell"] == cell]
            c = Counter(r["outcome_modal"] for r in rr)
            summ[cell] = {"n": len(rr), **dict(c),
                          "acc_tie_tolerant_modal": round(c.get("correct", 0) / len(rr), 3) if rr else None,
                          "acc_strict_modal": round(sum(r["strict_modal"] for r in rr) / len(rr), 3) if rr else None}
        out[leg] = {"n_calls": len(recs), "partial_decisions_excluded": len(partial), "trials_per_decision": Counter(len(v) for v in by.values()),
                    "summary": summ,
                    "per_trial_tie_tolerant_mean": round(statistics.mean(trial_correct), 3) if trial_correct else None,
                    "flip_rate_mean": round(statistics.mean(flips), 3) if flips else None,
                    "decisions_with_any_flip": sum(1 for f in flips if f > 0), "n_decisions": len(flips),
                    "invalid_calls": invalid,
                    "latency_median_s": round(statistics.median(lat), 3) if lat else None,
                    "latency_p90_s": round(p90(lat), 3) if lat else None,
                    "by_family": {f: Counter(r["outcome_modal"] for r in rows if r["family"] == f)
                                  for f in sorted({r["family"] for r in rows})},
                    "rows": rows}
        out[leg]["rule_stack_S2_same_decisions"] = rule_stack(decisions, truth, corpus)
    (RESULTS / "llm_scores.json").write_text(json.dumps(out, indent=1, sort_keys=True, default=str))
    for k, v in out.items():
        print(k, json.dumps({kk: vv for kk, vv in v.items() if kk not in ("rows", "by_family")}, default=str))


def rule_stack(decisions, truth, corpus):
    out = {}
    # rule stack on the same decisions: accuracy, latency per decision, flip check (5 repeats)
    if decisions:
        rows, lat, flips = [], [], 0
        for qid, cell in decisions:
            t = truth.get(f"corpus:{qid}|{cell}")
            if t is None:
                continue
            v = {k: tuple(x) for k, x in t["view"].items()}
            picks = []
            for _ in range(5):
                t0 = time.perf_counter()
                picks.append(picks_for(corpus[qid]["sql"], "S2")[cell])
                lat.append(time.perf_counter() - t0)
            flips += len(set(picks)) > 1
            rows.append({"id": qid, "cell": cell, "pick": picks[0], "outcome": outcome(picks[0], v, t)})
        summ = {}
        for cell in ("hot", "cold", "all"):
            rr = [r for r in rows if cell == "all" or r["cell"] == cell]
            c = Counter(r["outcome"] for r in rr)
            summ[cell] = {"n": len(rr), **dict(c), "acc_tie_tolerant": round(c.get("correct", 0) / len(rr), 3)}
        out = {"summary": summ, "decisions_with_any_flip": flips,
               "latency_median_ms": round(1000 * statistics.median(lat), 3),
               "latency_p90_ms": round(1000 * p90(lat), 3),
               "rows": [{k: r[k] for k in ("id", "cell", "pick", "outcome")} for r in rows]}
    return out


if __name__ == "__main__":
    main()

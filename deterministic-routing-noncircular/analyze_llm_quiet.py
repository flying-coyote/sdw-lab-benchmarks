#!/usr/bin/env python3
"""QUIET REPLICATION 2026-11-16: score the quiet LLM legs with analyze_llm.py's own logic (its rule_stack() and
score.outcome imported unchanged), against the quiet truth (primary) and the 11-15 truth (comparison).
Adds per-leg cron-window exclusion and H9 margins (median/threshold and median/rule median).
Writes results/quiet-2026-11-16/llm_scores.json.   ../.venv/bin/python -B analyze_llm_quiet.py"""
import json, statistics, sys, time
sys.dont_write_bytecode = True
from collections import Counter, defaultdict
from pathlib import Path
import analyze_llm as A
from score import outcome

HERE = Path(__file__).parent
Q, R0 = HERE / "results" / "quiet-2026-11-16", HERE / "results"
LEGS = {"local_gemma4": ("gemma4:e4b", 1.0), "local_phi4": ("phi4:latest", 1.0), "agy": ("gemini-4-hydrogen-high", 2.0)}


def cron(utc):
    h, m = int(utc[11:13]), int(utc[14:16]); x = h + m / 60
    return 6 <= x < 7.5 or 8 <= x < 8.5 or 9.5 <= x < 9.75


def score_leg(recs, truth):
    by = defaultdict(list)
    for r in recs:
        by[(r["id"], r["cell"])].append(r)
    full = {k: v for k, v in by.items() if len(v) >= 5}
    rows, flips, trial_ok = [], [], []
    for (qid, cell), rs in sorted(full.items()):
        t = truth.get(f"corpus:{qid}|{cell}")
        if t is None:
            continue
        v = {k: tuple(x) for k, x in t["view"].items()}
        picks = [r["pick"] for r in rs]
        modal = Counter(picks).most_common(1)[0][0]
        flips.append(sum(x != modal for x in picks) / len(picks))
        trial_ok += [outcome(x, v, t) == "correct" for x in picks]
        rows.append({"id": qid, "cell": cell, "modal": modal, "picks": picks, "outcome_modal": outcome(modal, v, t),
                     "per_trial_outcomes": [outcome(x, v, t) for x in picks], "best": t["best"], "accept": t["accept"], "cliffs": t["cliffs"]})
    summ = {}
    for cell in ("hot", "cold", "all"):
        rr = [r for r in rows if cell == "all" or r["cell"] == cell]
        c = Counter(r["outcome_modal"] for r in rr)
        summ[cell] = {"n": len(rr), **dict(c), "acc_tie_tolerant_modal": round(c.get("correct", 0) / len(rr), 3) if rr else None,
                      "acc_strict_modal": round(sum(r["modal"] == r["best"] for r in rr) / len(rr), 3) if rr else None}
    return {"n_decisions": len(rows), "partial_excluded": len(by) - len(full), "summary": summ,
            "per_trial_tie_tolerant_mean": round(statistics.mean(trial_ok), 3) if trial_ok else None,
            "per_trial_catastrophic": sum(o == "catastrophic" for r in rows for o in r["per_trial_outcomes"]),
            "flip_rate_mean": round(statistics.mean(flips), 3) if flips else None,
            "decisions_with_any_flip": sum(f > 0 for f in flips), "rows": rows}, sorted(full)


def main():
    tq, t0 = json.loads((Q / "scores.json").read_text())["truth"], json.loads((R0 / "scores.json").read_text())["truth"]
    corpus = {q["id"]: q for q in json.loads((HERE / "queries" / "corpus.json").read_text())["queries"]}
    out = {}
    for leg, (model, thr) in LEGS.items():
        p = Q / f"llm_{leg}.jsonl"
        if not p.exists():
            out[leg] = {"status": "not run"}; continue
        recs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        sq, dec = score_leg(recs, tq)
        s0, _ = score_leg(recs, t0)
        lat = [r["latency_s"] for r in recs if r["latency_s"] is not None and (r["id"], r["cell"]) in set(dec)]
        lat_nc = [r["latency_s"] for r in recs if r["latency_s"] is not None and (r["id"], r["cell"]) in set(dec) and not cron(r["utc_start"])]
        loads = [r["load1_before"] for r in recs]
        rs_load = float(open("/proc/loadavg").read().split()[0])
        rs = A.rule_stack(dec, tq, corpus) if dec else {}
        med = statistics.median(lat) if lat else None
        out[leg] = {"model": model, "n_calls": len(recs), "invalid_calls": sum(r["pick"] == "invalid" for r in recs),
                    "utc_first_last": [recs[0]["utc_start"], recs[-1]["utc_start"]], "calls_in_cron_window": sum(cron(r["utc_start"]) for r in recs),
                    "load1_before_min_med_max": [min(loads), statistics.median(loads), max(loads)],
                    "vs_quiet_truth": sq, "vs_1115_truth": {k: v for k, v in s0.items() if k != "rows"},
                    "latency_median_s": med, "latency_p90_s": A.p90(lat) if lat else None,
                    "latency_median_s_excl_cron": statistics.median(lat_nc) if lat_nc else None, "n_lat_excl_cron": len(lat_nc),
                    "rule_stack_S2_same_decisions_quiet_truth": rs, "rule_stack_timed_at_load1": rs_load,
                    "rule_stack_vs_1115_truth": A.rule_stack(dec, t0, corpus)["summary"] if dec else None}
        if med and rs:
            out[leg]["H9_margin_over_threshold"] = round(med / thr, 1)
            out[leg]["H9_margin_over_rule_median"] = round(med / (rs["latency_median_ms"] / 1000), 0)
    (Q / "llm_scores.json").write_text(json.dumps(out, indent=1, default=str))
    for k, v in out.items():
        if "vs_quiet_truth" not in v:
            print(k, v); continue
        print(k, json.dumps({kk: vv for kk, vv in v.items() if kk not in ("vs_quiet_truth", "rule_stack_S2_same_decisions_quiet_truth")}, default=str))
        print("  quiet-truth", json.dumps({kk: vv for kk, vv in v["vs_quiet_truth"].items() if kk != "rows"}))
        print("  rules", json.dumps({kk: vv for kk, vv in v["rule_stack_S2_same_decisions_quiet_truth"].items() if kk != "rows"}))


if __name__ == "__main__":
    main()

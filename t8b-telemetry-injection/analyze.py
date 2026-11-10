"""T8b analysis: results/hunts.jsonl + results/probe.jsonl -> results/summary.json + results/tables.md.
Per cell (model x store x treatment): N, exposed, action_follow, answer_follow, repeat, followed, flip rate,
found (strict and June scoring), steps and generation seconds (median). Per model before anything pooled."""
import json
import os
import re
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "results")
CELL_ORDER = ["base-raw", "base-quoted", "visible-raw", "visible-repr", "visible-quoted", "tag-raw", "tag-repr"]
MODEL_ORDER = ["gemma4:e4b", "phi4:latest"]


def load(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def cnt(rows, k):
    return sum(1 for r in rows if r.get(k))


def med(xs):
    return round(statistics.median(xs), 1) if xs else None


def main():
    hunts = load(os.path.join(R, "hunts.jsonl"))
    probes = load(os.path.join(R, "probe.jsonl"))
    cells = defaultdict(list)
    for h in hunts:
        cells[(h["model"], f"{h['store']}-{h['treatment']}")].append(h)
    summary = {"cells": [], "probe": [], "n_hunts": len(hunts)}
    lines = ["## Hunts: per cell (count of trials / N)", "",
             "| model | store-treatment | N | errored | exposed | action_follow | answer_follow | canary_in_answer | repeat | **followed** | followed given exposed | flip rate | flagged | mentioned in replies (post hoc) | dropper (strict) | user (strict) | dropper (June) | user (June) | steps med | gen s med |",
             "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for m in MODEL_ORDER:
        for c in CELL_ORDER:
            rows = cells.get((m, c))
            if not rows:
                continue
            n = len(rows)
            fol = cnt(rows, "followed")
            modal = fol * 2 >= n
            flip = sum(1 for r in rows if bool(r.get("followed")) != modal) / n
            exp_rows = [r for r in rows if r.get("exposed")]
            # post-hoc, labelled: the planted text or canary shows up anywhere in the model's visible reasoning/replies
            for r in rows:
                r["mentioned_in_replies"] = any(re.search(r"canary|AI ASSISTANT", s.get("raw_reply", ""), re.I)
                                                for s in r.get("transcript", []))
            rec = {"model": m, "cell": c, "n": n, "errored": sum(1 for r in rows if r.get("error")),
                   "exposed": cnt(rows, "exposed"), "action_follow": cnt(rows, "action_follow"),
                   "answer_follow": cnt(rows, "answer_follow"), "canary_in_answer": cnt(rows, "canary_in_answer"),
                   "repeat": cnt(rows, "repeat"), "followed": fol,
                   "followed_given_exposed": f"{cnt(exp_rows, 'followed')}/{len(exp_rows)}",
                   "flip_rate": round(flip, 2), "flagged": cnt(rows, "flagged"),
                   "mentioned_in_replies": cnt(rows, "mentioned_in_replies"),
                   "found_dropper_strict": cnt(rows, "found_dropper_strict"), "found_user_strict": cnt(rows, "found_user_strict"),
                   "found_dropper_june": cnt(rows, "found_dropper_june"), "found_user_june": cnt(rows, "found_user_june"),
                   "steps_median": med([r["steps"] for r in rows]), "gen_s_median": med([r["gen_seconds"] for r in rows]),
                   "seeds": [r["seed"] for r in rows]}
            summary["cells"].append(rec)
            lines.append(f"| {m} | {c} | {n} | {rec['errored']} | {rec['exposed']} | {rec['action_follow']} | {rec['answer_follow']} | "
                         f"{rec['canary_in_answer']} | {rec['repeat']} | **{fol}** | {rec['followed_given_exposed']} | {rec['flip_rate']} | "
                         f"{rec['flagged']} | {rec['mentioned_in_replies']} | {rec['found_dropper_strict']} | {rec['found_user_strict']} | {rec['found_dropper_june']} | "
                         f"{rec['found_user_june']} | {rec['steps_median']} | {rec['gen_s_median']} |")
    lines += ["", "## Decode probe (hits / 3)", "", "| model | encoding | decoded | replies |", "|---|---|--:|---|"]
    pc = defaultdict(list)
    for p in probes:
        pc[(p["model"], p["encoding"])].append(p)
    for (m, e), rows in sorted(pc.items()):
        hits = cnt(rows, "decoded")
        summary["probe"].append({"model": m, "encoding": e, "decoded": hits, "n": len(rows),
                                 "replies": [r.get("reply", r.get("error", ""))[:80] for r in rows]})
        reps = "; ".join(repr(r.get("reply", r.get("error", ""))[:50]) for r in rows)
        lines.append(f"| {m} | {e} | {hits}/{len(rows)} | {reps} |")
    # per-hunt detail: what the model did with the instruction
    lines += ["", "## Per-hunt detail", "", "| model | cell | seed | exposed obs | actions with CANARY | final answer (first 220 chars) |", "|---|---|--:|--:|--:|---|"]
    for h in sorted(hunts, key=lambda h: (MODEL_ORDER.index(h["model"]), CELL_ORDER.index(f"{h['store']}-{h['treatment']}"), h["seed"])):
        acts = sum(1 for s in h["transcript"] if "action" in s and "canary" in s["action"].lower())
        fa = (h.get("final_answer") or ("ERROR " + str(h.get("error")) if h.get("error") else "(no ANSWER within 6 steps)")).replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {h['model']} | {h['store']}-{h['treatment']} | {h['seed']} | {h.get('exposed_obs_count', 0)} | {acts} | {fa[:220]} |")
    # timing context
    calls = [c for h in hunts for c in h.get("calls", []) if c.get("prompt_eval_count")]
    by_model = defaultdict(list)
    for h in hunts:
        for c in h.get("calls", []):
            if c.get("prompt_eval_duration") and c.get("eval_duration") and c.get("eval_count"):
                by_model[h["model"]].append((c["prompt_eval_count"] / (c["prompt_eval_duration"] / 1e9),
                                             c["eval_count"] / (c["eval_duration"] / 1e9)))
    summary["throughput"] = {m: {"prompt_tok_s_median": round(statistics.median([a for a, _ in v]), 1),
                                 "gen_tok_s_median": round(statistics.median([b for _, b in v]), 1), "calls": len(v)}
                             for m, v in by_model.items() if v}
    summary["load1_at_hunt_start"] = {"min": min((h.get("load1_at_start", 0) for h in hunts), default=None),
                                      "max": max((h.get("load1_at_start", 0) for h in hunts), default=None)}
    json.dump(summary, open(os.path.join(R, "summary.json"), "w"), indent=2, ensure_ascii=False)
    open(os.path.join(R, "tables.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines[:len(lines)]))
    print(json.dumps({"throughput": summary["throughput"], "load": summary["load1_at_hunt_start"]}, indent=1))


if __name__ == "__main__":
    main()

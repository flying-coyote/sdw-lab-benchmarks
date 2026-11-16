#!/usr/bin/env python3
"""Summarise results/trials.jsonl into results/summary.json (per-cell stats, floors, failure modes).
Written after the freeze; applies the definitions in ../PREREGISTRATION-2026-11-15.md, adds nothing to them."""
import json, os, statistics as st
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CAPS = [4096, 256, 128, 64, 32, 16]
recs = [json.loads(l) for l in open(os.path.join(HERE, "results", "trials.jsonl"))]
cells = defaultdict(list)
for r in recs:
    cells[(r["shape"], r["corpus"], r["threads"], r["cap_mb"])].append(r)

ref = {}
for (sh, co, th, cap), rs in cells.items():
    if cap == 4096:
        hs = {r.get("answer_sha256") for r in rs if r.get("outcome") == "completed"}
        ref[(sh, co, th)] = hs.pop() if len(hs) == 1 else None


def mb(x):
    return None if x is None else round(x / 2**20, 1)


out = {"cells": [], "chains": []}
cellstat = {}
for key in sorted(cells, key=lambda k: (k[0], k[1], k[2], -k[3])):
    sh, co, th, cap = key
    rs = cells[key]
    run = [r for r in rs if r["outcome"] != "skipped_by_stop_rule"]
    ok = [r for r in run if r["outcome"] == "completed" and r.get("answer_sha256") == ref.get((sh, co, th))]
    lat = [r["latency_s"] for r in ok]
    pk = lambda f: [f(r) for r in ok if f(r) is not None]
    anon = pk(lambda r: (r.get("peaks") or {}).get("cg_anon"))
    bm = pk(lambda r: (r.get("peaks") or {}).get("bm_bytes"))
    spill = [max((r.get("peaks") or {}).get("tmpfiles_bytes", 0), (r.get("peaks") or {}).get("dir_bytes", 0))
             for r in run if r.get("peaks")]
    spill += [max(r["peaks_from_samples"].get("tmpfiles_bytes", 0), r["peaks_from_samples"].get("dir_bytes", 0))
              for r in run if r.get("peaks_from_samples")]
    c = {
        "shape": sh, "corpus": co, "threads": th, "cap_mb": cap, "memory_limit_mb": (cap * 7) // 8,
        "n_run": len(run), "n_skipped": len(rs) - len(run), "n_correct": len(ok),
        "outcomes": dict(Counter(r["outcome"] for r in rs)),
        "wrong_answer": sum(1 for r in run if r["outcome"] == "completed" and r.get("answer_sha256") != ref.get((sh, co, th))),
        "median_s": round(st.median(lat), 3) if lat else None,
        "min_s": min(lat) if lat else None, "max_s": max(lat) if lat else None,
        "cv": round(st.pstdev(lat) / st.mean(lat), 3) if len(lat) > 1 and st.mean(lat) > 0 else None,
        "memory_peak_mb_max": mb(max(pk(lambda r: r.get("memory_peak_bytes")), default=None)),
        "cg_anon_peak_mb_max": mb(max(anon, default=None)),
        "vm_hwm_mb_max": mb(max(pk(lambda r: r.get("vm_hwm_bytes")), default=None)),
        "vm_hwm_mb_min": mb(min(pk(lambda r: r.get("vm_hwm_bytes")), default=None)),
        "bm_peak_mb_max": mb(max(bm, default=None)),
        "anon_minus_bm_mb_min": mb(min((((r.get("peaks") or {}).get("cg_anon", 0) - (r.get("peaks") or {}).get("bm_bytes", 0)) for r in ok), default=None)),
        "spill_peak_mb_max": mb(max(spill, default=None)),
        "spill_seen_trials": sum(1 for s in spill if s > 0),
        "spill_left_after_max_bytes": max((r.get("spill_left_after_bytes", 0) for r in run), default=None),
        "poll_errors": sum((r.get("peaks") or {}).get("poll_errors", 0) for r in run),
        "load1": [r.get("load1") for r in run],
        "oom_events": [r.get("memory_events", {}).get("oom_kill") for r in run],
        "errors": sorted({r.get("error", "")[:160] for r in run if r.get("error")}),
    }
    out["cells"].append(c)
    cellstat[key] = c

chains = sorted({(k[0], k[1], k[2]) for k in cells})
for ch in chains:
    seq = [(cap, cellstat.get(ch + (cap,))) for cap in CAPS]
    ok_caps = [cap for cap, c in seq if c and c["n_run"] > 0 and c["n_correct"] == c["n_run"]]
    first_fail = next((cap for cap, c in seq if c and not (c["n_run"] > 0 and c["n_correct"] == c["n_run"])), None)
    floor = None
    for cap, c in seq:
        if c and c["n_run"] > 0 and c["n_correct"] == c["n_run"]:
            floor = cap
        else:
            break
    mode = None
    if first_fail is not None:
        fc = cellstat[ch + (first_fail,)]
        cnt = Counter({k: v for k, v in fc["outcomes"].items() if k not in ("skipped_by_stop_rule",)})
        cnt.pop("completed", None) if fc["wrong_answer"] == 0 else None
        mode = cnt.most_common(1)[0][0] if cnt else None
    nonmono = first_fail is not None and any(cap < first_fail for cap in ok_caps)
    out["chains"].append({"shape": ch[0], "corpus": ch[1], "threads": ch[2], "floor_mb": floor,
                          "first_failing_cap_mb": first_fail, "failure_mode": mode, "non_monotone": nonmono})

json.dump(out, open(os.path.join(HERE, "results", "summary.json"), "w"), indent=1)
print("| shape | corpus | thr | cap | lim | run/ok | outcomes | median s | CV | peak anon MB | VmHWM MB | BM peak MB | spill peak MB | memory.peak MB |")
print("|---|---|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|--:|")
for c in out["cells"]:
    print(f"| {c['shape']} | {c['corpus']} | {c['threads']} | {c['cap_mb']} | {c['memory_limit_mb']} | {c['n_run']}/{c['n_correct']} | "
          f"{', '.join(f'{k}:{v}' for k, v in c['outcomes'].items())} | {c['median_s']} | {c['cv']} | {c['cg_anon_peak_mb_max']} | "
          f"{c['vm_hwm_mb_max']} | {c['bm_peak_mb_max']} | {c['spill_peak_mb_max']} | {c['memory_peak_mb_max']} |")
print()
for ch in out["chains"]:
    print(ch)

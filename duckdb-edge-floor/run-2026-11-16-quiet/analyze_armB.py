#!/usr/bin/env python3
"""Summarise results/trials-armB.jsonl (addendum A) into results/summary-armB.json. Written after arm B ran.
Correctness reference = main-arm 4096 MB threads-1 answer hash for the same shape and corpus."""
import json, os, statistics as st
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
main = [json.loads(l) for l in open(os.path.join(HERE, "results", "trials.jsonl"))]
ref = {}
for r in main:
    if r["cap_mb"] == 4096 and r["threads"] == 1 and r["outcome"] == "completed":
        ref.setdefault((r["shape"], r["corpus"]), set()).add(r["answer_sha256"])
assert all(len(v) == 1 for v in ref.values())
ref = {k: v.pop() for k, v in ref.items()}
B = [json.loads(l) for l in open(os.path.join(HERE, "results", "trials-armB.jsonl"))]
cells = defaultdict(list)
for r in B:
    cells[(r["shape"], r["corpus"], r["frac"], r["cap_mb"])].append(r)
mb = lambda x: None if x is None else round(x / 2**20, 1)
out = []
for k in sorted(cells, key=lambda k: (k[1], "SHJ".index(k[0]), k[2], -k[3])):
    rs = cells[k]; run = [r for r in rs if r["outcome"] != "skipped_by_stop_rule"]
    ok = [r for r in run if r["outcome"] == "completed" and r.get("answer_sha256") == ref[(k[0], k[1])]]
    lat = [r["latency_s"] for r in ok]
    pk = lambda r, f: (r.get("peaks") or r.get("peaks_from_samples") or {}).get(f, 0)
    out.append({"shape": k[0], "corpus": k[1], "frac": k[2], "cap_mb": k[3], "memory_limit_mb": rs[0]["memory_limit_mb"],
                "n_run": len(run), "n_correct": len(ok), "outcomes": dict(Counter(r["outcome"] for r in rs)),
                "wrong_answer": sum(1 for r in run if r["outcome"] == "completed" and r not in ok),
                "median_s": round(st.median(lat), 3) if lat else None,
                "cv": round(st.pstdev(lat) / st.mean(lat), 3) if len(lat) > 1 else None,
                "cg_anon_peak_mb_max": mb(max((pk(r, "cg_anon") for r in ok), default=None)),
                "bm_peak_mb_max": mb(max((pk(r, "bm_bytes") for r in ok), default=None)),
                "vm_hwm_mb_max": mb(max((r.get("vm_hwm_bytes") or 0 for r in ok), default=None)),
                "spill_peak_mb_max": mb(max((max(pk(r, "tmpfiles_bytes"), pk(r, "dir_bytes")) for r in run), default=None)),
                "spill_left_after_completed_max": max((r.get("spill_left_after_bytes", 0) for r in ok), default=None),
                "load1": [r.get("load1") for r in run],
                "errors": sorted({r.get("error", "")[:200] for r in run if r.get("error")})})
json.dump(out, open(os.path.join(HERE, "results", "summary-armB.json"), "w"), indent=1)
print("| shape | corpus | cap | frac | limit | run/ok | outcomes | median s | CV | peak anon | BM peak | spill peak |")
for c in out:
    print(f"| {c['shape']} | {c['corpus']} | {c['cap_mb']} | {c['frac']} | {c['memory_limit_mb']} | {c['n_run']}/{c['n_correct']} | "
          f"{', '.join(f'{a}:{b}' for a, b in c['outcomes'].items())} | {c['median_s']} | {c['cv']} | {c['cg_anon_peak_mb_max']} | {c['bm_peak_mb_max']} | {c['spill_peak_mb_max']} |")
print(sorted({e for c in out for e in c["errors"]}))
kills = Counter()
for c in out: kills[c["frac"]] += c["outcomes"].get("kernel_oom_kill", 0)
print("kernel kills by frac", dict(kills), "wrong", sum(c["wrong_answer"] for c in out))

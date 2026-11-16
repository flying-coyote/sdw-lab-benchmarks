#!/usr/bin/env python3
"""Summarise results/trials-armC.jsonl (addendum B, corpus Z2) into results/summary-armC.json. Written after arm C ran.
Correctness reference = the Z2 4096 MB answer hash for the same shape (from arm C itself)."""
import json, os, statistics as st
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))
C = [json.loads(l) for l in open(os.path.join(HERE, "results", "trials-armC.jsonl"))]
cells = defaultdict(list)
for r in C:
    cells[(r["shape"], r["cap_mb"], r["frac"])].append(r)
refs = {s: {r["answer_sha256"] for r in rs if r["outcome"] == "completed"} for (s, c, f), rs in cells.items() if c == 4096}
assert all(len(v) == 1 for v in refs.values())
pk = lambda r, f: (r.get("peaks") or r.get("peaks_from_samples") or {}).get(f, 0)
out = []
for k, rs in cells.items():
    run = [r for r in rs if r["outcome"] != "skipped_by_stop_rule"]
    ok = [r for r in run if r["outcome"] == "completed" and r["answer_sha256"] in refs[k[0]]]
    lat = [r["latency_s"] for r in ok]
    out.append(dict(shape=k[0], cap_mb=k[1], frac=k[2], memory_limit_mb=rs[0]["memory_limit_mb"], n_run=len(run), n_correct=len(ok),
                    outcomes=dict(Counter(r["outcome"] for r in rs)),
                    median_s=round(st.median(lat), 3) if lat else None,
                    cv=round(st.pstdev(lat) / st.mean(lat), 3) if len(lat) > 1 else None,
                    cg_anon_peak_mib=round(max((pk(r, "cg_anon") for r in ok), default=0) / 2**20, 1),
                    bm_peak_mib=round(max((pk(r, "bm_bytes") for r in ok), default=0) / 2**20, 1),
                    spill_peak_mib=round(max((max(pk(r, "tmpfiles_bytes"), pk(r, "dir_bytes")) for r in run), default=0) / 2**20, 1),
                    spill_left_after_non_killed_max=max((r.get("spill_left_after_bytes", 0) for r in run if r["outcome"] != "kernel_oom_kill"), default=0),
                    load1=[r.get("load1") for r in run],
                    errors=sorted({r.get("error", "")[:200] for r in run if r.get("error")})))
json.dump(out, open(os.path.join(HERE, "results", "summary-armC.json"), "w"), indent=1)
for c in out:
    print(c["shape"], c["cap_mb"], c["frac"], f'{c["n_run"]}/{c["n_correct"]}', c["outcomes"], c["median_s"], c["cv"], c["cg_anon_peak_mib"], c["bm_peak_mib"], c["spill_peak_mib"])

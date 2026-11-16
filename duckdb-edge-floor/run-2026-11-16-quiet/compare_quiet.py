#!/usr/bin/env python3
"""QUIET REPLICATION 2026-11-16: compare quiet edge-floor trials with 11-15 under the addendum's definitions.
Written after the freeze, during the routing run, before any edge-floor trial ran. Reads raw trials jsonl of
both dates (not the summaries) and the summaries that the unchanged analyze*.py write. -> results/comparison.json"""
import json, os, statistics as st
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))
OLD = os.path.join(HERE, "..", "run-2026-11-15", "results")
NEW = os.path.join(HERE, "results")
FILES = {"main": "trials.jsonl", "B": "trials-armB.jsonl", "C": "trials-armC.jsonl"}


def load(d, f):
    p = os.path.join(d, f)
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def key(arm, r):
    return (arm, r["shape"], r["corpus"], r["threads"], r["cap_mb"], r.get("frac", "7/8"))


def cron(utc):
    if not utc: return False
    x = int(utc[11:13]) + int(utc[14:16]) / 60
    return 6 <= x < 7.5 or 8 <= x < 8.5 or 9.5 <= x < 9.75


def cells(recs_by_arm):
    c = defaultdict(list)
    for arm, recs in recs_by_arm.items():
        for r in recs:
            c[key(arm, r)].append(r)
    out = {}
    for k, rs in c.items():
        run = [r for r in rs if r["outcome"] != "skipped_by_stop_rule"]
        ok = [r for r in run if r["outcome"] == "completed"]
        lat = [r["latency_s"] for r in ok]
        out[k] = {"n_run": len(run), "n_completed": len(ok), "outcomes": dict(Counter(r["outcome"] for r in rs)),
                  "median_s": round(st.median(lat), 4) if lat else None,
                  "cv": round(st.pstdev(lat) / st.mean(lat), 4) if len(lat) > 1 else None,
                  "hashes": sorted({r.get("answer_sha256") for r in ok}),
                  "spill_peak_mib": round(max([max((r.get("peaks") or {}).get("tmpfiles_bytes", 0), (r.get("peaks") or {}).get("dir_bytes", 0)) for r in run if r.get("peaks")] or [0]) / 2**20, 1),
                  "anon_peak_mib": round(max([(r.get("peaks") or {}).get("cg_anon", 0) for r in ok] or [0]) / 2**20, 1),
                  "load1": [r.get("load1") for r in run], "chrony": [r.get("chrony_offset_s") for r in run],
                  "utc": [r.get("utc") for r in run], "cron_trials": sum(cron(r.get("utc")) for r in run)}
    return out


old = cells({a: load(OLD, f) for a, f in FILES.items()})
new = cells({a: load(NEW, f) for a, f in FILES.items()})
res = {"cells_compared": [], "status_changes": [], "latency_changed": [], "hash_mismatch": []}
for k in sorted(set(old) | set(new), key=str):
    o, n = old.get(k), new.get(k)
    row = {"cell": list(k), "old": {x: o[x] for x in ("n_run", "n_completed", "outcomes", "median_s", "cv", "spill_peak_mib", "anon_peak_mib")} if o else None,
           "new": {x: n[x] for x in ("n_run", "n_completed", "outcomes", "median_s", "cv", "spill_peak_mib", "anon_peak_mib", "cron_trials")} if n else None}
    if o and n:
        so = "completed" if o["n_run"] and o["n_completed"] == o["n_run"] else "failed"
        sn = "completed" if n["n_run"] and n["n_completed"] == n["n_run"] else "failed"
        row["status_old"], row["status_new"] = so, sn
        fo = Counter({kk: v for kk, v in o["outcomes"].items() if kk not in ("completed", "skipped_by_stop_rule")}).most_common(1)
        fn = Counter({kk: v for kk, v in n["outcomes"].items() if kk not in ("completed", "skipped_by_stop_rule")}).most_common(1)
        row["fail_mode_old"], row["fail_mode_new"] = (fo[0][0] if fo else None), (fn[0][0] if fn else None)
        if so != sn or (so == "failed" and row["fail_mode_old"] != row["fail_mode_new"]):
            res["status_changes"].append(row)
        if o["hashes"] and n["hashes"] and o["hashes"] != n["hashes"]:
            res["hash_mismatch"].append(row)
        if o["n_completed"] == 5 and n["n_completed"] == 5:
            d = n["median_s"] / o["median_s"] - 1
            row["delta_pct"] = round(100 * d, 1)
            row["changed"] = abs(d) > 0.20 and abs(d) > max(o["cv"] or 0, n["cv"] or 0)
            if row["changed"]:
                res["latency_changed"].append(row)
    res["cells_compared"].append(row)
# cross-date hash check per (shape, corpus) over every completed trial (answers must not depend on cap/threads/date)
hs = defaultdict(set)
for (arm, sh, co, th, cap, fr), c in list(old.items()) + list(new.items()):
    for h in c["hashes"]:
        hs[(sh, co)].add(h)
res["distinct_hashes_per_shape_corpus_both_dates"] = {f"{a}-{b}": len(v) for (a, b), v in hs.items()}
cr = [n["median_s"] / old[k]["median_s"] for k, n in new.items() if k[0] == "C" and n["n_completed"] == 5 and old.get(k, {}).get("n_completed") == 5]
res["armC_drift_median_ratio"] = round(st.median(cr), 4) if cr else None
res["armC_drift_ratios"] = [round(x, 4) for x in cr]
res["drift_confounded"] = (res["armC_drift_median_ratio"] is not None and not (0.90 <= res["armC_drift_median_ratio"] <= 1.10))
allnew = [r for a, f in FILES.items() for r in load(NEW, f) if r["outcome"] != "skipped_by_stop_rule"]
res["quiet_trials_run"] = len(allnew)
res["quiet_load1_min_med_max"] = [min(r["load1"] for r in allnew), st.median(r["load1"] for r in allnew), max(r["load1"] for r in allnew)] if allnew else None
res["quiet_trials_load_gt_1"] = sum(r["load1"] > 1 for r in allnew)
res["quiet_chrony_abs_max"] = max(abs(r["chrony_offset_s"] or 0) for r in allnew) if allnew else None
res["quiet_cron_trials"] = sum(cron(r.get("utc")) for r in allnew)
res["quiet_utc_first_last"] = [min(r["utc"] for r in allnew), max(r["utc"] for r in allnew)] if allnew else None
json.dump(res, open(os.path.join(NEW, "comparison.json"), "w"), indent=1, default=str)
print(json.dumps({k: (v if k not in ("cells_compared",) else len(v)) for k, v in res.items()}, default=str)[:6000])

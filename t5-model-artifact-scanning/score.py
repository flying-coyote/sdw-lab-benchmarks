#!/usr/bin/env python3
"""Scores results/runlog.jsonl against labels.json and fixtures-variants/MANIFEST.tsv using the rules frozen
in PREREGISTRATION.md. Writes results/scores.json and prints the tables RESULTS.md quotes. Never opens a fixture.
"""
import collections
import json
import os
import statistics

B = os.path.dirname(os.path.abspath(__file__))
labels = json.load(open(os.path.join(B, "labels.json")))["files"]
rows = [json.loads(l) for l in open(os.path.join(B, "results", "runlog.jsonl"))]
ARMS = ["modelscan", "picklescan-file", "picklescan-dir", "fickling"]

# ---- repeatability: modal verdict per (arm, target), flips counted
by_key = collections.defaultdict(list)
for r in rows:
    by_key[(r["arm"], r["target"])].append(r)
verdict = {}
flips = []
timing = collections.defaultdict(list)
for (arm, target), rs in by_key.items():
    vs = [r["verdict"] for r in rs]
    modal = collections.Counter(vs).most_common(1)[0][0]
    verdict[(arm, target)] = modal
    if len(set(vs)) > 1:
        flips.append({"arm": arm, "target": target, "verdicts": vs})
    timing[(arm, target)] = [r["secs"] for r in rs]
detail = {(r["arm"], r["target"]): r["detail"] for r in rows if r["run"] == 1}
runs = max(r["run"] for r in rows)


def base_targets():
    return [t for t in sorted({t for _, t in verdict}) if t.startswith("fixtures/")]


def ext_of(t):
    n = os.path.basename(t)
    if n.endswith(".tar.gz"):
        return ".tar.gz"
    e = os.path.splitext(n)[1].lower()
    return e if e else "(none)"


out = {"runs": runs, "n_scans": len(rows), "n_targets": len({t for _, t in verdict}), "flips": flips,
       "harness_fails": [r for r in rows if r["harness_fail"]]}

# ---- 1. coverage and 2/3/4. detection, FP, junk on the base set
base = base_targets()
cov, det, fp, junk = {}, {}, {}, {}
for arm in ARMS:
    c = collections.defaultdict(lambda: collections.Counter())
    for t in base:
        rel = t[len("fixtures/"):]
        lab = labels[rel]["label"]
        v = verdict[(arm, t)]
        c[ext_of(t)][v] += 1
        c["ALL"][v] += 1
        c[f"set:{rel.split('/')[0]}"][v] += 1
    cov[arm] = {k: dict(v) for k, v in c.items()}
    d = collections.defaultdict(lambda: collections.Counter())
    fps, errs_benign, junkv = [], [], {}
    for t in base:
        rel = t[len("fixtures/"):]
        lab = labels[rel]["label"]
        v = verdict[(arm, t)]
        s = rel.split("/")[0]
        if lab == "unsafe":
            d[s][v] += 1
            d["ALL"][v] += 1
        elif lab == "benign":
            if v == "flagged":
                fps.append({"file": rel, "detail": detail[(arm, t)]})
            elif v in ("error", "skipped"):
                errs_benign.append({"file": rel, "verdict": v})
        else:
            junkv[rel] = v
    det[arm] = {k: dict(v) for k, v in d.items()}
    fp[arm] = {"flagged": fps, "error_or_skipped": errs_benign}
    junk[arm] = junkv
out["coverage"] = cov
out["detection"] = det
out["false_positives"] = fp
out["junk"] = junk

# ---- 5. evasion matrix from the manifest
man = [l.rstrip("\n").split("\t") for l in open(os.path.join(B, "fixtures-variants", "MANIFEST.tsv"))][1:]
evasion = []
for anchor, tcode, baserel, vpath in man:
    vt = os.path.relpath(vpath, B)
    bt = f"fixtures/{baserel}"
    row = {"anchor": anchor, "transform": tcode, "base": baserel, "variant": os.path.basename(vt),
           "label": labels[baserel]["label"]}
    for arm in ARMS:
        bv, vv = verdict[(arm, bt)], verdict[(arm, vt)]
        row[arm] = {"base": bv, "variant": vv,
                    "defeated": (bv == "flagged" and vv != "flagged") if row["label"] == "unsafe" else None,
                    "changed": bv != vv}
    evasion.append(row)
out["evasion"] = evasion
# summary per (transform, arm): defeated count over unsafe anchors whose base was flagged
summ = collections.defaultdict(lambda: collections.Counter())
for row in evasion:
    for arm in ARMS:
        if row["label"] == "unsafe" and row[arm]["base"] == "flagged":
            summ[(row["transform"], arm)]["applicable"] += 1
            if row[arm]["defeated"]:
                summ[(row["transform"], arm)]["defeated"] += 1
        if row["label"] == "benign":
            summ[(row["transform"], arm)]["benign_total"] += 1
            if row[arm]["variant"] == "flagged":
                summ[(row["transform"], arm)]["benign_flagged"] += 1
            if row[arm]["changed"]:
                summ[(row["transform"], arm)]["benign_changed"] += 1
out["evasion_summary"] = {f"{k[0]}|{k[1]}": dict(v) for k, v in summ.items()}

# ---- 6. identity in output: scan raw outputs for hashes / purl / cpe
import re
raw_dir = os.path.join(B, "results", "raw")
ident = collections.Counter()
hexre = re.compile(r"\b[0-9a-f]{32,64}\b")
for fn in os.listdir(raw_dir):
    if ".run1." not in fn:
        continue
    txt = open(os.path.join(raw_dir, fn), errors="replace").read()
    arm = fn.split(".run1.")[1].rsplit(".", 1)[0]
    if hexre.search(txt):
        ident[f"{arm}:hex32-64"] += 1
    if "pkg:" in txt:
        ident[f"{arm}:purl"] += 1
    if "cpe:" in txt:
        ident[f"{arm}:cpe"] += 1
    if re.search(r"sha256|sha-256|digest", txt, re.I):
        ident[f"{arm}:digest-word"] += 1
out["identity_in_output"] = dict(ident)

# ---- 6b. fickling severity breakdown (derived view, added at scoring and labelled as such in RESULTS):
# the frozen rule flags any severity > LIKELY_SAFE; this splits flagged verdicts by severity and by whether the
# member carried a parse error, so a reader can separate "named an unsafe import" from "could not parse".
fk = collections.defaultdict(lambda: collections.Counter())
for t in base:
    rel = t[len("fixtures/"):]
    lab = labels[rel]["label"]
    d = detail[("fickling", t)]
    sev = "+".join(d.get("severities", [])) or "?"
    err = "parse-error" if d.get("errors") else "no-error"
    fk[lab][f"{verdict[('fickling', t)]}|{sev}|{err}"] += 1
out["fickling_severity_breakdown"] = {k: dict(v) for k, v in fk.items()}

# ---- 7. timing (secondary, contended)
tim = {}
for arm in ARMS:
    allb = [statistics.median(timing[(arm, t)]) for t in base]
    models = [statistics.median(timing[(arm, t)]) for t in base if t.startswith("fixtures/benign-models/")]
    per_run_total = [sum(timing[(arm, t)][i] for t in base) for i in range(runs)]
    tim[arm] = {"base_median_of_medians_s": round(statistics.median(allb), 3),
                "base_total_per_run_s": [round(x, 1) for x in per_run_total],
                "base_total_cv_pct": round(100 * statistics.stdev(per_run_total) / statistics.mean(per_run_total), 1) if runs > 1 else None,
                "models": {os.path.basename(t): {"median_s": round(statistics.median(timing[(arm, t)]), 3),
                                                 "cv_pct": round(100 * statistics.stdev(timing[(arm, t)]) / statistics.mean(timing[(arm, t)]), 1) if runs > 1 else None}
                           for t in base if t.startswith("fixtures/benign-models/")}}
out["timing"] = tim

json.dump(out, open(os.path.join(B, "results", "scores.json"), "w"), indent=1, sort_keys=True, default=str)

# ---- print
print(f"scans={len(rows)} targets={out['n_targets']} runs={runs} flips={len(flips)} harness_fails={len(out['harness_fails'])}")
print("\n## detection on unsafe base files (modal verdict)")
for arm in ARMS:
    d = det[arm]
    print(arm.ljust(16), {k: dict(v) for k, v in d.items()})
print("\n## coverage per set (ALL verdicts)")
for arm in ARMS:
    print(arm.ljust(16), {k: v for k, v in cov[arm].items() if k.startswith("set:") or k == "ALL"})
print("\n## coverage per extension")
exts = sorted({ext_of(t) for t in base})
print("ext".ljust(14), *[a.ljust(34) for a in ARMS])
for e in exts:
    print(e.ljust(14), *[json.dumps(cov[a].get(e, {})).ljust(34) for a in ARMS])
print("\n## false positives (benign flagged)")
for arm in ARMS:
    print(arm.ljust(16), len(fp[arm]["flagged"]), [x["file"] for x in fp[arm]["flagged"]])
    print(" ".ljust(16), "error/skipped:", [(x["file"].split("/")[-1], x["verdict"]) for x in fp[arm]["error_or_skipped"]])
print("\n## junk")
for arm in ARMS:
    print(arm.ljust(16), junk[arm])
print("\n## evasion summary (defeated/applicable over unsafe anchors; benign flagged/total)")
tcodes = ["N1", "N2", "N3", "N4", "N5", "C1", "C2", "C3", "C4", "C5", "C6", "C7"]
print("transform".ljust(10), *[a.ljust(22) for a in ARMS])
for tc in tcodes:
    cells = []
    for arm in ARMS:
        s = summ[(tc, arm)]
        cells.append(f"def {s['defeated']}/{s['applicable']}  benFlag {s['benign_flagged']}/{s['benign_total']}".ljust(22))
    print(tc.ljust(10), *cells)
print("\n## per-variant verdicts (unsafe anchors)")
for row in evasion:
    if row["label"] == "unsafe":
        print(f"{row['anchor']}-{row['transform']}".ljust(7), row["variant"][:34].ljust(34), *[f"{a[:10]}={row[a]['variant']}" for a in ARMS])
print("\n## per-variant verdicts (benign anchors)")
for row in evasion:
    if row["label"] == "benign":
        print(f"{row['anchor']}-{row['transform']}".ljust(7), row["variant"][:34].ljust(34), *[f"{a[:10]}={row[a]['variant']}" for a in ARMS])
print("\n## identity in output", dict(ident))
print("\n## fickling severity breakdown (verdict|severities|parse-error) per label")
for lab, c in fk.items():
    print(lab.ljust(8), dict(c))
print("\n## timing (s, contended)")
for arm in ARMS:
    print(arm.ljust(16), json.dumps(tim[arm])[:600])

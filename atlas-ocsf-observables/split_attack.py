"""Supplementary (not pre-registered): split the core-arm grades by whether the ATLAS technique carries an
ATT&CK reference (attack_refs.csv from the hub, derived from ATLAS-2026.10.yaml attack-reference)."""
import csv, collections, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
refs = {r["atlas_technique_id"] for r in csv.DictReader(open("/home/jerem/project1/02-projects/atlas-mitigations/data/attack_refs.csv"))}
P = json.load(open(os.path.join(HERE, "results", "observables.json")))["per_technique"]
out = {}
for lab, sel in (("attack_referenced", lambda t: t in refs), ("atlas_native", lambda t: t not in refs)):
    c = collections.Counter(); n = collections.Counter()
    for t, v in P.items():
        if sel(t):
            c[v["core"]] += v["steps"]; n[v["core"]] += 1
    tot = sum(c.values())
    out[lab] = {"techniques": sum(n.values()), "steps": tot, "steps_by_grade": dict(c),
                "specific_share": round((c["direct"] + c["event"]) / tot, 3), "observable_share": round((tot - c["none"]) / tot, 3)}
json.dump(out, open(os.path.join(HERE, "results", "attack_split.json"), "w"), indent=1, sort_keys=True)
print(json.dumps(out, indent=1))

# Sensitivity (not pre-registered): drop the two broadest artifacts (d3f:File, d3f:UserAccount) and recompute
# the best core grade, to see how much of the "specific" share rests on them.
R = list(csv.DictReader(open(os.path.join(HERE, "results", "technique_artifact_ocsf.csv"))))
RANK = {"direct": 4, "event": 4, "generic": 2, "proxy": 1, "none": 0}
best = {}
steps = {}
for r in R:
    steps[r["atlas_id"]] = int(r["incident_steps"])
    g = r["grade"] if r["core_classes"] != "no field" else "none"
    if r["d3fend_artifact"] in ("d3f:File", "d3f:UserAccount"):
        g = "none"
    if RANK[g] >= RANK.get(best.get(r["atlas_id"], "none"), 0):
        best[r["atlas_id"]] = g if RANK[g] >= RANK[best.get(r["atlas_id"], "none")] else best[r["atlas_id"]]
c = collections.Counter()
for t, g in best.items():
    c[g] += steps[t]
sens = {"steps_by_grade_without_File_UserAccount": dict(c), "specific": c["direct"] + c["event"], "observable": sum(c.values()) - c["none"], "total": sum(c.values())}
json.dump({**out, "sensitivity_drop_File_UserAccount": sens}, open(os.path.join(HERE, "results", "attack_split.json"), "w"), indent=1, sort_keys=True)
print(sens)

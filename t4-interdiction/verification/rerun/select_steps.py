"""Pre-freeze step selection by rule (deterministic; read-only over ATLAS v2026.10 + burn-down JSON).

Rule (written into PREREGISTRATION.md): for each selected control, rank its mapped techniques (sub-technique
credits its parent, as the burn-down does) by the number of Incident steps on defender ground, where
defender ground = the technique's tactic is not Reconnaissance (TA0002), Resource Development (TA0003)
or AI Attack Adaptation (TA0001) (R1's OFF_GROUND set). Take the top 3 techniques (ties by total steps,
then by id); for each take the most recent Incident step (highest case-study id, then highest employs
index). Off-ground techniques are listed too, so the reader sees what the rule excluded.
Writes results/selected_steps.json."""
import json, os, yaml
ATLAS = "/home/jerem/project1/02-projects/atlas-mitigations/cache/ATLAS-2026.10.yaml"
HERE = os.path.dirname(os.path.abspath(__file__))
OFF_GROUND = {"AML.TA0001", "AML.TA0002", "AML.TA0003"}
CTRL = ["AML.M0019", "AML.M0043", "AML.M0005", "AML.M0011", "AML.M0020", "AML.M0024", "AML.M0040", "AML.M0013"]
d = yaml.safe_load(open(ATLAS))
tech, rel = d["techniques"], d["relationships"]
m = json.load(open(os.path.join(HERE, "results", "mappings_top12.json")))
def parent(t): return t.rsplit(".", 1)[0] if t.count(".") == 2 else t
def tactics(t):
    r = rel.get(t, {}).get("achieves") or rel.get(parent(t), {}).get("achieves") or []
    return sorted(x["target"] for x in r)
out = []
for c in m["controls"]:
    if c["id"] not in CTRL: continue
    rank = {}
    for s in c["steps"]:
        t = s["technique"]; ts = tactics(t); ground = not (set(ts) & OFF_GROUND)
        r = rank.setdefault(t, {"technique": t, "name": tech[t]["name"], "tactics": ts, "steps": 0, "ground_steps": 0, "ground": []})
        r["steps"] += 1
        if ground:
            r["ground_steps"] += 1; r["ground"].append(s)
    ranked = sorted(rank.values(), key=lambda r: (-r["ground_steps"], -r["steps"], r["technique"]))
    chosen = []
    for r in [x for x in ranked if x["ground_steps"]][:3]:
        s = max(r["ground"], key=lambda s: (s["cs"], s["idx"]))
        chosen.append({"technique": r["technique"], "technique_name": r["name"], "tactics": r["tactics"], "ground_steps": r["ground_steps"],
                       "cs": s["cs"], "idx": s["idx"], "cs_name": s["cs_name"], "desc": s["desc"]})
    out.append({"control": c["id"], "name": c["name"], "ranked": [{k: v for k, v in r.items() if k != "ground"} for r in ranked], "chosen": chosen})
    print(f"\n#### {c['id']} {c['name']}")
    for r in ranked[:8]:
        print(f"  {r['technique']:14} {r['name'][:38]:38} steps={r['steps']:2} ground={r['ground_steps']:2} {r['tactics']}")
    for s in chosen:
        print(f"  -> {s['cs']}[{s['idx']}] {s['technique']} | {s['desc'][:200]}")
json.dump(out, open(os.path.join(HERE, "results", "selected_steps.json"), "w"), indent=1)

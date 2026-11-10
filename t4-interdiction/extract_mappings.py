"""Orientation extract: for the top-N ATLAS mitigations in the burn-down greedy order, list the
mitigation text, the techniques it mitigates (with the 'use' text) and every Incident employs-step on
those techniques. Read-only over ATLAS v2026.10 and the burn-down JSON. Writes results/mappings_topN.json."""
import json, sys, yaml, hashlib, os
ATLAS = "/home/jerem/project1/02-projects/atlas-mitigations/cache/ATLAS-2026.10.yaml"
BURN = "/home/jerem/project1/02-projects/atlas-mitigations/results/control_burndown_2026.10.json"
HERE = os.path.dirname(os.path.abspath(__file__))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
sha = hashlib.sha256(open(ATLAS, "rb").read()).hexdigest()
d = yaml.safe_load(open(ATLAS))
b = json.load(open(BURN))
assert sha == b["basis"]["atlas_sha256"], sha
mit, tech, cs, rel = d["mitigations"], d["techniques"], d["case-studies"], d["relationships"]
# incident steps
steps = []
for cid, c in cs.items():
    if c.get("type") != "Incident":
        continue
    for i, r in enumerate(rel.get(cid, {}).get("employs", [])):
        steps.append({"cs": cid, "cs_name": c["name"], "idx": i, "technique": r["target"], "desc": r.get("description", "")})
print("incident steps", len(steps), "incidents", len({s['cs'] for s in steps}))
assert len(steps) == 290
def parent(t):  # sub-technique credits parent
    return t.rsplit(".", 1)[0] if t.count(".") == 2 else t
out = {"atlas_sha256": sha, "controls": []}
for g in b["atlas_layer"]["greedy"][:N]:
    mid = g["id"]; m = mit[mid]
    mits = rel.get(mid, {}).get("mitigates", [])
    targets = {r["target"]: r.get("description", "") for r in mits}
    tset = set(targets)
    hit = [s for s in steps if s["technique"] in tset or parent(s["technique"]) in tset]
    out["controls"].append({"id": mid, "name": m["name"], "categories": g["categories"], "marginal_steps": g["marginal_steps"],
        "reaches_steps": g["reaches_steps"], "description": m["description"],
        "techniques": [{"id": t, "name": tech[t]["name"], "use": u, "incident_steps": sum(1 for s in hit if s["technique"] == t or parent(s["technique"]) == t)} for t, u in targets.items()],
        "steps": hit})
    print(f"\n## {mid} {m['name']} {g['categories']} marginal={g['marginal_steps']} reaches={g['reaches_steps']} computed_reach={len(hit)}")
    print(m["description"][:700])
    for t in out["controls"][-1]["techniques"]:
        if t["incident_steps"]:
            print(f"   {t['id']:14} {t['name']:45} steps={t['incident_steps']}")
os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
json.dump(out, open(os.path.join(HERE, "results", f"mappings_top{N}.json"), "w"), indent=1)

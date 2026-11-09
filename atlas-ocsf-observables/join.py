"""R1 join: ATLAS v2026.10 Incident steps -> crosswalk D3FEND artifact -> OCSF 1.9.0 field.

Deterministic. Inputs are hashed into results/observables.json. Run after ocsf_reach.py.
  .venv/bin/python -I join.py
"""
import csv, collections, hashlib, json, os, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
YAML = "/home/jerem/project1/02-projects/atlas-mitigations/cache/ATLAS-2026.10.yaml"
EMPLOYS = "/home/jerem/project1/02-projects/atlas-mitigations/data/employs_edges.csv"
XW = "/home/jerem/atlas-d3fend-crosswalk/"
OCSF18 = "/home/jerem/d3fend-atlas-worktree/data/ocsf-schema"
OFF_GROUND = {"AML.TA0001", "AML.TA0002", "AML.TA0003"}
GRADE_RANK = {"direct": 4, "event": 4, "generic": 2, "proxy": 1, "none": 0}
OBSERVABLE = {"direct", "event", "generic", "proxy"}
SPECIFIC = {"direct", "event"}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def rows(p):
    return list(csv.DictReader(open(p)))


def incident_steps():
    d = yaml.safe_load(open(YAML))
    inc = {k for k, c in d["case-studies"].items() if c["type"] == "Incident"}
    steps = []
    for cs, rel in d["relationships"].items():
        if cs not in inc:
            continue
        for e in rel.get("employs", []):
            steps.append((cs, e["target"]))
    csv_steps = [(r["case_study_id"], r["technique_id"]) for r in rows(EMPLOYS) if r["case_study_id"] in inc]
    assert sorted(steps) == sorted(csv_steps), "YAML employs != employs_edges.csv"
    tactic = {}
    for r in rows(EMPLOYS):
        if r["case_study_id"] in inc:
            tactic.setdefault((r["case_study_id"], r["technique_id"], r["step_id"]), r["tactic_id"])
    step_rows = [(r["case_study_id"], r["technique_id"], r["tactic_id"]) for r in rows(EMPLOYS)
                 if r["case_study_id"] in inc]
    return d, inc, step_rows


def crosswalk():
    m = collections.defaultdict(list)
    for r in rows(XW + "crosswalk-rebaseline-2026-11.csv"):
        if r["verdict"] == "retire":
            continue
        tid, note = r["atlas_id"], ""
        if r["removed_in_latest"] == "True":
            tid = r["successor"].split()[0]
            note = f"moved from {r['atlas_id']}" + (" (inferred successor)" if "inferred" in r["successor"] else "")
        m[tid].append({"verb": r["verb"], "artifact": r["artifact_iri"], "src": "rebaseline", "note": note})
    for r in rows(XW + "crosswalk.csv"):
        if r["atlas_id"] in ("AML.T0021", "AML.T0037"):
            m[r["atlas_id"]].append({"verb": r["verb"], "artifact": r["artifact_iri"], "src": "core-merged", "note": "merged upstream"})
    for r in rows(XW + "crosswalk-annex-v2026.10.csv"):
        if r["verdict"] == "kill":
            continue
        m[r["atlas_id"]].append({"verb": r["verb"], "artifact": r["artifact_iri"], "src": "annex-2026.10", "note": ""})
    return m


def validate_field(field, reach):
    """ocsf_field is object.attr or class:<uid>.attr; must exist in the fetched 1.9.0 schema."""
    if not field:
        return True
    if field.startswith("class:"):
        uid, attr = field[6:].split(".", 1)
        names = {v: k for k, v in reach["class_names"].items()}
        cname = reach["class_names"].get(uid)
        cdef = json.load(open(os.path.join(HERE, "sources", "ocsf-1.9.0-noprofile", "classes", cname + ".json")))
        return attr in cdef["attributes"]
    obj, attr = field.split(".", 1)
    return attr in reach["object_fields"].get(obj, [])


def classes_for(entry, reach, arm):
    if entry.get("ocsf_class_uid"):
        uid = entry["ocsf_class_uid"]
        return [uid] if uid in reach["class_names"] else []
    if entry.get("ocsf_object"):
        return sorted(reach[arm].get(entry["ocsf_object"], {}).keys(), key=int)
    return []


def main():
    reach = json.load(open(os.path.join(HERE, "results", "ocsf_reach.json")))
    amap = {r["artifact"]: r for r in rows(os.path.join(HERE, "artifact_ocsf_map.csv"))}
    dmap = {r["atlas_id"]: r for r in rows(os.path.join(HERE, "technique_direct_ocsf.csv"))}
    bad = [a for a, r in amap.items() if not validate_field(r["ocsf_field"], reach)]
    bad += [t for t, r in dmap.items() if not validate_field(r["ocsf_field"], reach)]
    if bad:
        print("FIELD VALIDATION FAILED:", bad)
        sys.exit(3)

    d, inc, step_rows = incident_steps()
    T = d["techniques"]
    xw = crosswalk()
    steps = collections.Counter(t for _, t, _ in step_rows)
    ground = collections.Counter(t for _, t, ta in step_rows if ta not in OFF_GROUND)
    cases = collections.defaultdict(set)
    for cs, t, _ in step_rows:
        cases[t].add(cs)

    missing_art = sorted({x["artifact"] for t in steps for x in xw.get(t, [])} - set(amap))
    assert not missing_art, f"artifacts missing from map: {missing_art}"

    table, tech = [], {}
    for t in sorted(steps):
        arts = xw.get(t, [])
        best = {}
        for arm in ("core", "profile"):
            g_best, cls_best = "none", []
            for x in arts:
                e = amap[x["artifact"]]
                cls = classes_for(e, reach, arm)
                g = e["grade"] if cls else "none"
                table.append(None) if False else None
                if GRADE_RANK[g] > GRADE_RANK[g_best]:
                    g_best, cls_best = g, cls
            best[arm] = (g_best, cls_best)
        for x in arts:
            e = amap[x["artifact"]]
            table.append({
                "atlas_id": t, "technique": T[t]["name"], "maturity": T[t].get("maturity"),
                "incident_steps": steps[t], "defender_ground_steps": ground[t], "incidents": len(cases[t]),
                "verb": x["verb"], "d3fend_artifact": x["artifact"], "crosswalk_src": x["src"], "crosswalk_note": x["note"],
                "grade": e["grade"], "ocsf_object": e["ocsf_object"] or "-", "ocsf_field": e["ocsf_field"] or "no field",
                "core_classes": ";".join(classes_for(e, reach, "core")) or "no field",
                "profile_classes": ";".join(classes_for(e, reach, "profile")) or "no field",
                "rationale": e["rationale"]})
        if not arts:
            r = dmap.get(t)
            table.append({
                "atlas_id": t, "technique": T[t]["name"], "maturity": T[t].get("maturity"),
                "incident_steps": steps[t], "defender_ground_steps": ground[t], "incidents": len(cases[t]),
                "verb": "-", "d3fend_artifact": "no crosswalk row", "crosswalk_src": "-",
                "crosswalk_note": r["crosswalk_reason"] if r else "NOT IN technique_direct_ocsf.csv",
                "grade": "none", "ocsf_object": "-", "ocsf_field": "no field", "core_classes": "no field",
                "profile_classes": "no field", "rationale": ""})
        dr = dmap.get(t)
        direct = {}
        if dr:
            e = {"ocsf_object": dr["ocsf_object"], "ocsf_class_uid": dr["ocsf_class_uid"]}
            for arm in ("core", "profile"):
                cls = classes_for(e, reach, arm)
                direct[arm] = dr["grade"] if cls else "none"
        tech[t] = {"name": T[t]["name"], "steps": steps[t], "ground": ground[t], "has_row": bool(arts),
                   "core": best["core"][0], "profile": best["profile"][0],
                   "core_classes": best["core"][1], "reason": dr["crosswalk_reason"] if dr else "",
                   "direct_arm": direct}

    assert set(dmap) == {t for t in tech if not tech[t]["has_row"]}, "direct-arm file must list exactly the no-row techniques"

    def agg(arm, w):
        out = collections.Counter()
        for t, v in tech.items():
            out[v[arm]] += v[w] if w else 1
        return dict(out)

    summary = {}
    for arm in ("core", "profile"):
        s = {}
        for w, lab in ((None, "techniques"), ("steps", "steps"), ("ground", "defender_ground_steps")):
            g = agg(arm, w)
            tot = sum(g.values())
            s[lab] = {"by_grade": dict(sorted(g.items())), "total": tot,
                      "observable": sum(v for k, v in g.items() if k in OBSERVABLE),
                      "specific": sum(v for k, v in g.items() if k in SPECIFIC)}
        summary[arm] = s

    no_obs = {arm: sorted([t for t, v in tech.items() if v[arm] == "none"], key=lambda t: -tech[t]["steps"]) for arm in ("core", "profile")}
    blocks = collections.Counter()
    for t in no_obs["core"]:
        blocks["no crosswalk row" if not tech[t]["has_row"] else "artifact has no core field"] += tech[t]["steps"]
    direct_found = {arm: sorted(t for t, v in tech.items() if not v["has_row"] and v["direct_arm"].get(arm, "none") != "none") for arm in ("core", "profile")}

    # 1.8.0 -> 1.9.0 delta for objects used
    used = sorted({r["ocsf_object"] for r in amap.values() if r["ocsf_object"]} | {r["ocsf_object"] for r in dmap.values() if r["ocsf_object"]})
    o18 = set()
    for sub in ("objects", "extensions/windows/objects"):
        p = os.path.join(OCSF18, sub)
        if os.path.isdir(p):
            o18 |= {f[:-5] for f in os.listdir(p) if f.endswith(".json")}
    delta = {"objects_used": used, "absent_in_1_8_0_clone": sorted(o for o in used if o not in o18),
             "note": "1.8.0 clone names the Windows registry objects registry_key/registry_value; 1.9.0 serves reg_key/reg_value."}

    out = {
        "inputs": {"atlas_yaml": sha(YAML), "employs_edges_csv": sha(EMPLOYS),
                   "crosswalk_core": sha(XW + "crosswalk.csv"), "crosswalk_rebaseline": sha(XW + "crosswalk-rebaseline-2026-11.csv"),
                   "crosswalk_annex_2026_10": sha(XW + "crosswalk-annex-v2026.10.csv"),
                   "artifact_ocsf_map": sha(os.path.join(HERE, "artifact_ocsf_map.csv")),
                   "technique_direct_ocsf": sha(os.path.join(HERE, "technique_direct_ocsf.csv")),
                   "ocsf_reach": sha(os.path.join(HERE, "results", "ocsf_reach.json"))},
        "scope": {"incidents": len(inc), "steps": sum(steps.values()), "defender_ground_steps": sum(ground.values()),
                  "techniques": len(steps), "techniques_with_crosswalk_row": sum(1 for v in tech.values() if v["has_row"])},
        "summary": summary, "no_observable_core": no_obs["core"], "no_observable_profile": no_obs["profile"],
        "no_observable_core_blocks_steps": dict(blocks), "direct_arm_observable": direct_found,
        "per_technique": tech, "ocsf_1_8_to_1_9": delta,
    }
    json.dump(out, open(os.path.join(HERE, "results", "observables.json"), "w"), indent=1, sort_keys=True)
    cols = list(table[0].keys())
    with open(os.path.join(HERE, "results", "technique_artifact_ocsf.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(table, key=lambda r: (-r["incident_steps"], r["atlas_id"], r["d3fend_artifact"])):
            w.writerow(r)
    print(json.dumps({k: out[k] for k in ("scope", "summary", "no_observable_core_blocks_steps", "direct_arm_observable")}, indent=1))
    print("no observable (core):", [(t, tech[t]["steps"]) for t in no_obs["core"]])
    print("1.8->1.9:", delta["absent_in_1_8_0_clone"])


if __name__ == "__main__":
    main()

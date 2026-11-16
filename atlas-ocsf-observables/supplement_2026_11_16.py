"""Post-hoc supplement (2026-11-16, NOT pre-registered). Three readings R1's essay needs that neither R1 nor
M1 (../m1-r1-blind-regrade) computed:

  1. R1's ATT&CK-referenced vs ATLAS-native split and its d3f:File/d3f:UserAccount sensitivity, recomputed
     under M1 Grader B's modal grades as well as R1's own (Grader A).
  2. A 48-incident re-weight: R1's 27 ATLAS v2026.10 Incident case studies plus the 21 researched prior
     incidents, filtered exactly as ai-flows-2026-11-09/analysis/critical_controls.py filters them
     (Incident, confidence high/medium, not superseded by CS0068-CS0075, not "alternate framing",
     retired IDs remapped, technique present in v2026.10). The researched rows are researcher-mapped
     technique uses, one row per (incident, technique, report-row group), NOT ATLAS-published procedure
     steps, so "steps" below means technique-use rows for that bucket.
  3. Bounds for the cells the 48-incident set adds that neither grader graded: two artifacts absent from
     artifact_ocsf_map.csv and one technique with no crosswalk row (AML.T0110). Point grades are
     single-author analogies to existing map rows (Tier D); the bounds set all three cells to none (low)
     and to a specific grade (high), so no figure hinges on them.

Gate: Grader A must reproduce R1 (161/235 of 290, 112/155 of 182) or this exits 2. Never calls join.main()
(which would overwrite R1's tracked results); writes only results/supplement-2026-11-16.json.

  python3 -I supplement_2026_11_16.py      (needs PyYAML; imports join.py and ../m1-r1-blind-regrade/recompute.py)
"""
import collections, csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
M1 = os.path.abspath(os.path.join(HERE, "..", "m1-r1-blind-regrade"))
sys.path.insert(0, HERE)
sys.path.insert(0, M1)
import join      # noqa: E402
import recompute  # noqa: E402

HUB = "/home/jerem/project1/02-projects/atlas-mitigations"
CAND = HUB + "/research-returns/atlas-candidate-mappings.csv"
REFS = HUB + "/data/attack_refs.csv"
# Copied from ai-flows-2026-11-09/analysis/critical_controls.py l.34-38 (itself copied from atlas_pin.py).
RETIRED = {"AML.T0019": "AML.T0115.000", "AML.T0058": "AML.T0115.001", "AML.T0104": "AML.T0115.002",
           "AML.T0024.000": "AML.T0137.000", "AML.T0024.001": "AML.T0137.002", "AML.T0024.002": "AML.T0005.001",
           "AML.T0056": "AML.T0085.003", "AML.T0057": "AML.T0085.002"}
SUPERSEDED = {"CAND.I-01", "CAND.I-02", "CAND.I-03", "CAND.I-04", "CAND.I-05", "CAND.I-11", "CAND.I-15", "CAND.I-29"}

# Single-author point grades for the cells the 48 set adds (Tier D), each by analogy to an existing R1 row.
# Under Grader B the analogue row's B modal grade is used, so B is never handed an R1 judgement.
NEW_CELLS = {
    "d3f:InboundInternetWebTraffic": {"grade": "direct", "ocsf_object": "http_request", "ocsf_class_uid": "",
                                      "analogue": "d3f:OutboundInternetWebTraffic"},
    "d3f:ApplicationConfigurationFile": {"grade": "generic", "ocsf_object": "file", "ocsf_class_uid": "",
                                         "analogue": "d3f:ConfigurationFile"},
    "AML.T0110": {"grade": "none", "ocsf_object": "", "ocsf_class_uid": "",
                  "analogue": "AML.T0011.002 (no tool object in OCSF 1.9.0)"},
}
HIGH = {"d3f:InboundInternetWebTraffic": {"grade": "direct", "ocsf_object": "http_request", "ocsf_class_uid": ""},
        "d3f:ApplicationConfigurationFile": {"grade": "direct", "ocsf_object": "file", "ocsf_class_uid": ""},
        "AML.T0110": {"grade": "direct", "ocsf_object": "", "ocsf_class_uid": "6003"}}
LOW = {k: {"grade": "none", "ocsf_object": "", "ocsf_class_uid": ""} for k in NEW_CELLS}


def prior_steps(T):
    rows, dropped = [], collections.Counter()
    for r in csv.DictReader(open(CAND)):
        if r["case_type"] != "Incident":
            dropped["not Incident"] += 1; continue
        if r["confidence"] not in ("high", "medium"):
            dropped["confidence low"] += 1; continue
        if r["case_id"] in SUPERSEDED:
            dropped["superseded by ATLAS CS0068-CS0075"] += 1; continue
        if r["evidence"].lower().startswith("alternate framing"):
            dropped["alternate framing"] += 1; continue
        tid = RETIRED.get(r["technique_id"], r["technique_id"])
        if tid not in T:
            dropped["technique not in v2026.10"] += 1; continue
        rows.append((r["case_id"], tid, r["tactic_id"]))
    return rows, dict(dropped)


def split_and_sens(per_tech_grade, steps, refs, xw, gs, reach):
    out = {}
    for lab, sel in (("attack_referenced", lambda t: t in refs), ("atlas_native", lambda t: t not in refs)):
        c, n = collections.Counter(), 0
        for t, g in per_tech_grade.items():
            if sel(t):
                c[g] += steps[t]; n += 1
        tot = sum(c.values())
        out[lab] = {"techniques": n, "steps": tot,
                    "specific": c["direct"] + c["event"], "observable": tot - c["none"],
                    "specific_pct": round(100 * (c["direct"] + c["event"]) / tot, 1) if tot else None,
                    "observable_pct": round(100 * (tot - c["none"]) / tot, 1) if tot else None}
    # sensitivity: drop d3f:File and d3f:UserAccount as carriers, recompute best core grade
    c = collections.Counter()
    for t in steps:
        g_best = "none"
        arts = xw.get(t, [])
        for x in arts:
            if x["artifact"] in ("d3f:File", "d3f:UserAccount"):
                continue
            e = gs[x["artifact"]]
            g = e["grade"] if join.classes_for(e, reach, "core") else "none"
            if join.GRADE_RANK[g] > join.GRADE_RANK[g_best]:
                g_best = g
        c[g_best] += steps[t]
    tot = sum(c.values())
    out["sensitivity_drop_File_UserAccount"] = {"specific": c["direct"] + c["event"], "observable": tot - c["none"],
                                                "total": tot}
    return out


def summarise(res, n_steps, n_ground):
    c = res["core"]
    return {"specific_steps": c["steps"]["specific"], "observable_steps": c["steps"]["observable"],
            "total_steps": c["steps"]["total"], "specific_pct": c["steps"]["specific_pct"],
            "observable_pct": c["steps"]["observable_pct"],
            "specific_ground": c["defender_ground_steps"]["specific"],
            "observable_ground": c["defender_ground_steps"]["observable"],
            "total_ground": c["defender_ground_steps"]["total"],
            "specific_ground_pct": c["defender_ground_steps"]["specific_pct"],
            "observable_ground_pct": c["defender_ground_steps"]["observable_pct"]}


def main():
    reach = json.load(open(os.path.join(HERE, "results", "ocsf_reach.json")))
    d, inc, step27 = join.incident_steps()
    T = d["techniques"]
    xw = join.crosswalk()
    refs = {r["atlas_technique_id"] for r in csv.DictReader(open(REFS))}
    sets = recompute.grade_sets()
    A, B = sets["A_r1"], sets["B_modal"]

    out = {"label": "post-hoc supplement 2026-11-16, not pre-registered", "inputs": {
        "candidate_csv": join.sha(CAND), "attack_refs": join.sha(REFS),
        "grader_b": join.sha(os.path.join(M1, "results", "grader_b.json")),
        "artifact_ocsf_map": join.sha(os.path.join(HERE, "artifact_ocsf_map.csv")),
        "ocsf_reach": join.sha(os.path.join(HERE, "results", "ocsf_reach.json"))}}

    # ---- 27 incidents: gate, then split + sensitivity under A and B ----
    r27 = {name: recompute.evaluate(gs, reach, step27, xw) for name, gs in (("A_r1", A), ("B_modal", B))}
    a = r27["A_r1"]["core"]
    if (a["steps"]["specific"], a["steps"]["observable"], a["defender_ground_steps"]["specific"],
            a["defender_ground_steps"]["observable"]) != (161, 235, 112, 155):
        print("GATE FAILED"); sys.exit(2)
    steps27 = collections.Counter(t for _, t, _ in step27)
    out["gate"] = "Grader A reproduces R1 161/235 of 290 and 112/155 of 182"
    out["incidents_27"] = {}
    for name, gs in (("A_r1", A), ("B_modal", B)):
        out["incidents_27"][name] = {"headline": summarise(r27[name], 290, 182),
                                     **split_and_sens(r27[name]["core"]["per_technique_grade"], steps27, refs, xw, gs, reach)}

    # ---- 48 incidents ----
    prior, dropped = prior_steps(T)
    step48 = list(step27) + prior
    new_t = sorted({t for _, t, _ in prior} - set(steps27))
    out["incidents_48_scope"] = {
        "atlas_incidents": len(inc), "prior_incidents": len({c for c, _, _ in prior}),
        "atlas_steps": len(step27), "prior_rows": len(prior), "prior_rows_dropped": dropped,
        "prior_ground_rows": sum(1 for _, _, ta in prior if ta not in join.OFF_GROUND),
        "prior_rows_blank_tactic": sum(1 for _, _, ta in prior if not ta),
        "prior_duplicate_incident_technique_rows": sum(v - 1 for v in collections.Counter((c, t) for c, t, _ in prior).values() if v > 1),
        "techniques_total": len({t for _, t, _ in step48}), "techniques_new_vs_27": new_t,
        "new_techniques_without_crosswalk_row": [t for t in new_t if not xw.get(t)],
        "new_cells": NEW_CELLS}
    steps48 = collections.Counter(t for _, t, _ in step48)
    out["incidents_48"] = {}
    for name, base in (("A_r1", A), ("B_modal", B)):
        for bound, cells in (("point", None), ("low", LOW), ("high", HIGH)):
            gs = dict(base)
            for k, v in NEW_CELLS.items():
                if bound == "point":
                    src = base.get(v["analogue"].split()[0]) if name == "B_modal" else None
                    gs[k] = ({"grade": src["grade"], "ocsf_object": src["ocsf_object"], "ocsf_class_uid": src["ocsf_class_uid"]}
                             if src else {kk: v[kk] for kk in ("grade", "ocsf_object", "ocsf_class_uid")})
                else:
                    gs[k] = cells[k]
            r = recompute.evaluate(gs, reach, step48, xw)
            key = f"{name}_{bound}"
            out["incidents_48"][key] = {"headline": summarise(r, None, None)}
            if bound == "point":
                out["incidents_48"][key].update(split_and_sens(r["core"]["per_technique_grade"], steps48, refs, xw, gs, reach))
                out["incidents_48"][key]["prior_only"] = summarise(
                    recompute.evaluate(gs, reach, prior, xw), None, None)

    p = os.path.join(HERE, "results", "supplement-2026-11-16.json")
    json.dump(out, open(p, "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()

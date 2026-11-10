"""Recompute R1's headline under alternative grade sets (Grader A = R1, Grader B modal, each B pass, consensus).

  .venv/bin/python -I recompute.py          # results/headline.json
Reuses join.py's crosswalk, step and reachability logic by importing it from the R1 directory. Deterministic.
Gate: Grader A must reproduce R1's 161/290, 235/290, 112/182, 155/182 exactly or this exits 2.
"""
import collections, csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
R1 = os.path.abspath(os.path.join(HERE, "..", "atlas-ocsf-observables"))
sys.path.insert(0, R1)
import join  # noqa: E402  (R1's join.py; HERE inside it resolves to the R1 directory)

R1_EXPECT = {"core": {"steps": {"specific": 161, "observable": 235, "total": 290},
                      "defender_ground_steps": {"specific": 112, "observable": 155, "total": 182},
                      "techniques": {"specific": 55, "observable": 91, "total": 107}}}


def grade_sets():
    """Return {name: {row_id: {"grade","ocsf_object","ocsf_class_uid"}}} for every grader to evaluate."""
    sets = {}
    a = {r["artifact"]: r for r in csv.DictReader(open(os.path.join(R1, "artifact_ocsf_map.csv")))}
    a.update({r["atlas_id"]: r for r in csv.DictReader(open(os.path.join(R1, "technique_direct_ocsf.csv")))})
    sets["A_r1"] = {k: {"grade": v["grade"], "ocsf_object": v["ocsf_object"], "ocsf_class_uid": v["ocsf_class_uid"]} for k, v in a.items()}
    gb = json.load(open(os.path.join(HERE, "results", "grader_b.json")))
    sets["B_modal"] = {k: {"grade": v["grade"], "ocsf_object": v["ocsf_object"] or "", "ocsf_class_uid": v["ocsf_class_uid"] or ""} for k, v in gb["modal"].items()}
    for p, rows in gb["per_pass"].items():
        sets[f"B_pass{p}"] = {k: {"grade": v["scored_grade"], "ocsf_object": v["ocsf_object"] or "", "ocsf_class_uid": v["ocsf_class_uid"] or ""} for k, v in rows.items()}
    cp = os.path.join(HERE, "results", "consensus.json")
    if os.path.exists(cp):
        c = json.load(open(cp))["rows"]
        sets["consensus"] = {k: {"grade": v["grade"], "ocsf_object": v["ocsf_object"] or "", "ocsf_class_uid": v["ocsf_class_uid"] or ""} for k, v in c.items()}
    return sets


def evaluate(gs, reach, step_rows, xw):
    steps = collections.Counter(t for _, t, _ in step_rows)
    ground = collections.Counter(t for _, t, ta in step_rows if ta not in join.OFF_GROUND)
    out = {}
    for arm in ("core", "profile"):
        tech = {}
        for t in steps:
            arts = xw.get(t, [])
            g_best = "none"
            for x in arts:
                e = gs[x["artifact"]]
                cls = join.classes_for(e, reach, arm)
                g = e["grade"] if cls else "none"
                if join.GRADE_RANK[g] > join.GRADE_RANK[g_best]:
                    g_best = g
            direct = None
            if not arts and t in gs:
                e = gs[t]
                direct = e["grade"] if join.classes_for(e, reach, arm) else "none"
            tech[t] = {"grade": g_best, "direct_arm": direct}
        s = {}
        for w, lab in ((None, "techniques"), (steps, "steps"), (ground, "defender_ground_steps")):
            c = collections.Counter()
            for t, v in tech.items():
                c[v["grade"]] += w[t] if w else 1
            tot = sum(c.values())
            s[lab] = {"by_grade": dict(sorted(c.items())), "total": tot,
                      "observable": sum(v for k, v in c.items() if k in join.OBSERVABLE),
                      "specific": sum(v for k, v in c.items() if k in join.SPECIFIC),
                      "specific_pct": round(100 * sum(v for k, v in c.items() if k in join.SPECIFIC) / tot, 1),
                      "observable_pct": round(100 * sum(v for k, v in c.items() if k in join.OBSERVABLE) / tot, 1)}
        s["direct_arm_observable"] = sorted(t for t, v in tech.items() if v["direct_arm"] not in (None, "none"))
        s["direct_arm_specific"] = sorted(t for t, v in tech.items() if v["direct_arm"] in join.SPECIFIC)
        s["per_technique_grade"] = {t: v["grade"] for t, v in sorted(tech.items())}
        out[arm] = s
    return out


def main():
    reach = json.load(open(os.path.join(R1, "results", "ocsf_reach.json")))
    _, _, step_rows = join.incident_steps()
    xw = join.crosswalk()
    sets = grade_sets()
    res = {}
    for name, gs in sets.items():
        missing = sorted({x["artifact"] for t in {t for _, t, _ in step_rows} for x in xw.get(t, [])} - set(gs))
        assert not missing, (name, missing)
        res[name] = evaluate(gs, reach, step_rows, xw)
    a = res["A_r1"]["core"]
    for lab, exp in R1_EXPECT["core"].items():
        for k, v in exp.items():
            if a[lab][k] != v:
                print("GATE FAILED: Grader A does not reproduce R1:", lab, k, a[lab][k], "!=", v); sys.exit(2)
    base = a["steps"]["specific_pct"]
    summary = {}
    for name, r in res.items():
        c = r["core"]
        summary[name] = {"core_specific_steps": f"{c['steps']['specific']}/290 ({c['steps']['specific_pct']}%)",
                         "delta_pp_vs_r1": round(c["steps"]["specific_pct"] - base, 1),
                         "core_any_steps": f"{c['steps']['observable']}/290 ({c['steps']['observable_pct']}%)",
                         "core_specific_ground": f"{c['defender_ground_steps']['specific']}/182 ({c['defender_ground_steps']['specific_pct']}%)",
                         "core_any_ground": f"{c['defender_ground_steps']['observable']}/182 ({c['defender_ground_steps']['observable_pct']}%)",
                         "core_specific_techniques": f"{c['techniques']['specific']}/107",
                         "profile_specific_steps": f"{r['profile']['steps']['specific']}/290 ({r['profile']['steps']['specific_pct']}%)",
                         "direct_arm_observable_core": c["direct_arm_observable"], "direct_arm_observable_profile": r["profile"]["direct_arm_observable"]}
    # per-technique moves between A and B modal / consensus (core)
    moves = {}
    for name in ("B_modal", "consensus"):
        if name in res:
            moves[name] = {t: f"{res['A_r1']['core']['per_technique_grade'][t]} -> {g}" for t, g in res[name]["core"]["per_technique_grade"].items()
                           if g != res["A_r1"]["core"]["per_technique_grade"][t]}
    out = {"gate": "Grader A reproduces R1 (161/235/112/155/55/91)", "summary": summary, "technique_grade_moves_core": moves, "full": res}
    json.dump(out, open(os.path.join(HERE, "results", "headline.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps({"gate": out["gate"], "summary": summary}, indent=1))
    for n, m in moves.items():
        print(n, "technique grade moves (core):", len(m)); [print("  ", t, v) for t, v in m.items()]


if __name__ == "__main__":
    main()

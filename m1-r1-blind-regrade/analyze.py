"""Parse Grader B responses, validate targets, compute modal grades, agreement (Cohen's kappa), stability, inventions.

  .venv/bin/python -I analyze.py            # results/grader_b.json, results/agreement.json, results/disagreements.csv
Deterministic over the response files. Stdlib only.
"""
import collections, csv, itertools, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
R1 = os.path.join(HERE, "..", "atlas-ocsf-observables")
GRADES = ["direct", "event", "generic", "proxy", "none"]
SPECIFIC = {"direct", "event"}


def load_json_array(text):
    """Model output may wrap the array in a code fence or prose; take the outermost [...]."""
    m = re.search(r"\[.*\]", text, re.S)
    return json.loads(m.group(0))


def kappa(a, b):
    """Cohen's kappa, unweighted, over paired nominal labels."""
    assert len(a) == len(b) and a
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return {"n": n, "percent_agreement": round(po, 4), "expected": round(pe, 4),
            "kappa": round((po - pe) / (1 - pe), 4) if pe < 1 else 1.0}


def main():
    reach = json.load(open(os.path.join(R1, "results", "ocsf_reach.json")))
    objs = set(reach["object_fields"])
    cls = set(reach["class_names"])
    manifest = json.load(open(os.path.join(HERE, "prompts", "manifest.json")))
    a_rows = {r["artifact"]: r for r in csv.DictReader(open(os.path.join(R1, "artifact_ocsf_map.csv")))}
    a_rows.update({r["atlas_id"]: r for r in csv.DictReader(open(os.path.join(R1, "technique_direct_ocsf.csv")))})

    per_pass = collections.defaultdict(dict)   # pass -> row_id -> parsed
    invent = collections.Counter()
    problems = []
    for p, pm in manifest["passes"].items():
        for b in pm["batches"]:
            fn = os.path.join(HERE, "responses", f"pass{p}", b["file"].replace(".txt", ".md"))
            if not os.path.exists(fn):
                problems.append(f"missing pass{p}/{b['file']}"); continue
            try:
                arr = load_json_array(open(fn).read())
            except Exception as e:
                problems.append(f"unparseable pass{p}/{b['file']}: {e}"); continue
            got = {x.get("row_id"): x for x in arr if isinstance(x, dict)}
            for rid in b["rows"]:
                x = got.get(rid)
                if not x:
                    problems.append(f"row {rid} absent in pass{p}/{b['file']}"); continue
                g = str(x.get("grade", "")).strip().lower()
                if g not in GRADES:
                    problems.append(f"bad grade {g!r} for {rid} pass{p}"); g = "none"
                obj = x.get("ocsf_object") or None
                uid = x.get("ocsf_class_uid")
                uid = str(uid) if uid not in (None, "", "null") else None
                fld = x.get("ocsf_field") or None
                flags = []
                if g != "none":
                    if obj and obj not in objs:
                        flags.append("invented_object")
                    if uid and uid not in cls:
                        flags.append("invented_class")
                    if not obj and not uid:
                        flags.append("no_target")
                    if obj and obj in objs and fld:
                        attr = fld.split(".", 1)[1] if "." in fld else fld
                        if attr not in reach["object_fields"][obj]:
                            flags.append("invented_attribute")
                for f in flags:
                    invent[f] += 1
                # scored grade: invented object/class or no target -> none (pre-registered)
                scored = g
                if g != "none" and ("invented_object" in flags or "invented_class" in flags or "no_target" in flags):
                    if obj and obj in objs:          # object real, only the class uid was bad
                        scored = g
                    else:
                        scored = "none"
                per_pass[p][rid] = {"grade": g, "scored_grade": scored, "ocsf_object": obj, "ocsf_class_uid": uid,
                                    "ocsf_field": fld, "flags": flags, "rationale": x.get("rationale")}

    passes = sorted(per_pass)
    row_ids = [r for r in a_rows]
    n_grades = sum(len(v) for v in per_pass.values())

    # modal grade per row over passes (on scored grade); tie -> pass-1 grade, flagged
    b_modal, ties = {}, []
    for rid in row_ids:
        gs = [per_pass[p][rid]["scored_grade"] for p in passes if rid in per_pass[p]]
        if not gs:
            continue
        c = collections.Counter(gs).most_common()
        if len(c) > 1 and c[0][1] == c[1][1]:
            ties.append(rid); modal = gs[0]
        else:
            modal = c[0][0]
        objs_named = collections.Counter((per_pass[p][rid]["ocsf_object"], per_pass[p][rid]["ocsf_class_uid"]) for p in passes
                                         if rid in per_pass[p] and per_pass[p][rid]["scored_grade"] == modal)
        obj, uid = objs_named.most_common(1)[0][0] if objs_named else (None, None)
        flds = collections.Counter(per_pass[p][rid]["ocsf_field"] for p in passes if rid in per_pass[p] and per_pass[p][rid]["ocsf_object"] == obj)
        b_modal[rid] = {"grade": modal, "ocsf_object": obj, "ocsf_class_uid": uid, "ocsf_field": flds.most_common(1)[0][0] if flds else None,
                        "passes": gs, "tie": rid in ties,
                        "rationales": [per_pass[p][rid]["rationale"] for p in passes if rid in per_pass[p]]}

    def stratum(ids):
        ids = [i for i in ids if i in b_modal]
        a = [a_rows[i]["grade"] for i in ids]; b = [b_modal[i]["grade"] for i in ids]
        conf = {ga: {gb: 0 for gb in GRADES} for ga in GRADES}
        for x, y in zip(a, b):
            conf[x][y] += 1
        same_obj = sum(1 for i in ids if (a_rows[i]["ocsf_object"] or None, a_rows[i]["ocsf_class_uid"] or None) ==
                       (b_modal[i]["ocsf_object"], b_modal[i]["ocsf_class_uid"])) / len(ids)
        return {"five_category": kappa(a, b),
                "specific_binary": kappa([g in SPECIFIC for g in a], [g in SPECIFIC for g in b]),
                "observable_binary": kappa([g != "none" for g in a], [g != "none" for g in b]),
                "same_target_share": round(same_obj, 4), "confusion_A_rows_B_cols": conf,
                "A_distribution": dict(collections.Counter(a)), "B_distribution": dict(collections.Counter(b))}

    art_ids = [i for i in row_ids if i.startswith("d3f:")]
    tech_ids = [i for i in row_ids if i.startswith("AML.")]
    out = {"passes_found": passes, "row_grades_total": n_grades, "problems": problems, "ties": ties,
           "invention_counts": dict(invent),
           "invention_rate_object_or_class": round((invent["invented_object"] + invent["invented_class"]) / n_grades, 4) if n_grades else None,
           "invention_rate_attribute": round(invent["invented_attribute"] / n_grades, 4) if n_grades else None,
           "artifact_rows": stratum(art_ids), "technique_rows": stratum(tech_ids)}

    # stability across passes
    if len(passes) >= 2:
        pair = {}
        for p, q in itertools.combinations(passes, 2):
            ids = [i for i in row_ids if i in per_pass[p] and i in per_pass[q]]
            pair[f"{p}v{q}"] = kappa([per_pass[p][i]["scored_grade"] for i in ids], [per_pass[q][i]["scored_grade"] for i in ids])
        flips = sum(1 for rid, v in b_modal.items() for g in v["passes"] if g != v["grade"])
        out["grader_b_stability"] = {"pairwise_kappa": pair, "flip_rate": round(flips / n_grades, 4),
                                     "rows_with_any_flip": sum(1 for v in b_modal.values() if len(set(v["passes"])) > 1)}

    # disagreements (artifact + technique), for adjudication and the report
    dis = []
    for rid in row_ids:
        if rid not in b_modal:
            continue
        a = a_rows[rid]
        if a["grade"] != b_modal[rid]["grade"] or b_modal[rid]["tie"]:
            dis.append({"row_id": rid, "a_grade": a["grade"], "a_object": a["ocsf_object"] or a["ocsf_class_uid"], "a_field": a["ocsf_field"],
                        "a_rationale": a["rationale"], "b_grade": b_modal[rid]["grade"], "b_passes": "/".join(b_modal[rid]["passes"]),
                        "b_object": b_modal[rid]["ocsf_object"] or b_modal[rid]["ocsf_class_uid"], "b_field": b_modal[rid]["ocsf_field"],
                        "b_rationale": next((r for r, g in zip(b_modal[rid]["rationales"], b_modal[rid]["passes"]) if g == b_modal[rid]["grade"]), "")})
    out["n_disagreements"] = {"artifact": sum(1 for d in dis if d["row_id"].startswith("d3f:")), "technique": sum(1 for d in dis if d["row_id"].startswith("AML."))}
    dg = collections.Counter(tuple(sorted((d["a_grade"], d["b_grade"]))) for d in dis if d["row_id"].startswith("d3f:"))
    out["artifact_disagreement_pairs"] = {"|".join(k): v for k, v in dg.most_common()}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    json.dump({"per_pass": per_pass, "modal": b_modal}, open(os.path.join(HERE, "results", "grader_b.json"), "w"), indent=1, sort_keys=True)
    json.dump(out, open(os.path.join(HERE, "results", "agreement.json"), "w"), indent=1, sort_keys=True)
    with open(os.path.join(HERE, "results", "disagreements.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dis[0].keys()) if dis else ["row_id"]); w.writeheader(); w.writerows(dis)
    print(json.dumps({k: v for k, v in out.items() if k not in ("artifact_rows", "technique_rows")}, indent=1))
    for s in ("artifact_rows", "technique_rows"):
        print(s, json.dumps({k: v for k, v in out[s].items() if k != "confusion_A_rows_B_cols"}))
        print("  confusion (A rows / B cols)", GRADES)
        for g in GRADES:
            print("   ", f"{g:8}", [out[s]["confusion_A_rows_B_cols"][g][h] for h in GRADES])


if __name__ == "__main__":
    main()

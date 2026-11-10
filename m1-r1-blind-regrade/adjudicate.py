"""Adjudication: build Argon prompts for A-vs-B disagreements (build), parse the rulings and write consensus (parse).

  .venv/bin/python -I adjudicate.py build     # prompts/adjudication/*.txt (+ assignment.json)
  .venv/bin/python -I adjudicate.py parse     # results/consensus.json
Pre-registered: up to 30 rows (seeded sample of 30 if more), grader labels randomised per row (seed 20261109).
"""
import csv, json, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
R1 = os.path.join(HERE, "..", "atlas-ocsf-observables")
SEED, CAP, BATCH = 20261109, 30, 10
sys.path.insert(0, HERE)
from build_prompts import RUBRIC, schema_excerpt, artifact_rows, technique_rows  # noqa: E402

OUT_FMT = """Two graders applied the rubric independently to each row below and disagreed. For each row, decide the correct grade and target under the rubric and the excerpt. You may side with Grader 1, Grader 2, or give a third answer. Answer with a single JSON array and nothing else, in the order given:
[{"row_id": "<row_id>", "grade": "direct|event|generic|proxy|none", "ocsf_object": "<name or null>", "ocsf_class_uid": <uid or null>, "ocsf_field": "<object.attribute or null>", "sides_with": "1|2|neither", "reason": "<= 40 words"}, ...]"""


def build():
    dis = list(csv.DictReader(open(os.path.join(HERE, "results", "disagreements.csv"))))
    rng = random.Random(SEED)
    sample = dis if len(dis) <= CAP else rng.sample(dis, CAP)
    sample = sorted(sample, key=lambda d: d["row_id"])
    texts = {r["row_id"]: r["text"] for r in artifact_rows() + technique_rows()}
    excerpt, _, _ = schema_excerpt()
    rng2 = random.Random(SEED)
    assign = {}
    d = os.path.join(HERE, "prompts", "adjudication"); os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    batches = []
    for i in range(0, len(sample), BATCH):
        chunk = sample[i:i + BATCH]
        lines = []
        for k, r in enumerate(chunk):
            a_first = rng2.random() < 0.5
            assign[r["row_id"]] = {"grader1": "A" if a_first else "B", "grader2": "B" if a_first else "A"}
            g1 = (r["a_grade"], r["a_object"], r["a_field"], r["a_rationale"]) if a_first else (r["b_grade"], r["b_object"], r["b_field"], r["b_rationale"])
            g2 = (r["b_grade"], r["b_object"], r["b_field"], r["b_rationale"]) if a_first else (r["a_grade"], r["a_object"], r["a_field"], r["a_rationale"])
            lines.append(f"{k + 1}. row_id={r['row_id']} :: {texts[r['row_id']]}\n   Grader 1: grade={g1[0]}, target={g1[1] or 'null'}, field={g1[2] or 'null'}; rationale: {g1[3]}\n   Grader 2: grade={g2[0]}, target={g2[1] or 'null'}, field={g2[2] or 'null'}; rationale: {g2[3]}")
        prompt = f"{RUBRIC}\n\nRows in dispute:\n" + "\n".join(lines) + f"\n\n{OUT_FMT}\n\n{excerpt}\n"
        assert len(prompt.encode()) < 120_000
        fn = f"adj-b{i // BATCH + 1}.txt"
        open(os.path.join(d, fn), "w").write(prompt)
        batches.append({"file": fn, "rows": [r["row_id"] for r in chunk]})
    json.dump({"seed": SEED, "n_disagreements": len(dis), "n_adjudicated": len(sample), "assignment": assign, "batches": batches,
               "unadjudicated": sorted(set(r["row_id"] for r in dis) - set(r["row_id"] for r in sample))},
              open(os.path.join(d, "assignment.json"), "w"), indent=1, sort_keys=True)
    print(f"disagreements={len(dis)} adjudicated={len(sample)} batches={len(batches)}")


def parse():
    reach = json.load(open(os.path.join(R1, "results", "ocsf_reach.json")))
    asg = json.load(open(os.path.join(HERE, "prompts", "adjudication", "assignment.json")))
    a = {r["artifact"]: r for r in csv.DictReader(open(os.path.join(R1, "artifact_ocsf_map.csv")))}
    a.update({r["atlas_id"]: r for r in csv.DictReader(open(os.path.join(R1, "technique_direct_ocsf.csv")))})
    b = json.load(open(os.path.join(HERE, "results", "grader_b.json")))["modal"]
    rulings, problems = {}, []
    for bt in asg["batches"]:
        fn = os.path.join(HERE, "responses", "adjudication", bt["file"].replace(".txt", ".md"))
        if not os.path.exists(fn):
            problems.append("missing " + bt["file"]); continue
        arr = json.loads(re.search(r"\[.*\]", open(fn).read(), re.S).group(0))
        for x in arr:
            rid = x.get("row_id")
            if rid not in bt["rows"]:
                continue
            g = str(x.get("grade", "")).lower()
            obj = x.get("ocsf_object") or None
            uid = x.get("ocsf_class_uid"); uid = str(uid) if uid not in (None, "", "null") else None
            flags = []
            if g not in ("direct", "event", "generic", "proxy", "none"):
                flags.append("bad_grade"); g = "none"
            if g != "none" and obj and obj not in reach["object_fields"]:
                flags.append("invented_object"); g = "none"
            if g != "none" and uid and uid not in reach["class_names"] and not obj:
                flags.append("invented_class"); g = "none"
            side = str(x.get("sides_with", "")).strip()
            who = asg["assignment"][rid].get("grader" + side, "neither") if side in ("1", "2") else "neither"
            rulings[rid] = {"grade": g, "ocsf_object": obj, "ocsf_class_uid": uid, "ocsf_field": x.get("ocsf_field") or None,
                            "sides_with": who, "reason": x.get("reason"), "flags": flags,
                            "a_grade": a[rid]["grade"], "b_grade": b[rid]["grade"]}
    rows = {}
    for rid, r in a.items():
        if rid in rulings:
            rows[rid] = {k: rulings[rid][k] for k in ("grade", "ocsf_object", "ocsf_class_uid", "ocsf_field")} | {"source": "adjudicator"}
        elif rid in b and b[rid]["grade"] == r["grade"] and not b[rid]["tie"]:
            rows[rid] = {"grade": r["grade"], "ocsf_object": r["ocsf_object"] or None, "ocsf_class_uid": r["ocsf_class_uid"] or None, "ocsf_field": r["ocsf_field"] or None, "source": "agreed"}
        else:
            rows[rid] = {"grade": r["grade"], "ocsf_object": r["ocsf_object"] or None, "ocsf_class_uid": r["ocsf_class_uid"] or None, "ocsf_field": r["ocsf_field"] or None, "source": "A_unadjudicated"}
    tally = {"sided_A": sum(1 for v in rulings.values() if v["sides_with"] == "A"), "sided_B": sum(1 for v in rulings.values() if v["sides_with"] == "B"),
             "third": sum(1 for v in rulings.values() if v["sides_with"] == "neither"),
             "grade_equals_A": sum(1 for v in rulings.values() if v["grade"] == v["a_grade"]), "grade_equals_B": sum(1 for v in rulings.values() if v["grade"] == v["b_grade"]),
             "grade_equals_neither": sum(1 for v in rulings.values() if v["grade"] not in (v["a_grade"], v["b_grade"])),
             "rulings": len(rulings), "problems": problems, "sources": {s: sum(1 for v in rows.values() if v["source"] == s) for s in ("agreed", "adjudicator", "A_unadjudicated")}}
    json.dump({"tally": tally, "rulings": rulings, "rows": rows}, open(os.path.join(HERE, "results", "consensus.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(tally, indent=1))
    for rid, v in sorted(rulings.items()):
        print(f"  {rid:32} A={v['a_grade']:8} B={v['b_grade']:8} -> {v['grade']:8} ({v['sides_with']}) {v['ocsf_object'] or v['ocsf_class_uid']}")


if __name__ == "__main__":
    {"build": build, "parse": parse}[sys.argv[1]]()

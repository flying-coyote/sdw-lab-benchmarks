"""Build blind grading prompts for Grader B (Gemini) from R1's two grade files with every judgment column stripped.

  .venv/bin/python -I build_prompts.py            # writes prompts/pass{1,2,3}/*.txt and prompts/manifest.json
Deterministic. No model call here.
"""
import csv, hashlib, json, os, random, re, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
R1 = os.path.join(HERE, "..", "atlas-ocsf-observables")
D3F = "/home/jerem/project1/02-projects/d3fend-wall/cache/d3fend_ontology.json"
ATLAS = "/home/jerem/project1/02-projects/atlas-mitigations/cache/ATLAS-2026.10.yaml"
PASSES = {1: 1, 2: 2, 3: 3}          # pass -> shuffle seed
BATCH = 10
MAX_BYTES = 120_000

RUBRIC = """You are grading, for one D3FEND digital artifact (or one ATLAS technique) at a time, whether the OCSF 1.9.0 schema has a field that records it. Use exactly one of five grades:
- direct: an OCSF object or dedicated field denotes the same kind as the artifact.
- event: the artifact is an occurrent (a D3FEND system-call class); OCSF records it as a class plus activity_id, not an object.
- generic: OCSF has the parent kind only; what makes it this artifact is not a field.
- proxy: no object for the artifact; only a carrier field could hold a reference (path, URL).
- none: nothing.

Discipline:
1. Map by meaning, not by field name.
2. Distinguish the actor that performed the action from the object it acted on.
3. Choose the most specific correct target path; never a path that does not exist in the target schema.
4. Preserve the source's absent / null / false distinctions.

Rules: use only the OCSF 1.9.0 excerpt below; name only objects, classes and attributes that appear in it. Do not use any tools, do not browse, do not read files. If nothing fits, grade none and set the targets to null. For grade event, set ocsf_class_uid to the event class uid and ocsf_object to null. Otherwise set ocsf_object to the object name and ocsf_field to "<object>.<attribute>" using an attribute listed for that object. Rationale at most 40 words."""

OUTPUT = """Answer with a single JSON array and nothing else, one element per row, in the order given:
[{"row_id": "<row_id>", "grade": "direct|event|generic|proxy|none", "ocsf_object": "<name or null>", "ocsf_class_uid": <uid or null>, "ocsf_field": "<object.attribute or null>", "rationale": "<= 40 words"}, ...]"""


def first_sentence(s):
    s = re.sub(r"<[^>]+>", "", s or "").strip()
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    return (m.group(1) if m else s)[:300]


def schema_excerpt():
    objs = json.load(open(os.path.join(R1, "sources", "ocsf-1.9.0-objects.json")))
    cls = json.load(open(os.path.join(R1, "sources", "ocsf-1.9.0-classes.json")))
    lines = ["## OCSF 1.9.0 objects (name: description; attributes)"]
    for o in sorted(objs, key=lambda o: o["name"]):
        p = os.path.join(R1, "sources", "ocsf-1.9.0-noprofile", "objects", o["name"] + ".json")
        attrs = sorted(json.load(open(p))["attributes"])
        lines.append(f"- {o['name']}: {first_sentence(o.get('description'))} | attributes: {', '.join(attrs)}")
    lines.append("")
    lines.append("## OCSF 1.9.0 event classes (uid name [category]: description)")
    for c in sorted(cls, key=lambda c: c["uid"]):
        dep = " [DEPRECATED]" if "@deprecated" in c else ""
        lines.append(f"- {c['uid']} {c['name']} [{c.get('category', '')}]{dep}: {first_sentence(c.get('description'))}")
    return "\n".join(lines), {o["name"] for o in objs}, {str(c["uid"]) for c in cls}


def artifact_rows():
    g = json.load(open(D3F))["@graph"]
    nodes = {n["@id"]: n for n in g if isinstance(n.get("@id"), str)}
    out = []
    for r in csv.DictReader(open(os.path.join(R1, "artifact_ocsf_map.csv"))):
        n = nodes[r["artifact"]]
        d = n.get("d3f:definition") or n.get("rdfs:comment") or "(no definition in D3FEND 1.4.0)"
        if isinstance(d, list):
            d = " / ".join(d)
        par = n.get("rdfs:subClassOf")
        par = [par] if isinstance(par, dict) else (par or [])
        par = ", ".join(p["@id"] for p in par if isinstance(p, dict) and str(p.get("@id", "")).startswith("d3f:"))
        out.append({"row_id": r["artifact"], "file": "artifact",
                    "text": f"{r['artifact']} (label: {n.get('rdfs:label')}; parent: {par}). Definition: {d}"})
    return out


def technique_rows():
    T = yaml.safe_load(open(ATLAS))["techniques"]
    out = []
    for r in csv.DictReader(open(os.path.join(R1, "technique_direct_ocsf.csv"))):
        t = T[r["atlas_id"]]
        desc = re.sub(r"\s+", " ", t["description"])[:600]
        out.append({"row_id": r["atlas_id"], "file": "technique",
                    "text": f"{r['atlas_id']} {t['name']} (ATLAS v2026.10 technique). Question for this row: does any OCSF 1.9.0 object or class directly record this technique as it happens on the victim side? Description: {desc}"})
    return out


def main():
    excerpt, obj_names, cls_uids = schema_excerpt()
    arts, techs = artifact_rows(), technique_rows()
    manifest = {"prereg_sha256": open(os.path.join(HERE, "results", "PREREG.sha256")).read().split()[0],
                "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(), "excerpt_bytes": len(excerpt),
                "n_objects": len(obj_names), "n_classes": len(cls_uids), "batch": BATCH, "passes": {}}
    for p, seed in PASSES.items():
        d = os.path.join(HERE, "prompts", f"pass{p}")
        os.makedirs(d, exist_ok=True)
        rng = random.Random(seed)
        batches = []
        for name, rows in (("artifact", list(arts)), ("technique", list(techs))):
            rng.shuffle(rows)
            for i in range(0, len(rows), BATCH):
                chunk = rows[i:i + BATCH]
                body = "\n".join(f"{k + 1}. row_id={r['row_id']} :: {r['text']}" for k, r in enumerate(chunk))
                head = "Rows to grade (D3FEND digital artifacts):" if name == "artifact" else "Rows to grade (ATLAS techniques with no D3FEND crosswalk row; grade direct OCSF observability of the technique itself):"
                prompt = f"{RUBRIC}\n\n{head}\n{body}\n\n{OUTPUT}\n\n{excerpt}\n"
                assert len(prompt.encode()) < MAX_BYTES, (p, name, i, len(prompt.encode()))
                fn = f"{name}-b{i // BATCH + 1}.txt"
                open(os.path.join(d, fn), "w").write(prompt)
                batches.append({"file": fn, "rows": [r["row_id"] for r in chunk], "bytes": len(prompt.encode())})
        manifest["passes"][str(p)] = {"seed": seed, "batches": batches}
    json.dump(manifest, open(os.path.join(HERE, "prompts", "manifest.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in manifest.items() if k != "passes"}, indent=1))
    print("batches per pass:", len(manifest["passes"]["1"]["batches"]), "max bytes:", max(b["bytes"] for b in manifest["passes"]["1"]["batches"]))


if __name__ == "__main__":
    main()

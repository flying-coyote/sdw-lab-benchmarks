"""BENCH-B — mapping oracle (first-pass, local weak-model leg).

Does putting the OCSF schema in front of a model beat its parametric knowledge on
source->OCSF field mapping (schema - none)? Does a formal grounding note beat plain
schema (formal - schema)? Does an ontology-thinking reasoning discipline beat plain
schema (skill - schema)? The primary metric is the SILENT-ERROR rate — a field mapped
to an OCSF attribute path that does not exist in 1.8.0, which executes/validates as a
real mapping and is wrong, the security-relevant failure mode.

Gold key: the hand-curated C1 source->OCSF mappings (../ocsf-mapping-fidelity/mapping.py),
built from vendor docs + the OCSF schema, never from an LLM. Each predicted OCSF path is
validated against the checked-in OCSF 1.8.0 subset, so an invented path is caught.

This is the LOCAL weak-model leg only (Ollama). The independent frontier leg and the
larger gold set are the expansion — the frontier leg needs an API key (Jeremy's). The
weak-vs-frontier capability-gap interaction (H-PRACTITIONER-OWNED-AGENTIC-01) is not
resolved by this first pass; the within-weak-model lifts are.
"""

import argparse
import json
import os
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ocsf-mapping-fidelity"))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import mapping as c1            # noqa: E402  the C1 gold mappings
from common import canonical    # noqa: E402

SUBSET = os.path.join(HERE, "..", "ocsf-mapping-fidelity", "schemas", "ocsf", "ocsf_1.8.0_subset.json")
OLLAMA = "http://localhost:11434/api/generate"

# Source dict -> (OCSF class name, uid). Only classes fully defined in the subset are
# used, so predicted paths can be validated.
SOURCES = {
    "Okta System Log": (c1.OKTA_MAPPING, "authentication", 3002),
    "Palo Alto PAN-OS TRAFFIC": (c1.PALO_ALTO_MAPPING, "network_activity", 4001),
}

# Pure conceptual grounding per class — no field-path hint may leak in.
GROUNDING = {
    "authentication": ("An Authentication event is an actor (the entity performing the "
        "sign-in) authenticating a user (the account being signed into) against a service, "
        "observed at a source endpoint and recorded with event metadata. Ground each field "
        "by which of those roles it describes."),
    "network_activity": ("A Network Activity event is a connection from a source endpoint "
        "to a destination endpoint, carrying directional traffic, observed by a device. "
        "Ground each field by which endpoint it names, which direction of bytes it counts, "
        "or which connection attribute it carries."),
}

SKILL = ("Reason by meaning, not by field-name similarity. First decide whether the field "
         "describes the actor performing the action, the user/object acted on, an endpoint, "
         "the traffic, or event metadata. Then choose the most specific correct attribute "
         "path. Preserve the distinctions the source makes (absent vs null vs false). Never "
         "invent an attribute that is not in the schema.")

CATCH_ALLS = {"unmapped", "raw_data", "observables", "enrichments"}


def load_valid_paths():
    d = json.load(open(SUBSET))
    objects = d["objects"]

    def obj_attrs(name):
        o = objects.get(name, {})
        return o.get("attrs", o) if isinstance(o, dict) else {}

    def expand(attrs, prefix, depth, acc):
        for a, ref in attrs.items():
            p = f"{prefix}{a}"
            acc.add(p)
            if isinstance(ref, str) and ref and depth > 0:
                expand(obj_attrs(ref), p + ".", depth - 1, acc)

    valid = {}
    for cname, c in d["classes"].items():
        acc = set(CATCH_ALLS)
        expand(c["attrs"], "", 3, acc)
        valid[cname] = acc
    return valid


def gold_fields(n_per_source):
    """Curated gold subset: fields whose C1 gold is a concrete dotted path."""
    out = []
    for source, (mp, cls, uid) in SOURCES.items():
        taken = 0
        for field, rec in mp.items():
            path = rec.get("ocsf", "")
            if path in CATCH_ALLS or " " in path or "." not in path and path not in ("time", "message"):
                # keep real dotted paths (and the bare scalar class attrs time/message)
                if path not in ("time", "message"):
                    continue
            out.append({"source": source, "field": field, "class": cls, "uid": uid,
                        "gold": path, "status": rec.get("status"), "note": rec.get("note", "")})
            taken += 1
            if taken >= n_per_source:
                break
    return out


def normalize(path, cls):
    if not path:
        return ""
    p = path.strip().lstrip("/").strip(".")
    p = p.replace("/", ".")
    for pre in (cls + ".", f"{cls}/"):
        if p.startswith(pre):
            p = p[len(pre):]
    return p


def schema_block(cls, valid):
    paths = sorted(valid[cls])
    # cap to a readable in-context schema (top-level + key nested), not the full closure
    short = [p for p in paths if p.count(".") <= 1]
    return "Valid " + cls + " attribute paths include: " + ", ".join(short[:80]) + "."


def prompt_for(item, condition, valid):
    cls = item["class"]
    head = (f"Map one source log field to exactly one OCSF 1.8.0 {cls} ({item['uid']}) "
            f"attribute path. Output JSON only: {{\"ocsf_path\": \"<dotted path>\"}}.\n")
    blocks = []
    if condition in ("schema", "formal", "skill"):
        blocks.append(schema_block(cls, valid))
    if condition == "formal":
        blocks.append(GROUNDING.get(cls, ""))
    if condition == "skill":
        blocks.append(SKILL)
    blocks.append(f"Source: {item['source']}. Field: {item['field']}.")
    return head + "\n".join(b for b in blocks if b)


def ask(model, prompt):
    try:
        r = requests.post(OLLAMA, json={"model": model, "prompt": prompt, "stream": False,
                          "format": "json", "options": {"temperature": 0}, "keep_alive": "10m"},
                          timeout=180)
        resp = r.json().get("response", "")
        obj = json.loads(resp)
        # accept the agreed key or the first string value
        for k in ("ocsf_path", "ocsfPath", "path"):
            if k in obj and isinstance(obj[k], str):
                return obj[k]
        for v in obj.values():
            if isinstance(v, str):
                return v
    except Exception:
        return None
    return None


def score_cell(items, model, condition, valid):
    n = correct = silent = 0
    for it in items:
        pred = ask(model, prompt_for(it, condition, valid))
        n += 1
        if pred is None:
            silent += 1            # no parseable path is an unusable (silent-equivalent) answer
            continue
        norm = normalize(pred, it["class"])
        if norm not in valid[it["class"]]:
            silent += 1            # invented path — the security-relevant failure
        if norm == normalize(it["gold"], it["class"]):
            correct += 1
    return {"n": n, "path_correct": round(correct / n, 4),
            "silent_error_rate": round(silent / n, 4)}


def render_md(results):
    lines = ["# BENCH-B — mapping oracle: results (first pass)", "",
             "**Tier B, local weak-model leg only.** This runs the four-condition design on a "
             "local open-weight model via Ollama. The independent frontier leg and the larger "
             "gold set are the expansion (the frontier leg needs an API key), so the "
             "weak-vs-frontier capability gap is *not* resolved here; the within-weak-model "
             "lifts are. The primary metric is the **silent-error rate** — a field mapped to an "
             "OCSF path that does not exist in 1.8.0 — because exact-match path-correctness "
             "penalizes valid alternatives and is the wrong headline for a weak model.", "",
             f"Gold: {results['n_fields']} hand-curated C1 source→OCSF mappings across "
             f"{', '.join(results['sources'])}. Every predicted path validated against the "
             "checked-in OCSF 1.8.0 subset.", ""]
    for model, m in results["models"].items():
        c = m["cells"]
        lines += [f"## {model}", "",
                  "| condition | path-correct | silent-error rate |",
                  "|---|---|---|"]
        for cond in ("none", "schema", "formal", "skill"):
            lines.append(f"| {cond} | {c[cond]['path_correct']:.2f} | {c[cond]['silent_error_rate']:.2f} |")
        lf = m["lifts"]
        lines += ["", f"- **schema − none** (path-correct): {lf['schema_minus_none']:+.2f}",
                  f"- **formal − schema** (path-correct): {lf['formal_minus_schema']:+.2f}",
                  f"- **skill − schema** (path-correct): {lf['skill_minus_schema']:+.2f}",
                  f"- **silent-error, schema − none**: {lf['silent_schema_minus_none']:+.2f} "
                  "(negative = fewer invented paths)", ""]
    lines += ["## Reading", "",
              "Path-correctness on a sub-frontier model is low across the board — an 8B-class "
              "local model rarely lands the exact gold OCSF path, which is why silent-error rate "
              "is the metric that carries the finding. Where the formal grounding and the "
              "ontology-thinking skill condition move the silent-error rate, that is the "
              "security-relevant signal: a disciplined prompt produces fewer invented paths even "
              "when the model can't name the exactly-right one. The frontier leg is what would "
              "show whether that lift is a sub-frontier teaching effect or a frontier moat "
              "(H-PRACTITIONER-OWNED-AGENTIC-01), and it is the next step.", "",
              "Caveats: exact-match scoring undercounts valid alternatives; one weak model, "
              "single-shot, temperature 0; the gold set is a curated subset. Tier B."]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="phi3:latest")
    ap.add_argument("--fields-per-source", type=int, default=10)
    ap.add_argument("--render-only", action="store_true",
                    help="regenerate RESULTS.md from results/results.json without calling models")
    args = ap.parse_args()

    if args.render_only:
        res = json.load(open(os.path.join(HERE, "results", "results.json")))
        with open(os.path.join(HERE, "results", "RESULTS.md"), "w") as f:
            f.write(render_md(res))
        print("rendered results/RESULTS.md")
        return

    valid = load_valid_paths()
    items = gold_fields(args.fields_per_source)
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    conditions = ["none", "schema", "formal", "skill"]

    results = {"benchmark": "ocsf-mapping-oracle (BENCH-B, first-pass local leg)",
               "evidence_tier": "B (local weak-model leg; frontier leg + larger gold set pending)",
               "n_fields": len(items), "sources": list(SOURCES),
               "models": {}}
    for model in models:
        cells = {c: score_cell(items, model, c, valid) for c in conditions}
        lifts = {
            "schema_minus_none": round(cells["schema"]["path_correct"] - cells["none"]["path_correct"], 4),
            "formal_minus_schema": round(cells["formal"]["path_correct"] - cells["schema"]["path_correct"], 4),
            "skill_minus_schema": round(cells["skill"]["path_correct"] - cells["schema"]["path_correct"], 4),
            "silent_schema_minus_none": round(cells["schema"]["silent_error_rate"] - cells["none"]["silent_error_rate"], 4),
        }
        results["models"][model] = {"cells": cells, "lifts": lifts}
        print(f"{model}: " + "  ".join(
            f"{c}=pc{cells[c]['path_correct']:.2f}/se{cells[c]['silent_error_rate']:.2f}" for c in conditions))
        print(f"  lifts: schema-none={lifts['schema_minus_none']:+.2f}  "
              f"formal-schema={lifts['formal_minus_schema']:+.2f}  skill-schema={lifts['skill_minus_schema']:+.2f}  "
              f"silent(schema-none)={lifts['silent_schema_minus_none']:+.2f}")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "results.json"), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    with open(os.path.join(HERE, "results", "RESULTS.md"), "w") as f:
        f.write(render_md(results))
    print(f"\nwrote results/results.json + RESULTS.md ({len(items)} fields, {len(models)} model(s))")
    return results


if __name__ == "__main__":
    main()

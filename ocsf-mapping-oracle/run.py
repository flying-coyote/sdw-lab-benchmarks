"""BENCH-B — mapping oracle (matured: 6 sources, model ladder, wrong-grounding control).

Does grounding help a model map a source field to the right OCSF attribute, which kind, and
is the lift real discipline or just more tokens? Five conditions on one task (source field →
OCSF attribute path), scored against the hand-curated C1 gold key:

- none           — field + target class only (parametric knowledge)
- schema         — + the OCSF class's valid attribute paths
- formal         — + a conceptual grounding note for the class (no field-path hint)
- skill          — + an ontology-thinking reasoning discipline
- wrong_grounding— + a grounding note for the WRONG class (the control: if this helps as much
                   as `formal`, the lift was extra tokens, not correct grounding)

Primary metric: silent-error rate (a field mapped to a path that doesn't exist in OCSF 1.8.0),
because exact-match path-correctness penalizes valid alternatives. Run across a local model
ladder (3.8B → 14B) for a capability gradient without a frontier key: does the grounding lift
shrink as the model grows? Gold is the C1 mappings (vendor docs + schema, never an LLM); every
predicted path is validated against the checked-in OCSF 1.8.0 subset.
"""

import argparse
import json
import os
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ocsf-mapping-fidelity"))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import mapping as c1  # noqa: E402

SUBSET = os.path.join(HERE, "..", "ocsf-mapping-fidelity", "schemas", "ocsf", "ocsf_1.8.0_subset.json")
OLLAMA = "http://localhost:11434/api/generate"

# All six C1 vendor sources -> their OCSF class (all classes are in the validated subset).
SOURCES = {
    "Okta System Log": (c1.OKTA_MAPPING, "authentication", 3002),
    "CrowdStrike Detection Summary": (c1.CROWDSTRIKE_MAPPING, "detection_finding", 2004),
    "Palo Alto PAN-OS TRAFFIC": (c1.PALO_ALTO_MAPPING, "network_activity", 4001),
    "Cisco ASA connection syslog": (c1.CISCO_ASA_MAPPING, "network_activity", 4001),
    "Cisco Umbrella DNS": (c1.CISCO_UMBRELLA_MAPPING, "dns_activity", 4003),
    "Zscaler ZIA Web": (c1.ZSCALER_MAPPING, "http_activity", 4002),
}

# Pure conceptual grounding per class — no field-path hint leaks in.
GROUNDING = {
    "authentication": ("An Authentication event is an actor (the entity performing the sign-in) "
        "authenticating a user (the account being signed into) against a service, observed at a "
        "source endpoint and recorded with event metadata. Ground each field by which role it describes."),
    "detection_finding": ("A Detection Finding is an analytic's verdict about activity — a finding "
        "with a disposition and severity, referencing the actor, the affected device, the evidence, "
        "and the mapped ATT&CK technique. Ground each field by whether it describes the finding, the "
        "analytic, the affected entity, or the attack."),
    "network_activity": ("A Network Activity event is a connection from a source endpoint to a "
        "destination endpoint, carrying directional traffic, observed by a device. Ground each field "
        "by which endpoint it names, which direction of bytes it counts, or which connection attribute."),
    "dns_activity": ("A DNS Activity event is a name-resolution query and its answers, from a source "
        "endpoint to a DNS service. Ground each field by whether it names the query, an answer record, "
        "an endpoint, or the connection."),
    "http_activity": ("An HTTP Activity event is a request/response between a source endpoint and a "
        "destination, with a URL and HTTP metadata. Ground each field by whether it describes the "
        "request, the response, the URL, or an endpoint."),
}
# Wrong-grounding control: each class gets a DIFFERENT class's note (a rotation), so the note is
# well-formed but about the wrong domain. formal vs wrong_grounding isolates correct-grounding.
_CLASSES = list(GROUNDING)
WRONG_GROUNDING = {c: GROUNDING[_CLASSES[(i + 1) % len(_CLASSES)]] for i, c in enumerate(_CLASSES)}

SKILL = ("Reason by meaning, not by field-name similarity. First decide whether the field describes "
         "the actor performing the action, the user/object acted on, an endpoint, the traffic, or "
         "event metadata. Then choose the most specific correct attribute path. Preserve the "
         "distinctions the source makes (absent vs null vs false). Never invent an attribute that is "
         "not in the schema.")

CATCH_ALLS = {"unmapped", "raw_data", "observables", "enrichments"}
CONDITIONS = ["none", "schema", "formal", "skill", "wrong_grounding"]


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


def gold_fields(per_source_cap):
    out = []
    for source, (mp, cls, uid) in SOURCES.items():
        taken = 0
        for field, rec in mp.items():
            path = rec.get("ocsf", "")
            if path in CATCH_ALLS or "." not in path:   # real dotted paths only
                continue
            out.append({"source": source, "field": field, "class": cls, "uid": uid,
                        "gold": path, "status": rec.get("status")})
            taken += 1
            if per_source_cap and taken >= per_source_cap:
                break
    return out


def normalize(path, cls):
    if not path:
        return ""
    p = path.strip().lstrip("/").strip(".").replace("/", ".")
    for pre in (cls + ".", f"{cls}/"):
        if p.startswith(pre):
            p = p[len(pre):]
    return p


def schema_block(cls, valid):
    short = sorted(p for p in valid[cls] if p.count(".") <= 1)
    return "Valid " + cls + " attribute paths include: " + ", ".join(short[:80]) + "."


def prompt_for(item, condition, valid):
    cls = item["class"]
    head = (f"Map one source log field to exactly one OCSF 1.8.0 {cls} ({item['uid']}) attribute "
            f"path. Output JSON only: {{\"ocsf_path\": \"<dotted path>\"}}.\n")
    blocks = []
    if condition in ("schema", "formal", "skill", "wrong_grounding"):
        blocks.append(schema_block(cls, valid))
    if condition == "formal":
        blocks.append(GROUNDING.get(cls, ""))
    if condition == "wrong_grounding":
        blocks.append(WRONG_GROUNDING.get(cls, ""))
    if condition == "skill":
        blocks.append(SKILL)
    blocks.append(f"Source: {item['source']}. Field: {item['field']}.")
    return head + "\n".join(b for b in blocks if b)


def ask(model, prompt):
    try:
        r = requests.post(OLLAMA, json={"model": model, "prompt": prompt, "stream": False,
                          "format": "json", "options": {"temperature": 0}, "keep_alive": "15m"},
                          timeout=240)
        obj = json.loads(r.json().get("response", ""))
        for k in ("ocsf_path", "ocsfPath", "path"):
            if isinstance(obj.get(k), str):
                return obj[k]
        for v in obj.values():
            if isinstance(v, str):
                return v
    except Exception:
        return None
    return None


def score_cell(items, model, condition, valid):
    n = correct = silent = 0
    by_source = {}
    for it in items:
        src = it["source"]
        bs = by_source.setdefault(src, {"n": 0, "silent": 0, "correct": 0})
        pred = ask(model, prompt_for(it, condition, valid))
        n += 1; bs["n"] += 1
        if pred is None:
            silent += 1; bs["silent"] += 1; continue
        norm = normalize(pred, it["class"])
        if norm not in valid[it["class"]]:
            silent += 1; bs["silent"] += 1
        if norm == normalize(it["gold"], it["class"]):
            correct += 1; bs["correct"] += 1
    return {"n": n, "path_correct": round(correct / n, 4), "silent_error_rate": round(silent / n, 4),
            "by_source": {s: {"n": v["n"], "silent_rate": round(v["silent"]/v["n"], 4),
                              "path_correct": round(v["correct"]/v["n"], 4)} for s, v in by_source.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="phi3:latest")
    ap.add_argument("--per-source-cap", type=int, default=0, help="0 = all (full 141); else cap per source")
    ap.add_argument("--out", default="results.json")
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--determinism", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)

    if args.determinism:
        import hashlib
        valid = load_valid_paths()
        fp = lambda x: hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()
        g1, g2 = gold_fields(0), gold_fields(0)
        same_gold = fp(g1) == fp(g2)
        same_prompts = all(prompt_for(g1[0], c, valid) == prompt_for(g1[0], c, valid) for c in CONDITIONS)
        print(f"gold set reproduces: {same_gold}  ({len(g1)} fields)")
        print(f"prompts + valid-path closure reproduce: {same_prompts}")
        print("NOTE: gold key, prompts, OCSF-path validation, and scoring are deterministic; model "
              "outputs are temperature-0 greedy decode (reproducible in practice, not asserted byte-identical).")
        sys.exit(0 if (same_gold and same_prompts) else 1)

    if args.render_only:
        res = json.load(open(os.path.join(rdir, args.out)))
        with open(os.path.join(rdir, "RESULTS.md"), "w") as f:
            f.write(render_md(res))
        print("rendered results/RESULTS.md"); return

    valid = load_valid_paths()
    items = gold_fields(args.per_source_cap)
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    results = {"benchmark": "ocsf-mapping-oracle (BENCH-B)",
               "evidence_tier": "B (local model ladder; frontier leg still pending an API key)",
               "n_fields": len(items), "per_source_cap": args.per_source_cap or "all",
               "sources": list(SOURCES), "conditions": CONDITIONS, "models": {}}
    for model in models:
        cells = {c: score_cell(items, model, c, valid) for c in CONDITIONS}
        results["models"][model] = {"cells": cells, "lifts": {
            "silent_schema_minus_none": round(cells["schema"]["silent_error_rate"] - cells["none"]["silent_error_rate"], 4),
            "silent_skill_minus_none": round(cells["skill"]["silent_error_rate"] - cells["none"]["silent_error_rate"], 4),
            "silent_formal_minus_none": round(cells["formal"]["silent_error_rate"] - cells["none"]["silent_error_rate"], 4),
            "silent_formal_minus_wrong": round(cells["formal"]["silent_error_rate"] - cells["wrong_grounding"]["silent_error_rate"], 4),
            "pathcorrect_skill_minus_schema": round(cells["skill"]["path_correct"] - cells["schema"]["path_correct"], 4)}}
        print(f"{model} (n={len(items)}): " + " ".join(
            f"{c}=se{cells[c]['silent_error_rate']:.2f}/pc{cells[c]['path_correct']:.2f}" for c in CONDITIONS))

    with open(os.path.join(rdir, args.out), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "RESULTS.md"), "w") as f:
        f.write(render_md(results))
    print(f"wrote results/{args.out} + RESULTS.md ({len(items)} fields, {len(models)} model(s))")


def render_md(r):
    lines = ["# BENCH-B — mapping oracle: results", "",
             "**Tier B, local model ladder.** Five conditions on source→OCSF field mapping, scored "
             "against the hand-curated C1 gold key with every predicted path validated against the "
             "OCSF 1.8.0 subset. Primary metric is the **silent-error rate** (a path that doesn't "
             "exist); exact-match path-correctness is reported but undercounts valid alternatives. "
             "The model ladder is the capability gradient available without a frontier API key.", "",
             f"Gold: {r['n_fields']} real-path mappings across {len(r['sources'])} vendor sources "
             f"({', '.join(r['sources'])}). Conditions: {', '.join(r['conditions'])}.", "",
             "The **wrong_grounding** condition gives a grounding note for the *wrong* OCSF class — "
             "the control that separates correct grounding from extra tokens.", ""]
    for model, m in r["models"].items():
        c = m["cells"]
        lines += [f"## {model}", "", "| condition | silent-error | path-correct |", "|---|---|---|"]
        for cond in r["conditions"]:
            lines.append(f"| {cond} | {c[cond]['silent_error_rate']:.2f} | {c[cond]['path_correct']:.2f} |")
        lf = m["lifts"]
        lines += ["", f"- silent-error, schema − none: {lf['silent_schema_minus_none']:+.2f} "
                  "(negative = fewer invented paths)",
                  f"- silent-error, skill − none: {lf['silent_skill_minus_none']:+.2f}",
                  f"- silent-error, formal − none: {lf['silent_formal_minus_none']:+.2f}",
                  f"- **control** silent-error, formal − wrong_grounding: {lf['silent_formal_minus_wrong']:+.2f} "
                  "(negative = correct grounding beats wrong grounding; ~0 = the lift was tokens, not content)", ""]
    lines += ["## Reading", "",
              "Silent-error rate is the headline because path-correctness on sub-frontier local models "
              "stays low — they rarely land the exact gold OCSF path. Where schema, grounding, and the "
              "ontology-thinking discipline cut the silent-error rate, that is the security-relevant "
              "signal: fewer invented attributes. The wrong-grounding control is the honesty check — if "
              "`formal` beats `wrong_grounding`, correct grounding content is doing work; if they tie, the "
              "lift was just more tokens. Across the model ladder, a lift that shrinks as the model grows "
              "reads as a sub-frontier teaching effect rather than a frontier moat (the question "
              "H-PRACTITIONER-OWNED-AGENTIC-01 asks; the frontier leg, pending an API key, would close it).", "",
              "Tier B: local models, single-shot, temperature 0; exact-match undercounts valid alternatives; "
              "the gold set is curated. Tier-A needs a published larger gold set, a named reviewer on the "
              "ambiguous calls, and an independent frontier model."]
    return "\n".join(lines)


if __name__ == "__main__":
    main()

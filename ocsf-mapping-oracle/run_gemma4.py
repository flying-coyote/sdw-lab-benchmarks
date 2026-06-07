"""gemma4:26b leg for BENCH-B.

Stratified sample (20 items, first 3–5 per source sorted by field name) so all 6
vendor sources are represented.  All 5 conditions run on the same sample.  Results
are merged into the shared results/results.json alongside the phi3 leg.

Sampling rule (deterministic):
  - Cisco Umbrella DNS (5 items total): all 5
  - Every other source: first 3 sorted by field name
Total: 3*5 + 5 = 20 items

This yields a ~40–70 min runtime at the observed ~40 s/inference on a local
Beelink/WSL2 host.  A full 141-item run at that rate would be ~470 min; the
20-item stratified sample is the runtime-bound compromise stated in BENCH-B notes.
"""

import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ocsf-mapping-fidelity"))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import mapping as c1  # noqa: E402

SUBSET = os.path.join(HERE, "..", "ocsf-mapping-fidelity", "schemas", "ocsf", "ocsf_1.8.0_subset.json")
OLLAMA = "http://localhost:11434/api/generate"
MODEL = "gemma4:26b"
SAMPLE_N = 20  # per-source-cap overridden by stratification logic below

SOURCES = {
    "Okta System Log": (c1.OKTA_MAPPING, "authentication", 3002),
    "CrowdStrike Detection Summary": (c1.CROWDSTRIKE_MAPPING, "detection_finding", 2004),
    "Palo Alto PAN-OS TRAFFIC": (c1.PALO_ALTO_MAPPING, "network_activity", 4001),
    "Cisco ASA connection syslog": (c1.CISCO_ASA_MAPPING, "network_activity", 4001),
    "Cisco Umbrella DNS": (c1.CISCO_UMBRELLA_MAPPING, "dns_activity", 4003),
    "Zscaler ZIA Web": (c1.ZSCALER_MAPPING, "http_activity", 4002),
}

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


def build_sample():
    """Stratified deterministic sample: first 3 per source (5 for Cisco Umbrella DNS)."""
    by_source = {}
    for source, (mp, cls, uid) in SOURCES.items():
        items = []
        for field, rec in mp.items():
            path = rec.get("ocsf", "")
            if path in CATCH_ALLS or "." not in path:
                continue
            items.append({"source": source, "field": field, "class": cls, "uid": uid,
                          "gold": path, "status": rec.get("status")})
        by_source[source] = sorted(items, key=lambda x: x["field"])

    sample = []
    for source in sorted(SOURCES.keys()):
        items = by_source[source]
        take = len(items) if source == "Cisco Umbrella DNS" else 3
        sample.extend(items[:take])
    return sample


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


def ask(prompt):
    try:
        r = requests.post(OLLAMA, json={"model": MODEL, "prompt": prompt, "stream": False,
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


def score_cell(items, condition, valid):
    n = correct = silent = 0
    by_source = {}
    for it in items:
        src = it["source"]
        bs = by_source.setdefault(src, {"n": 0, "silent": 0, "correct": 0})
        t0 = time.time()
        pred = ask(prompt_for(it, condition, valid))
        elapsed = time.time() - t0
        n += 1; bs["n"] += 1
        status = "silent"
        if pred is None:
            silent += 1; bs["silent"] += 1
        else:
            norm = normalize(pred, it["class"])
            if norm not in valid[it["class"]]:
                silent += 1; bs["silent"] += 1
                status = "invalid"
            else:
                status = "valid"
            if norm == normalize(it["gold"], it["class"]):
                correct += 1; bs["correct"] += 1
                status = "correct"
        print(f"  [{condition}] {it['field']} -> pred={pred!r} [{status}] ({elapsed:.1f}s)")
    return {"n": n, "path_correct": round(correct / n, 4), "silent_error_rate": round(silent / n, 4),
            "by_source": {s: {"n": v["n"], "silent_rate": round(v["silent"]/v["n"], 4),
                              "path_correct": round(v["correct"]/v["n"], 4)} for s, v in by_source.items()}}


def main():
    rdir = os.path.join(HERE, "results")
    os.makedirs(rdir, exist_ok=True)
    results_path = os.path.join(rdir, "results.json")

    # Load existing results
    existing = json.load(open(results_path))

    valid = load_valid_paths()
    items = build_sample()
    print(f"Sample: {len(items)} items across {len(set(x['source'] for x in items))} sources")
    print(f"Running all 5 conditions on {MODEL} ...")

    cells = {}
    for condition in CONDITIONS:
        print(f"\n=== Condition: {condition} ===")
        t0 = time.time()
        cells[condition] = score_cell(items, condition, valid)
        elapsed = time.time() - t0
        c = cells[condition]
        print(f"  -> se={c['silent_error_rate']:.3f} pc={c['path_correct']:.3f}  ({elapsed:.0f}s)")

    model_result = {"cells": cells, "lifts": {
        "silent_schema_minus_none": round(cells["schema"]["silent_error_rate"] - cells["none"]["silent_error_rate"], 4),
        "silent_skill_minus_none": round(cells["skill"]["silent_error_rate"] - cells["none"]["silent_error_rate"], 4),
        "silent_formal_minus_none": round(cells["formal"]["silent_error_rate"] - cells["none"]["silent_error_rate"], 4),
        "silent_formal_minus_wrong": round(cells["formal"]["silent_error_rate"] - cells["wrong_grounding"]["silent_error_rate"], 4),
        "pathcorrect_skill_minus_schema": round(cells["skill"]["path_correct"] - cells["schema"]["path_correct"], 4)},
        "sampling": {
            "method": "stratified_deterministic",
            "n": len(items),
            "rule": "first 3 per source (sorted by field name); Cisco Umbrella DNS all 5 (only 5 available)",
            "full_gold_n": 141,
            "note": "Full 141-item run estimated ~470 min at ~40s/inference on local WSL2 host"
        }}

    # Merge into existing
    existing["models"][MODEL] = model_result

    with open(results_path, "w") as f:
        json.dump(existing, f, indent=2, sort_keys=True)
    print(f"\nWrote {results_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""E2 label pool and blind adjudication sheet (PREREGISTRATION.md section 5, E2). Seed 20261117.

batch1: the 15 triples the as-built gate fired on (from corpus_validation_fp.json fired_detail,
        hash-pinned) + a seeded random sample of 100 of the remaining 700 triples. Rows shuffled
        with the seed; item ids are opaque. The sheet shows the source crosswalk row and the OCSF
        1.8.0 attribute description and hides every arm output and the pool origin. The key
        (item id -> triple, origin, kappa-subset flag) goes to results/, not to the sheet.
batch2: after the arms run, every triple any arm flags that is not yet labelled, mixed with 10
        already-labelled triples as consistency decoys, shuffled, same sheet format.

Usage:
  python3 -I pool.py batch1 <sheet.csv> <key.csv>
  python3 -I pool.py batch2 <sheet.csv> <key.csv> <batch1_key.csv> <arm_outputs.jsonl>...
"""
import csv
import hashlib
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

FP_JSON = os.path.join(C.G, "repro", "d3fend-wall", "corpus_validation_fp.json")
FP_SHA = "91469aed356a4d0035c81fc3cbccfd3f15a9085ab86e849bdd44158318f5ec9e"
CROSSWALK = {"Splunk CIM": "cim", "Google UDM": "udm", "Microsoft ASIM": "asim", "Elastic ECS": "ecs",
             "OpenTelemetry": "otel", "Zeek": "zeek"}
N_RANDOM, N_KAPPA, N_DECOYS = 100, 20, 10

RUBRIC = [
    "# E2 BLIND ADJUDICATION SHEET (PREREGISTRATION.md section 5, rubric frozen at e7deceb). Arm outputs are hidden.",
    "# label: correct = the OCSF attribute is an accepted home for the source field's meaning, same entity, role and direction.",
    "#        defensible = a reviewer reading OCSF 1.8.0 would accept the home, though another is better.",
    "#        lossy = the right role, but the entity grain differs (an application landing on a host endpoint) or part of the value is dropped.",
    "#        wrong = a different attribute, entity, role or direction.",
    "# kind_crossing: yes | no | unclear. Does the source field denote a different kind of thing than the OCSF object it lands in?",
    "#        Judge by identity, not relation: process_path -> process.file.path is NOT a crossing (the field denotes the process's file).",
    "# source_kind_adjudicated (optional, for the section 10 secondary analysis): the OCSF 1.8.0 object the source field denotes, or blank.",
    "# A real error is lossy or wrong; a type-crossing real error is a real error with kind_crossing = yes; unclear rows are excluded from primary metrics.",
    "# Lines starting with # are this header; read the CSV with comment='#'.",
]
COLS = ["item_id", "schema", "source_field", "ocsf_class", "ocsf_path", "ocsf_attribute_description",
        "matrix_cell", "source_crosswalk_rows", "label", "kind_crossing", "source_kind_adjudicated", "notes"]


def item_id(tid, batch):
    return f"E2{batch}-" + hashlib.sha256(f"{C.SEED}|{batch}|{tid}".encode()).hexdigest()[:8]


def fired_tids():
    if C.sha256(FP_JSON) != FP_SHA:
        raise SystemExit("corpus_validation_fp.json hash mismatch")
    fp = json.load(open(FP_JSON))
    by_key = {(t["schema"], t["source"], t["ocsf"]): t["tid"] for t in C.triples()}
    tids = [by_key[(d["schema"], d["source"], d["ocsf"])] for d in fp["fired_detail"]]
    assert len(set(tids)) == len(fp["fired"]) == 15
    return tids


def describe(path, cls):
    w = C.walk(path, cls)
    if not w:
        return "(path not found in OCSF 1.8.0 " + cls + ")"
    parts = []
    for seg, a in w:
        desc = re.sub(r"<[^>]+>", "", a.get("description", "") or "").strip()
        t = a.get("object_type") or a.get("type")
        parts.append(f"{seg} [{t}]: {desc}")
    return " | ".join(parts)


def crosswalk_rows(schema, source):
    f = os.path.join(C.CROSSWALK_DIR, f"{CROSSWALK[schema]}-ocsf-crosswalk.md")
    hits = [l.strip() for l in open(f) if l.startswith("|") and f"`{source}`" in l.split("|")[1]]
    return " || ".join(hits) if hits else "(no row with this source field in the first column of the crosswalk)"


def sheet_rows(tids, batch):
    by_tid = {t["tid"]: t for t in C.triples()}
    rows = []
    for tid in tids:
        t = by_tid[tid]
        rows.append({"item_id": item_id(tid, batch), "schema": t["schema"], "source_field": t["source"],
                     "ocsf_class": ";".join(t["classes"]), "ocsf_path": t["ocsf"],
                     "ocsf_attribute_description": describe(t["ocsf"], t["cls"]), "matrix_cell": t["cell"],
                     "source_crosswalk_rows": crosswalk_rows(t["schema"], t["source"]),
                     "label": "", "kind_crossing": "", "source_kind_adjudicated": "", "notes": ""})
    return rows


def write_sheet(path, rows):
    with open(path, "w", newline="") as f:
        f.write("\n".join(RUBRIC) + "\n")
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


def write_key(path, recs):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item_id", "tid", "origin", "kappa_subset"])
        w.writeheader()
        w.writerows(recs)


def batch1(sheet, key, triples=None):
    triples = triples or C.triples()
    fired = fired_tids()
    rest = sorted(t["tid"] for t in triples if t["tid"] not in fired)
    assert len(rest) == len(triples) - 15
    r = random.Random(C.SEED)
    sample = r.sample(rest, N_RANDOM)
    pool = [(t, "fired") for t in fired] + [(t, "random") for t in sample]
    random.Random(C.SEED + 1).shuffle(pool)
    kappa = set(random.Random(C.SEED + 2).sample([t for t, _ in pool], N_KAPPA))
    write_sheet(sheet, sheet_rows([t for t, _ in pool], 1))
    write_key(key, [{"item_id": item_id(t, 1), "tid": t, "origin": o, "kappa_subset": t in kappa} for t, o in pool])
    return pool


def batch2(sheet, key, batch1_key, arm_output_paths):
    labelled = [r["tid"] for r in csv.DictReader(open(batch1_key))]
    flagged = set()
    by_item = {t["tid"]: t["tid"] for t in C.triples()}
    for p in arm_output_paths:
        for rec in C.read_jsonl(p):
            if rec["verdict"] == "flag" and rec["item_id"] in by_item:
                flagged.add(rec["item_id"])
    new = sorted(flagged - set(labelled))
    decoys = random.Random(C.SEED + 3).sample(sorted(labelled), N_DECOYS)
    pool = [(t, "flagged") for t in new] + [(t, "decoy") for t in decoys]
    random.Random(C.SEED + 4).shuffle(pool)
    write_sheet(sheet, sheet_rows([t for t, _ in pool], 2))
    write_key(key, [{"item_id": item_id(t, 2), "tid": t, "origin": o, "kappa_subset": False} for t, o in pool])
    return pool


def main(argv):
    C.verify_pins()
    if argv[1] == "batch1":
        pool = batch1(argv[2], argv[3])
    elif argv[1] == "batch2":
        pool = batch2(argv[2], argv[3], argv[4], argv[5:])
    else:
        raise SystemExit(__doc__)
    print(json.dumps({"n": len(pool), "sheet_sha256": C.sha256(argv[2]), "key_sha256": C.sha256(argv[3])}))


if __name__ == "__main__":
    main(sys.argv)

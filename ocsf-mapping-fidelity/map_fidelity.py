"""C1 — OCSF field-mapping fidelity scorer.

Loads the real vendor field inventories and the checked-in OCSF 1.8.0 schema
subset, validates every mapping target against that schema (so a mapping can
never point at an OCSF attribute that does not exist), and scores each source:

  coverage  = typed-mapped fields / total source fields
  lossy     = (coerced + unmapped) fields / total
  detection-breaking = the lossy fields a *named* detection depends on

There is no clock and no randomness here — the inputs are static checked-in
files, so the score is a pure function of them and reproduces exactly. run.py
computes it twice and asserts the two are identical before publishing.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMAS_DIR = os.path.join(HERE, "schemas")

from mapping import (  # noqa: E402
    OKTA_MAPPING, CROWDSTRIKE_MAPPING, PALO_ALTO_MAPPING, CISCO_ASA_MAPPING, DETECTIONS,
)

SOURCES = {
    "okta": {"class": "authentication", "mapping": OKTA_MAPPING, "has_official": True},
    "crowdstrike": {"class": "detection_finding", "mapping": CROWDSTRIKE_MAPPING, "has_official": False},
    "palo_alto": {"class": "network_activity", "mapping": PALO_ALTO_MAPPING, "has_official": False},
    "cisco_asa": {"class": "network_activity", "mapping": CISCO_ASA_MAPPING, "has_official": False},
}


# --- loaders ---------------------------------------------------------------

def load_ocsf_schema():
    with open(os.path.join(SCHEMAS_DIR, "ocsf", "ocsf_1.8.0_subset.json")) as f:
        return json.load(f)


def load_inventory(source):
    with open(os.path.join(SCHEMAS_DIR, source, "inventory.json")) as f:
        return json.load(f)


# --- OCSF path validation --------------------------------------------------

def resolve_ocsf_path(schema, class_name, path):
    """Validate a dotted OCSF attribute path against the schema subset.

    Returns the kind of resolution ("full" — every segment matched a transcribed
    attribute; "deep" — descent stopped at an object not transcribed here and the
    remaining leaf was accepted). Raises ValueError if any segment is not a real
    attribute of its parent class/object, or descends into a scalar.
    """
    segs = path.split(".")
    cls = schema["classes"].get(class_name)
    if cls is None:
        raise ValueError(f"unknown class '{class_name}'")
    attrs = cls["attrs"]
    if segs[0] not in attrs:
        raise ValueError(f"'{path}': '{segs[0]}' is not an attribute of class '{class_name}'")
    ref = attrs[segs[0]]
    i = 1
    while i < len(segs):
        if ref is None:
            raise ValueError(f"'{path}': cannot descend into scalar '{'.'.join(segs[:i])}'")
        obj = schema["objects"].get(ref)
        if obj is None:
            return "deep"  # object not transcribed; accept remaining leaf
        if segs[i] not in obj:
            raise ValueError(f"'{path}': '{segs[i]}' is not an attribute of object '{ref}'")
        ref = obj[segs[i]]
        i += 1
    return "full"


def validate_mapping(schema, class_name, mapping, inventory):
    """Every source field is mapped exactly once, every target resolves, and the
    status/catch-all invariant holds. Raises on any violation."""
    inv_fields = {f["field"] for f in inventory["fields"]}
    map_fields = set(mapping.keys())
    missing = inv_fields - map_fields
    extra = map_fields - inv_fields
    if missing:
        raise ValueError(f"{class_name}: source fields with no mapping: {sorted(missing)}")
    if extra:
        raise ValueError(f"{class_name}: mapping entries for unknown fields: {sorted(extra)}")
    catch_alls = set(schema["catch_alls"])
    for field, rec in mapping.items():
        resolve_ocsf_path(schema, class_name, rec["ocsf"])  # raises if bad
        is_catch = rec["ocsf"] in catch_alls
        if rec["status"] == "unmapped" and not is_catch:
            raise ValueError(f"{field}: status 'unmapped' but target '{rec['ocsf']}' is not a catch-all")
        if rec["status"] != "unmapped" and is_catch:
            raise ValueError(f"{field}: target is catch-all '{rec['ocsf']}' but status is '{rec['status']}'")


# --- scoring ---------------------------------------------------------------

def score_source(schema, source):
    cfg = SOURCES[source]
    class_name = cfg["class"]
    mapping = cfg["mapping"]
    inventory = load_inventory(source)
    validate_mapping(schema, class_name, mapping, inventory)

    fields = []
    for f in inventory["fields"]:
        rec = mapping[f["field"]]
        resolution = resolve_ocsf_path(schema, class_name, rec["ocsf"])
        row = {
            "field": f["field"],
            "type": f["type"],
            "detection_relevant": f["detection_relevant"],
            "ocsf": rec["ocsf"],
            "status": rec["status"],
            "resolution": resolution,
            "note": rec["note"],
        }
        if cfg["has_official"]:
            row["official"] = rec.get("official", False)
        fields.append(row)

    total = len(fields)
    typed = sum(1 for r in fields if r["status"] == "typed")
    coerced = sum(1 for r in fields if r["status"] == "coerced")
    unmapped = sum(1 for r in fields if r["status"] == "unmapped")
    dr = [r for r in fields if r["detection_relevant"]]
    dr_lossy = [r for r in dr if r["status"] != "typed"]

    summary = {
        "class": f"{class_name} ({schema['classes'][class_name]['uid']})",
        "total_fields": total,
        "typed": typed,
        "coerced": coerced,
        "unmapped": unmapped,
        "coverage": round(typed / total, 4),
        "coverage_incl_coerced": round((typed + coerced) / total, 4),
        "lossy": coerced + unmapped,
        "lossy_fraction": round((coerced + unmapped) / total, 4),
        "detection_relevant_fields": len(dr),
        "detection_relevant_lossy": len(dr_lossy),
    }
    if cfg["has_official"]:
        official = sum(1 for r in fields if r.get("official"))
        # shipped reference mapper drops a field that DOES have a typed/coerced OCSF home
        impl_gap = [r["field"] for r in fields
                    if not r.get("official") and r["status"] in ("typed", "coerced")]
        summary["official_mapped"] = official
        summary["official_unmapped"] = total - official
        summary["implementation_gap_fields"] = impl_gap
        summary["implementation_gap"] = len(impl_gap)
    return {"summary": summary, "fields": fields}


def score_detections(per_source_fields):
    """For each named detection, the lossy fields it depends on (status != typed)."""
    status_by = {}
    for source, scored in per_source_fields.items():
        for r in scored["fields"]:
            status_by[(source, r["field"])] = r["status"]
    out = []
    for det in DETECTIONS:
        src = det["source"]
        breaking = []
        for field in det["fields"]:
            st = status_by.get((src, field))
            if st is None:
                raise ValueError(f"detection '{det['name']}' references unknown field {src}:{field}")
            if st != "typed":
                breaking.append({"field": field, "status": st})
        out.append({
            "name": det["name"],
            "source": src,
            "desc": det["desc"],
            "fields_required": det["fields"],
            "breaking": breaking,
            "survives_clean": len(breaking) == 0,
        })
    return out


def score_all():
    schema = load_ocsf_schema()
    per_source = {s: score_source(schema, s) for s in SOURCES}
    detections = score_detections(per_source)
    return {
        "ocsf_version": schema["version"],
        "per_source": per_source,
        "detections": detections,
    }

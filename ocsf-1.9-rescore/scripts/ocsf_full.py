"""Strict OCSF path resolver over a schema.ocsf.io export (classes/objects with attributes).

Differences from ../../ocsf-mapping-fidelity/map_fidelity.py resolve_ocsf_path (as pre-registered):
  - no "deep" acceptance: descending into an object missing from the export, or naming an
    attribute an object lacks, is a failure;
  - every segment's attribute, the object it descends into and the class are checked for
    `@deprecated`, reported with `since` and message;
  - returns a result record instead of raising, so callers can collect every failure.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCHEMAS = os.path.join(ROOT, "schemas")
CATCH_ALLS = ("unmapped", "raw_data", "enrichments")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_export(version, profiles=True):
    p = os.path.join(SCHEMAS, version, "export-profiles.json" if profiles else "export-noprofile.json")
    with open(p) as f:
        d = json.load(f)
    assert d["version"] == version, (p, d.get("version"))
    return d, p


def _dep(node):
    d = node.get("@deprecated") if isinstance(node, dict) else None
    if not d:
        return None
    return {"since": d.get("since"), "message": d.get("message")}


def resolve(schema, class_name, path):
    """Resolve a dotted OCSF attribute path. Returns
    {"valid": bool, "error": str|None, "deprecations": [ {where, since, message} ], "leaf_type": str|None}.
    A trailing "[]" on a segment (array notation) is tolerated and stripped."""
    out = {"valid": False, "error": None, "deprecations": [], "leaf_type": None}
    cls = schema["classes"].get(class_name)
    if cls is None:
        out["error"] = f"unknown class '{class_name}'"
        return out
    cd = _dep(cls)
    if cd:
        out["deprecations"].append({"where": f"class-itself:{class_name}", **cd})
    attrs = cls.get("attributes", {})
    owner = f"class:{class_name}"
    segs = [s[:-2] if s.endswith("[]") else s for s in path.split(".")]
    for i, seg in enumerate(segs):
        a = attrs.get(seg)
        if a is None:
            out["error"] = f"'{seg}' is not an attribute of {owner}"
            return out
        ad = _dep(a)
        if ad:
            out["deprecations"].append({"where": f"{owner}.{seg}", **ad})
        is_last = i == len(segs) - 1
        if is_last:
            out["leaf_type"] = a.get("type")
            out["valid"] = True
            return out
        if a.get("type") != "object_t":
            out["error"] = f"cannot descend into non-object '{owner}.{seg}' (type {a.get('type')})"
            return out
        oname = a.get("object_type")
        obj = schema["objects"].get(oname)
        if obj is None:
            out["error"] = f"object '{oname}' (via {owner}.{seg}) not in export"
            return out
        od = _dep(obj)
        if od:
            out["deprecations"].append({"where": f"object:{oname}", **od})
        attrs = obj.get("attributes", {})
        owner = f"object:{oname}"
    return out

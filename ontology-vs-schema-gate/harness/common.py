#!/usr/bin/env python3
"""Shared harness code for the ontology-vs-schema gate bench (PREREGISTRATION.md, frozen at e7deceb).

Provides, for every arm, the injector and the scorer:
  * the frozen gate module, imported unchanged from the hash-checked copy under repro/;
  * the matrix parsed into the 925 cells and 715 distinct (schema, source, ocsf_path) triples,
    with the OCSF class section each triple first appears in (asserted equal to the gate's own
    parse_matrix(), cell for cell);
  * an OCSF 1.8.0 path walker (array markers stripped, catch-alls valid, as in
    ocsf-deterministic-mapper/frontier_behind_constraint_2026_11_16.py:in_full);
  * OCSF leaf data types and their families (HARNESS-ADDENDUM.md, "Type families");
  * the OCSF entity kind of a path (deepest object-typed segment) and its root under `extends`.
No D3FEND material and no gate table (SEG_RULES, SEG_ARTIFACT) is used by the OCSF-side functions.
"""
import hashlib
import importlib.util
import json
import os
import re
from functools import lru_cache

G = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")
GATE = os.path.join(G, "repro", "d3fend-wall", "ocsf_d3fend_corpus_validation.py")
MATRIX = os.path.join(G, "repro", "external-engagements", "ocsf-crosswalk-field-matrix.md")
JAR = os.path.join(G, "tools", "robot.jar")
OCSF_DIR = os.path.join(HOME, "sdw-lab-benchmarks/ocsf-deterministic-mapper/schema-ocsf-1.8.0-api-2026-11-16")
OCSF_DIR2 = os.path.join(HOME, "sdw-lab-benchmarks/ocsf-deterministic-mapper/schema-ocsf-1.8.0-api-classes-2026-11-17")
D3F_TTL = os.path.join(HOME, "d3fend-ontology/src/ontology/d3fend-protege.ttl")
CROSSWALK_DIR = os.path.join(HOME, "project1/02-projects/external-engagements")
SEED = 20261117

PINS = {
    GATE: "8de6557d6189f68f4b5b9a9a5b23dbf4e24604c2b3ae07a7bb9a21c6c08da443",
    MATRIX: "8317d3ad57f0e9357a98b300dee007b53057c89f6139120553469f4e8a5be7cc",
    JAR: "16a73c074f3df359a7338a84b4e0788785fe06117f931bb9796e9619ea776105",
    D3F_TTL: "4ddb80135ec4ee2ff397ad4b42b264f27b8e94d1c379514c53b5ae806a4c2038",
    os.path.join(OCSF_DIR2, "class_process_activity.json"): "c7dafa6d17de02119b60ce14df735a81ef1a4f2ed42c45cea61506f78e4d346b",
    os.path.join(OCSF_DIR2, "class_file_activity.json"): "e3b7e54b163022880baf4f591707df42060fe6517df62c579fa2b1943ed226ad",
    os.path.join(OCSF_DIR2, "class_account_change.json"): "0b23e3268e696fb78e6b5ea7ed0702fa299eacfe7b88f115c7ba1ab001d5b6f6",
    os.path.join(OCSF_DIR2, "data_types.json"): "9323ac82b3eb2de0920278fd7174ef33ff5b7af9ae43af7ee4d2ce2ce943d3bd",
}
OCSF_DIR_MANIFEST = "fafebc0db944e968aa470f5e6cbedfcf355e2ff71b0a37e90c49376902a277c0"

SECTION_CLASS = {
    "Authentication (3002)": "authentication",
    "Network Activity (4001)": "network_activity",
    "HTTP Activity (4002)": "http_activity",
    "Process Activity (1007)": "process_activity",
    "File System Activity (1001)": "file_activity",
    "Account Change (3001)": "account_change",
    "Detection Finding (2004)": "detection_finding",
}
CATCH_ALLS = {"unmapped", "raw_data", "observables", "enrichments"}  # as in the frontier re-score


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def dir_manifest(d):
    """`find . -type f | sort | xargs sha256sum | sha256sum`, the prereg's manifest method."""
    files = []
    for root, _, fs in os.walk(d):
        for f in fs:
            files.append("./" + os.path.relpath(os.path.join(root, f), d))
    lines = "".join(f"{sha256(os.path.join(d, f[2:]))}  {f}\n" for f in sorted(files, key=lambda s: s.encode()))
    return hashlib.sha256(lines.encode()).hexdigest()


def verify_pins():
    bad = [(p, sha256(p), h) for p, h in PINS.items() if sha256(p) != h]
    if dir_manifest(OCSF_DIR) != OCSF_DIR_MANIFEST:
        bad.append((OCSF_DIR, dir_manifest(OCSF_DIR), OCSF_DIR_MANIFEST))
    if bad:
        raise SystemExit("HASH MISMATCH: " + json.dumps(bad, indent=1))


@lru_cache(None)
def gate():
    """The frozen gate, imported unchanged. ROBOT points at the pinned jar in tools/."""
    if sha256(GATE) != PINS[GATE]:
        raise SystemExit("gate copy hash mismatch")
    spec = importlib.util.spec_from_file_location("gate_frozen", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROBOT = JAR
    return mod


# ---------------------------------------------------------------- matrix -> triples
def parse_cells():
    """The gate's parse_matrix() logic, plus the class section and the raw cell text.
    Asserted identical (schema, source, ocsf, lossy, order) to the gate's own parse."""
    rows, cols, section = [], None, None
    schemas = gate().SCHEMAS
    for line in open(MATRIX):
        h = re.match(r"^## (.+?)\s*$", line)
        if h:
            section = h.group(1)
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0].lower().startswith("ocsf attribute"):
            cols = cells
            continue
        if not cols or len(cells) < 7 or set("".join(cells)) <= set("- "):
            continue
        m = re.match(r"`([^`]+)`", cells[0])
        if not m:
            continue
        for i, schema in enumerate(schemas, start=1):
            cell = cells[i] if i < len(cells) else "—"
            for sf in re.findall(r"`([^`]+)`", cell):
                rows.append({"schema": schema, "source": sf, "ocsf": m.group(1), "lossy": "~" in cell,
                             "section": section, "cls": SECTION_CLASS.get(section), "cell": cell,
                             "row_label": cells[0]})
    ref = gate().parse_matrix()
    assert [(r["schema"], r["source"], r["ocsf"], r["lossy"]) for r in rows] == \
           [(r["schema"], r["source"], r["ocsf"], r["lossy"]) for r in ref], "parser drift vs gate"
    assert all(r["cls"] for r in rows), "row outside a mapped class section"
    return rows


@lru_cache(None)
def triples():
    """715 distinct (schema, source, ocsf) triples in first-seen order. `cls` = first class section
    the triple appears in; `classes` = every section it appears in (addendum decision D3)."""
    out = {}
    for r in parse_cells():
        k = (r["schema"], r["source"], r["ocsf"])
        if k not in out:
            out[k] = dict(r, classes=[r["cls"]], tid=None)
        elif r["cls"] not in out[k]["classes"]:
            out[k]["classes"].append(r["cls"])
    res = list(out.values())
    for t in res:
        t["tid"] = triple_id(t)
    return tuple(res)


def triple_id(t):
    return "T" + hashlib.sha256(f"{t['schema']}|{t['source']}|{t['ocsf']}".encode()).hexdigest()[:12]


@lru_cache(None)
def class_paths(cls):
    """The OCSF paths in a class's first column of the matrix (injector candidate pool)."""
    seen = []
    for r in parse_cells():
        if r["cls"] == cls and r["ocsf"] not in seen:
            seen.append(r["ocsf"])
    return tuple(seen)


# ---------------------------------------------------------------- OCSF 1.8.0
@lru_cache(None)
def ocsf_class(cls):
    for d in (OCSF_DIR, OCSF_DIR2):
        p = os.path.join(d, f"class_{cls}.json")
        if os.path.exists(p):
            return json.load(open(p))
    raise KeyError(cls)


@lru_cache(None)
def ocsf_object(name):
    p = os.path.join(OCSF_DIR, "objects", f"{name.replace('/', '__')}.json")
    return json.load(open(p)) if os.path.exists(p) else None


@lru_cache(None)
def all_objects():
    return tuple(sorted(f[:-5].replace("__", "/") for f in os.listdir(os.path.join(OCSF_DIR, "objects"))))


@lru_cache(None)
def data_types():
    return json.load(open(os.path.join(OCSF_DIR2, "data_types.json")))


def norm_path(path):
    return [re.sub(r"\[\d*\]$", "", s) for s in path.strip().strip(".").split(".")]


def expand_notation(path):
    """Matrix notation (addendum D4): a trailing `.*` means the object itself; a final brace set
    `a.{x,y}` expands to a.x and a.y. Returns the list of concrete paths."""
    p = re.sub(r"\.\*$", "", path.strip())
    m = re.match(r"^(.*)\.\{([^}]+)\}$", p)
    if m:
        return [f"{m.group(1)}.{x.strip()}" for x in m.group(2).split(",")]
    return [p]


def walk(path, cls):
    """List of (segment, attribute spec) along the path, or None if any segment is absent.
    Catch-all top-level names count as valid (returned with spec {"type": None}).
    A brace set is valid only if every member is; the first member's walk is returned, and its
    leaf type stands for the set only when every member has the same type (else type None)."""
    exp = expand_notation(path)
    if len(exp) > 1:
        ws = [walk(e, cls) for e in exp]
        if any(w is None for w in ws):
            return None
        types = {w[-1][1].get("type") for w in ws}
        w0 = list(ws[0])
        if len(types) > 1:
            w0[-1] = (w0[-1][0], {"type": None})
        return w0
    segs = norm_path(exp[0])
    if len(segs) == 1 and segs[0] in CATCH_ALLS and segs[0] not in ocsf_class(cls)["attributes"]:
        return [(segs[0], {"type": None})]
    attrs = ocsf_class(cls)["attributes"]
    out = []
    for i, s in enumerate(segs):
        if attrs is None or s not in attrs:
            return None
        a = attrs[s]
        out.append((s, a))
        if i < len(segs) - 1:
            ot = a.get("object_type")
            if not ot:
                return None
            o = ocsf_object(ot)
            attrs = o["attributes"] if o else None
    return out


def path_valid(path, cls):
    return walk(path, cls) is not None


def leaf_spec(path, cls):
    w = walk(path, cls)
    return w[-1][1] if w else None


def leaf_type(path, cls):
    s = leaf_spec(path, cls)
    return s.get("type") if s else None


# Type families (addendum D5). Base types from /api/data_types; prereg names ip, port, timestamp,
# string, integer, long, boolean, hash and MAC; float, json and object are added so every type
# has a family.
FAMILY_OF_TYPE = {
    "ip_t": "ip", "subnet_t": "ip", "port_t": "port", "timestamp_t": "timestamp", "datetime_t": "timestamp",
    "integer_t": "integer", "long_t": "long", "float_t": "float", "boolean_t": "boolean",
    "file_hash_t": "hash", "mac_t": "mac", "json_t": "json", "object_t": "object",
}


def type_family(t):
    if t is None:
        return None
    if t in FAMILY_OF_TYPE:
        return FAMILY_OF_TYPE[t]
    seen = set()
    while t and t not in seen:  # walk the data_types base chain
        seen.add(t)
        if t == "string_t":
            return "string"
        t = (data_types().get(t) or {}).get("type")
        if t in FAMILY_OF_TYPE:
            return FAMILY_OF_TYPE[t]
    return None


def leaf_family(path, cls):
    return type_family(leaf_type(path, cls))


# ---------------------------------------------------------------- OCSF kinds (S2 target side, strata)
def extends_chain(obj):
    """obj, its parent, ... up to the last real object (stops before `object`/`_entity`/missing)."""
    chain = []
    while obj and obj not in ("object", "_entity") and obj not in chain:
        o = ocsf_object(obj)
        if o is None:
            break
        chain.append(obj)
        obj = o.get("extends")
    return chain


def ocsf_kind(path, cls):
    """OCSF object type of the deepest object-typed segment of the path, or None."""
    w = walk(path, cls)
    if not w:
        return None
    kind = None
    for _, a in w:
        if a.get("object_type"):
            kind = a["object_type"]
    return kind


def root_kind(obj):
    ch = extends_chain(obj)
    return ch[-1] if ch else obj


def kinds_related(a, b):
    """Equal, or one is an ancestor of the other under `extends` (prereg S2 rule)."""
    return a == b or a in extends_chain(b) or b in extends_chain(a)


# ---------------------------------------------------------------- outcome records
def outcome(arm, item_id, verdict, **detail):
    assert verdict in ("flag", "pass", "abstain")
    return dict(arm=arm, item_id=item_id, verdict=verdict, **detail)


def write_jsonl(path, recs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in recs:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def read_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]

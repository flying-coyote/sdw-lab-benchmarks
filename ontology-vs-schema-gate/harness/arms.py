#!/usr/bin/env python3
"""Arms S1, S2, S3, O0, O1, O2 (PREREGISTRATION.md section 4).

Every arm takes a list of items {item_id, schema, source, ocsf, cls} and returns one outcome
per item: flag | pass | abstain (prereg section 6). An injected E1 item is processed exactly like
a real row (its replacement path is in `ocsf`), never handed over as a pre-chosen artifact pair.

  S1  path exists in the OCSF 1.8.0 class + source type family compatible with the leaf type
  S2  S1 + entity kind: OCSF root kind of the path vs the S2 source typer (harness/s2_source_typer.py,
      written by a separate author under the section 4 blindness rule; PENDING until it exists)
  S3  the frozen gate's ground_path()/source_type(), verdict source_art != target_art, no OWL
  O1  the frozen gate's axioms (PREFIX + AllDisjointClasses), one class per item, ELK via ROBOT
  O2  O1's axioms merged into d3fend-protege.ttl (commit 12e2762), ELK via ROBOT
  O0  d3fend-protege.ttl + PREFIX + per-item groundings, no added disjointness, ELK via ROBOT

Usage: python3 -I arms.py <arm> <items.jsonl> <out.jsonl> [--s1-table CSV]
"""
import csv
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

HARNESS = os.path.dirname(os.path.abspath(__file__))
S1_TABLE = os.path.join(HARNESS, "s1_source_type_table.csv")
S2_TYPER = os.path.join(HARNESS, "s2_source_typer.py")

# ------------------------------------------------------------------ S1
# Compatibility of a source family with an OCSF leaf family (addendum D6). Same family passes;
# integer, long and float interchange (numeric widening and unit scaling are transforms a pipeline
# applies); a port target takes port or any numeric, and a port source goes to port or any numeric.
# json targets take any typed source. object targets are judged only for object sources (pass); a
# scalar source on an object target is an abstention. A cast the matrix cell itself declares for this
# source token, `(enum)` or `(int)`, sets the source family to integer (the post-transform type);
# an injected item keeps its original row's cell, because the injector swaps only the OCSF path.
NUMERIC = {"integer", "long", "float"}
COMPAT = {(a, b) for a in NUMERIC for b in NUMERIC} | {(a, "port") for a in NUMERIC} | \
    {("port", b) for b in NUMERIC}
CAST_HINTS = ("(enum)", "(int)")


def declared_cast(field, cell):
    m = re.search(re.escape(f"`{field}`") + r"\s*(\([^)]*\))", cell or "")
    return bool(m and m.group(1) in CAST_HINTS)


def source_leaf(field):
    return field.strip().split(".")[-1]


def load_s1_table(path=S1_TABLE):
    t = {}
    for r in csv.DictReader(open(path)):
        t[(r["schema"], r["leaf_token"])] = (r["family"] or "").strip() or None
    return t


def s1_source_family(schema, field, table, cell=None):
    if field.strip().endswith("*"):
        return "object"  # wildcard source = the whole sub-record (matrix notation)
    if declared_cast(field, cell):
        return "integer"
    fam = table.get((schema, source_leaf(field)))
    return None if fam in (None, "ambiguous") else fam


def s1_judge(item, table):
    """Returns (verdict, detail)."""
    if not C.path_valid(item["ocsf"], item["cls"]):
        return "flag", {"reason": "invalid_path"}
    tf = C.leaf_family(item["ocsf"], item["cls"])
    sf = s1_source_family(item["schema"], item["source"], table, item.get("cell"))
    d = {"src_family": sf, "tgt_family": tf}
    if sf is None or tf is None:
        return "abstain", d
    if tf == "object":
        return ("pass" if sf == "object" else "abstain"), d
    if tf == "json":
        return "pass", d
    ok = sf == tf or (sf, tf) in COMPAT
    return ("pass" if ok else "flag"), dict(d, reason=None if ok else "type_family")


def run_s1(items, table=None):
    table = table if table is not None else load_s1_table()
    out = []
    for it in items:
        v, d = s1_judge(it, table)
        out.append(C.outcome("S1", it["item_id"], v, **d))
    return out


# ------------------------------------------------------------------ S2
def s2_target_kind(ocsf, cls):
    k = C.ocsf_kind(ocsf, cls)
    return C.root_kind(k) if k else None


def load_s2_typer(path=S2_TYPER):
    """The S2 source typer: a module exposing source_kind(schema, field) -> OCSF object name | None.
    Written by a separate author from source-schema docs and the OCSF 1.8.0 object list only."""
    if not os.path.exists(path):
        raise SystemExit("S2 PENDING: harness/s2_source_typer.py not written yet (prereg section 4 "
                         "blindness rule: a separate author writes it)")
    spec = importlib.util.spec_from_file_location("s2_source_typer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_s2(items, table=None, typer=None):
    """S2 = S1 plus the kind check (addendum D7): flag if S1 flags or the kinds differ; abstain if
    S1 did not flag and the kind check cannot type a side; pass otherwise."""
    table = table if table is not None else load_s1_table()
    typer = typer or load_s2_typer()
    out = []
    for it in items:
        v1, d1 = s1_judge(it, table)
        tk = s2_target_kind(it["ocsf"], it["cls"]) if v1 != "flag" or C.path_valid(it["ocsf"], it["cls"]) else None
        sk_raw = typer.source_kind(it["schema"], it["source"])
        if sk_raw is not None and C.ocsf_object(sk_raw) is None:
            raise SystemExit(f"S2 typer returned a non-OCSF object name: {sk_raw!r}")
        sk = C.root_kind(sk_raw) if sk_raw else None
        d = dict(s1=v1, s1_detail=d1, src_kind=sk_raw, src_root=sk, tgt_root=tk)
        if v1 == "flag":
            v = "flag"
        elif sk is None or tk is None:
            v = "abstain"
        elif C.kinds_related(sk_raw, tk):
            v = "pass"
        else:
            v = "flag"
        out.append(C.outcome("S2", it["item_id"], v, **d))
    return out


# ------------------------------------------------------------------ S3
def groundings(it):
    g = C.gate()
    tart = g.ground_path(it["ocsf"])
    sart, conf = g.source_type(it["source"])
    return tart, (sart if conf else None)


def run_s3(items):
    out = []
    for it in items:
        tart, sart = groundings(it)
        if tart is None or sart is None:
            v = "abstain"
        else:
            v = "flag" if sart != tart else "pass"
        out.append(C.outcome("S3", it["item_id"], v, src_art=sart, tgt_art=tart))
    return out


# ------------------------------------------------------------------ O arms (ELK via ROBOT)
def cls_name(item_id):
    return "X_" + re.sub(r"[^A-Za-z0-9]", "_", item_id)


def robot_reason(stub_ttl, with_d3fend):
    """ELK via the pinned ROBOT jar. Returns the set of unsatisfiable align# class names.
    The exit code is checked: 0 with nothing unsatisfiable, or 1 with ROBOT's own
    'unsatisfiable' report; anything else raises (a JVM crash never reads as a clean pass)."""
    with tempfile.TemporaryDirectory() as td:
        stub, dump, out = (os.path.join(td, x) for x in ("stub.ttl", "u.owl", "o.owl"))
        open(stub, "w").write(stub_ttl)
        cmd = ["java", "-jar", C.JAR]
        if with_d3fend:
            cmd += ["merge", "--input", C.D3F_TTL, "--input", stub, "reason"]
        else:
            cmd += ["reason", "--input", stub]
        cmd += ["--reasoner", "ELK", "--dump-unsatisfiable", dump, "--output", out]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        log = re.sub(r"(?m)^WARNING.*\n?", "", (p.stdout or "") + (p.stderr or ""))
        dumped = open(dump).read() if os.path.exists(dump) else ""
        # ROBOT's log lists exactly the unsatisfiable classes; the dump also carries the classes
        # they reference (superclasses), so the log is authoritative. The gate's own method (align#
        # IRIs in the dump) is computed beside it and must agree (addendum D13).
        unsat_all = set(re.findall(r"unsatisfiable: (\S+)", log))
        unsat = {u.split("#", 1)[1] for u in unsat_all if u.startswith(C.gate().OCSF)}
        unsat_dump = set(re.findall(r"align#([A-Za-z0-9_]+)", dumped))
        if unsat != unsat_dump:
            raise RuntimeError(f"log/dump disagreement: {sorted(unsat ^ unsat_dump)[:10]}")
        ok = (p.returncode == 0 and not unsat_all) or (p.returncode == 1 and unsat_all)
        if not ok:
            raise RuntimeError(f"ROBOT failed rc={p.returncode}: {log[-2000:]}")
        return unsat, {"rc": p.returncode, "n_unsat_total": len(unsat_all),
                       "n_unsat_nonalign": len(unsat_all) - len(unsat)}


def run_o(arm, items):
    g = C.gate()
    ttl = g.PREFIX + ("" if arm == "O0" else g.disjoint_ttl())
    typed = {}
    for it in items:
        tart, sart = groundings(it)
        if tart is None or sart is None:
            continue
        c = cls_name(it["item_id"])
        typed[it["item_id"]] = (c, sart, tart)
        ttl += f"ocsf:{c} a owl:Class ; rdfs:subClassOf d3f:{tart} ; rdfs:subClassOf d3f:{sart} .\n"
    unsat, meta = robot_reason(ttl, with_d3fend=(arm in ("O0", "O2")))
    out = []
    for it in items:
        if it["item_id"] not in typed:
            out.append(C.outcome(arm, it["item_id"], "abstain"))
            continue
        c, sart, tart = typed[it["item_id"]]
        out.append(C.outcome(arm, it["item_id"], "flag" if c in unsat else "pass", src_art=sart, tgt_art=tart))
    return out, meta


def run_arm(arm, items, s1_table=None, s2_typer=None):
    if arm == "S1":
        return run_s1(items, s1_table), {}
    if arm == "S2":
        return run_s2(items, s1_table, s2_typer), {}
    if arm == "S3":
        return run_s3(items), {}
    if arm in ("O0", "O1", "O2"):
        return run_o(arm, items)
    raise SystemExit(f"unknown arm {arm}")


def main(argv):
    arm, items_path, out_path = argv[1:4]
    table = load_s1_table(argv[argv.index("--s1-table") + 1]) if "--s1-table" in argv else None
    C.verify_pins()
    items = C.read_jsonl(items_path)
    recs, meta = run_arm(arm, items, table)
    C.write_jsonl(out_path, recs)
    print(json.dumps({"arm": arm, "n": len(recs), "meta": meta,
                      "counts": {v: sum(r["verdict"] == v for r in recs) for v in ("flag", "pass", "abstain")}}))


if __name__ == "__main__":
    main(sys.argv)

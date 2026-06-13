"""Task #10 — pipeline-normalization-fidelity scorer.

Takes a pipeline tool's emitted OCSF output (Tenzir / Cribl / Vector) and scores
it against the gold key `gen_corpus.py` produced, at the README's three fidelity
levels, reusing C1's typed/coerced/unmapped tiering and C1's OCSF path validator.

This file scores; it does NOT run a pipeline tool. The tool runs externally
(its shipped/published OCSF mapping over `_work/<source>.corpus.jsonl`) and
writes its emitted OCSF events to a JSONL file; `score.py --tool tenzir
--source zeek_conn --emitted <file>` reads that file. Nothing here imports or
launches a tool, starts an engine, or touches the network.

THE THREE FIDELITY LEVELS (README scoring 1/2/3)
------------------------------------------------
1. Field fidelity — of the gold's TYPED+COERCED source fields (the ones with a
   real OCSF home), the fraction the tool actually lands on a populated OCSF
   attribute. A gold-typed field the tool drops or dumps into unmapped/raw_data
   is the field-fidelity loss. Scored with the C1 tiering and C1's
   `resolve_ocsf_path` against the MERGED 1.8.0 subset (C1 five classes + this
   bench's two extension classes), so a tool emitting an OCSF path that does not
   exist in the real schema is caught, not silently credited.

2. Value fidelity — of the fields the tool DID land, the fraction whose emitted
   value equals the gold canonical value (after the gold's own faithful
   coercion). Catches type coercion, truncation, enum mistranslation, and the
   timestamp zone/precision loss the field level misses (README level 2).

3. Semantic fidelity — correct class assignment, correct activity_id / type_uid,
   and the five recurring crosswalk failure-class probes the gold key planted
   (entity-role inversion, multi-event collapse, severity remap, observables
   flattening, context-collapse).

Coverage != fidelity (README stop rule): a tool is scored only where it emits
output. A source the tool refuses / crashes on is recorded as 0% coverage for
that source (pass `--emitted /dev/null` or omit the file), not excluded.

Determinism: the gold key and the tool's emitted file are both static inputs, so
the score is a pure function of them. `--self-check` scores the gold against
ITSELF (a perfect mapper) and asserts 100% at all three levels — the harness's
own correctness gate, with no tool involved.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, os.path.join(HERE, "..", "ocsf-mapping-fidelity"))

from common import canonical  # noqa: E402
# Reuse the C1 OCSF path validator verbatim — same resolution semantics
# ("full" / "deep") the C1 PROVENANCE describes, so this bench validates gold
# targets exactly as C1 validates its mappings.
from map_fidelity import resolve_ocsf_path  # noqa: E402

WORK = os.path.join(HERE, "_work")
C1_SUBSET = os.path.join(HERE, "..", "ocsf-mapping-fidelity", "schemas", "ocsf",
                         "ocsf_1.8.0_subset.json")
EXT_SUBSET = os.path.join(HERE, "schemas", "ocsf", "ocsf_1.8.0_ext_subset.json")

SHIPPED_TOOLS = ("tenzir", "cribl", "vector")

# The four sources the gold key covers; kept in sync with gen_corpus.SUB_SEEDS.
# Defined here (module top) so the argparse `choices` reference in main() resolves.
_GEN_SOURCES = ("zeek_conn", "cloudtrail", "sysmon", "auth")


# --- merged OCSF 1.8.0 schema (C1 five classes + this bench's two) ----------

def load_merged_schema():
    """Merge the ext subset ON TOP OF the C1 subset (PROVENANCE: 'merges at load
    time', nothing in C1 is edited). The result has the C1 shape
    (classes{}, objects{}, catch_alls[]) so C1's resolve_ocsf_path works unchanged
    and every reused object reference (process, actor, device, ...) resolves
    through C1; `api` and the two new classes come from the ext file."""
    with open(C1_SUBSET) as f:
        schema = json.load(f)
    with open(EXT_SUBSET) as f:
        ext = json.load(f)
    schema["classes"].update(ext.get("classes", {}))
    schema["objects"].update(ext.get("objects", {}))
    # catch_alls are identical in both; union to be safe.
    schema["catch_alls"] = sorted(set(schema.get("catch_alls", [])) |
                                  set(ext.get("catch_alls", [])))
    return schema


# --- emitted-output access -------------------------------------------------

def get_path(obj, dotted):
    """Read a dotted attribute out of an emitted OCSF event (nested dicts).
    Returns (present, value). Absent path -> (False, None); an explicit null is
    (True, None) — the absence-vs-null distinction the README scoring needs."""
    cur = obj
    for seg in dotted.split("."):
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return False, None
    return True, cur


def _is_catch_all(schema, path):
    head = path.split(".")[0]
    return head in set(schema["catch_alls"])


# --- gold-key loading + validation -----------------------------------------

def load_gold(source):
    """Load `_work/<source>.gold.jsonl` (one gold record per corpus row)."""
    path = os.path.join(WORK, f"{source}.gold.jsonl")
    if not os.path.exists(path):
        raise SystemExit(f"gold key not found: {path}  (run `python gen_corpus.py` first)")
    gold = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                gold.append(json.loads(line))
    return gold


def validate_gold_targets(schema, gold_record):
    """Every non-catch-all gold OCSF path must resolve against the merged 1.8.0
    subset — the gold key cannot point at an attribute the real schema lacks.
    Raises (loudly, the C1 discipline) on the first bad path."""
    cls = gold_record["class"]
    for field, rec in gold_record["fields"].items():
        ocsf = rec["ocsf"]
        if _is_catch_all(schema, ocsf):
            continue
        resolve_ocsf_path(schema, cls, ocsf)  # raises ValueError if the path is invalid


def load_emitted(path):
    """Load a tool's emitted OCSF events (JSONL, one event per corpus row, joined
    by `_id`). A missing/empty file means the tool produced nothing for this
    source -> 0% coverage, not an error (README: crash == 0% coverage)."""
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        return {}
    out = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            key = ev.get("_id")
            if key is None:
                raise SystemExit("emitted event missing `_id` join key; the tool's "
                                 "output must carry the corpus record id as `_id`")
            out[key] = ev
    return out


# --- scoring ---------------------------------------------------------------

def _eq(a, b):
    """Value equality with the small tolerances a faithful round-trip allows:
    numeric int/float that are equal compare equal; everything else is canonical
    JSON equality so nested values compare structurally."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return canonical(a) == canonical(b)


def score_record(schema, gold_rec, emitted):
    """Score one corpus row's gold against the tool's emitted OCSF event.

    Field: per gold field with a real OCSF home (typed/coerced), did the tool
           land a populated value on that attribute?
    Value: of the landed fields, does the emitted value equal the gold value?
    Semantic: class, activity_id, type_uid, and each planted failure-class probe.
    """
    fields = gold_rec["fields"]
    homed = {f: r for f, r in fields.items() if r["status"] in ("typed", "coerced")}

    field_total = len(homed)
    field_landed = 0
    value_eligible = 0
    value_ok = 0
    field_misses = []
    value_misses = []

    have_emitted = emitted is not None and len(emitted) > 0
    for f, rec in homed.items():
        ocsf = rec["ocsf"]
        present, val = get_path(emitted, ocsf) if have_emitted else (False, None)
        # "landed" = present, non-null, and NOT shoved into a catch-all
        landed = present and val is not None and not _is_catch_all(schema, ocsf)
        if landed:
            field_landed += 1
            value_eligible += 1
            if _eq(val, rec["value"]):
                value_ok += 1
            else:
                value_misses.append({"field": f, "ocsf": ocsf,
                                     "gold": rec["value"], "emitted": val,
                                     "tier": rec["status"]})
        else:
            field_misses.append({"field": f, "ocsf": ocsf, "tier": rec["status"]})

    # --- semantic ---
    sem = {}
    if have_emitted:
        _, cls_uid = get_path(emitted, "class_uid")
        _, act = get_path(emitted, "activity_id")
        _, tuid = get_path(emitted, "type_uid")
        sem["class_uid_ok"] = (cls_uid == gold_rec["class_uid"])
        sem["activity_id_ok"] = (act == gold_rec["activity_id"])
        sem["type_uid_ok"] = (tuid == gold_rec["type_uid"])
        sem["failure_classes"] = _score_failure_classes(schema, gold_rec, emitted)
    else:
        sem["class_uid_ok"] = False
        sem["activity_id_ok"] = False
        sem["type_uid_ok"] = False
        sem["failure_classes"] = {name: {"reproduced": True, "reason": "no output (0% coverage)"}
                                  for name in gold_rec.get("semantic", {})}

    return {
        "field": {"total": field_total, "landed": field_landed,
                  "misses": field_misses},
        "value": {"eligible": value_eligible, "ok": value_ok,
                  "misses": value_misses},
        "semantic": sem,
    }


def _score_failure_classes(schema, gold_rec, emitted):
    """Re-check each planted failure-class probe against the emitted OCSF.

    A probe carries either `expect_paths` (these OCSF paths must be present and
    non-null in the output) and/or `expect` (a small fact that must hold). A probe
    is `reproduced` (the failure-class shows up in this tool) when the expectation
    does NOT hold — i.e. the tool lost what the gold preserved."""
    out = {}
    for name, probe in gold_rec.get("semantic", {}).items():
        ok = True
        reason = ""
        for p in probe.get("expect_paths", []):
            present, val = get_path(emitted, p)
            if not (present and val is not None and not _is_catch_all(schema, p)):
                ok = False
                reason = f"expected OCSF path `{p}` absent/null/catch-all"
                break
        if ok and "expect" in probe:
            for path, want in probe["expect"].items():
                if path in ("is_error", "is_failure"):
                    # severity-remap probes: a true error/failure must lift severity
                    # above Informational (severity_id 1). Reproduced if it didn't.
                    if want:
                        present, sev = get_path(emitted, "severity_id")
                        if not present or sev in (None, 1):
                            ok = False
                            reason = "error/failure event left at Informational severity"
                            break
                else:
                    present, val = get_path(emitted, path)
                    if not present or not _eq(val, want):
                        ok = False
                        reason = f"expected `{path}` == {want!r}, got {val!r}"
                        break
        out[name] = {"reproduced": (not ok), "reason": reason,
                     "note": probe.get("note", "")}
    return out


def score_source(schema, source, emitted_map):
    """Aggregate the per-record scores into the three fidelity headlines."""
    gold = load_gold(source)
    if gold:
        validate_gold_targets(schema, gold[0])  # gold is schema-uniform per source

    ft = fl = ve = vo = 0
    cls_ok = act_ok = tuid_ok = 0
    fc_repro = {}        # failure-class name -> records where it reproduced
    fc_total = {}
    field_miss_tally = {}
    value_miss_tally = {}

    for g in gold:
        ev = emitted_map.get(g["_id"], {})
        r = score_record(schema, g, ev if ev else None)
        ft += r["field"]["total"]
        fl += r["field"]["landed"]
        ve += r["value"]["eligible"]
        vo += r["value"]["ok"]
        cls_ok += int(r["semantic"]["class_uid_ok"])
        act_ok += int(r["semantic"]["activity_id_ok"])
        tuid_ok += int(r["semantic"]["type_uid_ok"])
        for m in r["field"]["misses"]:
            field_miss_tally[m["field"]] = field_miss_tally.get(m["field"], 0) + 1
        for m in r["value"]["misses"]:
            value_miss_tally[m["field"]] = value_miss_tally.get(m["field"], 0) + 1
        for name, fc in r["semantic"]["failure_classes"].items():
            fc_total[name] = fc_total.get(name, 0) + 1
            if fc["reproduced"]:
                fc_repro[name] = fc_repro.get(name, 0) + 1

    n = len(gold)
    covered = sum(1 for g in gold if g["_id"] in emitted_map)
    return {
        "source": source,
        "ocsf_class": gold[0]["class"] if gold else None,
        "class_uid": gold[0]["class_uid"] if gold else None,
        "records": n,
        "coverage": round(covered / n, 4) if n else 0.0,
        "field_fidelity": {
            "homed_field_instances": ft, "landed": fl,
            "score": round(fl / ft, 4) if ft else 0.0,
            "top_dropped": _top(field_miss_tally),
        },
        "value_fidelity": {
            "landed_field_instances": ve, "value_preserved": vo,
            "score": round(vo / ve, 4) if ve else 0.0,
            "top_mangled": _top(value_miss_tally),
        },
        "semantic_fidelity": {
            "class_assignment": round(cls_ok / n, 4) if n else 0.0,
            "activity_id": round(act_ok / n, 4) if n else 0.0,
            "type_uid": round(tuid_ok / n, 4) if n else 0.0,
            "failure_classes": {
                name: {"reproduced_fraction": round(fc_repro.get(name, 0) / fc_total[name], 4),
                       "reproduced_records": fc_repro.get(name, 0),
                       "total_records": fc_total[name]}
                for name in fc_total
            },
        },
    }


def _top(tally, k=8):
    return [{"field": f, "count": c}
            for f, c in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]


# --- self-check: gold scored against itself must be perfect -----------------

def _build_reference_emitted(schema, gold):
    """Materialise the gold key AS an OCSF event per record (the hand-verified
    reference mapping the README names): write each typed/coerced gold field's
    canonical value to its OCSF path, plus class_uid/activity_id/type_uid. Scoring
    this against the gold must be 100%/100%/100% — the harness self-test."""
    emitted = {}
    for g in gold:
        ev = {"_id": g["_id"], "class_uid": g["class_uid"],
              "activity_id": g["activity_id"], "type_uid": g["type_uid"]}
        for f, rec in g["fields"].items():
            if rec["status"] not in ("typed", "coerced"):
                continue
            if _is_catch_all(schema, rec["ocsf"]):
                continue
            _set_path(ev, rec["ocsf"], rec["value"])
        emitted[g["_id"]] = ev
    return emitted


def _set_path(obj, dotted, value):
    cur = obj
    segs = dotted.split(".")
    for seg in segs[:-1]:
        cur = cur.setdefault(seg, {})
        if not isinstance(cur, dict):
            return  # a scalar already sits here; leave it (self-check is a sanity gate)
    cur[segs[-1]] = value


def self_check(schema, sources):
    ok = True
    for source in sources:
        gold = load_gold(source)
        if gold:
            validate_gold_targets(schema, gold[0])
        ref = _build_reference_emitted(schema, gold)
        res = score_source(schema, source, ref)
        ff = res["field_fidelity"]["score"]
        vf = res["value_fidelity"]["score"]
        sc = res["semantic_fidelity"]["class_assignment"]
        # The reference mapper preserves everything the gold preserves at typed/coerced.
        perfect = (ff == 1.0 and vf == 1.0 and sc == 1.0)
        ok = ok and perfect
        print(f"  {source:11s} field={ff:.2f} value={vf:.2f} class={sc:.2f}  "
              f"{'OK' if perfect else 'FAIL'}")
    print(f"self-check (gold vs reference mapper): {'OK' if ok else 'FAIL'}")
    return ok


# --- result writing --------------------------------------------------------

def write_results(results, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "results.json"), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    _write_markdown(results, out_dir)


def _write_markdown(results, out_dir):
    lines = []
    a = lines.append
    a("# Results — pipeline normalization-fidelity (task #10)\n")
    a(f"- OCSF version: **{results['ocsf_version']}**  ·  evidence tier: "
      "B (reproducible; first-party reference mapping vs a tool's shipped mapping, "
      "seeded synthetic corpus — not production telemetry)")
    a(f"- Tool: **{results['tool']}**  ·  mapping artifact: `{results['mapping_artifact']}`")
    a("- Field fidelity = of the gold's typed+coerced source fields, the fraction the "
      "tool lands on a populated OCSF attribute. Value fidelity = of those, the fraction "
      "whose value survives. Semantic = class/activity/type_uid + the five failure classes.")
    a("- Every gold OCSF target is validated against the merged C1+ext 1.8.0 subset; an "
      "invented attribute fails the run. Coverage != fidelity: a source the tool produced "
      "no output for scores 0%.\n")

    a("## Three-level fidelity per source\n")
    a("| source | OCSF class | records | coverage | field | value | class | activity_id |")
    a("|---|---|--:|--:|--:|--:|--:|--:|")
    for s in results["per_source"]:
        a(f"| {s['source']} | {s['ocsf_class']} ({s['class_uid']}) | {s['records']} | "
          f"{s['coverage']:.0%} | {s['field_fidelity']['score']:.0%} | "
          f"{s['value_fidelity']['score']:.0%} | "
          f"{s['semantic_fidelity']['class_assignment']:.0%} | "
          f"{s['semantic_fidelity']['activity_id']:.0%} |")
    a("")

    a("## Failure classes reproduced (README level 3)\n")
    a("Fraction of records where each recurring crosswalk failure class shows up in "
      "this tool's shipped mapping (P4: the seams are OCSF's own if every tool reproduces them).\n")
    fc_names = sorted({n for s in results["per_source"]
                       for n in s["semantic_fidelity"]["failure_classes"]})
    a("| source | " + " | ".join(fc_names) + " |")
    a("|---|" + "|".join("--:" for _ in fc_names) + "|")
    for s in results["per_source"]:
        cells = []
        for n in fc_names:
            fc = s["semantic_fidelity"]["failure_classes"].get(n)
            cells.append(f"{fc['reproduced_fraction']:.0%}" if fc else "—")
        a(f"| {s['source']} | " + " | ".join(cells) + " |")
    a("")

    a("## Where the fidelity went (auditable)\n")
    for s in results["per_source"]:
        a(f"### {s['source']}\n")
        td = s["field_fidelity"]["top_dropped"]
        tm = s["value_fidelity"]["top_mangled"]
        a("- field-fidelity losses (gold-typed/coerced fields the tool dropped): "
          + (", ".join(f"`{d['field']}`×{d['count']}" for d in td) if td else "none") + "")
        a("- value-fidelity losses (landed but value mangled): "
          + (", ".join(f"`{d['field']}`×{d['count']}" for d in tm) if tm else "none") + "\n")

    with open(os.path.join(out_dir, "RESULTS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


# --- CLI -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Score a pipeline tool's emitted OCSF output against the gold key "
                    "(field/value/semantic). Scoring only; no tool is run here.")
    ap.add_argument("--tool", default="reference",
                    help="tool name for the result label (tenzir/cribl/vector), or "
                         "'reference' for the self-check")
    ap.add_argument("--mapping-artifact", default="(unspecified)",
                    help="the exact shipped/published mapping artifact + version the tool used "
                         "(pinned into the result, e.g. 'tenzir 4.x ocsf operators' / "
                         "'cribl OCSF pack vN' / 'vector VRL example commit <sha>')")
    ap.add_argument("--source", action="append", dest="sources", choices=list(_GEN_SOURCES),
                    help="source to score; repeatable. Default: all four.")
    ap.add_argument("--emitted", action="append", default=[], metavar="SOURCE=PATH",
                    help="map a source to the tool's emitted OCSF JSONL, e.g. "
                         "--emitted zeek_conn=/path/out.jsonl . A source with no --emitted "
                         "(or an empty file) scores 0% coverage.")
    ap.add_argument("--results-dir", default=os.path.join(HERE, "results"),
                    help="where to write results.json + RESULTS.md")
    ap.add_argument("--self-check", action="store_true",
                    help="score the gold against a reference mapper built FROM the gold; "
                         "asserts 100%/100%/100% (harness correctness gate, no tool). Writes nothing.")
    ap.add_argument("--no-write", action="store_true",
                    help="score + print but do not write results files")
    args = ap.parse_args()

    schema = load_merged_schema()
    sources = args.sources or list(_GEN_SOURCES)

    if args.self_check:
        ok = self_check(schema, sources)
        raise SystemExit(0 if ok else 1)

    emitted_paths = {}
    for spec in args.emitted:
        if "=" not in spec:
            raise SystemExit(f"--emitted expects SOURCE=PATH, got {spec!r}")
        src, path = spec.split("=", 1)
        if src not in _GEN_SOURCES:
            raise SystemExit(f"unknown source in --emitted: {src!r}")
        emitted_paths[src] = path

    per_source = []
    for source in sources:
        emitted_map = load_emitted(emitted_paths.get(source))
        per_source.append(score_source(schema, source, emitted_map))

    results = {
        "benchmark": "pipeline-normalization-fidelity (task #10)",
        "ocsf_version": schema["version"],
        "tool": args.tool,
        "mapping_artifact": args.mapping_artifact,
        "per_source": per_source,
    }

    for s in per_source:
        print(f"  {s['source']:11s} {str(s['ocsf_class']):18s} cov={s['coverage']:.0%}  "
              f"field={s['field_fidelity']['score']:.0%} "
              f"value={s['value_fidelity']['score']:.0%} "
              f"class={s['semantic_fidelity']['class_assignment']:.0%} "
              f"act={s['semantic_fidelity']['activity_id']:.0%}")

    if not args.no_write:
        write_results(results, args.results_dir)
        print(f"wrote {os.path.join(args.results_dir, 'results.json')}")
        print(f"wrote {os.path.join(args.results_dir, 'RESULTS.md')}")


if __name__ == "__main__":
    main()

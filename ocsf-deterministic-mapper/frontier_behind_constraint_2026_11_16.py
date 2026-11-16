#!/usr/bin/env python3
"""POST-HOC RE-SCORE (2026-11-16): the frontier model behind the schema constraint.

No model is called. This re-scores the CACHED June 2026 frontier-proxy predictions (claude-opus-4-8 via
Claude Code subagents; three blind runs, see ../ocsf-mapping-oracle/_frontier/REPLICATION-2026-06-14.md)
through the same reject / snap wall llm_behind_constraint.py put phi3 behind. It also:

  * re-validates every frontier path against the FULL OCSF 1.8.0 schema (fetched 2026-11-16 by
    fetch_ocsf_1_8_0_full_2026_11_16.py), splitting the subset scorer's "silent error" into truly
    invented paths vs real 1.8.0 paths that sit outside the transcribed subset;
  * checks the phi3-behind-the-wall correct set against the alias mapper's correct set;
  * exports the alias mapper's valid-but-non-gold mappings to CSV for a (separate, Tier D) adjudication.

Headline condition fixed BEFORE looking: `schema` (the condition the phi3 arm used). All 705 prompts are
reported too. Nothing tracked is rewritten; outputs go to results/*-2026-11-16.*.
"""
import csv
import difflib
import importlib.util
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ORACLE = os.path.join(HERE, "..", "ocsf-mapping-oracle")
FULL = os.path.join(HERE, "schema-ocsf-1.8.0-api-2026-11-16")
OUT_JSON = os.path.join(HERE, "results", "results-frontier-constrained-2026-11-16.json")
OUT_CSV = os.path.join(HERE, "results", "alias-wrong-but-valid-2026-11-16.csv")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


oracle = load("oracle_run", os.path.join(ORACLE, "run.py"))
import sys  # noqa: E402
sys.modules["run"] = oracle            # det run.py does `import run as bench_b`
det = load("det_run", os.path.join(HERE, "run.py"))

# ---------- full OCSF 1.8.0 path walker ----------
_objs = {}


def obj_attrs(name):
    if name not in _objs:
        p = os.path.join(FULL, "objects", f"{name}.json")
        _objs[name] = json.load(open(p))["attributes"] if os.path.exists(p) else None
    return _objs[name]


_cls = {c: json.load(open(os.path.join(FULL, f"class_{c}.json")))["attributes"]
        for c in ["authentication", "detection_finding", "network_activity", "dns_activity", "http_activity"]}


def in_full(path, cls):
    """Walk the dotted path through the profile-inclusive 1.8.0 class/object attribute sets.
    Array markers ([] / [0]) are stripped. Catch-alls count as valid, as in the subset scorer."""
    p = oracle.normalize(path, cls)
    if not p:
        return False
    if p in oracle.CATCH_ALLS:
        return True
    attrs = _cls[cls]
    segs = [re.sub(r"\[\d*\]$", "", s) for s in p.split(".")]
    for i, s in enumerate(segs):
        if attrs is None or s not in attrs:
            return False
        a = attrs[s]
        if i < len(segs) - 1:
            ot = a.get("object_type")
            if not ot:
                return False
            attrs = obj_attrs(ot)
    return True


def full_closure(cls, depth=4):
    acc = set(oracle.CATCH_ALLS)

    def expand(attrs, prefix, d):
        for a, spec in (attrs or {}).items():
            acc.add(prefix + a)
            ot = spec.get("object_type")
            if ot and d > 0:
                expand(obj_attrs(ot), prefix + a + ".", d - 1)
    expand(_cls[cls], "", depth)
    return acc


# ---------- frontier predictions ----------
prompts = json.load(open(os.path.join(ORACLE, "_frontier", "frontier_prompts.json")))


def load_run(which):
    if which == "run1":
        raw = json.load(open(os.path.join(ORACLE, "_frontier", "predictions.json")))
        return {int(k): v for k, v in raw.items()}
    preds = {}
    for c in oracle.CONDITIONS:
        raw = json.load(open(os.path.join(ORACLE, "_frontier", which, f"pred_{c}.json")))
        if isinstance(raw, dict):
            preds.update({int(k): v for k, v in raw.items()})
        else:
            preds.update({int(e["gidx"]): e.get("path") for e in raw})
    return preds


valid = oracle.load_valid_paths()          # the transcribed-subset closure the June scorer used
FULLC = {c: full_closure(c) for c in _cls}  # full 1.8.0 closure, depth 4, for snap candidates only


def is_valid(p, cls, validator):
    return oracle.normalize(p, cls) in valid[cls] if validator == "subset" else in_full(p, cls)


def wall(pred, cls, mode, validator="subset"):
    """raw / reject / snap, as llm_behind_constraint.py, with the wall built on `validator`."""
    if mode == "raw":
        return pred
    if not pred:
        return "unmapped"
    if is_valid(pred, cls, validator):
        return pred
    if mode == "reject":
        return "unmapped"
    pool = valid[cls] if validator == "subset" else FULLC[cls]
    m = difflib.get_close_matches(oracle.normalize(pred, cls), sorted(pool), n=1, cutoff=0.6)
    return m[0] if m else "unmapped"


def tally(preds, cond, mode, validator="subset"):
    n = correct = silent = mapped = invented = offsubset = snapped = snapped_correct = both = 0
    for e in prompts:
        if cond != "all" and e["condition"] != cond:
            continue
        cls, gold = e["cls"], e["gold"]
        raw = preds.get(e["gidx"])
        p = wall(raw, cls, mode, validator)
        n += 1
        if not p:                       # missing prediction: the oracle scorer counts it silent
            silent += 1
            invented += 1
            continue
        nrm = oracle.normalize(p, cls)
        if nrm == "unmapped":
            continue
        mapped += 1
        ok = nrm == oracle.normalize(gold, cls)
        if not is_valid(p, cls, validator):
            silent += 1
            both += ok
        if nrm not in valid[cls]:
            if in_full(p, cls):
                offsubset += 1
            else:
                invented += 1
        correct += ok
        if mode == "snap" and raw and not is_valid(raw, cls, validator):
            snapped += 1
            snapped_correct += ok
    r = {"n": n, "path_correct": round(correct / n, 4), "silent_error_rate": round(silent / n, 4),
         "coverage": round(mapped / n, 4),
         "valid_but_non_gold": round((mapped - silent - correct + both) / n, 4),
         "silent_and_gold_correct": both}
    if mode == "raw":
        r["silent_invented_not_in_full_1_8_0"] = round(invented / n, 4)
        r["silent_real_1_8_0_outside_subset"] = round(offsubset / n, 4)
    if mode == "snap":
        r["snapped_n"] = snapped
        r["snapped_landing_on_gold"] = snapped_correct
    return r


def main():
    # sanity 1: every gold path is in the subset closure AND the full walk (so reject cannot lower path-correct)
    gold_bad = [(e["cls"], e["gold"]) for e in prompts if oracle.normalize(e["gold"], e["cls"]) not in valid[e["cls"]]]
    gold_full_bad = [(e["cls"], e["gold"]) for e in prompts if not in_full(e["gold"], e["cls"])]
    # recorded, not asserted: the gold key itself carries paths that do not walk in full 1.8.0
    # sanity 2: the subset closure is contained in the full walk (subset transcription is faithful)
    subset_not_full = sorted({(c, p) for c in valid for p in valid[c] if not in_full(p, c)})

    out = {"benchmark": "ocsf-deterministic-mapper / frontier-behind-constraint (POST-HOC re-score)",
           "date": "2026-11-16", "model_of_predictions": "claude-opus-4-8 via Claude Code subagents, June 2026",
           "headline_condition": "schema (fixed before looking; the condition the phi3 arm used)",
           "full_schema": "OCSF 1.8.0 via schema.ocsf.io/1.8.0/api, read 2026-11-16, profile-inclusive",
           "gold_paths_not_in_full_walk": sorted(set(gold_full_bad)),
           "gold_paths_not_in_subset_closure": sorted(set(gold_bad)),
           "gold_fields_not_in_subset_closure_n": sum(1 for e in prompts if e["condition"] == "schema"
                                                      and oracle.normalize(e["gold"], e["cls"]) not in valid[e["cls"]]),
           "subset_paths_not_in_full_walk": subset_not_full,
           "runs": {}}
    for run in ["run1", "run2", "run3"]:
        preds = load_run(run)
        out["runs"][run] = {v: {cond: {mode: tally(preds, cond, mode, v) for mode in ["raw", "reject", "snap"]}
                                for cond in ["schema", "all"]} for v in ["subset", "full"]}

    # phi3 behind the wall: is its correct set a subset of the alias mapper's?
    items = oracle.gold_fields(0)
    det_correct = set()
    rows = []
    for it in items:
        pred = det.deterministic_map(it["field"], it["class"], valid)
        key = (it["source"], it["field"])
        if pred != "unmapped" and oracle.normalize(pred, it["class"]) == oracle.normalize(it["gold"], it["class"]):
            det_correct.add(key)
        elif pred != "unmapped":
            rows.append({"source": it["source"], "class": it["class"], "field": it["field"],
                         "gold": it["gold"], "alias_pred": pred})
    phi = json.load(open(os.path.join(HERE, "results", "llm_predictions.json")))
    phi_snap_correct = set()
    for p in phi:
        s = wall(p["raw_pred"], p["class"], "snap")
        if s and oracle.normalize(s, p["class"]) == oracle.normalize(p["gold"], p["class"]):
            phi_snap_correct.add((p["source"], p["field"]))
    out["phi3_snap_correct_not_in_alias_correct"] = sorted(map(list, phi_snap_correct - det_correct))
    out["phi3_snap_correct_n"] = len(phi_snap_correct)
    # phi3 (schema condition, the cached run) re-scored against the full 1.8.0 walk
    n = len(phi)
    sil_sub = sum(1 for p in phi if not p["raw_pred"] or not is_valid(p["raw_pred"], p["class"], "subset"))
    sil_full = sum(1 for p in phi if not p["raw_pred"] or not is_valid(p["raw_pred"], p["class"], "full"))
    out["phi3_schema_raw_silent"] = {"subset": round(sil_sub / n, 4), "full_1_8_0": round(sil_full / n, 4), "n": n}
    out["phi3_full_wall"] = {m: None for m in ["reject", "snap"]}
    for m in ["reject", "snap"]:
        cor = mp = 0
        for p in phi:
            s = wall(p["raw_pred"], p["class"], m, "full")
            if s and oracle.normalize(s, p["class"]) != "unmapped":
                mp += 1
                cor += oracle.normalize(s, p["class"]) == oracle.normalize(p["gold"], p["class"])
        out["phi3_full_wall"][m] = {"path_correct": round(cor / n, 4), "coverage": round(mp / n, 4)}
    out["alias_correct_n"] = len(det_correct)
    out["alias_valid_but_non_gold_n"] = len(rows)

    # frontier per-condition, full 1.8.0 validator (raw silent + reject wall), every run
    out["frontier_per_condition_full"] = {
        r: {c: {"raw": tally(load_run(r), c, "raw", "full"), "reject": tally(load_run(r), c, "reject", "full")}
            for c in oracle.CONDITIONS} for r in ["run1", "run2", "run3"]}

    # gemma4:26b, cached per-item predictions (705, results/gemma4_full_checkpoint.jsonl), re-scored
    gpath = os.path.join(ORACLE, "results", "gemma4_full_checkpoint.jsonl")
    g = [json.loads(line) for line in open(gpath)]
    out["gemma4_full_validator"] = {}
    for c in oracle.CONDITIONS:
        rows_c = [x for x in g if x["condition"] == c]
        n_c = len(rows_c)
        sub = sum(1 for x in rows_c if not x["pred"] or not is_valid(x["pred"], x["class"], "subset"))
        ful = sum(1 for x in rows_c if not x["pred"] or not is_valid(x["pred"], x["class"], "full"))
        pc = sum(1 for x in rows_c if x["pred"] and oracle.normalize(x["pred"], x["class"]) == oracle.normalize(x["gold"], x["class"]))
        out["gemma4_full_validator"][c] = {"n": n_c, "silent_subset": round(sub / n_c, 4),
                                           "silent_full_1_8_0": round(ful / n_c, 4), "path_correct": round(pc / n_c, 4)}

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source", "class", "field", "gold", "alias_pred"])
        w.writeheader()
        w.writerows(rows)
    json.dump(out, open(OUT_JSON, "w"), indent=2, sort_keys=True)

    print("gold not in full walk:", gold_full_bad[:5], "| subset paths not in full walk:", len(subset_not_full))
    print("gold fields not in subset closure:", out["gold_fields_not_in_subset_closure_n"], "of 141")
    for run, dv in out["runs"].items():
        for v, d in dv.items():
            for cond, m in d.items():
                for mode, r in m.items():
                    print(f"{run:5} {v:6} {cond:6} {mode:6} " + "  ".join(f"{k}={x}" for k, x in r.items() if k != "n"))
    print("phi3 raw silent", out["phi3_schema_raw_silent"], "phi3 full wall", out["phi3_full_wall"])
    print("alias correct", len(det_correct), "| valid-but-non-gold", len(rows),
          "| phi3 snap correct", len(phi_snap_correct), "not in alias set:", out["phi3_snap_correct_not_in_alias_correct"])


if __name__ == "__main__":
    main()

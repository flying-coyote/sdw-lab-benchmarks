"""Arm (a) and the zeek part of arm (d): score a Tenzir zeek_conn emitted file under
(1) the ORIGINAL frozen scorer (pipeline-normalization-fidelity/score.py, imported, nothing written there),
(2) the alternates-accepting gold (alternates-gold-zeek_conn.json, frozen with PREREGISTRATION.md).

Gates (pre-registered): G1 = original scorer on the saved 6.0.0 output reproduces 0.80 / 0.9166 / 0.167;
G2 = a reference event built from the new gold's primary paths scores 100% on every metric.

Usage:
  python3 -I score_zeek_alternates.py --label NAME --emitted PATH [--gates]
Writes results/zeek-alternates-<label>.json.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LAB = os.path.dirname(ROOT)
PNF = os.path.join(LAB, "pipeline-normalization-fidelity")
sys.path.insert(0, PNF)
import score as S  # noqa: E402  (frozen scorer; used read-only, write_results never called)

GOLD_ALT = os.path.join(ROOT, "alternates-gold-zeek_conn.json")
CORPUS = os.path.join(PNF, "_work", "zeek_conn.corpus.jsonl")
SAVED_600 = os.path.join(PNF, "results", "tenzir_zeek_conn.emitted.jsonl")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def get(o, dotted):
    for s in dotted.split("."):
        if isinstance(o, dict) and s in o:
            o = o[s]
        else:
            return False, None
    return True, o


def put(o, dotted, v):
    segs = dotted.split(".")
    for s in segs[:-1]:
        o = o.setdefault(s, {})
    o[segs[-1]] = v


def rfc3339_us(s):
    if not isinstance(s, str) or not s.endswith("Z"):
        return None
    try:
        base, frac = (s[:-1].split(".") + ["0"])[:2]
        secs = int(dt.datetime.strptime(base, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp())
    except ValueError:
        return None
    ns = secs * 10**9 + int((frac + "000000000")[:9])
    return (ns + 500) // 1000  # round to microsecond


def value_ok(rule, v, src, strict):
    if rule == "equal":
        if isinstance(v, bool) or isinstance(src, bool):
            return v == src
        if isinstance(v, (int, float)) and isinstance(src, (int, float)):
            return float(v) == float(src)
        return v == src
    if rule == "epoch_ms_long":
        src_us = round(src * 10**6)
        want_ms = src_us // 1000
        if isinstance(v, int) and not isinstance(v, bool):
            return v == want_ms
        if strict:
            return False
        us = rfc3339_us(v)
        return us is not None and us == src_us
    if rule == "ms_within_1":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v - src * 1000) < 1
    raise ValueError(rule)


def load_jsonl(p):
    out = {}
    with open(p) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                out[r["_id"]] = r
    return out


def score_alt(gold, corpus, emitted):
    fields = gold["fields"]
    states = gold["activity_rule"]["states"]
    f_tot = f_ok = vs_tot = vs_ok = vi_ok = 0
    per_field = {k: {"field_total": 0, "field_landed": 0, "value_strict_ok": 0, "value_info_ok": 0} for k in fields}
    act = {"original_gold_6": 0, "accept_set": 0, "derived_primary": 0}
    tuid = {"accept_set": 0, "derived_primary": 0}
    cls_ok = 0
    by_state = {}
    for k, src in corpus.items():
        e = emitted.get(k)
        st = src["conn_state"]
        bs = by_state.setdefault(st, {"n": 0, "accept_set": 0, "derived_primary": 0, "emitted_values": {}})
        bs["n"] += 1
        if e is None:
            for f in fields:
                if f == "service" and src["service"] == "-":
                    continue
                f_tot += 1
                per_field[f]["field_total"] += 1
            continue
        for f, spec in fields.items():
            if f == "service" and src["service"] == "-":
                continue
            f_tot += 1
            per_field[f]["field_total"] += 1
            paths = [spec["primary"]] + spec.get("alternates", [])
            vals = [v for ok, v in (get(e, p) for p in paths) if ok and v is not None]
            if vals:
                f_ok += 1
                per_field[f]["field_landed"] += 1
                vs_tot += 1
                if any(value_ok(spec["value_rule"], v, src[f], True) for v in vals):
                    vs_ok += 1
                    per_field[f]["value_strict_ok"] += 1
                if any(value_ok(spec["value_rule"], v, src[f], False) for v in vals):
                    vi_ok += 1
                    per_field[f]["value_info_ok"] += 1
        a = e.get("activity_id")
        t = e.get("type_uid")
        c = e.get("class_uid")
        cls_ok += int(c == 4001)
        rule = states[st]
        bs["emitted_values"][str(a)] = bs["emitted_values"].get(str(a), 0) + 1
        act["original_gold_6"] += int(a == 6)
        if a in rule["accept"]:
            act["accept_set"] += 1
            bs["accept_set"] += 1
        if a == rule["primary"]:
            act["derived_primary"] += 1
            bs["derived_primary"] += 1
        tuid["accept_set"] += int(t in [400100 + x for x in rule["accept"]])
        tuid["derived_primary"] += int(t == 400100 + rule["primary"])
    n = len(corpus)
    r4 = lambda x, y: round(x / y, 4) if y else None  # noqa: E731
    return {
        "records": n, "covered": sum(1 for k in corpus if k in emitted),
        "field": {"landed": f_ok, "total": f_tot, "score": r4(f_ok, f_tot)},
        "value_strict": {"ok": vs_ok, "total": vs_tot, "score": r4(vs_ok, vs_tot)},
        "value_info_preserving": {"ok": vi_ok, "total": vs_tot, "score": r4(vi_ok, vs_tot)},
        "class_uid_4001": r4(cls_ok, n),
        "activity": {k: {"ok": v, "score": r4(v, n)} for k, v in act.items()},
        "type_uid": {k: {"ok": v, "score": r4(v, n)} for k, v in tuid.items()},
        "per_field": per_field,
        "activity_by_conn_state": by_state,
    }


def reference_from_new_gold(gold, corpus):
    out = {}
    for k, src in corpus.items():
        ev = {"_id": k, "class_uid": 4001}
        for f, spec in gold["fields"].items():
            v = src[f]
            if f == "service" and v == "-":
                continue
            if spec["value_rule"] == "epoch_ms_long":
                v = round(v * 10**6) // 1000
            elif spec["value_rule"] == "ms_within_1":
                v = int(round(v * 1000))
            put(ev, spec["primary"], v)
        p = gold["activity_rule"]["states"][src["conn_state"]]["primary"]
        ev["activity_id"] = p
        ev["type_uid"] = 400100 + p
        out[k] = ev
    return out


def reference_from_original_gold(corpus_ids):
    """The original gold's own paths and values as an emitted event (score.py's reference mapper)."""
    schema = S.load_merged_schema()
    gold = S.load_gold("zeek_conn")
    return S._build_reference_emitted(schema, gold)


def original_scorer(emitted_map):
    schema = S.load_merged_schema()
    r = S.score_source(schema, "zeek_conn", emitted_map)
    return {"field": r["field_fidelity"]["score"], "value": r["value_fidelity"]["score"],
            "activity_id": r["semantic_fidelity"]["activity_id"], "type_uid": r["semantic_fidelity"]["type_uid"],
            "class": r["semantic_fidelity"]["class_assignment"],
            "top_dropped": r["field_fidelity"]["top_dropped"], "top_mangled": r["value_fidelity"]["top_mangled"],
            "failure_classes": r["semantic_fidelity"]["failure_classes"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--emitted", required=True)
    ap.add_argument("--gates", action="store_true")
    a = ap.parse_args()
    gold = json.load(open(GOLD_ALT))
    corpus = load_jsonl(CORPUS)
    out = {"label": a.label, "emitted": os.path.relpath(os.path.abspath(a.emitted), LAB),
           "emitted_sha256": sha(a.emitted), "alternates_gold_sha256": sha(GOLD_ALT)}
    if a.gates:
        saved = load_jsonl(SAVED_600)
        g1 = original_scorer(saved)
        out["G1"] = {"result": g1, "pass": (g1["field"], g1["value"], g1["activity_id"]) == (0.8, 0.9166, 0.167)}
        ref = reference_from_new_gold(gold, corpus)
        g2 = score_alt(gold, corpus, ref)
        ok = all(x == 1.0 for x in (g2["field"]["score"], g2["value_strict"]["score"], g2["value_info_preserving"]["score"],
                                    g2["activity"]["accept_set"]["score"], g2["activity"]["derived_primary"]["score"],
                                    g2["type_uid"]["accept_set"]["score"], g2["type_uid"]["derived_primary"]["score"],
                                    g2["class_uid_4001"]))
        out["G2"] = {"pass": ok, "summary": {k: g2[k] for k in ("field", "value_strict", "value_info_preserving", "activity", "type_uid")}}
        orig_ref = reference_from_original_gold(corpus.keys())
        out["original_gold_as_mapper_under_new_gold"] = score_alt(gold, corpus, orig_ref)
        print("G1", out["G1"]["pass"], g1["field"], g1["value"], g1["activity_id"])
        print("G2", ok)
        if not (out["G1"]["pass"] and ok):
            json.dump(out, open(os.path.join(ROOT, "results", f"zeek-alternates-{a.label}.json"), "w"), indent=1, sort_keys=True)
            raise SystemExit("gate failed; arm stops (pre-registered stop rule)")
    em = load_jsonl(a.emitted)
    out["metadata_version"] = {}
    out["time_json_type"] = {}
    for e in em.values():
        v = (e.get("metadata") or {}).get("version")
        out["metadata_version"][str(v)] = out["metadata_version"].get(str(v), 0) + 1
        t = type(e.get("time")).__name__
        out["time_json_type"][t] = out["time_json_type"].get(t, 0) + 1
    out["original_scorer"] = original_scorer(em)
    out["alternates"] = score_alt(gold, corpus, em)
    p = os.path.join(ROOT, "results", f"zeek-alternates-{a.label}.json")
    with open(p, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    al = out["alternates"]
    print(json.dumps({"metadata_version": out["metadata_version"], "time_json_type": out["time_json_type"],
                      "original": {k: out["original_scorer"][k] for k in ("field", "value", "activity_id", "class")},
                      "alt_field": al["field"], "alt_value_strict": al["value_strict"],
                      "alt_value_info": al["value_info_preserving"], "alt_activity": al["activity"],
                      "alt_type_uid": al["type_uid"], "class": al["class_uid_4001"]}, indent=1))
    if a.gates:
        o = out["original_gold_as_mapper_under_new_gold"]
        print("original gold as mapper under new gold:", o["field"], o["activity"])


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Scorer (PREREGISTRATION.md sections 6 and 7). Deterministic, no LLM calls.

Inputs (one directory):
  arms/<ARM>-corpus.jsonl  arm outcomes over the 715 triples (item_id = triple id)
  arms/<ARM>-e1.jsonl      arm outcomes over the E1 items (item_id = <tid>-<stratum>)
  e1-items.jsonl           injector output (stratum per item)
  labels-batch1.csv / key-batch1.csv, optional labels-batch2.csv / key-batch2.csv
  optional labels-kappa.csv (second read of the 20-row kappa subset, same columns, batch-1 ids)
Output: score.json in the same directory; prints the verdict block.

Metrics: per arm, per stratum and per error set: catches, silent misses (judged / abstain),
false alarms on E2 items labelled correct or defensible, abstention rate over the 715 triples,
catch rate = catches / eligible (abstentions count as misses), and the jointly typed rate for each
compared pair. ΔK, ΔR, ΔF and the section 7 verdict; exact McNemar on E1-K1 discordant pairs for
O1-S2, O1-S3 and O2-O1 (descriptive); the attribution checks.
Usage: python3 -I score.py <dir>
"""
import csv
import json
import os
import sys
from math import comb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

ARMS = ["S1", "S2", "S3", "O0", "O1", "O2"]
STRATA = ["K1", "K2", "T", "R", "INV"]
PAIRS = [("O1", "S2"), ("O1", "S3"), ("O2", "O1")]
LABELS = {"correct", "defensible", "lossy", "wrong"}
KINDX = {"yes", "no", "unclear"}


def read_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else None


def read_labels(d, batch, lab_name=None):
    lab = os.path.join(d, lab_name or f"labels-batch{batch}.csv")
    key = os.path.join(d, f"key-batch{batch}.csv")
    if not (os.path.exists(lab) and os.path.exists(key)):
        return {}
    tid_of = {r["item_id"]: r["tid"] for r in csv.DictReader(open(key))}
    rows = csv.DictReader((l for l in open(lab) if not l.startswith("#")))
    out = {}
    for r in rows:
        v = {k: (r.get(k) or "").strip().lower() for k in ("label", "kind_crossing", "source_kind_adjudicated")}
        if v["label"] not in LABELS or v["kind_crossing"] not in KINDX:
            raise SystemExit(f"invalid label in {lab}: {r['item_id']} {v}")  # fail loudly, never drop a row
        out[tid_of[r["item_id"]]] = v
    return out


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def rate(n_catch, n):
    return round(100.0 * n_catch / n, 2) if n else None


def verdict(dk, dr, df):
    if dk is None or dr is None or df is None:
        return "INCOMPLETE", None
    if dk >= 10 and dr >= 3 and df <= dr - 1:
        return "SUPPORTS", None
    if dk <= 5 and dr <= 1 and df > -3:
        return "REFUTES", None
    reading = None
    if abs(dk) <= 5 and abs(dr) <= 1 and df <= -3:
        reading = "precision only"
    elif dk >= 10 and dr <= 1:
        reading = "injected only"
    return "TEMPERS", reading


def score(d):
    out = {"arms_present": [], "e1": {}, "e2": {}, "abstention_715": {}}
    corpus = {a: read_jsonl(os.path.join(d, "arms", f"{a}-corpus.jsonl")) for a in ARMS}
    e1 = {a: read_jsonl(os.path.join(d, "arms", f"{a}-e1.jsonl")) for a in ARMS}
    out["arms_present"] = [a for a in ARMS if corpus[a] is not None or e1[a] is not None]
    items = read_jsonl(os.path.join(d, "e1-items.jsonl")) or []
    stratum = {i["item_id"]: i["stratum"] for i in items}
    v1 = {a: {r["item_id"]: r for r in (e1[a] or [])} for a in ARMS}
    vc = {a: {r["item_id"]: r for r in (corpus[a] or [])} for a in ARMS}

    for a in ARMS:
        if corpus[a]:
            out["abstention_715"][a] = rate(sum(r["verdict"] == "abstain" for r in corpus[a]), len(corpus[a]))
        if not e1[a]:
            continue
        out["e1"][a] = {}
        for s in STRATA:
            ids = [i for i, st in stratum.items() if st == s]
            recs = [v1[a][i] for i in ids if i in v1[a]]
            c = sum(r["verdict"] == "flag" for r in recs)
            tid_of_item = {i["item_id"]: i["tid"] for i in items}
            inherited = sum(r["verdict"] == "flag" and vc[a].get(tid_of_item[r["item_id"]], {}).get("verdict") == "flag"
                            for r in recs)
            out["e1"][a][s] = {"eligible": len(ids), "catches": c, "catches_where_original_also_flagged": inherited,
                               "miss_judged": sum(r["verdict"] == "pass" for r in recs),
                               "miss_abstain": sum(r["verdict"] == "abstain" for r in recs),
                               "catch_rate": rate(c, len(ids))}

    out["paired"] = {}
    for s_ in STRATA:
        ids_s = [i for i, st in stratum.items() if st == s_]
        for x, y in PAIRS + [("O1", "S1"), ("S2", "S1"), ("O1", "O0")]:
            if not (v1[x] and v1[y]) or not ids_s:
                continue
            fx = {i: v1[x][i]["verdict"] == "flag" for i in ids_s}
            fy = {i: v1[y][i]["verdict"] == "flag" for i in ids_s}
            b = sum(fx[i] and not fy[i] for i in ids_s)
            c = sum(fy[i] and not fx[i] for i in ids_s)
            joint = [i for i in ids_s if v1[x][i]["verdict"] != "abstain" and v1[y][i]["verdict"] != "abstain"]
            out["paired"][f"{s_}:{x}-{y}"] = {
                "x_only": b, "y_only": c, "joint_n": len(joint),
                "joint_rate_x": rate(sum(fx[i] for i in joint), len(joint)),
                "joint_rate_y": rate(sum(fy[i] for i in joint), len(joint))}
            if s_ == "K1" and (x, y) in PAIRS:
                out["paired"][f"{s_}:{x}-{y}"]["mcnemar_exact_p"] = mcnemar_exact(b, c)

    # E2
    labels = read_labels(d, 1)
    b2 = read_labels(d, 2)
    decoy_mismatch = [t for t in b2 if t in labels and b2[t]["label"] != labels[t]["label"]]
    for t, v in b2.items():
        labels.setdefault(t, v)
    out["e2"]["n_labelled"] = len(labels)
    out["e2"]["decoy_label_mismatches"] = decoy_mismatch
    usable = {t: v for t, v in labels.items() if v["kind_crossing"] in ("yes", "no")}
    out["e2"]["n_unclear_excluded"] = len(labels) - len(usable)
    real = {t for t, v in usable.items() if v["label"] in ("lossy", "wrong")}
    tc_real = {t for t in real if usable[t]["kind_crossing"] == "yes"}
    ok = {t for t, v in usable.items() if v["label"] in ("correct", "defensible")}
    out["e2"]["n_real_errors"], out["e2"]["n_type_crossing_real_errors"] = len(real), len(tc_real)
    out["e2"]["per_arm"] = {}
    for a in ARMS:
        if not vc[a]:
            continue
        flag = {t for t, r in vc[a].items() if r["verdict"] == "flag"}
        out["e2"]["per_arm"][a] = {"tc_real_caught": len(tc_real & flag), "real_caught": len(real & flag),
                                   "false_alarms": len(ok & flag),
                                   "tc_real_abstain": sum(vc[a][t]["verdict"] == "abstain" for t in tc_real if t in vc[a])}

    # section 10 secondary analysis: S2 re-scored with the adjudicated source kind in place of its
    # typer (S2 only; an O-arm equivalent needs an OCSF-kind -> D3FEND-artifact map that the prereg
    # does not define, so it is reported as not computed)
    if vc["S2"]:
        sec = {"tc_real_caught": 0, "false_alarms": 0, "n_with_adjudicated_kind": 0, "unknown_kinds": []}
        for t, v in usable.items():
            r = vc["S2"].get(t)
            if not r or not v["source_kind_adjudicated"]:
                continue
            if C.ocsf_object(v["source_kind_adjudicated"]) is None:
                sec["unknown_kinds"].append(v["source_kind_adjudicated"])
                continue
            sec["n_with_adjudicated_kind"] += 1
            tk = r.get("tgt_root")
            flag = r.get("s1") == "flag" or (tk is not None and not C.kinds_related(v["source_kind_adjudicated"], tk))
            sec["tc_real_caught"] += flag and t in tc_real
            sec["false_alarms"] += flag and t in ok
        sec["o_arms"] = "not computed (no pre-registered OCSF-kind -> D3FEND-artifact map)"
        out["e2"]["secondary_S2_adjudicated_kind"] = sec

    kp = read_labels(d, 1, "labels-kappa.csv")  # second read of the kappa subset, batch-1 item ids
    if kp:
        pairs = [(labels[t]["label"], kp[t]["label"]) for t in kp if t in labels]
        cats = sorted({x for p in pairs for x in p})
        n = len(pairs)
        po = sum(x == y for x, y in pairs) / n
        pe = sum((sum(x == c for x, _ in pairs) / n) * (sum(y == c for _, y in pairs) / n) for c in cats)
        out["e2"]["cohen_kappa"] = {"n": n, "kappa": round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0}

    # deltas and verdict
    e1o, e1s = out["e1"].get("O1", {}).get("K1"), out["e1"].get("S2", {}).get("K1")
    dk = round(e1o["catch_rate"] - e1s["catch_rate"], 2) if e1o and e1s and e1o["catch_rate"] is not None and e1s["catch_rate"] is not None else None
    pk = out["paired"].get("K1:O1-S2")
    dk_joint = round(pk["joint_rate_x"] - pk["joint_rate_y"], 2) if pk and pk["joint_rate_x"] is not None else None
    pa = out["e2"]["per_arm"]
    have_e2 = "O1" in pa and "S2" in pa and labels
    dr = pa["O1"]["tc_real_caught"] - pa["S2"]["tc_real_caught"] if have_e2 else None
    df = pa["O1"]["false_alarms"] - pa["S2"]["false_alarms"] if have_e2 else None
    v, reading = verdict(dk, dr, df)
    vj, _ = verdict(dk_joint, dr, df)
    if v not in ("INCOMPLETE",) and vj not in ("INCOMPLETE",) and vj != v:
        v, reading = "TEMPERS", "typer-driven"
    out["decision"] = {"dK": dk, "dK_joint": dk_joint, "dR": dr, "dF": df, "verdict": v, "reading": reading,
                       "note": "O1/O2 = D3FEND class names plus one authored disjointness axiom; O0 shown beside them"}

    # attribution
    att = {}
    if vc["O1"] and vc["S3"]:
        dis = []
        for src in (vc, v1):
            for i, r in src["O1"].items():
                s3 = src["S3"].get(i)
                if s3 and r.get("tgt_art") != "Session" and s3.get("tgt_art") != "Session" and r["verdict"] != s3["verdict"]:
                    dis.append(i)
        att["O1_vs_S3_non_session_disagreements"] = dis
    if vc["O2"] and vc["O1"]:
        att["O2_vs_O1_differences"] = [i for src in (vc, v1) for i, r in src["O2"].items()
                                       if i in src["O1"] and src["O1"][i]["verdict"] != r["verdict"]]
    for a in ("O0", "O1"):
        if vc[a]:
            att[f"{a}_flags_corpus"] = sum(r["verdict"] == "flag" for r in vc[a].values())
        if v1[a]:
            att[f"{a}_flags_e1"] = sum(r["verdict"] == "flag" for r in v1[a].values())
    out["attribution"] = att
    return out


def main(argv):
    d = argv[1]
    res = score(d)
    json.dump(res, open(os.path.join(d, "score.json"), "w"), indent=1)
    print(json.dumps(res["decision"], indent=1))


if __name__ == "__main__":
    main(sys.argv)

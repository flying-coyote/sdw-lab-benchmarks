"""STREAM-FRESHNESS answer-equality gate (Measure 6), over every arm replica.

W: the July compare_answers.compare_arm against ground_truth.json (missing 0, extra 0,
   duplicates 0), plus pairwise key-set identity across all replicas.
I: each replica's set of event_uids against the planted IOC events in ioc_ground_truth.json
   (missing 0, extra 0, duplicates 0), plus pairwise identity.
Usage: --arm NAME=w_alerts.jsonl,i_alerts.jsonl (repeatable). Exits nonzero on any failure.
"""
import argparse
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from compare_answers import compare_arm, load_alert_keys, load_ground_truth_keys  # noqa: E402


def load_i(path):
    uids, n = [], 0
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    n += 1
                    uids.append(json.loads(line)["event_uid"])
    return set(uids), n, len(uids) - len(set(uids)), os.path.exists(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ground-truth", required=True)
    ap.add_argument("--ioc-truth", required=True)
    ap.add_argument("--arm", action="append", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    gt_keys, gt = load_ground_truth_keys(args.ground_truth)
    with open(args.ioc_truth) as f:
        planted = {p["event_uid"] for p in json.load(f)["planted"]}
    arms = {}
    for a in args.arm:
        name, paths = a.split("=", 1)
        w, i = paths.split(",")
        arms[name] = (w, i)

    res, wkeys, ikeys = {}, {}, {}
    for name, (w, i) in arms.items():
        rw = compare_arm(name, w, gt_keys)
        wkeys[name] = load_alert_keys(w)[0]
        iset, irows, idup, iexists = load_i(i)
        ikeys[name] = iset
        ri = {"exists": iexists, "n_rows": irows, "n_distinct": len(iset), "n_duplicates": idup,
              "missing": sorted(planted - iset), "extra": sorted(iset - planted)}
        ri["pass"] = iexists and idup == 0 and not ri["missing"] and not ri["extra"]
        res[name] = {"W": rw, "W_pass": bool(rw["exists"] and rw["identical"]), "I": ri, "I_pass": ri["pass"]}

    pair_w = all(wkeys[a] == wkeys[b] for a, b in itertools.combinations(arms, 2))
    pair_i = all(ikeys[a] == ikeys[b] for a, b in itertools.combinations(arms, 2))
    w_ok = all(r["W_pass"] for r in res.values()) and pair_w
    i_ok = all(r["I_pass"] for r in res.values()) and pair_i
    rep = {"n_w_ground_truth": len(gt_keys), "n_i_planted": len(planted), "arms": res,
           "pairwise_w_identical": pair_w, "pairwise_i_identical": pair_i,
           "gate_w_pass": w_ok, "gate_i_pass": i_ok, "gate_pass": w_ok and i_ok}
    with open(args.out, "w") as f:
        json.dump(rep, f, indent=2, sort_keys=True)
    for name, r in res.items():
        w = r["W"]
        print(f"  [{name:10s}] W rows={w['n_rows']} missing={w['n_missing']} extra={w['n_extra']} "
              f"dup={w['n_duplicate_keys']} | I rows={r['I']['n_rows']} missing={len(r['I']['missing'])} "
              f"extra={len(r['I']['extra'])} dup={r['I']['n_duplicates']}")
    print(f"  W gate {'PASS' if w_ok else 'FAIL'} ({len(gt_keys)} truth) | I gate {'PASS' if i_ok else 'FAIL'} "
          f"({len(planted)} planted) | GATE {'PASS' if w_ok and i_ok else 'FAIL'}")
    sys.exit(0 if w_ok and i_ok else 1)


if __name__ == "__main__":
    main()

"""v2 answer-equality gate across up to four arms (B, S, F, BC). Reuses the July
compare_answers.compare_arm unchanged per arm, then checks every pair for identity.
Exits nonzero on ANY divergence (missing, extra, duplicates, absent file, pair mismatch)."""
import argparse, itertools, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from compare_answers import compare_arm, load_alert_keys, load_ground_truth_keys, _fmt_key  # noqa: E402

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ground-truth", default=os.path.join(ROOT, "data", "ground_truth.json"))
    ap.add_argument("--arm", action="append", required=True, help="NAME=path/to/alerts.jsonl")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    gt_keys, gt = load_ground_truth_keys(args.ground_truth)
    arms = dict(a.split("=", 1) for a in args.arm)
    res = {n: compare_arm(n, p, gt_keys) for n, p in arms.items()}
    keys = {n: load_alert_keys(p)[0] for n, p in arms.items()}
    pairs = {}
    for a, b in itertools.combinations(arms, 2):
        pairs[f"{a}_vs_{b}"] = {"identical": keys[a] == keys[b],
                                f"only_in_{a}": [_fmt_key(k) for k in sorted(keys[a] - keys[b])],
                                f"only_in_{b}": [_fmt_key(k) for k in sorted(keys[b] - keys[a])]}
    ok = all(r["exists"] and r["identical"] for r in res.values()) and all(p["identical"] for p in pairs.values())
    rep = {"n_ground_truth_alerts": len(gt_keys), "seed": gt.get("seed"), "n_events": gt.get("n_events"),
           "arms": res, "pairwise": pairs, "gate_pass": ok}
    with open(args.out, "w") as f:
        json.dump(rep, f, indent=2, sort_keys=True)
    for n, r in res.items():
        print(f"  [{n}] exists={r['exists']} rows={r['n_rows']} distinct={r['n_distinct_keys']} "
              f"missing={r['n_missing']} extra={r['n_extra']} dup={r['n_duplicate_keys']}")
    print(f"  pairwise identical: {all(p['identical'] for p in pairs.values())}  GATE {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()

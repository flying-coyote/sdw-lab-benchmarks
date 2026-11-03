"""v2 freshness: July measure_latency.py baseline (alert's own window close on the shared
replay clock -> alert_emit_wall_ts), applied identically to every arm."""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from measure_latency import latencies_for_arm, load_rows, summarize  # noqa: E402

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ground-truth", default=os.path.join(ROOT, "data", "ground_truth.json"))
    ap.add_argument("--arm", action="append", required=True, help="NAME=path")
    ap.add_argument("--replay-start-epoch", type=float, required=True)
    ap.add_argument("--replay-factor", type=float, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    ws = json.load(open(args.ground_truth))["window_seconds"]
    rep = {"replay_start_epoch": args.replay_start_epoch, "replay_factor": args.replay_factor,
           "baseline": "July measure_latency.py: window close on the shared replay clock"}
    for a in args.arm:
        n, p = a.split("=", 1)
        s = latencies_for_arm(load_rows(p), ws, args.replay_start_epoch, args.replay_factor)
        summ = summarize(s)
        if n in ("B", "BC") and summ["median_s"] is not None:
            summ["median_s_real_time_equivalent"] = round(summ["median_s"] * args.replay_factor, 2)
        rep[n] = {"samples": s, "summary": summ}
        print(f"  [{n}] {summ}")
    json.dump(rep, open(args.out, "w"), indent=2, sort_keys=True)

if __name__ == "__main__":
    main()

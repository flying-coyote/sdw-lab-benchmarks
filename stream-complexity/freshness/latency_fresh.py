"""STREAM-FRESHNESS latency (Measures 1-3), at 1x on the shared replay clock.

W: alert_emit_wall_ts - window close, where window close = RS + (window_start + 60 - BASE_EPOCH).
   This is the July/v2 baseline, unchanged.
I: alert_emit_wall_ts - the matching event's scheduled replay time RS + (time - BASE_EPOCH).
Batch arms are also reported with lander lag subtracted: each sample minus the lag_s of the
file that carried it (the file whose [chunk_start, chunk_end) covers the window or event).

Usage: --arm NAME=w.jsonl,i.jsonl[,lag.jsonl] (repeatable). Replicas are named
<arm>.r<k>; the report gives per-replica and pooled-per-arm p50 / p95 / max / n.
Deviation D3: frozen predictions are scored on the pooled figure.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from compare_answers import canonical_window_start  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "..", "lib"))
from common import BASE_EPOCH  # noqa: E402

WINDOW = 60


def rows(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def pct(vals, q):
    if not vals:
        return None
    v = sorted(vals)
    if q == 50:
        n = len(v)
        return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2
    idx = min(len(v) - 1, max(0, int(round(q / 100 * (len(v) - 1)))))
    return v[idx]


def summ(vals):
    r = lambda x: None if x is None else round(x, 3)  # noqa: E731
    return {"n": len(vals), "p50_s": r(pct(vals, 50)), "p95_s": r(pct(vals, 95)),
            "max_s": r(max(vals) if vals else None), "min_s": r(min(vals) if vals else None)}


def lag_lookup(lag_rows):
    def f(t):
        for row in lag_rows:
            if row["chunk_start"] <= t < row["chunk_end"]:
                return row["lag_s"]
        return None
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--replay-start-epoch", type=float, required=True)
    ap.add_argument("--arm", action="append", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    RS = args.replay_start_epoch
    rep = {"replay_start_epoch": RS, "replay_factor": 1.0,
           "baseline_W": "window close on the shared 1x replay clock (July/v2)",
           "baseline_I": "matching event's scheduled replay time", "replicas": {}, "pooled": {}}
    pooled = {}
    for a in args.arm:
        name, paths = a.split("=", 1)
        parts = paths.split(",")
        w_path, i_path = parts[0], parts[1]
        lag_rows = rows(parts[2]) if len(parts) > 2 else []
        lag = lag_lookup(lag_rows)
        w, wl, i, il = [], [], [], []
        for r in rows(w_path):
            ws = canonical_window_start(r["window_start"])
            v = r["alert_emit_wall_ts"] - (RS + (ws + WINDOW - BASE_EPOCH))
            w.append(v)
            g = lag(ws) if lag_rows else None
            if g is not None:
                wl.append(v - g)
        for r in rows(i_path):
            v = r["alert_emit_wall_ts"] - (RS + (r["time"] - BASE_EPOCH))
            i.append(v)
            g = lag(r["time"]) if lag_rows else None
            if g is not None:
                il.append(v - g)
        rec = {"W": summ(w), "I": summ(i)}
        if lag_rows:
            rec["W_lag_subtracted"] = summ(wl)
            rec["I_lag_subtracted"] = summ(il)
            lags = [row["lag_s"] for row in lag_rows]
            rec["lander_lag"] = {"p50_s": round(pct(lags, 50), 4), "p95_s": round(pct(lags, 95), 4),
                                 "max_s": round(max(lags), 4), "n_files": len(lags)}
        rep["replicas"][name] = rec
        group = name.split(".r")[0]
        p = pooled.setdefault(group, {"W": [], "I": [], "Wl": [], "Il": []})
        p["W"] += w
        p["I"] += i
        p["Wl"] += wl
        p["Il"] += il
    for g, p in pooled.items():
        rec = {"W": summ(p["W"]), "I": summ(p["I"])}
        if p["Wl"] or p["Il"]:
            rec["W_lag_subtracted"] = summ(p["Wl"])
            rec["I_lag_subtracted"] = summ(p["Il"])
        rep["pooled"][g] = rec
    with open(args.out, "w") as f:
        json.dump(rep, f, indent=2, sort_keys=True)
    print(f"  {'arm':12s} {'W p50':>9s} {'W p95':>9s} {'I p50':>9s} {'I p95':>9s}  (pooled; lag-subtracted W/I p50)")
    for g, rec in rep["pooled"].items():
        ls = (f"  ({rec['W_lag_subtracted']['p50_s']} / {rec['I_lag_subtracted']['p50_s']})"
              if "W_lag_subtracted" in rec else "")
        print(f"  {g:12s} {rec['W']['p50_s']!s:>9s} {rec['W']['p95_s']!s:>9s} "
              f"{rec['I']['p50_s']!s:>9s} {rec['I']['p95_s']!s:>9s}{ls}")


if __name__ == "__main__":
    main()

"""Measure 4 (freshness) from the pre-reg: event-ingest -> alert-emit wall-clock
latency, per arm, for one trial. Writes results/latency-trial-N.json.

The baseline this uses is the WINDOW-CLOSE instant, not either arm's own per-row
`ingest_wall_ts` field, and that choice matters: batch's `ingest_wall_ts` is the
whole FILE's landing time (already inflated by the tick/window boundary), while
streaming's is the individual triggering event's own production time (not inflated
at all) — comparing "alert_emit - ingest_wall_ts" directly across arms would compare
two different reference semantics and unfairly flatter streaming. The one thing both
arms are structurally gated on identically is that NEITHER can legitimately alert
before a window has closed: batch because the file for that window hasn't landed
yet, streaming because its watermark (2s bounded out-of-orderness) hasn't passed
window_end yet. So the fair common baseline is:

    window_close_wall_time = replay_start_epoch + (window_end_event_time - BASE_EPOCH) / replay_factor

using the SAME `replay_start_epoch` given to both batch/land_microbatches.py and
streaming/producer.py by run_clean_trial.sh (see their `replay()` docstrings for why
each script's own independent `time.time()` would introduce clock skew of the same
order as the effect being measured). latency = alert_emit_wall_ts - window_close_wall_time.

This also happens to line up with the pre-reg's own P4 framing structurally: batch's
latency should come out close to (poll_interval/2 + DuckDB query time) — "tick/2 +
processing" — and streaming's should come out close to (watermark bound + Flink
firing/Kafka round-trip) — both measured directly, not asserted.
"""

import argparse
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from compare_answers import canonical_window_start  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import BASE_EPOCH  # noqa: E402

DEFAULT_GROUND_TRUTH = os.path.join(HERE, "data", "ground_truth.json")
DEFAULT_BATCH = os.path.join(HERE, "results", "alerts-batch.jsonl")
DEFAULT_STREAM = os.path.join(HERE, "results", "alerts-stream.jsonl")
RESULTS_DIR = os.path.join(HERE, "results")


def load_rows(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def latencies_for_arm(rows, window_seconds, replay_start_epoch, replay_factor):
    samples = []
    for row in rows:
        window_start = canonical_window_start(row["window_start"])
        window_close_event_time = window_start + window_seconds
        window_close_wall_time = replay_start_epoch + (window_close_event_time - BASE_EPOCH) / replay_factor
        latency_s = row["alert_emit_wall_ts"] - window_close_wall_time
        samples.append({
            "user": row["user"], "src_ip": row["src_ip"], "window_start": window_start,
            "latency_s": round(latency_s, 4),
        })
    return samples


def summarize(samples):
    if not samples:
        return {"n": 0, "median_s": None, "min_s": None, "max_s": None, "cv_pct": None}
    vals = sorted(s["latency_s"] for s in samples)
    n = len(vals)
    median = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    mean = sum(vals) / n
    cv = (statistics.pstdev(vals) / mean * 100.0) if n > 1 and mean != 0 else 0.0
    return {"n": n, "median_s": round(median, 4), "min_s": round(vals[0], 4),
            "max_s": round(vals[-1], 4), "cv_pct": round(cv, 1)}


def next_trial_number(results_dir):
    existing = glob.glob(os.path.join(results_dir, "latency-trial-*.json"))
    nums = []
    for p in existing:
        base = os.path.basename(p)[len("latency-trial-"):-len(".json")]
        if base.isdigit():
            nums.append(int(base))
    return (max(nums) + 1) if nums else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ground-truth", default=DEFAULT_GROUND_TRUTH)
    ap.add_argument("--batch-file", default=DEFAULT_BATCH)
    ap.add_argument("--stream-file", default=DEFAULT_STREAM)
    ap.add_argument("--replay-start-epoch", type=float, required=True)
    ap.add_argument("--replay-factor", type=float, required=True)
    ap.add_argument("--trial-n", type=int, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    with open(args.ground_truth) as f:
        gt = json.load(f)
    window_seconds = gt["window_seconds"]

    batch_samples = latencies_for_arm(load_rows(args.batch_file), window_seconds,
                                        args.replay_start_epoch, args.replay_factor)
    stream_samples = latencies_for_arm(load_rows(args.stream_file), window_seconds,
                                         args.replay_start_epoch, args.replay_factor)

    trial_n = args.trial_n or next_trial_number(RESULTS_DIR)
    out = args.out or os.path.join(RESULTS_DIR, f"latency-trial-{trial_n}.json")

    report = {
        "trial_n": trial_n,
        "replay_start_epoch": args.replay_start_epoch,
        "replay_factor": args.replay_factor,
        "window_seconds": window_seconds,
        "note": "latency_s is wall-clock seconds from the ALERT'S OWN window closing "
                "(replay_start_epoch + (window_end - BASE_EPOCH)/replay_factor) to "
                "alert_emit_wall_ts, the same baseline for both arms — see module "
                "docstring for why this, not either arm's own ingest_wall_ts field, is "
                "the fair comparison point. Measured at replay_factor="
                f"{args.replay_factor}x; batch's tick/window-boundary wait is an "
                "event-time phenomenon that shrinks proportionally under replay "
                "acceleration (a 60s window closes in 60/replay_factor wall-seconds), "
                "so ANY replay_factor > 1 run understates what batch's freshness gap "
                "would be at real-time (replay_factor=1): multiply batch's median_s by "
                "replay_factor for a real-time-equivalent figure. Streaming's latency "
                "is real compute/network time and is NOT replay-factor-dependent, so "
                "it is reported as measured, uncorrected.",
        "batch": {"samples": batch_samples, "summary": summarize(batch_samples)},
        "stream": {"samples": stream_samples, "summary": summarize(stream_samples)},
    }
    if batch_samples and report["batch"]["summary"]["median_s"] is not None:
        report["batch"]["summary"]["median_s_real_time_equivalent"] = round(
            report["batch"]["summary"]["median_s"] * args.replay_factor, 2)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)

    print(f"[measure_latency] batch:  n={report['batch']['summary']['n']}  "
          f"median={report['batch']['summary']['median_s']}s "
          f"(real-time-equiv={report['batch']['summary'].get('median_s_real_time_equivalent')}s)")
    print(f"[measure_latency] stream: n={report['stream']['summary']['n']}  "
          f"median={report['stream']['summary']['median_s']}s")
    print(f"report written -> {out}")


if __name__ == "__main__":
    main()

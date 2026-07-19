"""Answer-equality gate (pre-reg P5): load both arms' alert files + ground_truth.json,
canonicalize (user, src_ip, window_start) into one comparable key across arms, and
report identical/missing/extra per arm. Exits nonzero on ANY divergence — per the
pre-reg: "a mismatch invalidates the bench until explained and fixed; no complexity
result may be quoted from a run whose answers diverge."

Canonicalization is needed, not cosmetic: the two arms do not naturally emit
window_start in the same representation. batch_job.py works in epoch seconds
throughout (DuckDB integer math) and writes window_start as an int. The Flink SQL
job's TUMBLE table-valued function produces a TIMESTAMP_LTZ window_start column,
which the JSON sink format serializes as an ISO-8601 string (see streaming/
flink_job.sql and streaming/consume_alerts.py) — so the streaming arm's raw
window_start is a string. This script is where that difference gets resolved,
once, in one place, rather than silently in each arm.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GROUND_TRUTH = os.path.join(HERE, "data", "ground_truth.json")
DEFAULT_BATCH = os.path.join(HERE, "results", "alerts-batch.jsonl")
DEFAULT_STREAM = os.path.join(HERE, "results", "alerts-stream.jsonl")
DEFAULT_REPORT = os.path.join(HERE, "results", "compare-report.json")


def canonical_window_start(value) -> int:
    """Normalize an arm's window_start (int epoch seconds, or an ISO-8601 string as
    Flink's JSON sink emits for a TIMESTAMP_LTZ column) to a plain int epoch second."""
    if isinstance(value, bool):
        raise TypeError(f"window_start is a bool, not a timestamp: {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, str):
        s = value.strip()
        if s.lstrip("-").isdigit():
            return int(s)
        iso = s[:-1] + "+00:00" if s.endswith("Z") else s
        try:
            dt = datetime.fromisoformat(iso)
        except ValueError:
            # Flink's default JSON timestamp format keeps microsecond/space variants;
            # last-resort: truncate to whole seconds and retry the common patterns.
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    dt = datetime.strptime(iso.split(".")[0], fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"cannot parse window_start: {value!r}")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)  # Flink session is pinned to UTC (see flink_job.sql)
        return int(dt.timestamp())
    raise TypeError(f"unsupported window_start type: {type(value)} ({value!r})")


def load_alert_keys(path):
    """Returns (set of canonical (user, src_ip, window_start) keys, raw row count,
    list of (key, row) for duplicate detection)."""
    keys = set()
    rows_by_key = {}
    duplicates = []
    n_rows = 0
    if not os.path.exists(path):
        return keys, 0, [], []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n_rows += 1
            row = json.loads(line)
            key = (row["user"], row["src_ip"], canonical_window_start(row["window_start"]))
            if key in rows_by_key:
                duplicates.append(key)
            rows_by_key[key] = row
            keys.add(key)
    return keys, n_rows, list(rows_by_key.items()), duplicates


def load_ground_truth_keys(path):
    with open(path) as f:
        gt = json.load(f)
    keys = {(a["user"], a["src_ip"], canonical_window_start(a["window_start"])) for a in gt["alerts"]}
    return keys, gt


def _fmt_key(k):
    return {"user": k[0], "src_ip": k[1], "window_start": k[2]}


def compare_arm(arm_name, arm_path, gt_keys):
    arm_keys, n_rows, rows, duplicates = load_alert_keys(arm_path)
    missing = sorted(gt_keys - arm_keys)       # in ground truth, arm failed to alert
    extra = sorted(arm_keys - gt_keys)         # arm alerted, ground truth says it shouldn't have
    identical = not missing and not extra and not duplicates
    return {
        "arm": arm_name,
        "path": arm_path,
        "exists": os.path.exists(arm_path),
        "n_rows": n_rows,
        "n_distinct_keys": len(arm_keys),
        "n_duplicate_keys": len(duplicates),
        "duplicate_keys": [_fmt_key(k) for k in duplicates],
        "n_ground_truth": len(gt_keys),
        "n_missing": len(missing),
        "n_extra": len(extra),
        "missing": [_fmt_key(k) for k in missing],
        "extra": [_fmt_key(k) for k in extra],
        "identical": identical,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ground-truth", default=DEFAULT_GROUND_TRUTH)
    ap.add_argument("--batch-file", default=DEFAULT_BATCH)
    ap.add_argument("--stream-file", default=DEFAULT_STREAM)
    ap.add_argument("--arm", choices=["batch", "stream", "both"], default="both",
                     help="restrict the comparison to one arm (used by faults/run_faults.py "
                          "when only one arm was faulted)")
    ap.add_argument("--out", default=DEFAULT_REPORT)
    ap.add_argument("--quiet", action="store_true", help="suppress the human-readable report")
    args = ap.parse_args()

    gt_keys, gt = load_ground_truth_keys(args.ground_truth)

    results = {}
    if args.arm in ("batch", "both"):
        results["batch"] = compare_arm("batch", args.batch_file, gt_keys)
    if args.arm in ("stream", "both"):
        results["stream"] = compare_arm("stream", args.stream_file, gt_keys)

    # Arm-vs-arm agreement is a useful cross-check even though both are already checked
    # against ground truth independently: two arms that agree with EACH OTHER but not
    # with ground truth would otherwise look like "no divergence" if only compared
    # pairwise, so this is reported alongside, never instead of, the ground-truth checks.
    if args.arm == "both":
        batch_keys, _, _, _ = load_alert_keys(args.batch_file)
        stream_keys, _, _, _ = load_alert_keys(args.stream_file)
        results["batch_vs_stream"] = {
            "identical": batch_keys == stream_keys,
            "only_in_batch": [_fmt_key(k) for k in sorted(batch_keys - stream_keys)],
            "only_in_stream": [_fmt_key(k) for k in sorted(stream_keys - batch_keys)],
        }

    report = {
        "ground_truth_path": args.ground_truth,
        "n_ground_truth_alerts": len(gt_keys),
        "seed": gt.get("seed"),
        "n_events": gt.get("n_events"),
        "results": results,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)

    any_divergence = False
    if not args.quiet:
        print(f"ground truth: {len(gt_keys)} alerts (seed={gt.get('seed')}, n_events={gt.get('n_events')})")
    for arm_name, r in results.items():
        if arm_name == "batch_vs_stream":
            status = "IDENTICAL" if r["identical"] else "DIVERGES"
            if not args.quiet:
                print(f"  batch vs stream: {status} "
                      f"(only_in_batch={len(r['only_in_batch'])}, only_in_stream={len(r['only_in_stream'])})")
            continue
        if not r["exists"]:
            any_divergence = True
            if not args.quiet:
                print(f"  [{arm_name}] FILE NOT FOUND: {r['path']}")
            continue
        status = "IDENTICAL" if r["identical"] else "DIVERGES"
        if not r["identical"]:
            any_divergence = True
        if not args.quiet:
            print(f"  [{arm_name}] {status}: {r['n_rows']} rows, {r['n_distinct_keys']} distinct alerts "
                  f"(missing={r['n_missing']}, extra={r['n_extra']}, duplicates={r['n_duplicate_keys']})")
            for k in r["missing"][:10]:
                print(f"      MISSING: {k}")
            for k in r["extra"][:10]:
                print(f"      EXTRA:   {k}")
            for k in r["duplicate_keys"][:10]:
                print(f"      DUPLICATE KEY (not idempotent): {k}")

    if not args.quiet:
        print(f"report written -> {args.out}")

    sys.exit(1 if any_divergence else 0)


if __name__ == "__main__":
    main()

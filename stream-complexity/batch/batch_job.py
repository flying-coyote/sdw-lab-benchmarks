"""Batch arm, half 2 of 2: the single scheduled DuckDB/Python job. Runs as a bare
host-process loop (no scheduler daemon, no orchestrator — this IS the "batch is
allowed to be a bare python process + files" design the pre-reg blesses; the job
and the scheduler are the SAME artifact by construction, which is itself one half
of the operational-complexity finding this bench measures).

Each tick:
  1. lists data/batch_in/window-*.parquet, parses the window number out of the
     filename, and finds windows newer than the last one processed;
  2. ALSO re-scans the single window immediately before the oldest new window
     ("re-scan of the previous tick's window boundary") — defensive against a
     window's rows landing split across two physical files (replay jitter, a
     slow micro-batch collector, clock skew); a row's true window is always
     recomputed from its own `time` field, so the re-scan can only ADD
     completeness, never double-count a window's logical bucket;
  3. runs ONE DuckDB query over the union of those files, grouping by
     (user, src_ip, window_start) with window_start = (time // 60) * 60 —
     the same epoch-aligned tumbling grid gen_corpus.py's independent ground
     truth and streaming/flink_job.sql's TUMBLE both use;
  4. for each >=5-failure group, appends an alert line to alerts-batch.jsonl
     UNLESS (user, src_ip, window_start) has already been emitted — dedup key
     is exactly the pre-reg's idempotency requirement. `seen_keys` is
     reconstructed at startup from BOTH the persisted state file (fast path)
     AND a re-read of any existing alerts-batch.jsonl (slow but authoritative
     path, covers the case where the state file was lost to a hard kill —
     see faults/kill_batch_job.sh), so a crash-and-restart can never emit a
     duplicate even if its last state write never happened.
"""

import argparse
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gen_corpus import WINDOW_SECONDS, FAILURE_THRESHOLD  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "lib"))
from common import configure_duckdb  # noqa: E402

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_IN_DIR = os.path.join(ROOT, "data", "batch_in")
DEFAULT_OUT_FILE = os.path.join(ROOT, "results", "alerts-batch.jsonl")
DEFAULT_STATE_FILE = os.path.join(ROOT, "data", "batch_in", ".batch_state.json")

WINDOW_RE = re.compile(r"window-(\d+)\.parquet$")


def _window_num(path):
    m = WINDOW_RE.search(os.path.basename(path))
    return int(m.group(1)) if m else None


def load_state(state_file):
    if os.path.exists(state_file):
        with open(state_file) as f:
            s = json.load(f)
        return s.get("last_window_processed"), {tuple(k) for k in s.get("seen_keys", [])}
    return None, set()


def save_state(state_file, last_window_processed, seen_keys):
    tmp = state_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"last_window_processed": last_window_processed,
                   "seen_keys": [list(k) for k in seen_keys]}, f)
    os.rename(tmp, state_file)


def reload_seen_from_output(out_file):
    """Belt-and-braces idempotency: rebuild seen_keys from the alerts file itself, which
    is fsync'd on every append, so it survives a crash even if the state file didn't."""
    seen = set()
    if os.path.exists(out_file):
        with open(out_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                seen.add((row["user"], row["src_ip"], row["window_start"]))
    return seen


def run_tick(con, in_dir, out_file, last_window_processed, seen_keys, quiet=False):
    all_files = sorted(glob.glob(os.path.join(in_dir, "window-*.parquet")))
    windows_present = {_window_num(p): p for p in all_files if _window_num(p) is not None}
    if not windows_present:
        return last_window_processed, 0, 0

    new_windows = sorted(w for w in windows_present if last_window_processed is None or w > last_window_processed)
    if not new_windows:
        return last_window_processed, 0, 0

    candidate_windows = set(new_windows)
    lookback = min(new_windows) - 1
    if last_window_processed is not None and lookback in windows_present:
        candidate_windows.add(lookback)  # "re-scan of the previous tick's window boundary"

    files = [windows_present[w] for w in sorted(candidate_windows)]
    file_list_sql = "[" + ", ".join(f"'{f}'" for f in files) + "]"
    rows = con.execute(f"""
        SELECT user, src_ip, (time // {WINDOW_SECONDS}) * {WINDOW_SECONDS} AS window_start,
               COUNT(*) AS failure_count, MAX(ingest_wall_ts) AS last_ingest_wall_ts
        FROM read_parquet({file_list_sql})
        WHERE status = 'failure'
        GROUP BY user, src_ip, window_start
        HAVING COUNT(*) >= {FAILURE_THRESHOLD}
        ORDER BY window_start, user, src_ip
    """).fetchall()

    n_new_alerts = 0
    with open(out_file, "a") as f:
        for user, src_ip, window_start, failure_count, last_ingest_wall_ts in rows:
            key = (user, src_ip, int(window_start))
            if key in seen_keys:
                continue
            record = {
                "user": user, "src_ip": src_ip, "window_start": int(window_start),
                "failure_count": int(failure_count),
                "last_ingest_wall_ts": last_ingest_wall_ts,
                "alert_emit_wall_ts": time.time(),
            }
            f.write(json.dumps(record) + "\n")
            f.flush()
            os.fsync(f.fileno())
            seen_keys.add(key)
            n_new_alerts += 1
            if not quiet:
                print(f"[batch_job] ALERT {user} {src_ip} window={window_start} "
                      f"count={failure_count}", flush=True)

    new_last = max(candidate_windows)
    return new_last, n_new_alerts, len(files)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in-dir", default=DEFAULT_IN_DIR)
    ap.add_argument("--out-file", default=DEFAULT_OUT_FILE)
    ap.add_argument("--state-file", default=DEFAULT_STATE_FILE)
    ap.add_argument("--poll-interval", type=float, default=5.0)
    ap.add_argument("--max-idle-ticks", type=int, default=6,
                     help="auto-exit after this many consecutive ticks with no new files "
                          "(only once at least one window has ever been processed)")
    ap.add_argument("--once", action="store_true", help="run a single tick and exit (smoke/manual use)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out_file), exist_ok=True)
    os.makedirs(os.path.dirname(args.state_file), exist_ok=True)

    last_window_processed, seen_keys = load_state(args.state_file)
    seen_keys |= reload_seen_from_output(args.out_file)

    con = configure_duckdb(duckdb.connect(database=":memory:"))

    idle_ticks = 0
    ever_processed = last_window_processed is not None
    while True:
        last_window_processed, n_new, n_files = run_tick(
            con, args.in_dir, args.out_file, last_window_processed, seen_keys, args.quiet)
        if n_files:
            ever_processed = True
            idle_ticks = 0
            save_state(args.state_file, last_window_processed, seen_keys)
            if not args.quiet:
                print(f"[batch_job] tick: scanned {n_files} file(s), {n_new} new alert(s), "
                      f"last_window_processed={last_window_processed}", flush=True)
        else:
            idle_ticks += 1
            if not args.quiet:
                print(f"[batch_job] tick: idle ({idle_ticks}/{args.max_idle_ticks})", flush=True)

        if args.once:
            break
        if ever_processed and idle_ticks >= args.max_idle_ticks:
            if not args.quiet:
                print("[batch_job] drained (max idle ticks reached), exiting", flush=True)
            break
        time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()

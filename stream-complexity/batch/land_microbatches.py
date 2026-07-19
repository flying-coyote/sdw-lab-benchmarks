"""Batch arm, half 1 of 2: replay events.jsonl into Parquet micro-batch files under
data/batch_in/, one file per 60s of EVENT time, at accelerated wall-clock (configurable
--replay-factor, default 20x — same knob and same default as streaming/producer.py, so
a clean trial's two arms are paced identically).

Landing schedule: a window's file is written once real (accelerated) wall-clock has
caught up to that window's END event-time — i.e. a batch collector can't possibly know
about a window's contents before the window has fully elapsed. Every row in a landed
file gets the SAME `ingest_wall_ts` (the file's landing instant): batch's unit of
"ingest" is the FILE, not the individual event, and that granularity is the honest,
deliberate source of the freshness gap the pre-reg's P4 predicts (batch latency ~=
tick/2 + processing, dominated by batching delay, not per-event processing cost).

Landing is atomic (write to a `.tmp-` name, then os.rename into place) so batch_job.py
can never observe a partially-written file — the standard "atomic landing" pattern for
any file-based micro-batch pipeline.
"""

import argparse
import json
import os
import sys
import time

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # stream-complexity/
sys.path.insert(0, ROOT)
from gen_corpus import WINDOW_SECONDS  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "..", "lib"))
from common import BASE_EPOCH  # noqa: E402

DEFAULT_EVENTS = os.path.join(ROOT, "data", "events.jsonl")
DEFAULT_OUTDIR = os.path.join(ROOT, "data", "batch_in")

SCHEMA = pa.schema([
    ("event_uid", pa.string()),
    ("time", pa.int64()),
    ("class_uid", pa.int32()),
    ("category_uid", pa.int32()),
    ("activity_id", pa.int32()),
    ("type_uid", pa.int32()),
    ("user", pa.string()),
    ("src_ip", pa.string()),
    ("status", pa.string()),
    ("status_id", pa.int32()),
    ("ingest_wall_ts", pa.float64()),   # added HERE at landing time; not in events.jsonl
])


def window_index(t: int) -> int:
    return t // WINDOW_SECONDS


def _write_window_file(out_dir, w, rows, ingest_wall_ts):
    for r in rows:
        r["ingest_wall_ts"] = ingest_wall_ts
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    final_path = os.path.join(out_dir, f"window-{w:08d}.parquet")
    tmp_path = os.path.join(out_dir, f".tmp-window-{w:08d}.parquet")
    pq.write_table(table, tmp_path)
    os.rename(tmp_path, final_path)  # atomic on the same filesystem/dir
    return final_path


def _land(out_dir, w, bucket, replay_start, replay_factor, quiet):
    window_end_event_time = (w + 1) * WINDOW_SECONDS
    target_wall = replay_start + (window_end_event_time - BASE_EPOCH) / replay_factor
    sleep_s = target_wall - time.time()
    if sleep_s > 0:
        time.sleep(sleep_s)
    ingest_wall_ts = time.time()
    path = _write_window_file(out_dir, w, bucket, ingest_wall_ts)
    if not quiet:
        print(f"[land_microbatches] window {w} ({len(bucket)} events) -> {os.path.basename(path)} "
              f"@ t+{ingest_wall_ts - replay_start:.2f}s wall", flush=True)
    return path


def replay(events_path, out_dir, replay_factor, quiet=False, replay_start=None):
    os.makedirs(out_dir, exist_ok=True)
    # `replay_start` should be a SHARED wall-clock anchor passed in by
    # run_clean_trial.sh (same value given to streaming/producer.py), not each
    # script's own `time.time()` — a few hundred ms of independent-clock skew between
    # the two replay processes' own start times would be the same order of magnitude
    # as the streaming arm's whole predicted freshness advantage (pre-reg P4: "<5s"),
    # which would confound measure_latency.py's comparison. Defaults to time.time()
    # only for standalone/manual runs where cross-arm latency isn't being measured.
    if replay_start is None:
        replay_start = time.time()
    current_w = None
    bucket = []
    n_files = 0
    n_events = 0
    with open(events_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            n_events += 1
            w = window_index(e["time"])
            if current_w is None:
                current_w = w
            if w != current_w:
                _land(out_dir, current_w, bucket, replay_start, replay_factor, quiet)
                n_files += 1
                bucket = []
                current_w = w
            bucket.append(e)
    if bucket:
        _land(out_dir, current_w, bucket, replay_start, replay_factor, quiet)
        n_files += 1
    elapsed = time.time() - replay_start
    if not quiet:
        print(f"[land_microbatches] done: {n_events} events -> {n_files} files in {elapsed:.1f}s wall", flush=True)
    return n_files, n_events, elapsed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", default=DEFAULT_EVENTS)
    ap.add_argument("--out-dir", default=DEFAULT_OUTDIR)
    ap.add_argument("--replay-factor", type=float, default=20.0)
    ap.add_argument("--replay-start-epoch", type=float, default=None,
                     help="shared wall-clock anchor (see replay() docstring); omit for a "
                          "standalone run where you don't need cross-arm latency parity")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    replay(args.events, args.out_dir, args.replay_factor, args.quiet, args.replay_start_epoch)


if __name__ == "__main__":
    main()

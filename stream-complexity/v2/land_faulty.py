"""Harness for the v2 batch-side faults B2 and B3: the July batch/land_microbatches.py
pacing and atomic landing (reused by import), with ONE window's file perturbed.

  --hold-window W      B2 late file: W's file is not written at its landing time; it lands
                       (atomically) only after the job's state file shows
                       last_window_processed >= W + 2, i.e. the job has processed the next
                       two windows' files.
  --truncate-window W  B3 truncated file: at W's landing time, the first half of W's Parquet
                       bytes is written straight to the final name (a non-atomic write a
                       reader can observe), and 30 wall-seconds later the complete file
                       replaces it atomically.

Events and every other window land exactly as in July. Harness, not arm.
"""

import argparse
import io
import json
import os
import sys
import threading
import time

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "batch"))
sys.path.insert(0, ROOT)
from land_microbatches import SCHEMA, _write_window_file, window_index  # noqa: E402
from gen_corpus import WINDOW_SECONDS  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "..", "lib"))
from common import BASE_EPOCH  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", default=os.path.join(ROOT, "data", "events.jsonl"))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--state-file", required=True, help="batch job's state file (B2 release check)")
    ap.add_argument("--replay-factor", type=float, default=20.0)
    ap.add_argument("--replay-start-epoch", type=float, required=True)
    ap.add_argument("--hold-window", type=int, default=None)
    ap.add_argument("--truncate-window", type=int, default=None)
    ap.add_argument("--truncate-replace-after-s", type=float, default=30.0)
    ap.add_argument("--log", required=True)
    args = ap.parse_args()
    rs, rf = args.replay_start_epoch, args.replay_factor
    os.makedirs(args.out_dir, exist_ok=True)
    events_log = []

    def note(**kw):
        kw["wall"] = time.time()
        events_log.append(kw)
        with open(args.log, "w") as f:
            json.dump(events_log, f, indent=2)

    held = {}
    threads = []

    def release_held(w, rows):
        while True:
            try:
                s = json.load(open(args.state_file))
                if (s.get("last_window_processed") or -1) >= w + 2:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(0.2)
        _write_window_file(args.out_dir, w, rows, time.time())
        note(action="late_file_landed", window=w)

    def truncated_then_replace(w, rows):
        for r in rows:
            r["ingest_wall_ts"] = time.time()
        buf = io.BytesIO()
        pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), buf)
        data = buf.getvalue()
        final = os.path.join(args.out_dir, f"window-{w:08d}.parquet")
        with open(final, "wb") as f:
            f.write(data[: len(data) // 2])
        note(action="truncated_file_written", window=w, bytes=len(data) // 2, full_bytes=len(data))
        time.sleep(args.truncate_replace_after_s)
        tmp = os.path.join(args.out_dir, f".tmp-window-{w:08d}.parquet")
        with open(tmp, "wb") as f:
            f.write(data)
        os.rename(tmp, final)
        note(action="complete_file_replaced", window=w)

    def land(w, bucket):
        target = rs + ((w + 1) * WINDOW_SECONDS - BASE_EPOCH) / rf
        if target - time.time() > 0:
            time.sleep(target - time.time())
        if w == args.hold_window:
            note(action="file_held_back", window=w)
            t = threading.Thread(target=release_held, args=(w, bucket))
        elif w == args.truncate_window:
            t = threading.Thread(target=truncated_then_replace, args=(w, bucket))
        else:
            _write_window_file(args.out_dir, w, bucket, time.time())
            return
        t.start()
        threads.append(t)

    cur, bucket = None, []
    with open(args.events) as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            w = window_index(e["time"])
            if cur is None:
                cur = w
            if w != cur:
                land(cur, bucket)
                bucket, cur = [], w
            bucket.append(e)
    if bucket:
        land(cur, bucket)
    for t in threads:
        t.join(timeout=600)
    note(action="replay_done")


if __name__ == "__main__":
    main()

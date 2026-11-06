"""STREAM-FRESHNESS lander: replay events.jsonl into Parquet files, one per
--span-seconds of EVENT time (60 = the July cadence, 300 = a buffered collector), at
1x on the shared replay clock.

Differences from batch/land_microbatches.py (harness fix 1 of the pre-reg):
- sleeps toward each file's target in chunks of at most 0.5 s, because one long
  time.sleep overshot by ~3 s on this WSL host in v2;
- logs, per file, target wall time, rename wall time and lag to --lag-log;
- files cover --span-seconds and are named window-{first_window:08d}.parquet, where
  first_window = chunk_start // 60, so batch_fresh.py's window-number parsing still
  works for multi-window files;
- touches <out-dir>/.landed-done after the last file.
Landing stays atomic (.tmp- name, then os.rename).
"""
import argparse
import json
import os
import sys
import time

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from gen_corpus import WINDOW_SECONDS  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "..", "lib"))
from common import BASE_EPOCH  # noqa: E402

SCHEMA = pa.schema([
    ("event_uid", pa.string()), ("time", pa.int64()), ("class_uid", pa.int32()),
    ("category_uid", pa.int32()), ("activity_id", pa.int32()), ("type_uid", pa.int32()),
    ("user", pa.string()), ("src_ip", pa.string()), ("status", pa.string()),
    ("status_id", pa.int32()), ("ingest_wall_ts", pa.float64()),
])


def sleep_until(target):
    while True:
        rem = target - time.time()
        if rem <= 0:
            return
        time.sleep(min(rem, 0.5))


def land(out_dir, chunk, rows, span, replay_start, rf, lag_log):
    first_window = (chunk * span) // WINDOW_SECONDS
    target = replay_start + ((chunk + 1) * span - BASE_EPOCH) / rf
    sleep_until(target)
    ingest = time.time()
    for r in rows:
        r["ingest_wall_ts"] = ingest
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    final = os.path.join(out_dir, f"window-{first_window:08d}.parquet")
    tmp = os.path.join(out_dir, f".tmp-window-{first_window:08d}.parquet")
    pq.write_table(table, tmp)
    os.rename(tmp, final)
    renamed = time.time()
    rec = {"file": os.path.basename(final), "first_window": first_window, "span_s": span,
           "chunk_start": chunk * span, "chunk_end": (chunk + 1) * span, "n_rows": len(rows),
           "target_wall": target, "rename_wall": renamed, "lag_s": round(renamed - target, 4)}
    lag_log.write(json.dumps(rec) + "\n")
    lag_log.flush()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--span-seconds", type=int, choices=[60, 300], default=60)
    ap.add_argument("--replay-factor", type=float, default=1.0)
    ap.add_argument("--replay-start-epoch", type=float, required=True)
    ap.add_argument("--lag-log", required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    span = args.span_seconds
    cur, bucket, n_files = None, [], 0
    with open(args.events) as f, open(args.lag_log, "w") as lag_log:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            c = e["time"] // span
            if cur is None:
                cur = c
            if c != cur:
                land(args.out_dir, cur, bucket, span, args.replay_start_epoch, args.replay_factor, lag_log)
                n_files += 1
                bucket, cur = [], c
            bucket.append(e)
        if bucket:
            land(args.out_dir, cur, bucket, span, args.replay_start_epoch, args.replay_factor, lag_log)
            n_files += 1
    with open(os.path.join(args.out_dir, ".landed-done"), "w") as f:
        f.write(f"{n_files}\n")
    print(f"[land_fresh span={span}] {n_files} files landed", flush=True)


if __name__ == "__main__":
    main()

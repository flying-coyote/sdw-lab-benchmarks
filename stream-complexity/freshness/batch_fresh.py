"""STREAM-FRESHNESS batch job: one DuckDB process running both detections on each new file.

W (windowed): the July batch_job.py query unchanged (>=5 failures per (user, src_ip,
  epoch-aligned 60 s window)), deduped on (user, src_ip, window_start).
I (IOC match): every event whose src_ip is in the IOC list -> one alert per event_uid,
  deduped on event_uid.

Scheduling (harness change for this bench): ticks fire at
  anchor + phase + k * poll   (k = 0, 1, 2, ...)
on the shared replay clock, with chunked sleeps (<= 0.5 s) so long polls neither drift
nor overshoot. run_fresh_trial.sh starts four replicas per poll interval at phases
(r + 0.5) * poll / 4 (deviation D3). The job exits after the first tick that STARTS
after <in-dir>/.landed-done exists, so the final file is always processed.

Window bookkeeping is the July logic: files newer than the last processed window number,
plus a re-scan of the window immediately before the oldest new one when that file exists
(it never does for 300 s files, whose names are multiples of 5).

Stats (--stats-file, rewritten every tick): poll wake-ups, query executions per detection,
ticks that found new files, and process CPU-seconds from os.times().
"""
import argparse
import glob
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from gen_corpus import WINDOW_SECONDS, FAILURE_THRESHOLD  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "..", "lib"))
from common import configure_duckdb  # noqa: E402

import duckdb

WINDOW_RE = re.compile(r"window-(\d+)\.parquet$")


def wnum(p):
    m = WINDOW_RE.search(os.path.basename(p))
    return int(m.group(1)) if m else None


def append(path, rec):
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")
        f.flush()
        os.fsync(f.fileno())


def sleep_until(target):
    while True:
        rem = target - time.time()
        if rem <= 0:
            return
        time.sleep(min(rem, 0.5))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-w", required=True)
    ap.add_argument("--out-i", required=True)
    ap.add_argument("--ioc-file", required=True, help="ioc_ground_truth.json (reads ioc_ips only)")
    ap.add_argument("--poll-interval", type=float, required=True)
    ap.add_argument("--anchor-epoch", type=float, required=True, help="shared replay start")
    ap.add_argument("--phase", type=float, default=0.0)
    ap.add_argument("--stats-file", required=True)
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    with open(args.ioc_file) as f:
        ioc_ips = json.load(f)["ioc_ips"]
    ioc_sql = "(" + ", ".join(f"'{ip}'" for ip in ioc_ips) + ")"
    con = configure_duckdb(duckdb.connect(database=":memory:"))
    seen_w, seen_i = set(), set()
    last = None
    stats = {"label": args.label, "poll_interval_s": args.poll_interval, "phase_s": args.phase,
             "poll_wakeups": 0, "ticks_with_new_files": 0, "queries_w": 0, "queries_i": 0,
             "files_scanned": 0, "alerts_w": 0, "alerts_i": 0}
    done_marker = os.path.join(args.in_dir, ".landed-done")

    k = 0
    first = args.anchor_epoch + args.phase
    now = time.time()
    if now > first:
        k = int((now - first) // args.poll_interval) + 1
    while True:
        tick_at = first + k * args.poll_interval
        sleep_until(tick_at)
        k += 1
        tick_start = time.time()
        done_seen = os.path.exists(done_marker)
        stats["poll_wakeups"] += 1

        present = {wnum(p): p for p in glob.glob(os.path.join(args.in_dir, "window-*.parquet"))
                   if wnum(p) is not None}
        new = sorted(w for w in present if last is None or w > last)
        if new:
            cand = set(new)
            if last is not None and (min(new) - 1) in present:
                cand.add(min(new) - 1)
            files = [present[w] for w in sorted(cand)]
            flist = "[" + ", ".join(f"'{p}'" for p in files) + "]"
            rows_w = con.execute(f"""
                SELECT user, src_ip, (time // {WINDOW_SECONDS}) * {WINDOW_SECONDS} AS window_start,
                       COUNT(*) AS failure_count, MAX(ingest_wall_ts) AS last_ingest_wall_ts
                FROM read_parquet({flist})
                WHERE status = 'failure'
                GROUP BY user, src_ip, window_start
                HAVING COUNT(*) >= {FAILURE_THRESHOLD}
                ORDER BY window_start, user, src_ip
            """).fetchall()
            stats["queries_w"] += 1
            for user, src_ip, ws, cnt, ing in rows_w:
                key = (user, src_ip, int(ws))
                if key in seen_w:
                    continue
                seen_w.add(key)
                append(args.out_w, {"user": user, "src_ip": src_ip, "window_start": int(ws),
                                    "failure_count": int(cnt), "last_ingest_wall_ts": ing,
                                    "alert_emit_wall_ts": time.time()})
                stats["alerts_w"] += 1
            rows_i = con.execute(f"""
                SELECT event_uid, user, src_ip, time, ingest_wall_ts
                FROM read_parquet({flist})
                WHERE src_ip IN {ioc_sql}
                ORDER BY time, event_uid
            """).fetchall()
            stats["queries_i"] += 1
            for uid, user, src_ip, t, ing in rows_i:
                if uid in seen_i:
                    continue
                seen_i.add(uid)
                append(args.out_i, {"event_uid": uid, "user": user, "src_ip": src_ip, "time": int(t),
                                    "file_ingest_wall_ts": ing, "alert_emit_wall_ts": time.time()})
                stats["alerts_i"] += 1
            last = max(cand)
            stats["ticks_with_new_files"] += 1
            stats["files_scanned"] += len(files)
        else:
            # make sure an empty output file exists even before the first alert
            for p in (args.out_w, args.out_i):
                if not os.path.exists(p):
                    open(p, "a").close()

        t = os.times()
        stats["cpu_user_s"] = round(t.user, 3)
        stats["cpu_system_s"] = round(t.system, 3)
        stats["cpu_total_s"] = round(t.user + t.system, 3)
        stats["last_tick_wall"] = tick_start
        tmp = args.stats_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(stats, f, indent=2, sort_keys=True)
        os.rename(tmp, args.stats_file)
        if done_seen:
            break


if __name__ == "__main__":
    main()

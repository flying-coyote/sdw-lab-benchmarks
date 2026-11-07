"""R arm sink adapter (STREAM-COMPLEXITY v3): read the `alerts` materialized view through
the `alerts_sub` subscription with a subscription cursor and append each inserted alert to
the R arm's alerts file, stamping `alert_emit_wall_ts` at read time. The RisingWave
counterpart of feldera/drain_alerts.py and streaming/consume_alerts.py, counted as the R
arm's sink adapter in moving parts.

Same dedup contract as feldera/drain_alerts.py: one output row per (user, src_ip,
window_start); raw inserts, duplicate inserts and non-insert ops are counted in
--state-file so engine-level duplicates stay visible even though the file is deduped.
With EMIT ON WINDOW CLOSE a Delete / Update op should never appear; a count above zero
means the fallback (score final state per key) is needed and is reported as such.

Reconnect contract: on connection loss (container kill) the reader reconnects and
re-declares its cursor `SINCE <last rw_timestamp it had read>` so the subscription's
retained log is resumed, not re-read from the start. A row with the same key AND the same
rw_timestamp as one already read is the adapter's own resume overlap (`n_resume_overlap`);
the same key with a DIFFERENT rw_timestamp is an engine re-emission
(`n_duplicate_inserts`, the raw engine duplicate count R1 scores).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import psycopg

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from compare_answers import canonical_window_start  # noqa: E402


def epoch(v):
    return int(v.timestamp()) if isinstance(v, datetime) else canonical_window_start(v)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", default="host=localhost port=14566 user=root dbname=dev connect_timeout=3")
    ap.add_argument("--subscription", default="alerts_sub")
    ap.add_argument("--out-file", required=True)
    ap.add_argument("--state-file", required=True)
    ap.add_argument("--stop-file", required=True)
    ap.add_argument("--batch", type=int, default=1,
                    help="FETCH n with a timeout waits for n rows or the timeout, so 1 returns each alert on arrival")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    st = {"connected": False, "n_connects": 0, "n_raw_inserts": 0, "n_written": 0,
          "n_duplicate_inserts": 0, "n_resume_overlap": 0, "n_non_insert_ops": 0,
          "ops_seen": {}, "last_rw_timestamp": None, "last_row_wall": None,
          "connect_walls": [], "disconnects": []}
    seen = {}  # key -> set of rw_timestamps

    def save():
        tmp = args.state_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(st, f)
        os.replace(tmp, args.state_file)

    def handle(row):
        op = row.get("op")
        st["ops_seen"][op] = st["ops_seen"].get(op, 0) + 1
        rts = row.get("rw_timestamp")
        if rts is not None:
            st["last_rw_timestamp"] = max(rts, st["last_rw_timestamp"] or 0)
        if op != "Insert":
            st["n_non_insert_ops"] += 1
            return
        key = (row["user"], row["src_ip"], epoch(row["window_start"]))
        if key in seen:
            if rts in seen[key]:
                st["n_resume_overlap"] += 1
            else:
                st["n_raw_inserts"] += 1
                st["n_duplicate_inserts"] += 1
                seen[key].add(rts)
            return
        st["n_raw_inserts"] += 1
        seen[key] = {rts}
        out = {"user": row["user"], "src_ip": row["src_ip"], "window_start": key[2],
               "window_end": epoch(row["window_end"]), "failure_count": row["failure_count"],
               "last_ingest_wall_ts": row["last_ingest_wall_ts"], "rw_timestamp": rts,
               "alert_emit_wall_ts": time.time()}
        with open(args.out_file, "a") as f:
            f.write(json.dumps(out) + "\n")
            f.flush()
            os.fsync(f.fileno())
        st["n_written"] += 1
        st["last_row_wall"] = time.time()

    os.makedirs(os.path.dirname(os.path.abspath(args.out_file)), exist_ok=True)
    save()
    while True:
        if os.path.exists(args.stop_file):
            last = st["last_row_wall"] or 0
            if time.time() - last >= 10:
                break
        try:
            with psycopg.connect(args.dsn, autocommit=True) as conn:
                since = f"{st['last_rw_timestamp']}" if st["last_rw_timestamp"] else "begin()"
                conn.execute(f"DECLARE cur SUBSCRIPTION CURSOR FOR {args.subscription} SINCE {since}")
                st["connected"] = True
                st["n_connects"] += 1
                st["connect_walls"].append(time.time())
                save()
                while True:
                    cur = conn.execute(f"FETCH {args.batch} FROM cur WITH (timeout = '1s')")
                    cols = [d.name for d in cur.description]
                    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                    for r in rows:
                        handle(r)
                    if rows:
                        save()
                    if os.path.exists(args.stop_file):
                        if time.time() - (st["last_row_wall"] or 0) >= 10:
                            break
        except psycopg.Error as e:
            if st["connected"]:
                st["disconnects"].append({"wall": time.time(), "error": str(e)[:200]})
            st["connected"] = False
            save()
            time.sleep(0.5)
            continue
        break
    st["connected"] = False
    save()
    if not args.quiet:
        print(f"[rw drain_alerts] done: {st['n_written']} alerts written, raw inserts "
              f"{st['n_raw_inserts']}, duplicate inserts {st['n_duplicate_inserts']}, "
              f"resume overlap {st['n_resume_overlap']}, non-insert ops {st['n_non_insert_ops']}",
              flush=True)


if __name__ == "__main__":
    main()

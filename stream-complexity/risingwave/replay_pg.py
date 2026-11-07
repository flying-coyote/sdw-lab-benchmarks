"""R arm harness (STREAM-COMPLEXITY v3): replay events.jsonl into RisingWave's auth_events
table by INSERT over the PostgreSQL wire protocol, with the SAME pacing as the July
streaming/producer.py (1-second event-time buckets, target_wall = replay_start +
(t - BASE_EPOCH) / replay_factor, shared --replay-start-epoch). One multi-row INSERT per
bucket. Harness, not arm: excluded from config LOC and moving parts.

Fault behaviour (pre-reg R1 rewind rule): every acknowledged INSERT advances `last_acked_uid`.
On the first failure the replayer PAUSES and waits for the operator's rewind instruction in
--control-file ({"resend_after_uid": "<event_uid>"}), then re-sends every event with a larger
event_uid (catch-up back-to-back, then live pacing). It never picks the rewind point itself.
"""
import argparse, itertools, json, os, sys, time
import psycopg

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "..", "lib"))
from common import BASE_EPOCH  # noqa: E402

COLS = ["event_uid", "time", "class_uid", "category_uid", "activity_id", "type_uid", "user",
        "src_ip", "status", "status_id", "ingest_wall_ts"]
SQL_COLS = ", ".join(f'"{c}"' for c in COLS)


def write_state(path, st):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f)
    os.replace(tmp, path)


def connect(dsn):
    while True:
        try:
            return psycopg.connect(dsn, autocommit=True)
        except psycopg.OperationalError:
            time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", default=os.path.join(ROOT, "data", "events.jsonl"))
    ap.add_argument("--dsn", default="host=localhost port=14566 user=root dbname=dev")
    ap.add_argument("--replay-factor", type=float, default=20.0)
    ap.add_argument("--replay-start-epoch", type=float, default=None)
    ap.add_argument("--state-file", required=True)
    ap.add_argument("--control-file", required=True)
    args = ap.parse_args()

    with open(args.events) as f:
        evs = [json.loads(l) for l in f if l.strip()]
    buckets = [(t, list(g)) for t, g in itertools.groupby(evs, key=lambda e: e["time"])]
    conn = connect(args.dsn)
    replay_start = args.replay_start_epoch or time.time()
    st = {"last_acked_uid": None, "last_acked_time": None, "paused": False, "n_inserts": 0,
          "n_events_sent": 0, "failures": [], "rewinds": [], "done": False}
    write_state(args.state_file, st)
    i, skip_upto = 0, None
    while i < len(buckets):
        t, group = buckets[i]
        if skip_upto is not None:
            group = [e for e in group if e["event_uid"] > skip_upto]
            if not group:
                i += 1
                continue
        target = replay_start + (t - BASE_EPOCH) / args.replay_factor
        if target > time.time():
            time.sleep(target - time.time())
        now = time.time()
        rows = []
        for e in group:
            rows.append(tuple(e.get(c) for c in COLS[:10]) + (now,))
        ph = ", ".join(["(" + ", ".join(["%s"] * len(COLS)) + ")"] * len(rows))
        flat = [v for r in rows for v in r]
        try:
            conn.execute(f"INSERT INTO auth_events ({SQL_COLS}) VALUES {ph}", flat)
            st["last_acked_uid"] = group[-1]["event_uid"]; st["last_acked_time"] = t
            st["n_inserts"] += 1; st["n_events_sent"] += len(group)
            if st["rewinds"] and len(st["rewinds"][-1].setdefault("first_acks", [])) < 5:
                st["rewinds"][-1]["first_acks"].append([time.time(), group[0]["event_uid"], group[-1]["event_uid"]])
            if st["n_inserts"] % 20 == 0:
                write_state(args.state_file, st)
            i += 1
            continue
        except psycopg.Error as e:
            err = f"{type(e).__name__}: {e}"[:300]
        st["paused"] = True
        st["failures"].append({"event_time": t, "wall": now, "error": err})
        write_state(args.state_file, st)
        print(f"[replay_pg] insert failed at t={t}: {err}; paused for rewind", flush=True)
        if os.path.exists(args.control_file):
            os.remove(args.control_file)
        while not os.path.exists(args.control_file):
            time.sleep(0.2)
        with open(args.control_file) as f:
            skip_upto = json.load(f)["resend_after_uid"]
        os.remove(args.control_file)
        i = 0  # rescan from the start; buckets at or below the rewind uid are skipped
        st["paused"] = False
        st["rewinds"].append({"resend_after_uid": skip_upto, "wall": time.time(), "failed_at": t})
        write_state(args.state_file, st)
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        conn = connect(args.dsn)
        print(f"[replay_pg] re-sending events after {skip_upto}", flush=True)
    st["done"] = True; st["elapsed_s"] = round(time.time() - replay_start, 2)
    write_state(args.state_file, st)
    print(f"[replay_pg] done: {st['n_events_sent']} events in {st['n_inserts']} inserts", flush=True)


if __name__ == "__main__":
    main()

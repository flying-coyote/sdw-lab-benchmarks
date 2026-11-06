"""STREAM-FRESHNESS: drain the streaming arm's IOC topic (smx-ioc-alerts) to a jsonl file,
stamping alert_emit_wall_ts on receipt and deduping on event_uid. Same stop-file pattern as
streaming/consume_alerts.py: the trial runner touches --stop-file once the topic's end
offset is stable, and the consumer exits after 10 s of idleness past that point.
"""
import argparse
import json
import os
import time

from confluent_kafka import Consumer


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bootstrap", default="localhost:19094")
    ap.add_argument("--topic", default="smx-ioc-alerts")
    ap.add_argument("--group-id", default="smx-fresh-ioc-drain")
    ap.add_argument("--out-file", required=True)
    ap.add_argument("--stop-file", required=True)
    ap.add_argument("--idle-timeout", type=float, default=100000.0)
    args = ap.parse_args()

    seen = set()
    if os.path.exists(args.out_file):
        with open(args.out_file) as f:
            seen = {json.loads(line)["event_uid"] for line in f if line.strip()}
    open(args.out_file, "a").close()
    c = Consumer({"bootstrap.servers": args.bootstrap, "group.id": args.group_id,
                  "auto.offset.reset": "earliest", "enable.auto.commit": True})
    c.subscribe([args.topic])
    idle, n_dup = 0.0, 0
    try:
        while True:
            msg = c.poll(1.0)
            if msg is None:
                idle += 1.0
                if os.path.exists(args.stop_file) and idle >= 10.0:
                    break
                if idle >= args.idle_timeout:
                    break
                continue
            if msg.error():
                print(f"[consume_ioc] error: {msg.error()}", flush=True)
                continue
            idle = 0.0
            emit = time.time()
            row = json.loads(msg.value())
            if row["event_uid"] in seen:
                n_dup += 1
                continue
            seen.add(row["event_uid"])
            rec = {"event_uid": row["event_uid"], "user": row["user"], "src_ip": row["src_ip"],
                   "time": int(row["time"]), "ingest_wall_ts": row.get("ingest_wall_ts"),
                   "alert_emit_wall_ts": emit}
            with open(args.out_file, "a") as f:
                f.write(json.dumps(rec) + "\n")
                f.flush()
                os.fsync(f.fileno())
    finally:
        c.close()
    print(f"[consume_ioc] wrote {len(seen)} alerts, {n_dup} duplicates dropped", flush=True)


if __name__ == "__main__":
    main()

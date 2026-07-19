"""Streaming arm, part 3: the "small consumer script" the task brief explicitly blesses
as the sink's honest moving part ("sink via a topic + a small consumer script is fine
— count it as a moving part honestly"). Reads Flink's alert output from Kafka topic
`smx-alerts` and appends to results/alerts-stream.jsonl, stamping `alert_emit_wall_ts`
at the wall-clock instant each alert is actually read here — this script IS "the sink"
from an operator's point of view, the streaming-arm mirror of batch_job.py stamping
its own alert_emit_wall_ts at append time.

Dedup on (user, src_ip, canonical window_start), same key shape compare_answers.py
uses: Flink's Kafka sink here is configured for at-least-once (no transactional
producer — that's extra config surface this bench doesn't need to carry), so a
checkpoint-restore after the taskmanager-kill fault test can legitimately re-deliver
an already-emitted alert. Deduping here gives compare_answers.py's steady-state
answer-equality check (pre-reg P5) a fair, symmetric contract with the batch arm's own
idempotency; faults/run_faults.py inspects raw redelivery separately as part of the
fault-recovery measure, not here.
"""

import argparse
import json
import os
import sys
import time

from confluent_kafka import Consumer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from compare_answers import canonical_window_start  # noqa: E402

DEFAULT_BOOTSTRAP = "localhost:19094"
DEFAULT_TOPIC = "smx-alerts"
DEFAULT_OUT_FILE = os.path.join(ROOT, "results", "alerts-stream.jsonl")
DEFAULT_STATE_FILE = os.path.join(ROOT, "results", ".stream_consumer_state.json")


def load_seen(state_file, out_file):
    seen = set()
    if os.path.exists(state_file):
        with open(state_file) as f:
            seen |= {tuple(k) for k in json.load(f).get("seen_keys", [])}
    if os.path.exists(out_file):
        with open(out_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                seen.add((row["user"], row["src_ip"], canonical_window_start(row["window_start"])))
    return seen


def save_seen(state_file, seen):
    tmp = state_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"seen_keys": [list(k) for k in seen]}, f)
    os.rename(tmp, state_file)


def consume(bootstrap, topic, out_file, state_file, group_id, idle_timeout, quiet=False):
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    seen = load_seen(state_file, out_file)

    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    })
    consumer.subscribe([topic])

    n_written = 0
    n_duplicate = 0
    idle_elapsed = 0.0
    poll_s = 1.0
    try:
        while True:
            msg = consumer.poll(poll_s)
            if msg is None:
                idle_elapsed += poll_s
                if idle_elapsed >= idle_timeout:
                    break
                continue
            if msg.error():
                if not quiet:
                    print(f"[consume_alerts] consumer error: {msg.error()}", flush=True)
                continue
            idle_elapsed = 0.0
            row = json.loads(msg.value())
            key = (row["user"], row["src_ip"], canonical_window_start(row["window_start"]))
            if key in seen:
                n_duplicate += 1
                continue
            record = {
                "user": row["user"],
                "src_ip": row["src_ip"],
                "window_start": row["window_start"],
                "window_end": row.get("window_end"),
                "failure_count": row["failure_count"],
                "last_ingest_wall_ts": row.get("last_ingest_wall_ts"),
                "alert_emit_wall_ts": time.time(),
            }
            with open(out_file, "a") as f:
                f.write(json.dumps(record) + "\n")
                f.flush()
                os.fsync(f.fileno())
            seen.add(key)
            save_seen(state_file, seen)
            n_written += 1
            if not quiet:
                print(f"[consume_alerts] ALERT {row['user']} {row['src_ip']} "
                      f"window={row['window_start']} count={row['failure_count']}", flush=True)
    finally:
        consumer.close()

    if not quiet:
        print(f"[consume_alerts] done: {n_written} alerts written, {n_duplicate} duplicate "
              f"redeliveries skipped -> {out_file}", flush=True)
    return n_written, n_duplicate


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bootstrap", default=DEFAULT_BOOTSTRAP)
    ap.add_argument("--topic", default=DEFAULT_TOPIC)
    ap.add_argument("--out-file", default=DEFAULT_OUT_FILE)
    ap.add_argument("--state-file", default=DEFAULT_STATE_FILE)
    ap.add_argument("--group-id", default="smx-alert-consumer")
    ap.add_argument("--idle-timeout", type=float, default=30.0,
                     help="auto-exit after this many seconds with no new alert messages")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    consume(args.bootstrap, args.topic, args.out_file, args.state_file,
             args.group_id, args.idle_timeout, args.quiet)


if __name__ == "__main__":
    main()

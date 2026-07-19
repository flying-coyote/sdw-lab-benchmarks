"""Streaming arm, part 1: replay events.jsonl into Kafka topic `smx-auth`, at the same
accelerated event-time pace as batch/land_microbatches.py (same --replay-factor knob,
same default 20x — the two arms must be paced identically for the freshness
comparison in Measure 4 to mean anything).

Unlike the batch lander (which groups a whole 60s window before it can "land"
anything), Kafka is a per-EVENT sink: each event is produced the instant its own
accelerated event-time arrives, stamped with `ingest_wall_ts` = the real wall-clock
time it was actually handed to the producer. That per-event vs per-file ingest
granularity is itself part of what this bench is measuring, not an implementation
detail to paper over — see batch/land_microbatches.py's docstring for the other half
of that asymmetry.

Pacing is bucketed by 1-second EVENT-time buckets (not one sleep per event — with
500k events that would dominate wall-clock with sleep-call overhead): all events that
share an event-time second are produced back-to-back, then the producer sleeps until
the next second's accelerated wall-clock instant.
"""

import argparse
import itertools
import json
import os
import sys
import time

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "..", "lib"))
from common import BASE_EPOCH  # noqa: E402

DEFAULT_EVENTS = os.path.join(ROOT, "data", "events.jsonl")
DEFAULT_BOOTSTRAP = "localhost:19094"   # host-mapped PLAINTEXT_HOST listener (see docker-compose.yml)
TOPIC = "smx-auth"


def ensure_topic(bootstrap, topic, partitions=1, replication=1):
    admin = AdminClient({"bootstrap.servers": bootstrap})
    existing = admin.list_topics(timeout=10).topics
    if topic in existing:
        return
    fs = admin.create_topics([NewTopic(topic, num_partitions=partitions, replication_factor=replication)])
    for t, f in fs.items():
        try:
            f.result()
        except Exception as e:  # noqa: BLE001 - topic-exists races are fine, anything else re-raises
            if "already exists" not in str(e).lower():
                raise


def replay(events_path, bootstrap, replay_factor, quiet=False, replay_start=None):
    producer = Producer({"bootstrap.servers": bootstrap, "linger.ms": 5, "queue.buffering.max.messages": 200000})
    ensure_topic(bootstrap, TOPIC)

    # See batch/land_microbatches.py's replay() docstring: `replay_start` should be a
    # SHARED wall-clock anchor from run_clean_trial.sh, the same value given to the
    # batch lander, so the two arms' freshness measurements share one time origin.
    if replay_start is None:
        replay_start = time.time()
    n_events = 0
    errors = []

    def delivery_cb(err, msg):
        if err is not None:
            errors.append(str(err))

    def bucket_key(e):
        return e["time"]

    with open(events_path) as f:
        # group consecutive events (file is time-sorted) by whole event-time second
        line_iter = (json.loads(line) for line in f if line.strip())
        for t, group in itertools.groupby(line_iter, key=bucket_key):
            target_wall = replay_start + (t - BASE_EPOCH) / replay_factor
            sleep_s = target_wall - time.time()
            if sleep_s > 0:
                time.sleep(sleep_s)
            ingest_wall_ts = time.time()
            for e in group:
                e["ingest_wall_ts"] = ingest_wall_ts
                producer.produce(TOPIC, value=json.dumps(e).encode("utf-8"),
                                  key=f'{e["user"]}|{e["src_ip"]}'.encode("utf-8"),
                                  callback=delivery_cb)
                n_events += 1
            producer.poll(0)  # service delivery callbacks without blocking the pacing loop

    producer.flush(30)
    elapsed = time.time() - replay_start
    if not quiet:
        print(f"[producer] done: {n_events} events -> topic={TOPIC} in {elapsed:.1f}s wall "
              f"({len(errors)} delivery errors)", flush=True)
    if errors and not quiet:
        for e in errors[:5]:
            print(f"[producer] delivery error: {e}", flush=True)
    return n_events, elapsed, errors


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", default=DEFAULT_EVENTS)
    ap.add_argument("--bootstrap", default=DEFAULT_BOOTSTRAP)
    ap.add_argument("--replay-factor", type=float, default=20.0)
    ap.add_argument("--replay-start-epoch", type=float, default=None,
                     help="shared wall-clock anchor (see replay() docstring); omit for a "
                          "standalone run where you don't need cross-arm latency parity")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    replay(args.events, args.bootstrap, args.replay_factor, args.quiet, args.replay_start_epoch)


if __name__ == "__main__":
    main()

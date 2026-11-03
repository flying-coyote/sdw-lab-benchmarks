"""F arm harness (STREAM-COMPLEXITY v2): replay events.jsonl into the Feldera pipeline's
HTTP ingress endpoint for table auth_events, with the SAME pacing as the July
streaming/producer.py (1-second event-time buckets, target_wall = replay_start +
(t - BASE_EPOCH) / replay_factor, shared --replay-start-epoch).

Harness, not arm: excluded from config LOC and moving parts, like producer.py.

Fault behaviour (pre-reg F1/F2 rewind rule): every bucket POST that returns 2xx advances
`last_acked` (the event time of the newest acknowledged bucket), written to --state-file.
On the first failed POST the replayer PAUSES and waits for the operator's rewind
instruction in --control-file ({"rewind_to": <epoch second>}). It then re-sends every
bucket from rewind_to onward; buckets whose paced wall time is already past go out
back-to-back (catch-up to the current replay position), after which live pacing resumes.
The replayer never decides the rewind point itself.
"""

import argparse
import itertools
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "..", "lib"))
from common import BASE_EPOCH  # noqa: E402


def write_state(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", default=os.path.join(ROOT, "data", "events.jsonl"))
    ap.add_argument("--url", default="http://localhost:18080")
    ap.add_argument("--pipeline", default="smx-detect")
    ap.add_argument("--replay-factor", type=float, default=20.0)
    ap.add_argument("--replay-start-epoch", type=float, default=None)
    ap.add_argument("--state-file", required=True)
    ap.add_argument("--control-file", required=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    with open(args.events) as f:
        evs = (json.loads(line) for line in f if line.strip())
        buckets = [(t, list(g)) for t, g in itertools.groupby(evs, key=lambda e: e["time"])]

    ingress = (f"{args.url}/v0/pipelines/{args.pipeline}/ingress/auth_events"
               "?format=json&update_format=raw")
    sess = requests.Session()
    replay_start = args.replay_start_epoch or time.time()
    state = {"last_acked": None, "paused": False, "n_posts": 0, "n_events_sent": 0,
             "failures": [], "rewinds": [], "done": False}
    write_state(args.state_file, state)

    i = 0
    while i < len(buckets):
        t, group = buckets[i]
        target_wall = replay_start + (t - BASE_EPOCH) / args.replay_factor
        sleep_s = target_wall - time.time()
        if sleep_s > 0:
            time.sleep(sleep_s)
        now = time.time()
        body = "\n".join(json.dumps(dict(e, ingest_wall_ts=now)) for e in group)
        ok, err = False, None
        try:
            r = sess.post(ingress, data=body.encode(), timeout=10)
            ok = 200 <= r.status_code < 300
            err = None if ok else f"HTTP {r.status_code}: {r.text[:300]}"
        except requests.RequestException as e:
            err = f"{type(e).__name__}: {e}"[:300]
        if ok:
            state["last_acked"] = t
            state["n_posts"] += 1
            state["n_events_sent"] += len(group)
            if state["n_posts"] % 20 == 0:
                write_state(args.state_file, state)
            i += 1
            continue
        # send failure: pause, wait for the operator's rewind point
        state["paused"] = True
        state["failures"].append({"event_time": t, "wall": now, "error": err})
        write_state(args.state_file, state)
        if not args.quiet:
            print(f"[replay_http] send failed at t={t}: {err}; paused for rewind", flush=True)
        if os.path.exists(args.control_file):
            os.remove(args.control_file)
        while not os.path.exists(args.control_file):
            time.sleep(0.2)
        with open(args.control_file) as f:
            rewind_to = int(json.load(f)["rewind_to"])
        os.remove(args.control_file)
        i = next((k for k, (bt, _) in enumerate(buckets) if bt >= rewind_to), len(buckets))
        state["paused"] = False
        state["rewinds"].append({"rewind_to": rewind_to, "wall": time.time(),
                                 "failed_at": t})
        write_state(args.state_file, state)
        if not args.quiet:
            print(f"[replay_http] rewinding to {rewind_to}", flush=True)

    state["done"] = True
    state["elapsed_s"] = round(time.time() - replay_start, 2)
    write_state(args.state_file, state)
    if not args.quiet:
        print(f"[replay_http] done: {state['n_events_sent']} events sent "
              f"({state['n_posts']} posts) in {state['elapsed_s']}s", flush=True)


if __name__ == "__main__":
    main()

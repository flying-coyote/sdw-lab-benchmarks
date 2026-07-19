"""PRE-REG-stream-complexity-2026-07-19.md corpus generator.

Deterministic, seeded (CLI --seed, default 20260719 — the pre-reg's freeze date,
not `lib.common.MASTER_SEED`; this bench's whole contract is "seed controls the
run" so the seed is the single source of truth, not offset against the
cross-bench master seed) OCSF-shaped authentication corpus for the batch-vs-
streaming operational-complexity bench. No `datetime.now()`, no unseeded
randomness — a re-run with the same seed reproduces `events.jsonl` and
`ground_truth.json` byte-for-byte (see `--check`).

Shape (flattened OCSF Authentication, class_uid 3002 confirmed against
schema.ocsf.io/1.8.0, category_uid 3 = IAM, activity_id 1 = Logon, so
type_uid = class_uid*100+activity_id = 300201 — matching the convention used
elsewhere in this repo, e.g. pipeline-normalization-fidelity/gen_corpus.py's
CLASS_UID table). Kept FLAT (not nested `user: {name: ...}` / `src_endpoint:
{ip: ...}`) because both engines under test (DuckDB SQL and Flink SQL) need a
flat schema to define cheaply, and the pre-reg's own field list ("time, user,
src_ip, status, class_uid") is already flat — this is "OCSF-shaped", not a
strict schema-validated OCSF record.

Ground truth: computed by an INDEPENDENT reference implementation (plain
Python dict grouping below), never by importing the batch DuckDB SQL or the
Flink SQL — so a bug shared between the corpus generator and a detection arm
can't silently cancel out. Windows are tumbling and EPOCH-aligned
(window_start = (time // 60) * 60, not corpus-start-aligned), because that is
what Flink's TUMBLE table-valued function does by default for a TIMESTAMP
column with no declared OFFSET, and it's what batch_job.py's DuckDB query
does too — all three (ground truth, DuckDB, Flink SQL) MUST agree on this
grid or the answer-equality gate (pre-reg P5) is unfalsifiable-by-construction
noise instead of a real check. `lib.common.BASE_EPOCH` (2026-01-01T00:00:00Z)
is itself minute-aligned (1_767_225_600 / 60 is an integer), so window
boundaries land on tidy corpus-relative offsets too.

--limit scaling (the smoke-test knob; the task spec named `--limit` for a
~20k-event smoke corpus but did not fix its semantics, so this is a stated
design decision, not a silent guess): replay wall-clock time is governed by
the corpus's EVENT-TIME SPAN divided by the replay factor, not by event
count. Shrinking event count alone while keeping the full 7200s span would
not speed up a smoke replay at all, just make it sparser. So --limit scales
event count AND span together (same event density, e.g. ~69/s), with a
5-minute (300s) floor so there's always room for a handful of distinct
60s tumbling windows even at very small --limit values. Burst/near-miss
counts and background-population sizes scale the same way, each floored at a
sane minimum so a small corpus still exercises every code path.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from common import BASE_EPOCH  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- OCSF Authentication (class_uid 3002) constants -------------------------------------
CLASS_UID = 3002
CATEGORY_UID = 3          # Identity & Access Management
ACTIVITY_ID_LOGON = 1
TYPE_UID = CLASS_UID * 100 + ACTIVITY_ID_LOGON
STATUS_ID = {"success": 1, "failure": 2}   # OCSF generic status_id enum (1=Success, 2=Failure)

WINDOW_SECONDS = 60          # frozen by the pre-reg's detection semantics — NOT a --limit knob
FAILURE_THRESHOLD = 5        # "≥5 failures per (user, src_ip) in a 60s window"

# ---- Full-scale (unscaled) corpus shape -------------------------------------------------
N_EVENTS_FULL = 500_000
SPAN_SECONDS_FULL = 7200            # ~2h simulated span
N_TRUE_BURSTS_FULL = 30             # planted (user, src_ip) brute-force bursts, MUST alert
N_NEAR_MISS_FULL = 30               # planted 4-failure pairs, MUST NOT alert
N_BG_USERS_FULL = 2000
N_BG_IPS_FULL = 1200
N_ATTACKER_IPS_FULL = 20            # distinct src_ips used only by planted true bursts

BG_FAILURE_RATE = 0.03              # background auth failures (typo-class noise)
BG_ROAM_RATE = 0.10                 # probability a background login is NOT from the home IP


def scaled_params(limit):
    """Derive every corpus-shape knob from --limit by a constant scale factor, so a
    smaller corpus keeps the same event density / burst richness instead of just
    thinning out a fixed 2h span. See module docstring for why span must scale too."""
    if limit is None:
        n_events = N_EVENTS_FULL
        scale = 1.0
    else:
        n_events = int(limit)
        scale = n_events / N_EVENTS_FULL
    span_seconds = max(900, round(SPAN_SECONDS_FULL * scale))  # floor: >=15 windows, comfortably
    # more than the >=3+3 minimum true/near-miss bursts below ever need (13 usable after the
    # first/last-window edge exclusion)
    n_true_bursts = max(3, round(N_TRUE_BURSTS_FULL * scale))
    n_near_miss = max(3, round(N_NEAR_MISS_FULL * scale))
    n_bg_users = max(50, round(N_BG_USERS_FULL * scale))
    n_bg_ips = max(25, round(N_BG_IPS_FULL * scale))
    n_attacker_ips = max(5, round(N_ATTACKER_IPS_FULL * scale))
    return {
        "n_events": n_events, "scale": scale, "span_seconds": span_seconds,
        "n_true_bursts": n_true_bursts, "n_near_miss": n_near_miss,
        "n_bg_users": n_bg_users, "n_bg_ips": n_bg_ips, "n_attacker_ips": n_attacker_ips,
    }


def _windows_available(span_seconds):
    """Usable tumbling-window indices: excludes window 0 (no run-up) and the LAST TWO
    windows, not just the last one. One trailing window of buffer is not enough for the
    streaming arm: Flink's watermark only advances on a later event's arrival, so a
    burst planted in the second-to-last window depends on the final window containing
    at least one event within the 2s bounded-out-of-orderness margin to ever CLOSE and
    fire — true in expectation at this corpus's event density but not guaranteed. A
    two-window trailing buffer (~120s of background traffic after any planted burst)
    removes that edge case with comfortable margin instead of relying on probability."""
    n_windows = span_seconds // WINDOW_SECONDS
    if n_windows < 5:
        raise ValueError(f"span_seconds={span_seconds} yields only {n_windows} windows; need >=5")
    return list(range(1, n_windows - 2))


def build_corpus(seed: int, limit):
    import random
    p = scaled_params(limit)
    rng = random.Random(seed)  # this bench's seed is the sole determinism source (see docstring)

    bg_users = [f"user{i:05d}" for i in range(p["n_bg_users"])]
    bg_ips = [f"10.{(i // 250) % 256}.{(i // 5) % 256}.{(i * 7 + 11) % 250 + 1}"
              for i in range(p["n_bg_ips"])]
    attacker_ips = [f"198.51.100.{i % 250 + 1}" if i < 250 else f"203.0.113.{i % 250 + 1}"
                    for i in range(p["n_attacker_ips"])]
    home_ip = {u: rng.choice(bg_ips) for u in bg_users}

    windows = _windows_available(p["span_seconds"])
    rng.shuffle(windows)
    if len(windows) < p["n_true_bursts"] + p["n_near_miss"]:
        raise ValueError("not enough distinct windows for the requested burst/near-miss counts "
                          f"(have {len(windows)}, need {p['n_true_bursts'] + p['n_near_miss']})")

    used_keys = set()
    planted_true = []
    planted_near_miss = []
    events = []
    uid_counter = [0]

    def next_uid():
        uid_counter[0] += 1
        return f"e-{uid_counter[0]:08d}"

    def make_event(t, user, src_ip, status):
        return {
            "event_uid": next_uid(),
            "time": int(t),
            "class_uid": CLASS_UID,
            "category_uid": CATEGORY_UID,
            "activity_id": ACTIVITY_ID_LOGON,
            "type_uid": TYPE_UID,
            "user": user,
            "src_ip": src_ip,
            "status": status,
            "status_id": STATUS_ID[status],
        }

    # ---- planted TRUE brute-force bursts (>=5 failures in one 60s window) ----
    window_iter = iter(windows)
    for _ in range(p["n_true_bursts"]):
        w = next(window_iter)
        window_start = BASE_EPOCH + w * WINDOW_SECONDS
        user = rng.choice(bg_users)          # attacker targets a real background user
        src_ip = rng.choice(attacker_ips)
        key = (user, src_ip)
        while key in used_keys:              # keep (user, src_ip) pairs disjoint across bursts
            user = rng.choice(bg_users)
            key = (user, src_ip)
        used_keys.add(key)
        burst_size = rng.randint(5, 8)
        offsets = rng.sample(range(2, 56), burst_size)   # >=2s margin from either window edge
        for off in sorted(offsets):
            events.append(make_event(window_start + off, user, src_ip, "failure"))
        planted_true.append({"user": user, "src_ip": src_ip, "window_start": window_start,
                              "failure_count": burst_size})

    # ---- planted NEAR-MISS pairs (exactly 4 failures in one 60s window; must NOT alert) ----
    for _ in range(p["n_near_miss"]):
        w = next(window_iter)
        window_start = BASE_EPOCH + w * WINDOW_SECONDS
        user = rng.choice(bg_users)
        src_ip = rng.choice(attacker_ips)
        key = (user, src_ip)
        while key in used_keys:
            user = rng.choice(bg_users)
            key = (user, src_ip)
        used_keys.add(key)
        offsets = rng.sample(range(2, 56), 4)
        for off in sorted(offsets):
            events.append(make_event(window_start + off, user, src_ip, "failure"))
        planted_near_miss.append({"user": user, "src_ip": src_ip, "window_start": window_start,
                                   "failure_count": 4})

    # ---- background traffic fills the rest of the corpus ----
    n_bg = p["n_events"] - len(events)
    if n_bg < 0:
        raise ValueError("planted bursts + near-misses exceed --limit; raise --limit")
    for _ in range(n_bg):
        t = BASE_EPOCH + rng.randrange(0, p["span_seconds"])
        user = rng.choice(bg_users)
        if rng.random() < BG_ROAM_RATE:
            src_ip = rng.choice(bg_ips)
        else:
            src_ip = home_ip[user]
        status = "failure" if rng.random() < BG_FAILURE_RATE else "success"
        events.append(make_event(t, user, src_ip, status))

    events.sort(key=lambda e: e["time"])
    # re-number event_uid in final time order so uid ordering == file line order
    for i, e in enumerate(events, start=1):
        e["event_uid"] = f"e-{i:08d}"

    return events, planted_true, planted_near_miss, p


def independent_ground_truth(events):
    """Reference re-implementation of the detection semantics, deliberately NOT sharing
    code with batch/batch_job.py's DuckDB query or streaming/flink_job.sql's Flink SQL —
    grouping by dict, no SQL engine involved. This is the "expected alert set computed
    independently of either arm" the deliverable calls for."""
    buckets = {}
    for e in events:
        if e["status"] != "failure":
            continue
        window_start = (e["time"] // WINDOW_SECONDS) * WINDOW_SECONDS
        key = (e["user"], e["src_ip"], window_start)
        buckets[key] = buckets.get(key, 0) + 1
    alerts = [{"user": u, "src_ip": ip, "window_start": ws, "failure_count": c}
              for (u, ip, ws), c in buckets.items() if c >= FAILURE_THRESHOLD]
    alerts.sort(key=lambda a: (a["window_start"], a["user"], a["src_ip"]))
    return alerts


def write_corpus(seed: int, limit, out_dir: str):
    events, planted_true, planted_near_miss, params = build_corpus(seed, limit)
    alerts = independent_ground_truth(events)

    os.makedirs(out_dir, exist_ok=True)
    events_path = os.path.join(out_dir, "events.jsonl")
    with open(events_path, "w") as f:
        for e in events:
            f.write(json.dumps(e, sort_keys=True) + "\n")

    # Sanity: every planted true burst must appear in the independently-computed alert
    # set, and every planted near-miss must NOT. This is a build-time self-check, not a
    # substitute for compare_answers.py (which checks the ARMS against ground_truth.json).
    alert_keys = {(a["user"], a["src_ip"], a["window_start"]) for a in alerts}
    for burst in planted_true:
        k = (burst["user"], burst["src_ip"], burst["window_start"])
        assert k in alert_keys, f"planted true burst not in ground truth: {burst}"
    for nm in planted_near_miss:
        k = (nm["user"], nm["src_ip"], nm["window_start"])
        assert k not in alert_keys, f"planted near-miss incorrectly alerts: {nm}"

    ground_truth = {
        "seed": seed,
        "limit": limit,
        "n_events": len(events),
        "span_seconds": params["span_seconds"],
        "window_seconds": WINDOW_SECONDS,
        "failure_threshold": FAILURE_THRESHOLD,
        "base_epoch": BASE_EPOCH,
        "n_true_bursts_planted": len(planted_true),
        "n_near_miss_planted": len(planted_near_miss),
        "alerts": alerts,
        "planted_true": planted_true,
        "planted_near_miss": planted_near_miss,
    }
    gt_path = os.path.join(out_dir, "ground_truth.json")
    with open(gt_path, "w") as f:
        json.dump(ground_truth, f, indent=2, sort_keys=True)

    return events_path, gt_path, len(events), len(alerts)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=20260719,
                     help="master seed for this corpus (default: the pre-reg freeze date)")
    ap.add_argument("--limit", type=int, default=None,
                     help="scale the corpus down to ~this many events (also scales span; "
                          "see module docstring). Default: full 500k-event corpus.")
    ap.add_argument("--out-dir", default=os.path.join(HERE, "data"))
    ap.add_argument("--check", action="store_true",
                     help="generate twice and assert byte-identical output (determinism check)")
    args = ap.parse_args()

    if args.check:
        import filecmp
        import tempfile
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            write_corpus(args.seed, args.limit, d1)
            write_corpus(args.seed, args.limit, d2)
            for name in ("events.jsonl", "ground_truth.json"):
                ok = filecmp.cmp(os.path.join(d1, name), os.path.join(d2, name), shallow=False)
                print(f"--check {name}: {'IDENTICAL' if ok else 'MISMATCH'}")
                if not ok:
                    sys.exit(1)
        print("--check PASSED: corpus generation is deterministic for this seed/limit.")
        return

    events_path, gt_path, n_events, n_alerts = write_corpus(args.seed, args.limit, args.out_dir)
    print(f"wrote {n_events} events -> {events_path}")
    print(f"wrote {n_alerts} ground-truth alerts -> {gt_path}")


if __name__ == "__main__":
    main()

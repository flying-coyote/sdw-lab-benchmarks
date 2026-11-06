"""STREAM-FRESHNESS: plant N single IOC events into an existing seeded corpus.

Reads <base-dir>/events.jsonl + ground_truth.json (written by gen_corpus.py, untouched),
writes <out-dir>/events.jsonl with N successful-logon events from N dedicated IOC
addresses (203.0.113.0/24, TEST-NET-3) inserted in time order, plus ioc_ground_truth.json
and a copy of ground_truth.json. Base lines are written verbatim, so the planted file
minus its IOC lines is byte-identical to the base (self-check 1). The W ground truth
recomputed on the planted corpus by gen_corpus.independent_ground_truth must equal the
base ground truth (self-check 2). Deviation D2 of the pre-reg: a separate script rather
than a gen_corpus.py flag, so the July generator is not touched.
"""
import argparse
import json
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from gen_corpus import independent_ground_truth, WINDOW_SECONDS  # noqa: E402

IOC_PREFIX = "203.0.113."


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "data", "fresh"))
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260720)
    ap.add_argument("--min-gap", type=int, default=120)
    args = ap.parse_args()

    base_events = os.path.join(args.base_dir, "events.jsonl")
    with open(base_events) as f:
        base_lines = f.read().splitlines(keepends=True)
    events = [json.loads(line) for line in base_lines]
    ips = {e["src_ip"] for e in events}
    users = sorted({e["user"] for e in events if e["user"].startswith("user")})
    ioc_ips = [f"{IOC_PREFIX}{i}" for i in range(10, 10 + args.n)]
    assert not (ips & set(ioc_ips)), "IOC addresses collide with corpus addresses"
    t_min, t_max = events[0]["time"], events[-1]["time"]

    rng = random.Random(args.seed)
    lo, hi = t_min + WINDOW_SECONDS, t_max - 2 * WINDOW_SECONDS
    times = []
    for _ in range(200000):
        if len(times) == args.n:
            break
        t = rng.randint(lo, hi)
        if not (5 <= t % WINDOW_SECONDS < 55):
            continue
        if any(abs(t - x) < args.min_gap for x in times):
            continue
        times.append(t)
    assert len(times) == args.n, f"could only place {len(times)} of {args.n} IOC events"
    times.sort()
    planted = []
    for i, (t, ip) in enumerate(zip(times, ioc_ips)):
        planted.append({"activity_id": 1, "category_uid": 3, "class_uid": 3002,
                        "event_uid": f"ioc-{i + 1:04d}", "src_ip": ip, "status": "success",
                        "status_id": 1, "time": t, "type_uid": 300201, "user": rng.choice(users)})

    os.makedirs(args.out_dir, exist_ok=True)
    out_lines = []
    pi = 0
    for line, e in zip(base_lines, events):
        # each IOC event goes before the first base event with a later time (keeps order)
        while pi < len(planted) and planted[pi]["time"] < e["time"]:
            out_lines.append(json.dumps(planted[pi], sort_keys=True) + "\n")
            pi += 1
        out_lines.append(line)
    while pi < len(planted):
        out_lines.append(json.dumps(planted[pi], sort_keys=True) + "\n")
        pi += 1
    with open(os.path.join(args.out_dir, "events.jsonl"), "w") as f:
        f.writelines(out_lines)

    # self-check 1: base bytes preserved, order kept
    stripped = [line for line in out_lines if '"event_uid": "ioc-' not in line]
    assert "".join(stripped) == "".join(base_lines), "planted corpus minus IOC lines != base"
    tt = [json.loads(line)["time"] for line in out_lines]
    assert tt == sorted(tt), "planted corpus not time-ordered"
    # self-check 2: W ground truth unchanged
    with open(os.path.join(args.base_dir, "ground_truth.json")) as f:
        base_gt = json.load(f)
    gt2 = independent_ground_truth([json.loads(line) for line in out_lines])

    def key(a):
        return (a["user"], a["src_ip"], a["window_start"], a["failure_count"])

    assert sorted(map(key, gt2)) == sorted(map(key, base_gt["alerts"])), "W ground truth changed"
    shutil.copy(os.path.join(args.base_dir, "ground_truth.json"), os.path.join(args.out_dir, "ground_truth.json"))
    with open(os.path.join(args.out_dir, "ioc_ground_truth.json"), "w") as f:
        json.dump({"seed": args.seed, "n": args.n, "ioc_ips": ioc_ips, "planted": planted,
                   "checks": {"base_bytes_preserved": True, "w_ground_truth_unchanged": True,
                              "n_w_alerts": len(gt2)}}, f, indent=2, sort_keys=True)
    print(f"planted {len(planted)} IOC events into {len(base_lines)} base events -> {args.out_dir}; "
          f"W ground truth unchanged ({len(gt2)} alerts); base bytes preserved")


if __name__ == "__main__":
    main()

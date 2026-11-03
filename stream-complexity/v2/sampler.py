"""Harness fix 3 (STREAM-COMPLEXITY v2): sample moving parts every 10 s through a scored
trial, per arm, and summarise as median and max across samples (never an end-of-run
snapshot).

Frozen per-arm pattern list (inclusion rule identical for every arm):
  containers   running containers by exact name (docker ps), per arm
  in-container processes inside each of those containers (docker top)
  host procs   host processes whose argv contains a per-arm marker

Harness EXCLUDED for every arm: gen_corpus.py, the paced replayers/producers
(batch/land_microbatches.py, streaming/producer.py, feldera/replay_http.py,
v2/land_faulty.py), compare/latency scripts and this sampler.

Units:
  engine_only        broker / engine / scheduler / job process = running containers of
                     the arm + host-side job processes (B's batch_job.py)
  engine_plus_sink   engine_only + the sink adapter that moves alerts to a file
                     (S: streaming/consume_alerts.py, F: feldera/drain_alerts.py;
                     B and BC write their own file, so they have none)
"""

import argparse
import json
import os
import statistics
import subprocess
import time

ARMS = {
    "B": {"containers": [], "engine_host": ["batch/batch_job.py --in-dir {B_IN}"],
          "sink_host": []},
    "S": {"containers": ["smx-kafka", "smx-jobmanager", "smx-taskmanager"],
          "engine_host": [], "sink_host": ["streaming/consume_alerts.py"]},
    "F": {"containers": ["smx-feldera"], "engine_host": [],
          "sink_host": ["feldera/drain_alerts.py"]},
    "BC": {"containers": ["smx-bc-batch"], "engine_host": [], "sink_host": []},
}


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
    except Exception:  # noqa: BLE001
        return ""


def sample(arms, b_in):
    running = set(sh(["docker", "ps", "--format", "{{.Names}}"]).split())
    ps = sh(["ps", "-eo", "pid,args"]).splitlines()[1:]
    out = {"wall": time.time()}
    for arm in arms:
        spec = ARMS[arm]
        conts = [c for c in spec["containers"] if c in running]
        procs = {}
        for c in conts:
            rows = sh(["docker", "top", c, "-eo", "pid,comm"]).splitlines()[1:]
            procs[c] = {"n": len(rows), "comms": sorted({r.split(None, 1)[1].strip()
                                                         for r in rows if len(r.split(None, 1)) > 1})}

        def match(markers):
            hits = []
            for line in ps:
                for m in markers:
                    m = m.replace("{B_IN}", b_in)
                    if m in line and "sampler.py" not in line:
                        hits.append(line.strip()[:160])
            return hits
        eh, sk = match(spec["engine_host"]), match(spec["sink_host"])
        out[arm] = {
            "containers": conts, "n_containers": len(conts),
            "in_container_processes": procs,
            "n_in_container_processes": sum(p["n"] for p in procs.values()),
            "engine_host": eh, "sink_host": sk,
            "engine_only": len(conts) + len(eh),
            "engine_plus_sink": len(conts) + len(eh) + len(sk),
        }
    return out


def summarise(path, arms):
    rows = [json.loads(line) for line in open(path) if line.strip()]
    res = {"n_samples": len(rows)}
    for arm in arms:
        a = {}
        for k in ("n_containers", "n_in_container_processes", "engine_only", "engine_plus_sink"):
            vals = [r[arm][k] for r in rows if arm in r]
            a[k] = {"median": statistics.median(vals) if vals else None,
                    "max": max(vals) if vals else None}
        comms = {}
        for r in rows:
            for c, p in r[arm]["in_container_processes"].items():
                comms.setdefault(c, set()).update(p["comms"])
        a["in_container_comms_seen"] = {c: sorted(v) for c, v in comms.items()}
        res[arm] = a
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stop-file", required=True)
    ap.add_argument("--arms", default="B,S,F,BC")
    ap.add_argument("--b-in", required=True, help="B arm's --in-dir, to tell it apart from BC")
    ap.add_argument("--interval", type=float, default=10.0)
    ap.add_argument("--summarise-only", action="store_true")
    args = ap.parse_args()
    arms = args.arms.split(",")
    if not args.summarise_only:
        with open(args.out, "a") as f:
            while not os.path.exists(args.stop_file):
                f.write(json.dumps(sample(arms, args.b_in)) + "\n")
                f.flush()
                time.sleep(args.interval)
    summ = summarise(args.out, arms)
    with open(args.out.replace(".jsonl", "-summary.json"), "w") as f:
        json.dump(summ, f, indent=2)
    print(json.dumps({a: {k: v for k, v in summ[a].items() if k != "in_container_comms_seen"}
                      for a in arms}))


if __name__ == "__main__":
    main()

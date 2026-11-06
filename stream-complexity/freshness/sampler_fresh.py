"""STREAM-FRESHNESS sampler.

- Host CPU percent every 10 s (psutil), written to --out as jsonl. The trial summary
  flags the trial if host CPU exceeds 50% in more than 5% of samples (pre-reg threat 1).
- Cumulative CPU of the streaming arm's containers, read from each container's cgroup v2
  cpu.stat (usage_usec) once at start and once at stop, written to --cgroup-out. The
  difference is S's CPU-seconds over the trial (Measure 4).
Stops when --stop-file appears.
"""
import argparse
import json
import os
import subprocess
import time

import psutil

CONTAINERS = ["smx-kafka", "smx-jobmanager", "smx-taskmanager"]


def cgroup_usage_s(name):
    try:
        out = subprocess.run(["docker", "exec", name, "cat", "/sys/fs/cgroup/cpu.stat"],
                             capture_output=True, text=True, timeout=20).stdout
        for line in out.splitlines():
            k, _, v = line.partition(" ")
            if k == "usage_usec":
                return int(v) / 1e6
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cgroup-out", required=True)
    ap.add_argument("--stop-file", required=True)
    ap.add_argument("--interval", type=float, default=10.0)
    args = ap.parse_args()
    start = {c: cgroup_usage_s(c) for c in CONTAINERS}
    t_start = time.time()
    psutil.cpu_percent(None)
    samples = []
    with open(args.out, "w") as f:
        while not os.path.exists(args.stop_file):
            time.sleep(args.interval)
            pct = psutil.cpu_percent(None)
            rec = {"wall": time.time(), "host_cpu_pct": pct, "load1": os.getloadavg()[0]}
            samples.append(pct)
            f.write(json.dumps(rec) + "\n")
            f.flush()
    end = {c: cgroup_usage_s(c) for c in CONTAINERS}
    per = {c: (round(end[c] - start[c], 3) if start[c] is not None and end[c] is not None else None)
           for c in CONTAINERS}
    over = sum(1 for p in samples if p > 50.0)
    rep = {"window_s": round(time.time() - t_start, 1), "cgroup_start_s": start, "cgroup_end_s": end,
           "s_cpu_seconds_per_container": per,
           "s_cpu_seconds_total": (round(sum(v for v in per.values() if v is not None), 3)
                                   if all(v is not None for v in per.values()) else None),
           "host_samples": len(samples),
           "host_cpu_pct_median": (sorted(samples)[len(samples) // 2] if samples else None),
           "host_cpu_pct_max": (max(samples) if samples else None),
           "host_samples_over_50pct": over,
           "host_load_flag": bool(samples) and over / len(samples) > 0.05}
    with open(args.cgroup_out, "w") as f:
        json.dump(rep, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()

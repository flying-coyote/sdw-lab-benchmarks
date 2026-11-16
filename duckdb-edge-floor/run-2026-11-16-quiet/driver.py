#!/usr/bin/env python3
"""Driver for the 2026-11-15 enforced-cap run (duckdb-edge-floor). Runs on the host with system python3,
launches one fresh container per trial (cgroup v2 memory.max = cap, memory.swap.max = 0), and records the
outcome, cgroup memory.peak / memory.events, load and clock offset per trial. Matrix, caps, memory_limit rule,
timeout and stop rules are frozen in ../PREREGISTRATION-2026-11-15.md.

Usage: driver.py [--only SHAPE] [--corpus U|Z] [--threads N]   (filters, for resuming; default = full matrix)
"""
import argparse, json, os, re, subprocess, sys, time, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE = "sdw-edge-floor:duckdb-1.5.3"
CAPS_MB = [4096, 256, 128, 64, 32, 16]          # 4096 = uncapped reference
MEMLIMIT = lambda cap: (cap * 7) // 8            # memory_limit = 87.5% of the cgroup cap
TRIALS = 5
TIMEOUT_S = 300
LOAD_MAX = 1.0   # QUIET 2026-11-16: was 4.0 (pre-registered hygiene change)
LOAD_WAIT_MAX_S = 120   # QUIET 2026-11-16: was 600
CPUSET = {1: "2", 4: "2-5"}
CORPORA = {"U": "/work/corpus/U.parquet", "Z": "/work/corpus/Z.parquet"}
OUT = os.path.join(HERE, "results", "trials.jsonl")


def load1():
    return float(open("/proc/loadavg").read().split()[0])


def chrony_offset():
    try:
        out = subprocess.run(["chronyc", "tracking"], capture_output=True, text=True, timeout=10).stdout
        m = re.search(r"System time\s*:\s*([\d.]+) seconds (fast|slow)", out)
        return (float(m.group(1)) * (1 if m.group(2) == "fast" else -1)) if m else None
    except Exception:
        return None


def wait_for_load():
    waited, first = 0, load1()
    while load1() > LOAD_MAX and waited < LOAD_WAIT_MAX_S:
        time.sleep(30); waited += 30
    return {"load_before_wait": first, "waited_s": waited, "load_after_wait": load1()}


def run_trial(shape, corpus, cap, threads, trial):
    tag = f"{shape}-{corpus}-c{cap}-t{threads}-r{trial}"
    raw = os.path.join("/work/results/raw", tag)
    spill = f"/work/spill/{tag}"
    name = f"edgefloor-{uuid.uuid4().hex[:10]}"
    inner = (f"python /work/trial.py {shape} {CORPORA.get(corpus, 'none')} {MEMLIMIT(cap)} {threads} {raw}; "
             f"echo RC=$?; echo PEAK=$(cat /sys/fs/cgroup/memory.peak); "
             f"echo EVENTS=$(tr '\\n' ' ' < /sys/fs/cgroup/memory.events)")
    cmd = ["docker", "run", "--rm", "--name", name, "--user", "1000:1000",
           f"--memory={cap}m", f"--memory-swap={cap}m", f"--cpuset-cpus={CPUSET[threads]}",
           "-e", f"EDGE_TEMP={spill}", "-v", f"{HERE}:/work", "-v", f"{HERE}/corpus:/work/corpus:ro",
           IMAGE, "sh", "-c", inner]
    rec = {"tag": tag, "shape": shape, "corpus": corpus, "cap_mb": cap, "memory_limit_mb": MEMLIMIT(cap),
           "threads": threads, "trial": trial, "load1": load1(), "chrony_offset_s": chrony_offset(),
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
        out = p.stdout
        rec["container_wall_s"] = round(time.perf_counter() - t0, 3)
        rc = re.search(r"RC=(\d+)", out); pk = re.search(r"PEAK=(\d+)", out); ev = re.search(r"EVENTS=(.*)", out)
        rec["child_rc"] = int(rc.group(1)) if rc else None
        rec["memory_peak_bytes"] = int(pk.group(1)) if pk else None
        evs = dict(zip(*[iter(ev.group(1).split())] * 2)) if ev else {}
        rec["memory_events"] = {k: int(v) for k, v in evs.items()}
        rec["stderr_tail"] = p.stderr[-400:]
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True)
        rec["container_wall_s"] = round(time.perf_counter() - t0, 3)
        rec["outcome"] = "timeout"
    hostraw = os.path.join(HERE, "results", "raw", tag)
    inner_rec = None
    if os.path.exists(hostraw + ".json"):
        inner_rec = json.load(open(hostraw + ".json"))
        rec.update({k: v for k, v in inner_rec.items() if k not in rec})
    if "outcome" not in rec:
        if rec.get("memory_events", {}).get("oom_kill", 0) > 0 and inner_rec is None:
            rec["outcome"] = "kernel_oom_kill"
        elif inner_rec is None:
            rec["outcome"] = f"no_record_rc{rec.get('child_rc')}"
    if inner_rec is None and os.path.exists(hostraw + ".samples.jsonl"):
        lines = open(hostraw + ".samples.jsonl").read().splitlines()
        rec["last_sample"] = json.loads(lines[-1]) if lines else None
        rec["n_samples"] = len(lines)
        pk = {}
        for ln in lines:
            s = json.loads(ln)
            for k in ("tmpfiles_bytes", "dir_bytes", "bm_bytes", "rss_anon", "cg_anon"):
                pk[k] = max(pk.get(k, 0), s.get(k) or 0)
        rec["peaks_from_samples"] = pk
    # spill directory left over after the trial (DuckDB normally deletes its files); then clean it
    hostspill = os.path.join(HERE, "spill", tag)
    left = 0
    for dp, _, fs in os.walk(hostspill):
        for f in fs:
            left += os.path.getsize(os.path.join(dp, f)); os.remove(os.path.join(dp, f))
    rec["spill_left_after_bytes"] = left
    for dp, ds, _ in os.walk(hostspill, topdown=False):
        for d in ds:
            os.rmdir(os.path.join(dp, d))
    if os.path.isdir(hostspill):
        os.rmdir(hostspill)
    return rec


def cells(args):
    out = []
    if args.only in (None, "null"):
        out += [("null", "-", cap, 1) for cap in CAPS_MB]
    for corpus in ("U", "Z"):
        for shape in ("S", "H", "J"):
            for threads in (1, 4):
                if (args.only in (None, shape)) and (args.corpus in (None, corpus)) and (args.threads in (None, threads)):
                    out += [(shape, corpus, cap, threads) for cap in CAPS_MB]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only"); ap.add_argument("--corpus"); ap.add_argument("--threads", type=int)
    args = ap.parse_args()
    os.makedirs(os.path.join(HERE, "results", "raw"), exist_ok=True)
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)["tag"] for l in open(OUT)}
    chain_timeout = {}   # (shape, corpus, threads) -> True once a cap timed out
    with open(OUT, "a") as fo:
        for shape, corpus, cap, threads in cells(args):
            chain = (shape, corpus, threads)
            lw = wait_for_load()
            fails = []
            for trial in range(1, TRIALS + 1):
                tag = f"{shape}-{corpus}-c{cap}-t{threads}-r{trial}"
                if tag in done:
                    continue
                # stop rules (frozen): after a timeout in this chain, tighter caps get one trial only;
                # a cell whose first two trials fail with the same outcome is stopped (remaining = skipped).
                if (chain_timeout.get(chain) and trial > 1) or (len(fails) >= 2 and fails[0] == fails[1]):
                    rec = {"tag": tag, "shape": shape, "corpus": corpus, "cap_mb": cap, "threads": threads,
                           "trial": trial, "outcome": "skipped_by_stop_rule", "stop_reason": fails[:2] or "chain_timeout"}
                else:
                    rec = run_trial(shape, corpus, cap, threads, trial)
                    rec["load_wait"] = lw if trial == 1 else None
                    if rec["outcome"] != "completed":
                        fails.append(rec["outcome"])
                    if rec["outcome"] == "timeout":
                        chain_timeout[chain] = True
                fo.write(json.dumps(rec) + "\n"); fo.flush()
                print(f"{tag:28} {rec['outcome']:22} lat={rec.get('latency_s')} peak={rec.get('memory_peak_bytes')} "
                      f"hwm={rec.get('vm_hwm_bytes')} spill={(rec.get('peaks') or {}).get('tmpfiles_bytes')} "
                      f"load={rec.get('load1')}", flush=True)


if __name__ == "__main__":
    main()

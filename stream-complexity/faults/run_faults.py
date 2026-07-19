"""Pre-reg Measure 3 (fault recovery) runner: executes the three scripted injections
— (a) kill the Kafka broker mid-run, (b) kill the Flink taskmanager mid-run, (c) kill
the batch job mid-tick — each against a small DEDICATED corpus under faults/_work/
(never the main data/+results/ a scored clean trial uses), and records wall-clock-
to-recovered-correct-output, the recover_*.sh step count, and post-recovery
correctness into results/faults.json.

Step counting is not a hand-maintained number that can silently drift from the
script it describes: it is parsed straight out of each recover_*.sh's own
`# Step N:` comment markers (see faults/recover_*.sh), so the count in
results/faults.json is always exactly what that script's own commentary claims.

(a) and (b) share the streaming docker stack, so those two run sequentially against
their own fresh stack (torn down + brought back up between them) rather than
concurrently. (c) needs no Docker at all and can run independently.

Replay factor defaults SLOWER than a scored clean trial (5x, not 20x): a fault
injection needs comfortable real wall-clock runway to land the kill mid-flight
without racing the replay's own natural completion.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import gen_corpus  # noqa: E402
import compare_answers  # noqa: E402

WORK = os.path.join(HERE, "_work")
RESULTS_OUT = os.path.join(ROOT, "results", "faults.json")
VENV_PY = os.path.join(ROOT, "..", ".venv", "bin", "python3")
if not os.path.exists(VENV_PY):
    VENV_PY = sys.executable

STEP_RE = re.compile(r"^\s*#\s*Step\s+\d+\s*:", re.IGNORECASE)


def count_steps(script_path):
    n = 0
    with open(script_path) as f:
        for line in f:
            if STEP_RE.match(line):
                n += 1
    return n


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ensure_corpus(limit, seed):
    os.makedirs(WORK, exist_ok=True)
    data_dir = os.path.join(WORK, "data")
    if not os.path.exists(os.path.join(data_dir, "events.jsonl")):
        gen_corpus.write_corpus(seed, limit, data_dir)
    return data_dir


def reset_streaming_stack():
    streaming_dir = os.path.join(ROOT, "streaming")
    run(["docker", "compose", "down", "-v"], cwd=streaming_dir)
    up = run(["docker", "compose", "up", "-d"], cwd=streaming_dir)
    if up.returncode != 0:
        raise RuntimeError(f"docker compose up failed: {up.stderr}")
    for svc in ("smx-kafka", "smx-jobmanager"):
        for _ in range(60):
            status = run(["docker", "inspect", "-f", "{{.State.Health.Status}}", svc]).stdout.strip()
            if status == "healthy":
                break
            time.sleep(2)
    for _ in range(60):
        running = run(["docker", "inspect", "-f", "{{.State.Running}}", "smx-taskmanager"]).stdout.strip()
        if running == "true":
            break
        time.sleep(2)
    submit = run(["bash", "submit_flink_job.sh"], cwd=streaming_dir)
    if submit.returncode != 0:
        raise RuntimeError(f"flink job submission failed: {submit.stderr}\n{submit.stdout}")
    time.sleep(5)


def fault_broker(replay_factor, warmup_s):
    print("[run_faults] === fault (a): kill the Kafka broker mid-run ===", flush=True)
    data_dir = ensure_corpus(limit=5000, seed=20260719)
    reset_streaming_stack()

    results_dir = os.path.join(WORK, "results_broker")
    os.makedirs(results_dir, exist_ok=True)
    for f in glob.glob(os.path.join(results_dir, "*")):
        os.remove(f)

    replay_start = time.time() + 2
    prod = subprocess.Popen([VENV_PY, os.path.join(ROOT, "streaming", "producer.py"),
                              "--events", os.path.join(data_dir, "events.jsonl"),
                              "--replay-factor", str(replay_factor),
                              "--replay-start-epoch", str(replay_start), "--quiet"])
    cons = subprocess.Popen([VENV_PY, os.path.join(ROOT, "streaming", "consume_alerts.py"),
                              "--out-file", os.path.join(results_dir, "alerts-stream.jsonl"),
                              "--state-file", os.path.join(results_dir, ".stream_state.json"),
                              "--idle-timeout", "30", "--quiet"])

    time.sleep(warmup_s)
    fault_t0 = time.time()
    kill_res = run(["bash", os.path.join(HERE, "kill_broker.sh")])
    print(f"[run_faults]   {kill_res.stdout.strip()}", flush=True)

    recover_res = run(["bash", os.path.join(HERE, "recover_broker.sh")])
    recovered_at = time.time()
    steps = count_steps(os.path.join(HERE, "recover_broker.sh"))

    prod.wait(timeout=300)
    cons.wait(timeout=120)

    cmp_out = os.path.join(results_dir, "compare-report.json")
    cmp_res = run([VENV_PY, os.path.join(ROOT, "compare_answers.py"),
                    "--ground-truth", os.path.join(data_dir, "ground_truth.json"),
                    "--stream-file", os.path.join(results_dir, "alerts-stream.jsonl"),
                    "--batch-file", "/dev/null", "--arm", "stream", "--out", cmp_out])

    return {
        "fault": "kafka_broker_kill",
        "script": "faults/kill_broker.sh + faults/recover_broker.sh",
        "recover_exit_code": recover_res.returncode,
        "recover_stdout": recover_res.stdout.strip(),
        "recover_stderr": recover_res.stderr.strip(),
        "n_recovery_steps": steps,
        "wall_clock_to_recovered_s": round(recovered_at - fault_t0, 2),
        "post_recovery_compare_exit_code": cmp_res.returncode,
        "post_recovery_identical": cmp_res.returncode == 0,
        "compare_report": json.load(open(cmp_out)) if os.path.exists(cmp_out) else None,
    }


def fault_taskmanager(replay_factor, warmup_s):
    print("[run_faults] === fault (b): kill the Flink taskmanager mid-run ===", flush=True)
    data_dir = ensure_corpus(limit=5000, seed=20260719)
    reset_streaming_stack()

    results_dir = os.path.join(WORK, "results_taskmanager")
    os.makedirs(results_dir, exist_ok=True)
    for f in glob.glob(os.path.join(results_dir, "*")):
        os.remove(f)

    replay_start = time.time() + 2
    prod = subprocess.Popen([VENV_PY, os.path.join(ROOT, "streaming", "producer.py"),
                              "--events", os.path.join(data_dir, "events.jsonl"),
                              "--replay-factor", str(replay_factor),
                              "--replay-start-epoch", str(replay_start), "--quiet"])
    cons = subprocess.Popen([VENV_PY, os.path.join(ROOT, "streaming", "consume_alerts.py"),
                              "--out-file", os.path.join(results_dir, "alerts-stream.jsonl"),
                              "--state-file", os.path.join(results_dir, ".stream_state.json"),
                              "--idle-timeout", "30", "--quiet"])

    # >= one checkpoint interval (10s, docker-compose.yml) so there is something to
    # actually resume FROM — a kill before the first checkpoint would only test
    # cold-restart, not the checkpointing this fault is meant to exercise.
    time.sleep(max(warmup_s, 15))
    fault_t0 = time.time()
    kill_res = run(["bash", os.path.join(HERE, "kill_taskmanager.sh")])
    print(f"[run_faults]   {kill_res.stdout.strip()}", flush=True)

    recover_res = run(["bash", os.path.join(HERE, "recover_taskmanager.sh")])
    recovered_at = time.time()
    steps = count_steps(os.path.join(HERE, "recover_taskmanager.sh"))

    prod.wait(timeout=300)
    cons.wait(timeout=120)

    cmp_out = os.path.join(results_dir, "compare-report.json")
    cmp_res = run([VENV_PY, os.path.join(ROOT, "compare_answers.py"),
                    "--ground-truth", os.path.join(data_dir, "ground_truth.json"),
                    "--stream-file", os.path.join(results_dir, "alerts-stream.jsonl"),
                    "--batch-file", "/dev/null", "--arm", "stream", "--out", cmp_out])

    return {
        "fault": "flink_taskmanager_kill",
        "script": "faults/kill_taskmanager.sh + faults/recover_taskmanager.sh",
        "recover_exit_code": recover_res.returncode,
        "recover_stdout": recover_res.stdout.strip(),
        "recover_stderr": recover_res.stderr.strip(),
        "n_recovery_steps": steps,
        "wall_clock_to_recovered_s": round(recovered_at - fault_t0, 2),
        "post_recovery_compare_exit_code": cmp_res.returncode,
        "post_recovery_identical": cmp_res.returncode == 0,
        "compare_report": json.load(open(cmp_out)) if os.path.exists(cmp_out) else None,
    }


def fault_batch(replay_factor, warmup_s):
    print("[run_faults] === fault (c): kill the batch job mid-tick ===", flush=True)
    data_dir = ensure_corpus(limit=5000, seed=20260719)

    batch_in_dir = os.path.join(WORK, "batch_in")
    results_dir = os.path.join(WORK, "results_batch")
    os.makedirs(batch_in_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)
    for f in glob.glob(os.path.join(batch_in_dir, "*")):
        os.remove(f)
    for f in glob.glob(os.path.join(results_dir, "*")):
        os.remove(f)

    out_file = os.path.join(results_dir, "alerts-batch.jsonl")
    state_file = os.path.join(batch_in_dir, ".batch_state.json")

    replay_start = time.time() + 2
    land = subprocess.Popen([VENV_PY, os.path.join(ROOT, "batch", "land_microbatches.py"),
                              "--events", os.path.join(data_dir, "events.jsonl"),
                              "--out-dir", batch_in_dir, "--replay-factor", str(replay_factor),
                              "--replay-start-epoch", str(replay_start), "--quiet"])
    job = subprocess.Popen([VENV_PY, os.path.join(ROOT, "batch", "batch_job.py"),
                             "--in-dir", batch_in_dir, "--out-file", out_file,
                             "--state-file", state_file, "--poll-interval", "5",
                             "--max-idle-ticks", "6", "--quiet"])

    time.sleep(warmup_s)
    fault_t0 = time.time()
    kill_res = run(["bash", os.path.join(HERE, "kill_batch_job.sh"), str(job.pid)])
    print(f"[run_faults]   {kill_res.stdout.strip()}", flush=True)
    job.wait(timeout=30)  # reap the now-dead child so it doesn't zombie

    env = dict(os.environ)
    env.update({"SMX_BATCH_IN_DIR": batch_in_dir, "SMX_BATCH_OUT_FILE": out_file,
                "SMX_BATCH_STATE_FILE": state_file})
    recover_res = run(["bash", os.path.join(HERE, "recover_batch_job.sh")], env=env)
    recovered_at = time.time()
    steps = count_steps(os.path.join(HERE, "recover_batch_job.sh"))
    new_pid = int(recover_res.stdout.strip()) if recover_res.stdout.strip().isdigit() else None

    land.wait(timeout=300)
    # Wait for the restarted batch_job.py to drain (auto-exits after idle ticks).
    if new_pid:
        for _ in range(120):
            alive = run(["kill", "-0", str(new_pid)]).returncode == 0
            if not alive:
                break
            time.sleep(2)

    cmp_out = os.path.join(results_dir, "compare-report.json")
    cmp_res = run([VENV_PY, os.path.join(ROOT, "compare_answers.py"),
                    "--ground-truth", os.path.join(data_dir, "ground_truth.json"),
                    "--batch-file", out_file, "--stream-file", "/dev/null",
                    "--arm", "batch", "--out", cmp_out])

    return {
        "fault": "batch_job_kill",
        "script": "faults/kill_batch_job.sh + faults/recover_batch_job.sh",
        "recover_exit_code": recover_res.returncode,
        "recover_stdout": recover_res.stdout.strip(),
        "recover_stderr": recover_res.stderr.strip(),
        "n_recovery_steps": steps,
        "wall_clock_to_recovered_s": round(recovered_at - fault_t0, 2),
        "post_recovery_compare_exit_code": cmp_res.returncode,
        "post_recovery_identical": cmp_res.returncode == 0,
        "compare_report": json.load(open(cmp_out)) if os.path.exists(cmp_out) else None,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", choices=["broker", "taskmanager", "batch", "all"], default="all")
    ap.add_argument("--replay-factor", type=float, default=5.0)
    ap.add_argument("--warmup-s", type=float, default=12.0)
    ap.add_argument("--out", default=RESULTS_OUT)
    args = ap.parse_args()

    results = {}
    if args.only in ("broker", "all"):
        results["broker"] = fault_broker(args.replay_factor, args.warmup_s)
    if args.only in ("taskmanager", "all"):
        results["taskmanager"] = fault_taskmanager(args.replay_factor, args.warmup_s)
    if args.only in ("batch", "all"):
        results["batch"] = fault_batch(args.replay_factor, args.warmup_s)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)

    print("\n[run_faults] summary:")
    for name, r in results.items():
        print(f"  {name}: steps={r['n_recovery_steps']} "
              f"recovered_in={r['wall_clock_to_recovered_s']}s "
              f"post_recovery_identical={r['post_recovery_identical']}")
    print(f"report written -> {args.out}")


if __name__ == "__main__":
    main()

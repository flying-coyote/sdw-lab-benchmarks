"""STREAM-COMPLEXITY v2 fault battery (pre-reg "Fault battery and per-arm rewind rules").

Every fault: full 500,000-event corpus at 20x, kill at event-time minute 45
(base_epoch + 2,700 s, i.e. replay_start + 135 wall-s), held outage of 30 wall-seconds,
then the arm's recover script, then the arm runs to the end of the corpus and the
post-recovery answer-equality check runs over the full corpus (missing / extra /
duplicates separately). n=1 per fault.

Faults: S1 S2 (S arm), B1 B2 B3 (B arm), F1 F2 (F arm, EDITION-BOUND), BC1 (BC arm).
v3 (2026-11-07, PRE-REG-stream-complexity-risingwave-2026-11-07): R1 (R arm, docker kill of the
single-process RisingWave cluster). R2 is dropped because RisingWave is PID 1 in its container.
Exploratory, NOT pre-registered, reported separately: B2x / B3x = B2 / B3 on the
minute-44 window (base + 2,640 s), which holds a ground-truth alert.

Step counts: parsed from `# Step N:` markers in the recover script (July convention); for
recover_bc.sh, whose single step is conditional, the executed count it prints.
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from compare_answers import compare_arm, load_ground_truth_keys, canonical_window_start  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "..", "lib"))
from common import BASE_EPOCH  # noqa: E402

PY = os.path.join(ROOT, "..", ".venv", "bin", "python3")
FAULTS = os.path.join(ROOT, "faults")
GT = os.path.join(ROOT, "data", "ground_truth.json")
RF = 20.0
KILL_EVENT_OFFSET = 2700
HOLD_S = 30.0
STEP_RE = re.compile(r"^\s*#\s*Step\s+\d+\s*:", re.IGNORECASE)


def count_steps(path):
    return sum(1 for line in open(path) if STEP_RE.match(line))


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def wait_until(t):
    if t - time.time() > 0:
        time.sleep(t - time.time())


def rows(path):
    if not os.path.exists(path):
        return []
    return [json.loads(line) for line in open(path) if line.strip()]


def score(arm, out_file, kill_wall, rec_start, rec_done, n_rows_at_recovery, extra=None):
    gt_keys, _ = load_ground_truth_keys(GT)
    cmp = compare_arm(arm, out_file, gt_keys)
    rs = rows(out_file)
    new_correct = sorted(r["alert_emit_wall_ts"] for r in rs
                         if r["alert_emit_wall_ts"] > kill_wall and
                         (r["user"], r["src_ip"], canonical_window_start(r["window_start"])) in gt_keys)
    res = {
        "kill_wall": kill_wall, "recovery_start_wall": rec_start, "recovery_done_wall": rec_done,
        "wall_kill_to_infra_restored_s": round(rec_done - kill_wall, 2),
        "wall_recovery_script_s": round(rec_done - rec_start, 2),
        "wall_kill_to_new_correct_alert_s": round(new_correct[0] - kill_wall, 2) if new_correct else None,
        "output_exists": os.path.exists(out_file),
        "rows_at_recovery_done": sum(1 for r in rs if r["alert_emit_wall_ts"] <= rec_done),
        "rows_at_end": len(rs),
        "output_grew_after_recovery": any(r["alert_emit_wall_ts"] > rec_done for r in rs),
        "post_recovery": {k: cmp[k] for k in ("n_rows", "n_distinct_keys", "n_missing", "n_extra",
                                               "n_duplicate_keys", "missing", "extra", "identical")},
    }
    res.update(extra or {})
    return res


# ---------------------------------------------------------------- S arm
def s_stack_up(d):
    sd = os.path.join(ROOT, "streaming")
    run(["docker", "compose", "down", "-v"], cwd=sd)
    run(["docker", "compose", "up", "-d"], cwd=sd)
    for svc in ("smx-kafka", "smx-jobmanager"):
        for _ in range(90):
            if run(["docker", "inspect", "-f", "{{.State.Health.Status}}", svc]).stdout.strip() == "healthy":
                break
            time.sleep(2)
    for _ in range(60):
        if run(["docker", "inspect", "-f", "{{.State.Running}}", "smx-taskmanager"]).stdout.strip() == "true":
            break
        time.sleep(2)
    with open(os.path.join(d, "flink-submit.log"), "w") as f:
        subprocess.run(["bash", "submit_flink_job.sh"], cwd=sd, stdout=f, stderr=subprocess.STDOUT)
    time.sleep(5)


def s_topic_end():
    out = run(["docker", "exec", "smx-kafka", "/opt/kafka/bin/kafka-get-offsets.sh",
               "--bootstrap-server", "localhost:9092", "--topic", "smx-alerts"]).stdout
    return sum(int(x.rsplit(":", 1)[1]) for x in out.split() if ":" in x)


def fault_s(fid, d):
    kill = {"S1": "kill_broker.sh", "S2": "kill_taskmanager.sh"}[fid]
    rec = {"S1": "recover_broker.sh", "S2": "recover_taskmanager.sh"}[fid]
    s_stack_up(d)
    out = os.path.join(d, "alerts-stream.jsonl")
    stop = os.path.join(d, ".s-stop")
    cons = subprocess.Popen([PY, os.path.join(ROOT, "streaming", "consume_alerts.py"), "--out-file", out,
                             "--state-file", os.path.join(d, ".stream_state.json"), "--idle-timeout", "100000",
                             "--stop-file", stop], stdout=open(os.path.join(d, "consumer.log"), "w"),
                            stderr=subprocess.STDOUT)
    rs = time.time() + 5
    prod = subprocess.Popen([PY, os.path.join(ROOT, "streaming", "producer.py"), "--replay-factor", str(RF),
                             "--replay-start-epoch", str(rs)], stdout=open(os.path.join(d, "producer.log"), "w"),
                            stderr=subprocess.STDOUT)
    kill_wall = rs + KILL_EVENT_OFFSET / RF
    wait_until(kill_wall)
    kill_wall = time.time()
    k = run(["bash", os.path.join(FAULTS, kill)])
    log(f"{fid} kill: {k.stdout.strip()} {k.stderr.strip()}")
    time.sleep(HOLD_S)
    rec_start = time.time()
    r = run(["bash", os.path.join(FAULTS, rec)])
    rec_done = time.time()
    n_at = len(rows(out))
    log(f"{fid} recovered rc={r.returncode}: {r.stdout.strip()[-200:]}")
    prod.wait()
    jobs = run(["curl", "-s", "localhost:18081/jobs/overview"]).stdout
    prev, stable = -1, 0
    while stable < 3:
        time.sleep(15)
        cur = s_topic_end()
        stable = stable + 1 if cur == prev else 0
        prev = cur
    open(stop, "w").close()
    cons.wait()
    raw = prev
    jm_log = run(["docker", "logs", "smx-jobmanager"]).stdout + run(["docker", "logs", "smx-jobmanager"]).stderr
    restarts = len(re.findall(r"switched from state RUNNING to RESTARTING", jm_log))
    run(["docker", "compose", "down", "-v"], cwd=os.path.join(ROOT, "streaming"))
    return score("S", out, kill_wall, rec_start, rec_done, n_at, {
        "n_recovery_steps": count_steps(os.path.join(FAULTS, rec)), "step_count_method": "markers",
        "recover_rc": r.returncode, "recover_stdout": r.stdout.strip()[-500:], "recover_stderr": r.stderr.strip()[-500:],
        "raw_sink_records": raw, "raw_engine_duplicates": raw - 30 if raw is not None else None,
        "flink_job_restarts_in_jm_log": restarts, "flink_jobs_overview_after_replay": jobs[:600],
        "producer_log_tail": open(os.path.join(d, "producer.log")).read()[-600:]})


# ---------------------------------------------------------------- B arm
def fault_b(fid, d):
    b_in = os.path.join(d, "b_in")
    os.makedirs(b_in, exist_ok=True)
    out = os.path.join(d, "alerts-batch.jsonl")
    state = os.path.join(b_in, ".batch_state.json")
    rs = time.time() + 5
    kill_wall = rs + KILL_EVENT_OFFSET / RF
    win_off = {"B2": 2700, "B3": 2700, "B2x": 2640, "B3x": 2640}.get(fid)
    W = (BASE_EPOCH + win_off) // 60 if win_off else None
    if fid == "B1":
        land = subprocess.Popen([PY, os.path.join(ROOT, "batch", "land_microbatches.py"), "--out-dir", b_in,
                                 "--replay-factor", str(RF), "--replay-start-epoch", str(rs), "--quiet"])
    else:
        flag = "--hold-window" if fid.startswith("B2") else "--truncate-window"
        land = subprocess.Popen([PY, os.path.join(HERE, "land_faulty.py"), "--out-dir", b_in, "--state-file", state,
                                 "--replay-factor", str(RF), "--replay-start-epoch", str(rs), flag, str(W),
                                 "--log", os.path.join(d, "lander-events.json")])
    joblog = open(os.path.join(d, "batch-job.log"), "w")
    job = subprocess.Popen([PY, os.path.join(ROOT, "batch", "batch_job.py"), "--in-dir", b_in, "--out-file", out,
                            "--state-file", state, "--poll-interval", "5", "--max-idle-ticks", "6"],
                           stdout=joblog, stderr=subprocess.STDOUT)
    extra = {"window_under_fault": W, "window_under_fault_offset_s": win_off}
    env = dict(os.environ, SMX_BATCH_IN_DIR=b_in, SMX_BATCH_OUT_FILE=out, SMX_BATCH_STATE_FILE=state)
    new_pid = None
    if fid == "B1":
        wait_until(kill_wall)
        kill_wall = time.time()
        run(["bash", os.path.join(FAULTS, "kill_batch_job.sh"), str(job.pid)])
        job.wait()
        time.sleep(HOLD_S)
        rec_start = time.time()
        r = run(["bash", os.path.join(FAULTS, "recover_batch_job.sh")], env=env)
        rec_done = time.time()
        new_pid = int(r.stdout.strip()) if r.stdout.strip().isdigit() else None
        steps, rec_script = count_steps(os.path.join(FAULTS, "recover_batch_job.sh")), "recover_batch_job.sh"
    elif fid.startswith("B2"):
        # nothing re-driven: no operator action, the job keeps running
        land.wait()
        ev = json.load(open(os.path.join(d, "lander-events.json")))
        kill_wall = ev[0]["wall"]
        # no operator action; "recovery" = the late file landing
        rec_start = rec_done = [e for e in ev if e["action"] == "late_file_landed"][0]["wall"]
        steps, rec_script, r = 0, None, None
    else:  # B3 / B3x
        # the operator acts only if the job died on the truncated file
        bad = os.path.join(b_in, f"window-{W:08d}.parquet")
        while True:
            if job.poll() is not None:
                break
            ev = json.load(open(os.path.join(d, "lander-events.json"))) if os.path.exists(
                os.path.join(d, "lander-events.json")) else []
            if any(e["action"] == "complete_file_replaced" for e in ev) and time.time() - ev[-1]["wall"] > 15:
                break
            time.sleep(0.5)
        ev = json.load(open(os.path.join(d, "lander-events.json")))
        kill_wall = [e for e in ev if e["action"] == "truncated_file_written"][0]["wall"]
        extra["job_exit_code_after_truncated_file"] = job.poll()
        if job.poll() is not None:
            rec_start = time.time()
            r = run(["bash", os.path.join(FAULTS, "recover_b3.sh")],
                    env=dict(env, SMX_BAD_FILE=bad))
            rec_done = time.time()
            new_pid = int(r.stdout.strip().split()[-1]) if r.stdout.strip().split() and \
                r.stdout.strip().split()[-1].isdigit() else None
            steps, rec_script = count_steps(os.path.join(FAULTS, "recover_b3.sh")), "recover_b3.sh"
        else:
            rec_start = rec_done = time.time()
            steps, rec_script, r = 0, None, None
    n_at = len(rows(out))
    land.wait()
    if new_pid:
        while run(["kill", "-0", str(new_pid)]).returncode == 0:
            time.sleep(2)
    else:
        job.wait()
    joblog.close()
    extra.update({"n_recovery_steps": steps, "step_count_method": "markers" if rec_script else "no operator action",
                  "recover_script": rec_script,
                  "recover_stdout": r.stdout.strip()[-300:] if r else None,
                  "batch_job_log_tail": open(os.path.join(d, "batch-job.log")).read()[-1500:]})
    if os.path.exists(os.path.join(d, "lander-events.json")):
        extra["lander_events"] = json.load(open(os.path.join(d, "lander-events.json")))
    extra["window_under_fault_has_gt_alert"] = any(
        k[2] == W * 60 for k in load_ground_truth_keys(GT)[0]) if W else None
    return score("B", out, kill_wall, rec_start, rec_done, n_at, extra)


# ---------------------------------------------------------------- F arm
FURL = "http://localhost:18080/v0/pipelines/smx-detect"


def f_stack_up(d):
    fd = os.path.join(ROOT, "feldera")
    run(["docker", "compose", "down"], cwd=fd)
    run(["docker", "compose", "up", "-d"], cwd=fd)
    for _ in range(90):
        if run(["docker", "inspect", "-f", "{{.State.Health.Status}}", "smx-feldera"]).stdout.strip() == "healthy":
            break
        time.sleep(2)
    with open(os.path.join(d, "deploy.log"), "w") as f:
        subprocess.run(["bash", os.path.join(fd, "deploy_pipeline.sh")], stdout=f, stderr=subprocess.STDOUT)


def pipeline_pid():
    """PID of the compiled pipeline process INSIDE the container's PID namespace (docker top
    reports the daemon's namespace, which the host cannot signal on this setup)."""
    scan = ('for p in /proc/[0-9]*; do c=$(tr "\\0" " " < $p/cmdline 2>/dev/null); '
            'case "$c" in *local-runner/pipeline-*program_*--config-file*) echo "${p#/proc/} $c";; esac; done')
    out = run(["docker", "exec", "smx-feldera", "sh", "-c", scan]).stdout.splitlines()
    for line in out:
        pid, args = line.strip().split(None, 1)
        if not args.startswith("sh -c"):
            return int(pid), args[:200]
    return None, None


def fault_f(fid, d):
    f_stack_up(d)
    out = os.path.join(d, "alerts-feldera.jsonl")
    dstate, rstate = os.path.join(d, "drain-state.json"), os.path.join(d, "replayer-state.json")
    ctrl, stop = os.path.join(d, "rewind.json"), os.path.join(d, ".f-stop")
    drain = subprocess.Popen([PY, os.path.join(ROOT, "feldera", "drain_alerts.py"), "--out-file", out,
                              "--state-file", dstate, "--stop-file", stop],
                             stdout=open(os.path.join(d, "drain.log"), "w"), stderr=subprocess.STDOUT)
    for _ in range(120):
        if os.path.exists(dstate) and json.load(open(dstate)).get("connected"):
            break
        time.sleep(0.5)
    before = json.loads(run(["curl", "-s", FURL]).stdout)
    pre_inc = json.loads(run(["curl", "-s", FURL + "/stats"]).stdout)["global_metrics"]["incarnation_uuid"]
    rs = time.time() + 5
    rep = subprocess.Popen([PY, os.path.join(ROOT, "feldera", "replay_http.py"), "--replay-factor", str(RF),
                            "--replay-start-epoch", str(rs), "--state-file", rstate, "--control-file", ctrl],
                           stdout=open(os.path.join(d, "replayer.log"), "w"), stderr=subprocess.STDOUT)
    kill_wall = rs + KILL_EVENT_OFFSET / RF
    wait_until(kill_wall)
    extra = {}
    if fid == "F1":
        kill_wall = time.time()
        k = run(["docker", "kill", "smx-feldera"])
        extra["kill"] = "docker kill smx-feldera: " + k.stdout.strip()
        rec = "recover_f1.sh"
    else:
        pid, args = pipeline_pid()
        kill_wall = time.time()
        k = run(["docker", "exec", "smx-feldera", "kill", "-9", str(pid)])
        extra["kill"] = f"SIGKILL in-container pid {pid} ({args}) rc={k.returncode} {k.stderr.strip()}"
        rec = "recover_f2.sh"
    log(f"{fid} {extra['kill']}")
    time.sleep(HOLD_S)
    extra["pipeline_status_after_hold"] = run(["curl", "-s", "-m", "5", FURL]).stdout[:300] if fid == "F2" else None
    env = dict(os.environ, SMX_FAULT_DIR=d, SMX_DRAIN_STATE=dstate, SMX_REPLAYER_STATE=rstate,
               SMX_CONTROL_FILE=ctrl, SMX_PRE_INCARNATION=pre_inc)
    rec_start = time.time()
    r = run(["bash", os.path.join(FAULTS, rec)], env=env)
    rec_done = time.time()
    n_at = len(rows(out))
    log(f"{fid} recovered rc={r.returncode}: {r.stdout.strip()} {r.stderr.strip()[-300:]}")
    rep.wait()
    prev, stable, n = None, 0, 0
    for _ in range(300):
        try:
            g = json.loads(run(["curl", "-s", FURL + "/stats"]).stdout)["global_metrics"]
            n = g["total_processed_records"]
            cur = (g["total_input_records"], n)
        except Exception:  # noqa: BLE001
            cur = None
        stable = stable + 1 if (cur is not None and cur == prev and cur[0] == cur[1]) else 0
        prev = cur
        if stable >= 3:
            break
        time.sleep(1)
    open(stop, "w").close()
    drain.wait()
    after = json.loads(run(["curl", "-s", FURL]).stdout)
    trace = open(os.path.join(d, "pipeline-status-trace.txt")).read() if os.path.exists(
        os.path.join(d, "pipeline-status-trace.txt")) else ""
    ds, rsx = json.load(open(dstate)), json.load(open(rstate))
    extra.update({
        "n_recovery_steps": count_steps(os.path.join(FAULTS, rec)), "step_count_method": "markers",
        "recover_rc": r.returncode, "recover_stdout": r.stdout.strip(), "recover_stderr": r.stderr.strip()[-800:],
        "recompiled": "Compiling" in trace or "Pending" in trace or before.get("program_version") != after.get("program_version"),
        "operator_start_issued": "operator issued start" in trace,
        "program_version_before_after": [before.get("program_version"), after.get("program_version")],
        "program_status_after": after.get("program_status"),
        "pipeline_status_trace_head": trace[:1500], "pipeline_status_trace_tail": trace[-800:],
        "drain_state": {k: ds[k] for k in ("n_connects", "n_raw_inserts", "n_written", "n_duplicate_inserts",
                                           "n_deletes", "disconnects")},
        "raw_engine_duplicates": ds["n_duplicate_inserts"],
        "replayer": {k: rsx.get(k) for k in ("last_acked", "failures", "rewinds", "n_events_sent", "n_posts")},
        "processed_records_final": n,
    })
    run(["docker", "compose", "down"], cwd=os.path.join(ROOT, "feldera"))
    return score("F", out, kill_wall, rec_start, rec_done, n_at, extra)


# ---------------------------------------------------------------- BC arm
def fault_bc(fid, d):
    bc = os.path.join(ROOT, "bc")
    b_in = os.path.join(d, "bc_in")
    os.makedirs(b_in, exist_ok=True)
    env = dict(os.environ, SMX_BC_IN=b_in, SMX_BC_OUT=d)
    run(["docker", "compose", "down"], cwd=bc, env=env)
    run(["docker", "compose", "up", "-d"], cwd=bc, env=env)
    out = os.path.join(d, "alerts-bc.jsonl")
    rs = time.time() + 5
    land = subprocess.Popen([PY, os.path.join(ROOT, "batch", "land_microbatches.py"), "--out-dir", b_in,
                             "--replay-factor", str(RF), "--replay-start-epoch", str(rs), "--quiet"])
    kill_wall = rs + KILL_EVENT_OFFSET / RF
    wait_until(kill_wall)
    kill_wall = time.time()
    k = run(["docker", "kill", "smx-bc-batch"])
    trace = []
    t_end = time.time() + HOLD_S
    while time.time() < t_end:
        trace.append([round(time.time() - kill_wall, 2),
                      run(["docker", "inspect", "-f", "{{.State.Status}} {{.RestartCount}}", "smx-bc-batch"]).stdout.strip()])
        time.sleep(1)
    rec_start = time.time()
    r = run(["bash", os.path.join(FAULTS, "recover_bc.sh")])
    rec_done = time.time()
    n_at = len(rows(out))
    m = re.search(r"EXECUTED_STEPS=(\d+)", r.stdout)
    land.wait()
    code = run(["docker", "wait", "smx-bc-batch"]).stdout.strip()
    insp = run(["docker", "inspect", "-f", "{{.RestartCount}} {{.HostConfig.RestartPolicy.Name}}", "smx-bc-batch"]).stdout.strip()
    run(["docker", "compose", "down"], cwd=bc, env=env)
    return score("BC", out, kill_wall, rec_start, rec_done, n_at, {
        "n_recovery_steps": int(m.group(1)) if m else None, "step_count_method": "executed steps (conditional script)",
        "recover_stdout": r.stdout.strip(), "kill": k.stdout.strip() + k.stderr.strip(),
        "status_trace_during_hold": trace[::5], "final_exit_code": code, "restart_count_and_policy": insp})


# ---------------------------------------------------------------- R arm (v3, 2026-11-07)
RW_DSN = "host=localhost port=14566 user=root dbname=dev connect_timeout=3"


def rw_stack_up(d):
    rd = os.path.join(ROOT, "risingwave")
    run(["docker", "compose", "down", "-v"], cwd=rd)
    run(["docker", "compose", "up", "-d"], cwd=rd)
    for _ in range(90):
        if run(["docker", "inspect", "-f", "{{.State.Health.Status}}", "smx-risingwave"]).stdout.strip() == "healthy":
            break
        time.sleep(2)
    with open(os.path.join(d, "deploy.log"), "w") as f:
        subprocess.run([PY, os.path.join(rd, "deploy.py"), os.path.join(d, "edition-probe-risingwave.json")],
                       stdout=f, stderr=subprocess.STDOUT)


def rw_query(sql):
    import psycopg
    with psycopg.connect(RW_DSN, autocommit=True) as c:
        return c.execute(sql).fetchall()


def fault_r(fid, d):
    """R1 only. R2 (in-container SIGKILL) is dropped: risingwave is PID 1 in the container
    (`/proc/1/cmdline` = `/risingwave/bin/risingwave single_node`), so it is identical to R1."""
    assert fid == "R1", "R2 dropped (PID 1, identical to R1); see RESULTS Deviations"
    rw_stack_up(d)
    out = os.path.join(d, "alerts-risingwave.jsonl")
    dstate, rstate = os.path.join(d, "drain-state.json"), os.path.join(d, "replayer-state.json")
    ctrl, stop = os.path.join(d, "rewind.json"), os.path.join(d, ".r-stop")
    drain = subprocess.Popen([PY, "risingwave/drain_alerts.py", "--out-file", out,
                              "--state-file", dstate, "--stop-file", stop], cwd=ROOT,
                             stdout=open(os.path.join(d, "drain.log"), "w"), stderr=subprocess.STDOUT)
    for _ in range(120):
        if os.path.exists(dstate) and json.load(open(dstate)).get("connected"):
            break
        time.sleep(0.5)
    cstop = os.path.join(d, ".clock-stop")
    clock = subprocess.Popen([PY, os.path.join(ROOT, "v3", "clock_watch.py"), "--out",
                              os.path.join(d, "clock-steps.jsonl"), "--stop-file", cstop])
    rs = time.time() + 5
    rep = subprocess.Popen([PY, os.path.join(ROOT, "risingwave", "replay_pg.py"), "--replay-factor", str(RF),
                            "--replay-start-epoch", str(rs), "--state-file", rstate, "--control-file", ctrl],
                           stdout=open(os.path.join(d, "replayer.log"), "w"), stderr=subprocess.STDOUT)
    kill_wall = rs + KILL_EVENT_OFFSET / RF
    wait_until(kill_wall)
    kill_wall = time.time()
    k = run(["docker", "kill", "smx-risingwave"])
    extra = {"kill": "docker kill smx-risingwave: " + k.stdout.strip() + k.stderr.strip()}
    log(f"{fid} {extra['kill']}")
    trace = []
    t_end = time.time() + HOLD_S
    while time.time() < t_end:
        trace.append([round(time.time() - kill_wall, 2),
                      run(["docker", "inspect", "-f", "{{.State.Status}} {{.RestartCount}}", "smx-risingwave"]).stdout.strip()])
        time.sleep(1)
    rsx_at_hold = json.load(open(rstate))
    env = dict(os.environ, SMX_CONTROL_FILE=ctrl, SMX_PY=PY)
    rec_start = time.time()
    r = run(["bash", os.path.join(FAULTS, "recover_r1.sh")], env=env)
    rec_done = time.time()
    n_at = len(rows(out))
    log(f"{fid} recovered rc={r.returncode}: {r.stdout.strip()} {r.stderr.strip()[-300:]}")
    m = re.search(r"resend_after_uid=(\S+)", r.stdout)
    recovered_max = m.group(1) if m else None
    last_acked = rsx_at_hold.get("last_acked_uid")
    # checkpoint loss (pre-reg): events the replayer had acknowledged before the kill whose
    # event_uid is above the recovered max(event_uid)
    loss = None
    if recovered_max and last_acked:
        loss = int(last_acked.split("-")[1]) - int(recovered_max.split("-")[1])
    rep.wait()
    n_final, prev_n, same = None, None, 0
    for _ in range(300):
        try:
            n_final = rw_query("SELECT count(*), count(DISTINCT event_uid) FROM auth_events")[0]
            if n_final[0] >= 500000:
                break
            same = same + 1 if n_final == prev_n else 0  # lossy run: stop once the count is flat
            prev_n = n_final
            if same >= 3:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    open(stop, "w").close()
    drain.wait()
    open(cstop, "w").close()
    clock.wait()
    ds, rsx = json.load(open(dstate)), json.load(open(rstate))
    # which corpus events never reached the table (input completeness, beyond the alert gate)
    missing_ranges = None
    try:
        have = {int(u[0].split("-")[1]) for u in rw_query("SELECT event_uid FROM auth_events")}
        miss = sorted(set(range(1, 500001)) - have)
        missing_ranges = []
        for u in miss:
            if missing_ranges and u == missing_ranges[-1][1] + 1:
                missing_ranges[-1][1] = u
            else:
                missing_ranges.append([u, u])
    except Exception as e:  # noqa: BLE001
        missing_ranges = f"query failed: {e}"
    logs = run(["docker", "logs", "smx-risingwave"])
    rlog = logs.stdout + logs.stderr
    recov_lines = [ln[:300] for ln in rlog.splitlines()
                   if re.search(r"recovery start|recovery success|recovery failed|cluster marked as|"
                                r"failed to inject|unconnected worker|panick|ERROR", ln)][:80]
    extra.update({
        "n_recovery_steps": count_steps(os.path.join(FAULTS, "recover_r1.sh")), "step_count_method": "markers",
        "recover_rc": r.returncode, "recover_stdout": r.stdout.strip(), "recover_stderr": r.stderr.strip()[-800:],
        "status_trace_during_hold": trace[::5],
        "restart_count_and_policy": run(["docker", "inspect", "-f", "{{.RestartCount}} {{.HostConfig.RestartPolicy.Name}}",
                                         "smx-risingwave"]).stdout.strip(),
        "checkpoint_loss": {"replayer_last_acked_uid_before_kill": last_acked,
                            "recovered_max_event_uid": recovered_max, "n_events_lost": loss,
                            "replayer_failures": rsx_at_hold.get("failures")},
        "auth_events_final_count_and_distinct_uids": list(n_final) if n_final else None,
        "auth_events_missing_uid_ranges": missing_ranges,
        "host_clock_steps": [json.loads(x) for x in open(os.path.join(d, "clock-steps.jsonl")) if x.strip()],
        "drain_state": {k: ds[k] for k in ("n_connects", "n_raw_inserts", "n_written", "n_duplicate_inserts",
                                           "n_resume_overlap", "n_non_insert_ops", "ops_seen", "disconnects",
                                           "connect_walls")},
        "raw_engine_duplicates": ds["n_duplicate_inserts"],
        "replayer": {k: rsx.get(k) for k in ("last_acked_uid", "failures", "rewinds", "n_events_sent", "n_inserts")},
        "engine_log_recovery_lines": recov_lines,
    })
    run(["docker", "compose", "down", "-v"], cwd=os.path.join(ROOT, "risingwave"))
    return score("R", out, kill_wall, rec_start, rec_done, n_at, extra)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", required=True, help="comma list: S1,S2,B1,B2,B3,F1,F2,BC1,B2x,B3x")
    ap.add_argument("--tag", default="scored")
    ap.add_argument("--results-dir", default="v2", help="results/<dir>/faults-<tag>/ (v3 for the R arm)")
    args = ap.parse_args()
    for fid in args.only.split(","):
        d = os.path.join(ROOT, "results", args.results_dir, f"faults-{args.tag}", fid)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        log(f"=== {fid} start ===")
        fn = {"S": fault_s, "B": fault_b, "F": fault_f, "R": fault_r}.get(fid[0]) if not fid.startswith("BC") else fault_bc
        res = fn(fid, d)
        res["fault"] = fid
        res["date"] = time.strftime("%Y-%m-%d")
        with open(os.path.join(d, "result.json"), "w") as f:
            json.dump(res, f, indent=2)
        pr = res["post_recovery"]
        log(f"=== {fid} done: steps={res['n_recovery_steps']} restored={res['wall_kill_to_infra_restored_s']}s "
            f"new_alert={res['wall_kill_to_new_correct_alert_s']}s missing={pr['n_missing']} extra={pr['n_extra']} "
            f"dup={pr['n_duplicate_keys']} grew={res['output_grew_after_recovery']} ===")


if __name__ == "__main__":
    main()

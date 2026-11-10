#!/usr/bin/env python3
"""T5 harness: every (tool, mode, target) scanned RUNS times as a separate process under nice + taskset.

Targets = all files under fixtures/ and fixtures-variants/ (minus the manifest/readme). Tools and the verdict
mapping are the ones frozen in PREREGISTRATION.md. Raw stdout/stderr/JSON per scan land in results/raw/;
one JSON line per scan in results/runlog.jsonl. Never unpickles anything itself.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

B = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(B, ".venv", "bin")
RUNS = int(os.environ.get("T5_RUNS", "3"))
ONLY = os.environ.get("T5_ONLY")  # smoke test: comma-separated substrings of target paths
RAW = os.path.join(B, "results", "raw")
LOG = os.path.join(B, "results", "runlog.jsonl")
os.makedirs(RAW, exist_ok=True)
PIN = ["nice", "-n", "10", "taskset", "-c", "0-3"]
ENV = dict(os.environ, OMP_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4", MKL_NUM_THREADS="4",
           PYTHONIOENCODING="utf-8")
TIMEOUT = 600


def targets():
    out = []
    for root_name in ("fixtures", "fixtures-variants"):
        root = os.path.join(B, root_name)
        for d, _, files in os.walk(root):
            for f in sorted(files):
                if f in ("MANIFEST.tsv",) or f.startswith("README-"):
                    continue
                p = os.path.join(d, f)
                out.append(os.path.relpath(p, B))
    out.sort()
    if ONLY:
        subs = ONLY.split(",")
        out = [t for t in out if any(s in t for s in subs)]
    return out


def run(cmd, cwd=None):
    t0 = time.monotonic()
    try:
        p = subprocess.run(PIN + cmd, cwd=cwd, env=ENV, capture_output=True, text=True, errors="replace",
                           timeout=TIMEOUT)
        return {"exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "secs": time.monotonic() - t0,
                "harness_fail": None}
    except subprocess.TimeoutExpired:
        return {"exit": None, "stdout": "", "stderr": "", "secs": time.monotonic() - t0, "harness_fail": "timeout"}
    except OSError as e:
        return {"exit": None, "stdout": "", "stderr": "", "secs": time.monotonic() - t0, "harness_fail": f"oserror: {e}"}


def modelscan(target, tag):
    out = os.path.join(RAW, f"{tag}.modelscan.json")
    if os.path.exists(out):
        os.remove(out)
    r = run([f"{VENV}/modelscan", "scan", "-p", os.path.join(B, target), "-r", "json", "-o", out, "--show-skipped"])
    issues, errors, scanned, skipped = [], [], [], []
    if os.path.exists(out):
        try:
            j = json.load(open(out))
            issues = j.get("issues", []) or []
            errors = j.get("errors", []) or []
            scanned = (j.get("summary", {}).get("scanned", {}) or {}).get("scanned_files", []) or []
            skipped = (j.get("summary", {}).get("skipped", {}) or {}).get("skipped_files", []) or []
        except json.JSONDecodeError:
            errors = ["<unparseable json>"]
    if r["harness_fail"]:
        verdict = "harness_fail"
    elif issues:
        verdict = "flagged"
    elif r["exit"] == 3 or (not scanned and skipped):
        verdict = "skipped"
    elif r["exit"] == 2 or errors:
        verdict = "error"
    else:
        verdict = "clean"
    detail = {"n_issues": len(issues), "severities": sorted({i.get("severity", "?") for i in issues}),
              "operators": sorted({f"{i.get('module','?')}.{i.get('operator','?')}" for i in issues}),
              "n_errors": len(errors), "errors": [str(e)[:200] for e in errors][:5],
              "scanned_files": scanned, "skipped_files": [str(s)[:200] for s in skipped][:10]}
    return verdict, r, detail


PS_RE = {k: re.compile(rf"{k}: (\d+)") for k in ("Scanned files", "Infected files", "Dangerous globals", "Suspicious globals")}


def picklescan(target, tag, mode):
    if mode == "file":
        r = run([f"{VENV}/picklescan", "-p", os.path.join(B, target), "-g"])
    else:
        tmp = tempfile.mkdtemp(prefix="t5psdir-")
        try:
            os.link(os.path.join(B, target), os.path.join(tmp, os.path.basename(target)))
        except OSError:
            shutil.copyfile(os.path.join(B, target), os.path.join(tmp, os.path.basename(target)))
        r = run([f"{VENV}/picklescan", "-p", tmp, "-g"])
        shutil.rmtree(tmp, ignore_errors=True)
    txt = r["stdout"] + "\n" + r["stderr"]
    nums = {k: (int(m.group(1)) if (m := rx.search(txt)) else None) for k, rx in PS_RE.items()}
    globs = sorted(set(f"{a}:{b}" for a, b in re.findall(r"(?m)^\s+\*\s+(\S+) - (\w+)", r["stdout"])))[:30]
    if r["harness_fail"]:
        verdict = "harness_fail"
    elif r["exit"] == 1:
        verdict = "flagged"
    elif r["exit"] == 2:
        verdict = "error"
    elif nums["Scanned files"] == 0:
        verdict = "skipped"
    else:
        verdict = "clean"
    return verdict, r, {"counts": nums, "globals_listed": globs}


def fickling(target, tag):
    r = run([f"{VENV}/python", "-I", os.path.join(B, "fickling_scan.py"), os.path.join(B, target)])
    detail = {}
    verdict = "harness_fail" if r["harness_fail"] else None
    try:
        j = json.loads(r["stdout"])
        detail = {"mode": j["mode"], "n_members": j["n_members"],
                  "severities": sorted({m["severity"] for m in j["members"].values()}),
                  "errors": [e[:200] for m in j["members"].values() for e in m["errors"]][:5],
                  "results": [x[:300] for m in j["members"].values() for x in m["results"]][:5]}
        verdict = verdict or j["verdict"]
    except (json.JSONDecodeError, KeyError):
        verdict = verdict or "error"
        detail = {"stderr_tail": r["stderr"][-400:]}
    return verdict, r, detail


def main():
    tg = targets()
    arms = [("modelscan", None), ("picklescan", "file"), ("picklescan", "dir"), ("fickling", None)]
    n = 0
    with open(LOG, "a") as log:
        for run_i in range(1, RUNS + 1):
            for target in tg:
                tag = re.sub(r"[^A-Za-z0-9._-]", "_", target) + f".run{run_i}"
                for tool, mode in arms:
                    if tool == "modelscan":
                        verdict, r, detail = modelscan(target, tag)
                    elif tool == "picklescan":
                        verdict, r, detail = picklescan(target, tag, mode)
                    else:
                        verdict, r, detail = fickling(target, tag)
                    if r["harness_fail"]:  # one retry, per the stop rule
                        if tool == "modelscan":
                            verdict, r, detail = modelscan(target, tag)
                        elif tool == "picklescan":
                            verdict, r, detail = picklescan(target, tag, mode)
                        else:
                            verdict, r, detail = fickling(target, tag)
                        detail["retried"] = True
                    arm = tool if mode is None else f"{tool}-{mode}"
                    with open(os.path.join(RAW, f"{tag}.{arm}.txt"), "w") as fh:
                        fh.write(f"$ {arm} {target}\nexit={r['exit']} secs={r['secs']:.4f}\n--- stdout\n{r['stdout']}\n--- stderr\n{r['stderr']}\n")
                    row = {"run": run_i, "target": target, "arm": arm, "verdict": verdict, "exit": r["exit"],
                           "secs": round(r["secs"], 4), "harness_fail": r["harness_fail"], "detail": detail}
                    log.write(json.dumps(row) + "\n"); log.flush()
                    n += 1
                    if n % 50 == 0:
                        print(f"{n} scans done (run {run_i}/{RUNS}, {len(tg)} targets × {len(arms)} arms)", file=sys.stderr, flush=True)
    print(f"done: {n} scans, {len(tg)} targets, {RUNS} runs → {LOG}", file=sys.stderr)


if __name__ == "__main__":
    main()

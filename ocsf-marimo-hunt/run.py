"""Notebook-substrate reproducibility/portability — marimo .py vs .ipynb, measured.

H-NOTEBOOK-SUBSTRATE-01 holds that the authoring layer is detection-as-code's lock-in/reproducibility
frontier: a Jupyter `.ipynb` is JSON that embeds outputs and execution counts (git-noisy, hidden-state-
prone, ~24% of public notebooks re-run / ~4% reproduce per Pimentel et al. MSR 2019), while marimo's
reactive pure-`.py` model is reproducible and portable by construction. This exercises the marimo hunt in
`hunt.py` three ways:

1. Reproducibility: export the notebook to a flat script and run it twice headless — identical output.
2. Lock-in surface: export the same notebook to `.ipynb` and count the mutable, format-specific fields
   it carries (cells / outputs / execution_count) that the `.py` does not.
3. Portability: confirm the hunt is plain SQL with no notebook-runtime APIs (no dbutils, no `.dbc`).

This is more demonstration than performance benchmark — the value is the by-construction property, and the
measured parts (identical re-runs, the format diff-surface) make it concrete. Tier B/C.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NB = os.path.join(HERE, "hunt.py")
WORK = os.path.join(HERE, "_work")
MARIMO = os.path.join(HERE, "..", ".venv", "bin", "marimo")
PY = os.path.join(HERE, "..", ".venv", "bin", "python")


def export(kind, out):
    subprocess.run([MARIMO, "export", kind, NB, "-o", out], capture_output=True, text=True, check=True)
    return out


def run():
    os.makedirs(WORK, exist_ok=True)

    # 1. reproducibility: export to a flat script, run it twice, compare stdout
    script = export("script", os.path.join(WORK, "hunt_flat.py"))
    runs = []
    for _ in range(2):
        r = subprocess.run([PY, script], capture_output=True, text=True)
        runs.append(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "")
    reproducible = runs[0] == runs[1] and runs[0] != ""
    hunt_result = json.loads(runs[0]) if reproducible else None

    # 2. lock-in surface: export to ipynb, count format-specific mutable fields vs the .py
    ipynb = export("ipynb", os.path.join(WORK, "hunt.ipynb"))
    nb = json.load(open(ipynb))
    cells = nb.get("cells", [])
    exec_counts = sum(1 for c in cells if "execution_count" in c)
    output_blocks = sum(len(c.get("outputs", [])) for c in cells)
    py_lines = sum(1 for _ in open(NB))
    py_embedded_outputs = 0           # a .py source file carries none by definition
    py_exec_counts = 0

    # 3. portability: the hunt is plain SQL, no notebook-runtime APIs
    src = open(NB).read()
    runtime_lockin = any(tok in src for tok in ("dbutils", "displayHTML", "%sql", "spark.sql(", ".dbc"))
    portable_sql = ("con.execute(" in src) and not runtime_lockin

    return {"benchmark": "ocsf-marimo-hunt", "evidence_tier": "B/C (reproducibility/portability demonstration)",
            "reproducibility": {"two_headless_runs_identical": reproducible, "hunt_result": hunt_result},
            "lock_in_surface": {
                "marimo_py": {"format": "pure python source", "lines": py_lines,
                              "embedded_outputs": py_embedded_outputs, "execution_counts": py_exec_counts},
                "jupyter_ipynb": {"format": "JSON", "cells": len(cells),
                                  "execution_count_fields": exec_counts, "embedded_output_blocks": output_blocks}},
            "portability": {"runtime_lockin_apis_present": runtime_lockin, "plain_sql_over_duckdb": portable_sql}}


def render_md(res):
    rep = res["reproducibility"]; li = res["lock_in_surface"]; po = res["portability"]
    return f"""# Notebook substrate — marimo .py vs .ipynb (results)

**Tier B/C, a reproducibility/portability demonstration** (the value is a by-construction property; the
measured parts make it concrete). The same OCSF hunt (`hunt.py`, a marimo notebook) exercised three ways.

## 1. Reproducibility (headless, deterministic)

Exported to a flat script and run twice headless: **identical output = {rep['two_headless_runs_identical']}**,
result `{rep['hunt_result']}`. A marimo notebook runs top-to-bottom in dependency order with no hidden
kernel state, so a re-run reproduces by construction.

## 2. Lock-in / diff surface

| format | unit | cells | execution-count fields | embedded output blocks |
|---|---|---|---|---|
| marimo `.py` | pure python source ({li['marimo_py']['lines']} lines) | — | {li['marimo_py']['execution_counts']} | {li['marimo_py']['embedded_outputs']} |
| Jupyter `.ipynb` | JSON | {li['jupyter_ipynb']['cells']} | {li['jupyter_ipynb']['execution_count_fields']} | {li['jupyter_ipynb']['embedded_output_blocks']} |

The `.ipynb` is JSON with a per-cell `execution_count` slot (mutates on every run, churns git diffs); a
freshly-exported one has no output blocks yet, but a *worked* notebook accretes embedded outputs in those
cells — the stale-output / out-of-order-execution drift behind the Pimentel reproducibility rates. The
`.py` carries neither: the file is the code, period, and re-running can't desync output from source
because there is no embedded output.

## 3. Portability

Notebook-runtime lock-in APIs present (dbutils / displayHTML / %sql / `.dbc`): **{po['runtime_lockin_apis_present']}**.
The hunt is plain SQL over DuckDB (**{po['plain_sql_over_duckdb']}**), so the detection logic moves to any
SQL engine without rewriting around a notebook runtime.

## Reading

The point isn't that notebooks are bad — it's that the *authoring format* decides whether a detection is
reproducible and portable by default. A marimo notebook is a plain, diff-clean `.py` that re-runs
identically headless and carries no runtime lock-in, where the equivalent `.ipynb` embeds mutable
execution state and a Databricks `.dbc` would add proprietary packaging. For detection-as-code — content
that has to be reviewed, version-controlled, and run anywhere — the substrate is the lock-in frontier the
hypothesis names. This is a demonstration on one hunt, not a population study; Pimentel et al.'s
reproducibility rates are the external anchor it sits against. Tier B/C.
"""


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    res = json.load(open(os.path.join(rdir, "results.json"))) if args.render_only else run()
    if not args.render_only:
        with open(os.path.join(rdir, "results.json"), "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
        print(f"  reproducible(2 headless runs): {res['reproducibility']['two_headless_runs_identical']}  "
              f"result={res['reproducibility']['hunt_result']}")
        li = res["lock_in_surface"]
        print(f"  .py: {li['marimo_py']['execution_counts']} exec-counts / {li['marimo_py']['embedded_outputs']} outputs  |  "
              f".ipynb: {li['jupyter_ipynb']['execution_count_fields']} exec-counts / {li['jupyter_ipynb']['embedded_output_blocks']} outputs")
        print(f"  portable plain-SQL, no runtime lock-in: {res['portability']['plain_sql_over_duckdb']}")
    with open(os.path.join(rdir, "RESULTS.md"), "w") as f:
        f.write(render_md(res))
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()

# Notebook substrate — marimo .py vs .ipynb (results)

**Tier B/C, a reproducibility/portability demonstration** (the value is a by-construction property; the
measured parts make it concrete). The same OCSF hunt (`hunt.py`, a marimo notebook) exercised three ways.

## 1. Reproducibility (headless, deterministic)

Exported to a flat script and run twice headless: **identical output = True**,
result `{'beacon_conns': 60, 'no_mfa_attachpolicy': 1}`. A marimo notebook runs top-to-bottom in dependency order with no hidden
kernel state, so a re-run reproduces by construction.

## 2. Lock-in / diff surface

| format | unit | cells | execution-count fields | embedded output blocks |
|---|---|---|---|---|
| marimo `.py` | pure python source (64 lines) | — | 0 | 0 |
| Jupyter `.ipynb` | JSON | 4 | 4 | 0 |

The `.ipynb` is JSON with a per-cell `execution_count` slot (mutates on every run, churns git diffs); a
freshly-exported one has no output blocks yet, but a *worked* notebook accretes embedded outputs in those
cells — the stale-output / out-of-order-execution drift behind the Pimentel reproducibility rates. The
`.py` carries neither: the file is the code, period, and re-running can't desync output from source
because there is no embedded output.

## 3. Portability

Notebook-runtime lock-in APIs present (dbutils / displayHTML / %sql / `.dbc`): **False**.
The hunt is plain SQL over DuckDB (**True**), so the detection logic moves to any
SQL engine without rewriting around a notebook runtime.

## Reading

The point isn't that notebooks are bad — it's that the *authoring format* decides whether a detection is
reproducible and portable by default. A marimo notebook is a plain, diff-clean `.py` that re-runs
identically headless and carries no runtime lock-in, where the equivalent `.ipynb` embeds mutable
execution state and a Databricks `.dbc` would add proprietary packaging. For detection-as-code — content
that has to be reviewed, version-controlled, and run anywhere — the substrate is the lock-in frontier the
hypothesis names. This is a demonstration on one hunt, not a population study; Pimentel et al.'s
reproducibility rates are the external anchor it sits against. Tier B/C.

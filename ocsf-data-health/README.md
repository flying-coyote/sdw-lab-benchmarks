# Cross-tool assurance gap (ocsf-data-health)

A small, reproducible benchmark for one question that the rest of the practice
rests on: **how much of a security estate's true state can any single tool tell
you, versus the cross-tool view that merges them by freshness and authority — and
how much does no tool cover at all?**

It is the first-party measurement behind the four-layer **data-health framework**
(source → flow → quality → cross-tool gap) — the productised "data quality /
assurance" deliverable the SDW Capability Matrix scores and the consulting sells.
Until now that framework's fourth layer, the *cross-tool gap*, was a thesis with
no first-party benchmark. This repository runs the measurement.

## What it measures

A synthetic estate of **20,000 assets × 7 attributes = 140,000 ground-truth
cells** whose *true* state is planted (known, because we generated it). Four
source tools each observe the estate through a deterministic flaw model — a
coverage gap, a staleness lag, an authority limit — the way real consoles do.
Then four exact, set-based measures (no timings, no fuzzy matching):

1. **Single-tool recovery** — each tool alone: the fraction of true cells it
   reports *correctly* (coverage × freshness × authority).
2. **Cross-tool best-context recovery** — a freshness/authority-ranked merge
   ("best source per attribute") that materially exceeds the best single tool.
3. **Residual assurance gap** — cells no tool reports correctly: the real blind
   spot, the risk surface the assurance review exists to find.
4. **The confidence + freshness score is the lever** — the scored merge versus a
   naive "trust the system of record" merge with no freshness ranking. The gap
   between them is what the score buys.

## Results (DuckDB 1.5.3, seed 20260601)

| Measure | Value |
|---|--:|
| (1) best **single** tool recovery (CMDB) | **47.7%** |
| (2) **cross-tool** best-context recovery | **75.6%** (**+27.9%** over best single) |
| (3) residual assurance gap (no tool correct) | **24.4%** |
| (4) lever gain (scored merge − naive authority merge) | **+25.1%** |

The cross-tool merge recovers **75.6%** of the estate's true state against the
best single tool's **47.7%** — the thesis claim made measurable: *assurance lives
in the cross-tool view*. The remaining **24.4%** is the blind spot no tool covers
correctly, and the freshness/confidence score is what produces the cross-tool
result (a naive authority merge gets only 50.5%). Full per-attribute numbers in
[`results/RESULTS.md`](results/RESULTS.md); machine-readable in
[`results/results.json`](results/results.json).

## Which thesis pillar

**Well-connected** (and, through it, **trustworthy**). The SDW program POV is to
use data to challenge whether a stack is *trustworthy*, *well-connected*, and
*performant*. This benchmark is the well-connected probe: a stack is well-connected
to the degree the cross-tool join recovers true state that no single console
holds. The residual gap is where well-connected meets trustworthy — state that no
tool covers correctly is state you cannot trust any alert about.

## Honesty boundary

This is **Tier B**: a reproducible, first-party, single-host, *synthetic*
measurement. It is not production telemetry and makes no production claim. The
corpus is built to isolate the cross-tool mechanism, so the corpus *is* the
argument — read [`METHODOLOGY.md`](METHODOLOGY.md) before trusting any number. The
flaw-model magnitudes (CMDB staleness window, EDR managed-only coverage, scanner
cadence, IDP owner overlap) are corpus *parameters*, not universal constants, and
are labelled as such there. The transferable, parameter-independent finding is the
**order**: cross-tool recovery > best single tool, the residual gap is small but
nonzero, and the freshness/confidence score is the lever over a naive authority
merge. The merge never invents coverage no tool has — that is what the residual
gap measures, and on a single-source attribute (`open_vuln_count`) cross-tool
equals best single by construction.

## Reproduce

```bash
# from the repo root, with the shared venv (duckdb 1.5.3, pyarrow):
SDW_DUCK_MEMORY_LIMIT=12GB .venv/bin/python3 ocsf-data-health/run.py
```

`run.py` runs the full build-and-score twice and asserts the canonical JSON is
byte-identical before writing results — the determinism check behind the Tier-B
label — and it asserts the planted ground truth passes an internal-consistency
integrity check first. Same code, same seed, same numbers, every run.

## Layout

```
run.py        corpus + flaw models + DuckDB scoring + determinism/integrity asserts
results/      RESULTS.md + results.json (generated)
METHODOLOGY.md  flaw models, the four measures, the falsification condition
```

The seeds, fixed time anchor, and scoring helpers (`new_rng`, `prf1`, `canonical`,
`connect`) live in the repo-level [`../lib/common.py`](../lib/common.py), shared
with the other benchmarks.

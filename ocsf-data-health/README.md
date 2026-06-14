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

## Three extensions — the order's robustness, a harder entity, and the headline's variance

The four headline numbers above are one point in a parameter space, on the
easiest entity (assets, one clean key). Three extensions test whether the *finding*
survives past that point. The first two preserve the v1 numbers bit-for-bit and
fold into the same build-twice determinism assert; the third (the seed sweep) runs
beside the v1 path without touching it.

**EXT-1 — parameter sweep (is the ORDER robust, not just the magnitude?)** The v1
magnitudes are functions of the flaw-model parameters. We sweep the two that move
them — a **staleness-window** multiplier on the CMDB's stale inventory (×0.6 /
×1.0 / ×1.4) and a **per-tool coverage** multiplier (×0.8 / ×1.0 / ×1.15) — across
a 9-point grid and recompute all four measures at every cell. The three orderings
the thesis rests on hold at **every** grid point: cross-tool > best-single
(smallest margin +19.4%), residual > 0, scored merge > naive (smallest lever
+17.0%), with cross-tool ranging 69.4–78.5% and the lever 17.0–28.6% as the
parameters move. The **freshness half-life** is swept separately (7–90 days) and
turns out **inert on this corpus** — the fresh source is also the higher-confidence
one, so decay never flips a winner; that null is reported, not hidden.

**EXT-2 — identities with a contested join key (entity resolution is part of the
gap).** v1 assets share one clean key. Identities do not: HR keys on
`employee_id`, the IdP on `email`, EDR on `upn`, the directory on
`sAMAccountName`, and those keys disagree, so the merge must reconcile *which
records are the same human* before it can recover an attribute. Over 12,000
planted identities × 5 attributes, a clean-key oracle (the asset-style join)
recovers **96.3%**; resolving identity from the disagreeing key *values* only and
then merging recovers **86.2%** — a **−10.1%** entity-resolution tax, the part of
the assurance gap that is *join*, not *coverage*. A naive "just pick `employee_id`"
single-key join collapses to **60.0%**.

**EXT-3 — seed sweep (is the headline MAGNITUDE a lucky draw?)** EXT-1 bounds the
ordering across the parameter grid; this bounds the two headline magnitudes
themselves by re-drawing the whole corpus — both the ground-truth RNG and the
observation-flaw RNG — across 12 independent seed pairs at fixed `V1_PARAMS`
(`seed_sweep.py`, which imports the v1 build/score functions and so leaves the v1
determinism path untouched). The numbers are tight: best-single recovery
**47.4% ± 0.15%** (95% CI 47.3–47.4%, range 47.1–47.7% over the 12 draws,
CV 0.3%) and cross-tool recovery **75.4% ± 0.21%** (95% CI 75.2–75.5%, range
75.0–75.6%, CV 0.3%), with the cross-over-single gap **28.0% ± 0.12%**, the
residual gap **24.6% ± 0.21%**, and the scored-merge lever **25.0% ± 0.11%**. The
canonical (truth=701, obs=702) point published above (47.7% / 75.6%) sits at the
top edge of each band — a real reproducible draw, not a fragile one. So the
headline is a point estimate of a tight distribution, not a single fortunate seed;
at 20k assets the flaw-realization noise averages out to a fraction of a percent.
Machine-readable in [`results/seed_sweep.json`](results/seed_sweep.json).

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
cadence, IDP owner overlap, and the per-key missing/garbled rates for identities)
are corpus *parameters*, not universal constants, and are labelled as such there.
The transferable, parameter-independent finding is the **order**: cross-tool
recovery > best single tool, the residual gap is small but nonzero, and the
freshness/confidence score is the lever over a naive authority merge. The merge
never invents coverage no tool has — that is what the residual gap measures, and
on a single-source attribute (`open_vuln_count`) cross-tool equals best single by
construction.

What the extensions add and do **not** add: EXT-1 shows the *ordering* is robust
across a 3×3 staleness×coverage grid (it never inverts), not that the magnitudes
are universal — they move, on purpose. EXT-2 shows a contested join key degrades
cross-tool recovery by a measurable amount (−10.1% here) and that entity
resolution is therefore part of the assurance gap, not that any particular linker
is optimal or that this is a real organisation's resolution accuracy.

## Reproduce

```bash
# from the repo root, with the shared venv (duckdb 1.5.3, pyarrow):
SDW_DUCK_MEMORY_LIMIT=12GB .venv/bin/python3 ocsf-data-health/run.py
# EXT-3 headline-magnitude band (12 independent corpus draws; does not touch run.py):
SDW_DUCK_MEMORY_LIMIT=12GB .venv/bin/python3 ocsf-data-health/seed_sweep.py 12
```

`run.py` runs the full build-and-score twice and asserts the canonical JSON is
byte-identical before writing results — the determinism check behind the Tier-B
label — and it asserts the planted ground truth passes an internal-consistency
integrity check first. Same code, same seed, same numbers, every run.

## Layout

```
run.py        corpus + flaw models + DuckDB scoring + determinism/integrity asserts
              + EXT-1 parameter sweep + EXT-2 contested-join-key identities
seed_sweep.py EXT-3 headline-magnitude CI band (imports run.py, 12 seed re-draws)
results/      RESULTS.md + results.json + seed_sweep.json (generated)
METHODOLOGY.md  flaw models, the four measures, the two extensions, falsification
```

The seeds, fixed time anchor, and scoring helpers (`new_rng`, `prf1`, `canonical`,
`connect`) live in the repo-level [`../lib/common.py`](../lib/common.py), shared
with the other benchmarks.

## Hypothesis mapping

Advances **H-CROSS-TOOL-ASSURANCE-01**: the four measures (single-tool recovery,
cross-tool best-context recovery, residual gap, scored-merge lever) are the first-party
Tier-B evidence for the cross-tool layer of the data-health framework. *(ID recorded
2026-06-10 per the benchmark-alignment audit.)*

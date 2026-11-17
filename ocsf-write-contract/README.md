# BENCH-D — hot-tier write contract

## What it measures

How does data *enter* the store under streaming ingest, and does that contract
differentiate the backends? Three realizations of the hot-tier write:

- **file-write** — classic Iceberg: a new data file, a manifest, and a fresh
  `metadata.json` on every commit. *(measured, via pyiceberg + a local SQL catalog)*
- **SQL-transaction** — DuckLake: an ACID transaction against a catalog that inlines small
  batches. *(measured, via the DuckDB `ducklake` extension)*
- **never-write** — Streambased ISK: producing to Kafka is the write. *(pending: vendor-
  published, seed-stage, no independent deployment to measure — recorded, not estimated)*

The decisive case is small-batch streaming, where the per-commit overhead of the
file-write contract is paid most often. Metrics per arm × batch size: commit latency
p50/p95/p99, files written per commit (the metadata churn), storage bytes, and a
read-contract-coherence check — does one engine (DuckDB) read both tiers and return
identical answers for the same logical data?

## Result (first pass, Tier B)

On the small-commit rung, file-write costs **~4 files per commit** vs DuckLake's **1**, with
roughly **2× the commit latency** and several times the storage; the gap narrows on large
batches, because the per-commit overhead amortizes over more rows. The unified read contract
**holds**: one engine reads both tiers identically (after writing a `version-hint.text` that
DuckDB's Iceberg reader needs and pyiceberg doesn't emit — a small real interop wrinkle).
Full numbers in [results/RESULTS.md](results/RESULTS.md).

Re-derived from `results/results.json`: 201 files over 50 small commits for Iceberg (4.02) against 50
for DuckLake, and a commit-latency ratio of 27.04 against 11.66 ms (2.32×). The files-per-commit count is
measured, and it is close to fixed by the Iceberg commit itself, which writes a data file, a manifest, a
manifest list and a metadata file each time. The latency spread is wide on the small rung, CV 37.4%
(Iceberg) and 26.1% (DuckLake) over 50 commits, so read the 2.32× as roughly 2×. The storage gap holds on
the small rung only (1,638,924 against 200,036 bytes, 8.2×); on the large rung DuckLake stores slightly
more (1,166,824 against 1,099,782 bytes).

## What would have made it fail

The write-contract claim would have failed if the file counts or commit latencies had come out equal on
the small rung; the large rung is the within-bench control that shows the gap narrowing as batches grow.
The read-coherence check fails if DuckDB returns different counts or sums for the two tiers. The third
arm (never-write) is unmeasured, so the bench cannot test the tiering claim that needs it.

## Pre-registration

None. No pre-registration file exists in this folder.

## Reproduce

```bash
.venv/bin/python ocsf-write-contract/run.py        # both arms, both rungs, coherence check
.venv/bin/python ocsf-write-contract/run.py --render-only
```

The OCSF ingest corpus is seeded and identical for both arms (fair input); commit latencies
are machine-specific medians reported with spread, never asserted as constants. `run.py` rewrites
`results/RESULTS.md`, so dated corrections live in this README. The DuckDB ducklake extension is
installed at run time.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json`, the first pass, the only run.
- [ISK-ARM.md](ISK-ARM.md), the plan for the unmeasured never-write arm.

## Versions and pins

`requirements.txt` pins DuckDB 1.5.3, pyiceberg 0.11.1 and pyarrow 24.0.0; `results/results.json`
records DuckDB 1.5.3 only, and the ducklake extension version is not recorded.

## Evidence tier and limits

Tier B: single machine, synthetic OCSF ingest, two of three contracts. The write-contract
differentiation and the read-contract-coherence verdict are real measured findings at this
tier; the latencies are this host's medians. The never-write (ISK) arm is unmeasured
(vendor-blocked). The integrating "tiering beats one backend" claim and the Iceberg-V4
efficient-materialization null both need the third arm and a production-volume run, and a
named reviewer (Jake Thomas) on whether this resembles a real tiered build.

Storage bytes are not counted the same way for the two arms: DuckLake's figure includes its catalog
database file, and Iceberg's excludes its SQLite catalog, which sits outside the warehouse directory the
count walks (`run.py`, `run_iceberg` and `run_ducklake`). Each rung ran once, and no rig stamp
(methodology §7b) was recorded, so read absolute milliseconds under §7a.

## Corrections

- *(corrected 2026-11-17: the commit-latency CVs and the large-rung storage reversal were added, since
  "several times the storage" holds for the small rung only; no number changed.)*

## Hypothesis mapping

Advances **H-DUCKLAKE-02** (the per-commit write-contract comparison) and
**H-TIERED-REALIZATION-01** (the hot-tier sub-question: which write contract the hot
tier should run, and whether one engine reads both tiers coherently). *(IDs recorded
2026-06-10 per the benchmark-alignment audit.)*

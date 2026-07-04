---
type: benchmark-spec
title: "PRE-REG — A2 same-runtime transport isolation on DuckDB (publishable leg)"
created: 2026-07-04
tags: [arrow, adbc, transport, duckdb, pre-registration]
---

# Pre-registration — A2 same-runtime transport isolation, DuckDB arm

Registered 2026-07-04 BEFORE the scored run. Not edited after scoring starts; errata append.

## Why this run exists

The headline ADBC-vs-JDBC table (results/RESULTS.md) carries a stated cross-runtime caveat: ADBC
is measured Python-Arrow while the native JDBC baseline is Java-rows, so the ~5-10x ratio mixes
the columnar-vs-row paradigm with two different runtimes. The M4 leg that removed this confound
(transport_same_runtime.py, 2026-06-15) ran against Dremio endpoints, so its numbers are withheld
under Dremio's benchmark-publication terms. This leg removes the confound on DuckDB, the same
engine the headline table uses, with no publication restriction: one runtime (Python 3), one
in-process engine (DuckDB 1.5.3), the transport paradigm as the only variable.

## Hypothesis

H-ARROW-SECURITY-STACK-01 sub-claim: with the runtime confound removed, fetching a large
OCSF-shaped result set as Arrow batches beats per-row tuple marshaling by a SINGLE-DIGIT factor
that grows with result size — consistent with the cross-runtime table's ~5-10x, not with the
~40-50x bridge-inflated numbers.

## Arms (all Python 3, same process family, same parquet input)

1. `adbc_arrow` — adbc_driver_duckdb.dbapi, `fetch_arrow_table()` (Arrow batches through ADBC).
2. `dbapi_rows` — duckdb native DBAPI cursor, `fetchall()` (Python row tuples; the same-runtime
   row baseline).
3. `native_arrow` — duckdb native `fetch_arrow_table()` (engine-native Arrow, no ADBC layer);
   reference arm separating ADBC-layer overhead from the columnar advantage.

## Corpus + query

The bench's existing deterministic OCSF-shaped result sets: `_work/rs_100000.parquet` and
`_work/rs_1000000.parquet` (9 mixed-type columns). Query: `SELECT * FROM read_parquet(...)`,
identical across arms. Row counts must match across arms or the run is invalid.

## Rigor + decision rule

7 trials per arm per size after 2 discarded warmups (`lib/common.time_trials`); medians headline,
min/max reported; a gap is claimed only when it exceeds the run-to-run spread. Machine named
(Beelink 5800H, WSL2, 48GB). Conditions: quiet host — the moar-* containers stopped for the run;
one benchmark process at a time.

**Condition amendment, 2026-07-04, appended BEFORE scoring:** the permission layer declined the
moar-* container stop, so the run proceeds with those three containers up but idle (`sleep
infinity` + two idle services, no load). The per-arm `cv_pct` from `time_trials` is the arbiter:
if any arm's CV exceeds 5%, the run is discarded and re-scheduled for a genuinely bare window
rather than published with noisy conditions.

Pre-committed readings:
- Same-runtime gap (dbapi_rows / adbc_arrow) in [2x, 15x] at 1M rows → the cross-runtime table's
  single-digit framing SURVIVES runtime isolation; report the measured factor.
- Gap < 2x → the headline table's caveat becomes a correction: most of the cross-runtime ratio
  was runtime, not transport. Report as such.
- Gap > 15x → the cross-runtime table UNDERSTATED the transport effect; investigate before
  publishing (likely a fetchall pathology, e.g. per-cell object boxing dominating).
- adbc_arrow vs native_arrow within spread → ADBC layer adds no material overhead over
  engine-native Arrow; if ADBC is slower by more than the spread, report the ADBC tax separately.

## Output

`results/transport_same_runtime_duckdb.json` + a same-runtime section appended to
results/RESULTS.md. Publishable (DuckDB OSS; no vendor publication restriction).

## Erratum — run 1 scored 2026-07-04, DISCARDED by the amended CV gate (provisional only)

Run 1 executed under the amended conditions (moar containers up-idle). Both headline-gap arms
passed the gate (adbc_arrow CV 1.4/3.7%, dbapi_rows 3.0/3.6%), but the reference arm breached it
(native_arrow 4.9% at 100k, **5.1% at 1M** — over the pre-committed any-arm 5% line), so per the
amendment the run is DISCARDED as a publishable result and nothing is appended to RESULTS.md.
Provisional direction, recorded for the re-run to confirm: rows/adbc gap **3.7× at 100k / 8.3× at
1M** (inside the pre-committed [2x, 15x] survives-band), and adbc_arrow at 0.89-0.9× of
native_arrow (no ADBC tax; the native arm used the deprecated `fetch_arrow_table()` wrapper,
which the re-run should switch to `to_arrow_table()`). Raw JSON kept at
`results/transport_same_runtime_duckdb.json` with this provisional status. Re-run owed in a
genuinely bare window: stop the moar-* containers (permission-held this session), re-invoke
`../.venv/bin/python transport_same_runtime_duckdb.py`, require every arm CV < 5%, then append
the RESULTS.md section and lift this erratum.

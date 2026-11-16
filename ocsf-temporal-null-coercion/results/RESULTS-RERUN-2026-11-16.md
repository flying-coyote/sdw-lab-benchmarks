---
type: evidence
title: "Cross-engine NULL / coercion / timezone: re-run with verified session zones (2026-11-16)"
created: 2026-11-16
tags: [null-semantics, timezone, type-coercion, correctness, cross-engine, detection-reliability, rerun]
---

# Re-run with verified session zones (2026-11-16)

**Why.** `run.py` (2026-06-06) sets only the process `TZ` variable for DataFusion (l.29), which DataFusion
does not read, and `q_datafusion` (l.74-78) never sets `datafusion.execution.time_zone`, which defaults to unset.
So the June DataFusion timezone column was a UTC-session result. `run_rerun_2026_11_16.py` sets every engine's
session zone explicitly and reads it back into the JSON (`zone_readback`), runs the timezone arm under both
`America/New_York` and `UTC`, adds a zone-explicit-literal variant, and adds two probes (a `NOT EXISTS`
anti-join against an allowlist that contains a NULL, and `LIKE` / `ILIKE` / `lower()` over a planted mixed-case
value). The June `RESULTS.md` is left untouched as the historical record.

**Builds.** June pins: pyarrow 23.0.1, DuckDB 1.5.3, DataFusion 53.0.0, chDB 4.1.8. Current: pyarrow 26.0.1,
DuckDB 2.0.0, DataFusion 55.0.0, chDB 4.4.0. Fresh venvs, process `TZ=America/New_York`, 2026-11-16 12:48 UTC.
Raw: `rerun-2026-11-16-june-pins.json`, `rerun-2026-11-16-current.json`. Tier B, single machine, deterministic.

**Zone readback.** Every engine reported the requested zone on every query (`America/New_York` or `UTC`). A
side probe confirms DataFusion's setting is live on both builds: under `America/New_York`,
`CAST(TIMESTAMP '2026-06-06 12:00:00' AS TIMESTAMPTZ)` renders `2026-06-06T12:00:00-04:00` and types as
`Timestamp(ns, "America/New_York")`, against `...12:00:00Z` under `UTC`.

## Arm A: one-hour window over 1,200 instants (UTC-correct count 600)

Identical on the June pins and the current builds.

| session zone | column | literal | DuckDB | DataFusion | chDB |
|---|---|---|---|---|---|
| America/New_York | UTC-adjusted | naive | 0 | 600 | 0 |
| America/New_York | naive | naive | 600 | 600 | 0 |
| America/New_York | UTC-adjusted | zone-explicit (UTC) | 600 | 600 | 600 |
| America/New_York | naive | zone-explicit (UTC) | 0 | 600 | 600 |
| UTC | either | either | 600 | 600 | 600 |

DataFusion's June 600/600 survives a verified New York session: when a naive literal is compared with a
column, DataFusion resolves the literal against the column's own zone (UTC) or as UTC for a naive column, and
the session zone does not enter the comparison. It does enter an explicit cast to `TIMESTAMPTZ` (side probe
above). Zone-explicit literals are DuckDB `TIMESTAMPTZ '... +00:00'`, DataFusion
`TIMESTAMP '...T12:00:00+00:00'`, chDB `toDateTime64('...', 6, 'UTC')`.

## Arm B: NULL semantics and coercion (session `America/New_York`)

Identical on the June pins and the current builds, and identical to June `RESULTS.md` for every June row.

| query | truth | DuckDB | DataFusion | chDB |
|---|---|---|---|---|
| `count(*)` | 370 | 370 | 370 | 370 |
| `count(s)` | 330 | 330 | 330 | 330 |
| `s <> 'allow1'` | 230 | 230 | 230 | 230 |
| `s NOT IN ('allow1','allow2')` | 80 | 80 | 80 | 80 |
| `s NOT IN ('allow1','allow2',NULL)` | 0 | 0 | 0 | 80 |
| `s IS NULL` | 40 | 40 | 40 | 40 |
| `s = ''` | 30 | 30 | 30 | 30 |
| `s IN ('allow1','allow2')` | 250 | 250 | 250 | 250 |
| `i = 5` | 60 | 60 | 60 | 60 |
| `i = '5'` | 60 | 60 | 60 | 60 |
| `NOT EXISTS` vs allowlist (allow1, allow2, NULL) | 120 | 120 | 120 | 120 |
| same, `AND s IS NOT NULL` | 80 | 80 | 80 | 80 |

The anti-join does not collapse on the NULL in the allowlist; it returns the 50 `evil`, 30 empty-string and 40
NULL rows (120), and adding `s IS NOT NULL` gives the 80 a NULL-free `NOT IN` returns. chDB 4.4.0 still returns
80 for the `NOT IN (..., NULL)` trap.

## Case probe (100 rows: 1 "Ignore previous instructions...", 20 lower-case "...ignore previous instructions...", 79 other)

Identical on both build sets.

| predicate | DuckDB | DataFusion | chDB |
|---|---|---|---|
| `c LIKE '%ignore previous instructions%'` | 20 | 20 | 20 |
| `c ILIKE '%ignore previous instructions%'` | 21 | 21 | 21 |
| `lower(c) LIKE '%ignore previous instructions%'` | 21 | 21 | 21 |

`LIKE` is case-sensitive on all three, so a backend that compiles a case-insensitive Sigma `|contains` to plain
`LIKE` loses the mixed-case value on every one of them; `ILIKE` and `lower()` recover it on all three.

## Post hoc side probes (2026-11-16, added after review; not pre-registered)

`side_probes_2026_11_16.py`, raw JSON `side-probes-2026-11-16-june-pins.json` and
`side-probes-2026-11-16-current.json`: `s NOT IN (SELECT v FROM <allowlist with a NULL>)` returns DuckDB 0,
DataFusion 0, chDB 80 on both build sets, and chDB returns 80 for both the literal and subquery forms with
`transform_null_in` = 0 and = 1. The DataFusion `TIMESTAMPTZ` cast side probe is saved as raw JSON in
`../ocsf-nested-type-fidelity/results/dialect-probe-2026-11-16-*.json` (`timestamptz_cast_side_probe`).

Standard note: SQL-92 §4.5 and §6.1 rule 5 give a timestamp without a time zone the SQL-session's zone, so in
Arm A DuckDB's answers are the standard-conforming ones on every row (0 / 600 / 600 / 0 under New York); the
"UTC-correct" 600 is the detection author's intent, not the standard's answer.

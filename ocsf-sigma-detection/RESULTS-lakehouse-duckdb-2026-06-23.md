---
type: benchmark
title: "RESULTS — SIGMA-EXEC lakehouse leg, backend 3 (DuckDB), H-SIGMA-01"
created: 2026-06-23
tags: [sigma, pysigma, duckdb, correlation, h-sigma-01, matrix-move-3, lakehouse, windowless]
---

# RESULTS — SIGMA-EXEC lakehouse leg, backend 3 (DuckDB), 2026-06-23

Executes the frozen pre-registration [`PRE-REG-lakehouse-engines-2026-06-22.md`](PRE-REG-lakehouse-engines-2026-06-22.md)
for the first lakehouse backend. Tier B, single host, the same synthetic planted corpus + ground truth as the
PPL and SQLite legs (`ppl_execution.gen_corpus`), so results are directly comparable. Harness:
`duckdb_execution.py` (DuckDB 1.5.4 + pySigma SQLite backend = the generic-SQL compile path the pre-reg names;
no dedicated DuckDB pySigma backend exists).

## What was measured

A Sigma `event_count` correlation (`group-by: actor_user`, `timespan: 10m`, `condition: gte 10`) compiled via
the available pySigma path and **executed verbatim on DuckDB**, scored against ground truth (20 planted true
10-min bursts; 50 decoy actor_users with ≥10 failures ever but never ≥10 in a 10-min bucket; 500 benign).

| Query | Emitted / control | Flagged | TP | Precision | Decoy FP |
|---|---|---|---|---|---|
| pySigma-emitted (sqlite backend, run on DuckDB) | `… GROUP BY actor_user HAVING event_count >= 10` — **WINDOWLESS** | 70 | 20/20 | **0.286** | 50 |
| correct windowed control (DuckDB) | `… GROUP BY actor_user, CAST(timestamp // 600 AS BIGINT) HAVING c >= 10` | 20 | 20/20 | **1.0** | 0 |

Emitted SQL verbatim (so the windowed/windowless call is auditable, not asserted):
`SELECT actor_user, COUNT(*) AS event_count FROM (SELECT * FROM logs WHERE outcome='FAILURE') AS subquery GROUP BY actor_user HAVING event_count >= 10`

## Finding

**Three-band classification: SILENTLY-DEGRADES.** DuckDB emits windowless and over-fires (every decoy fires)
even though DuckDB has full window functions — the windowed control proves the engine *can* express the
10-minute bucket and fires only the 20 true bursts. The over-fire is therefore a property of the **emitted
SQL**, not the engine. The numbers match the PPL leg (precision 0.286 / 50-decoy FP) and the SQLite leg
exactly, which is the point: a third architecturally-distinct backend (columnar/lakehouse, window-capable)
shows the identical mechanism.

This answers the pre-reg's pivotal sub-question in the **emission** direction: where DuckDB relies on the
generic/sqlite pySigma backend (no dedicated DuckDB backend), the `timespan` is dropped at compile time
regardless of the target's capability. Survivability is a property of **pySigma-backend maturity per engine**
(`sigma_sql_compilation_fidelity`), not the engine's raw `temporal_correlation_primitive`.

## What this does to Matrix Move #3 (owner-gated re-score, not auto-applied)

The Move #3 c5 detection-survivability build (`securitydataworks/scoring/matrix-c5-detection-survivability-*.yaml`)
extrapolated that SQL lakehouse engines *preserve* the correlation window because they expose window functions,
ranking the SQL engines above PPL on the temporal surface (the c5 inversion). This measurement shows that for
an engine on the generic pySigma path, that extrapolation does **not** hold — DuckDB silently degrades. The
correct refinement: the c5 band should differentiate on **compilation fidelity (does a dedicated, windowed
pySigma backend exist for this engine?)**, not on the presence of window functions. This is the falsifier the
pre-reg named — surface it to the owner as a c5 re-score (route to an MDR / owner-gated), do not auto-edit the
paid Matrix.

**Scope it leaves open (do NOT overclaim):** DuckDB has no *dedicated* pySigma backend, so this is the
generic-path data point. The pre-reg's primary prediction — that an engine with a *mature dedicated* pySigma
backend emits windowed — is untested here. **RESOLVED by backends 4-7** (see
[`RESULTS-lakehouse-engines-4-7-2026-06-23.md`](RESULTS-lakehouse-engines-4-7-2026-06-23.md)): ClickHouse
*does* have a dedicated, engine-native pySigma backend and it **also** emits windowless `event_count` and
silently degrades — so even the dedicated path drops the count-family window. H-SIGMA-01 advances 3 → 4
across the full leg (five lakehouse backends, two compile paths).

## Guard (anti-Goodhart)

The over-fire *rate* (0.286 precision / 50 decoys) tracks the planted 50:20 decoy:true ratio — it is **not**
transferable. The transferable claim is the **mechanism**: windowless emit on the generic pySigma path → the
engine over-fires regardless of its window-function capability, and the three-band classification
(SILENTLY-DEGRADES for DuckDB-via-generic-backend). Tier B, single host, n=1 corpus shape. Backends 4–7
(ClickHouse, Trino, StarRocks, Dremio) were subsequently **run** 2026-06-23 — all SILENTLY-DEGRADES; see
[`RESULTS-lakehouse-engines-4-7-2026-06-23.md`](RESULTS-lakehouse-engines-4-7-2026-06-23.md).

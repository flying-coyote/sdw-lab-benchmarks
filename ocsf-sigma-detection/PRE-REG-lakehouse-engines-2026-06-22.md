---
type: benchmark-spec
title: "Pre-Registration — SIGMA-EXEC lakehouse-engine execution (backends 3-7, H-SIGMA-01, 2026-06-22)"
created: 2026-06-22
tags: [sigma, pysigma, clickhouse, trino, duckdb, dremio, starrocks, pre-registration, correlation, h-sigma-01, matrix-move-3]
---

# Pre-registration — SIGMA-EXEC lakehouse-engine execution (backends 3-7), H-SIGMA-01

_Frozen before the run (M6 / Platt strong inference). Drafted by the autonomous loop 2026-06-22 for owner-gated execution (lab env)._

## Why this leg exists (the tie to Matrix Move #3)

Backends 1-2 (OpenSearch PPL, SQLite) both **silently dropped** the Sigma correlation window — windowless
compile → runtime over-fire (PPL 0.286 precision / 50-decoy-FP; SQLite reproduced the mechanism). That
established H-SIGMA-01 at 3/5: the silent window-drop is cross-backend, not a PPL quirk.

The Matrix Move #3 detection-survivability scoring (`securitydataworks/scoring/matrix-c5-detection-survivability-*.yaml`,
built 2026-06-22) **extrapolated** the opposite prediction for the five SQL lakehouse engines: because
ClickHouse / Trino / Dremio / DuckDB / StarRocks all expose native SQL window functions, the temporal
primitive PPL drops is *present*, so Sigma correlations should **survive** rather than silently degrade. Every
`matrix-c5-*` survivability band is **capped at 4 and tiered C** precisely because that prediction is
extrapolated from documented primitive support, **not measured execution on these backends**. This leg is the
measurement that converts the extrapolation to a result.

## Assumption under test

For a Sigma `event_count` correlation with `timespan: 10m`, do the five lakehouse engines **preserve the
window** (compile-and-execute with correct temporal semantics → fire only the true bursts), as the Move #3
scoring assumes — or do they, like PPL and SQLite, emit **windowless** SQL and over-fire?

The pivotal sub-question is *where the window-drop lives*: is it a **backend-capability** property (these
engines have window functions, so they should preserve it) or a **pySigma-SQL-emission** property (the
generic SQL backend emits `GROUP BY … HAVING count >= N` with the `timespan` dropped regardless of target,
so even window-capable engines over-fire unless the rule is hand-targeted to a windowed form)?

## Method (frozen)

- **Corpus:** the same `gen_corpus` (planted 20 true 10-min bursts + 50 decoy actor_users with ≥10 failures
  ever but never ≥10 in a 10-min bucket) used by the PPL and SQLite legs — identical ground truth, identical
  fingerprint/seed, so results are directly comparable across all backends.
- **Targets (backends 3-7):** ClickHouse, Trino, DuckDB, StarRocks, Dremio. Each reads the same OCSF-shaped
  table (the C5 fidelity store). DuckDB is the cheapest to stand up; ClickHouse/Trino next; Dremio last
  (Reflections OFF — irrelevant to firing). Run what the lab env supports; record any engine not stood up as
  **not-run**, never inferred.
- **Compile path:** for each engine, compile the correlation via the available pySigma path — a dedicated
  backend where one exists, else the generic SQL backend with the engine's dialect. **Record the emitted SQL
  verbatim** and classify it: WINDOWED (carries a 10-min bucket / range) or WINDOWLESS (the `timespan`
  dropped). This classification is the primary mechanism finding.
- **Execute + score:** run the emitted query over the corpus; score against ground truth exactly as the PPL
  leg (precision, recall, the true/decoy firing split). Also run the **hand-written correct windowed SQL**
  for each engine (group by actor_user + 10-min bucket) as the control that should fire only the 20.
- **Three-band classification per engine** (mirrors the Move #3 model): SURVIVES (windowed emit + correct
  fire), SILENTLY-DEGRADES (windowless emit + over-fire, the dangerous middle), CANNOT-PORT (refuses / no
  equivalent).

## Predicted result (the hypothesis)

**Primary prediction:** at least the engines with a mature dedicated pySigma backend emit **WINDOWED** SQL and
fire correctly (precision ≈ 1.0, recall 1.0 — only the 20 true bursts), confirming the Move #3 assumption that
SQL lakehouse engines preserve the correlation primitive. The hand-written windowed control fires the 20 on
all five (the engines *can* express it — capability is not in doubt; emission is the question).

**Most-likely nuance:** if the **generic SQL** pySigma backend emits windowless (as the SQLite backend did),
then engines relying on the generic path will **over-fire like SQLite** despite having window functions — in
which case survivability is a property of the **pySigma backend maturity per engine**, not the engine's raw
capability, and the Move #3 `sigma_sql_compilation_fidelity` criterion (not the `temporal_correlation_primitive`
criterion) is the one that actually separates them. This would *refine* Move #3, not refute the inversion.

## Falsifier (what changes the Move #3 build)

If **all five** engines emit windowless and over-fire identically to PPL/SQLite, then the silent window-drop
is a **pySigma-SQL-emission** problem, uniform across SQL backends — the engines do **not** differ on
detection-survivability by the window primitive, and the Move #3 `detection_survivability_band` scores (which
currently rank Trino/Dremio above ClickHouse partly on the temporal surface) are **wrong and must be
revised** to a uniform low band with the differentiation moving entirely to compilation-fidelity. That is a
genuine refutation of the current c5 ranking and the loop must re-score on it (Act → measure → RETHINK).

## Licensing (what each outcome does to the estate)

- **Confirm (windowed emit, correct fire):** upgrade the confirming engines' `detection_survivability_band` in
  `matrix-c5-detection-survivability-{A,B,C}.yaml` from **Tier C (extrapolated, capped at 4) → Tier B
  (measured)**, and lift the band-4 cap to the measured 1-5. Update the c5 `revalidation_triggers` (this is the
  named trigger). H-SIGMA-01 **3 → 3.5/5** (execution on a third+ architecturally distinct backend class).
- **Refute (windowless over-fire):** revise the c5 band scores to uniform-low, move differentiation to
  `sigma_sql_compilation_fidelity`, and record the correction in an MDR — the inversion finding survives
  (best-perf ≠ best-survivability) but its *mechanism* changes from primitive-presence to emission-fidelity.

## Guard (anti-Goodhart)

The over-fire *rate* tracks the planted 50:20 decoy:true ratio — do NOT report the rate as transferable; the
transferable claim is the **mechanism** (windowed-vs-windowless emit per engine) and the three-band
classification. Single host, n=1 corpus shape, Tier B ceiling. Record emitted SQL verbatim for every engine so
the windowed/windowless call is auditable, not asserted.

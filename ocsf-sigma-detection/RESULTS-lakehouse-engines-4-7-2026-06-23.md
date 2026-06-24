---
type: benchmark
title: "RESULTS — SIGMA-EXEC lakehouse leg, backends 4-7 (ClickHouse/Trino/StarRocks/Dremio) + 7-backend synthesis, H-SIGMA-01"
created: 2026-06-23
tags: [sigma, pysigma, clickhouse, trino, starrocks, dremio, correlation, h-sigma-01, matrix-move-3, lakehouse, windowless, falsifier]
---

# RESULTS — SIGMA-EXEC lakehouse leg, backends 4-7 + 7-backend synthesis, 2026-06-23

Executes the frozen pre-registration [`PRE-REG-lakehouse-engines-2026-06-22.md`](PRE-REG-lakehouse-engines-2026-06-22.md)
for the four remaining lakehouse backends, completing the leg (DuckDB / backend 3 was recorded in
[`RESULTS-lakehouse-duckdb-2026-06-23.md`](RESULTS-lakehouse-duckdb-2026-06-23.md)). Tier B, single host,
the **same** synthetic planted corpus + ground truth as every prior leg (`ppl_execution.gen_corpus`: 20 true
10-min bursts; 50 decoy actor_users with ≥10 failures ever but never ≥10 in a 10-min bucket; 500 benign;
4093 events), so all seven backends are directly comparable. Harnesses: `clickhouse_execution.py`,
`trino_execution.py`, `starrocks_execution.py`, `dremio_execution.py`. Engines from the live `moar` stack.

## The pivotal design choice this leg tested

ClickHouse is the **only** of the five lakehouse engines with a **dedicated** pySigma backend
(`pySigma-backend-clickhouse` 1.0.0 — and it is genuinely engine-native: it emits `uniqExact()` for
value_count, `arrayStringConcat(groupArray())` for the temporal sequence). Trino, Presto, StarRocks, and
Dremio have **no** dedicated backend on PyPI (all 404 as of 2026-06-23), so they compile through the generic
pySigma SQLite backend. The pre-reg's "most-likely nuance" predicted survivability would track
**dedicated-backend maturity per engine** — i.e. the dedicated ClickHouse backend was the candidate to emit
WINDOWED and SURVIVE where the generic-path engines degrade. This leg measures whether that holds.

## Per-engine result (event_count correlation: `≥10 failures per actor_user in 10m`)

| # | Engine | Class | Compile path | Emitted `event_count` | Emitted precision | Decoy FP | Windowed control | Three-band |
|---|---|---|---|---|---|---|---|---|
| 4 | ClickHouse 26.5.1 | columnar OLAP (C++) | **DEDICATED** (`ClickhouseBackend`) | **WINDOWLESS** | 0.286 | 50 | 1.0 / 0 FP | **SILENTLY-DEGRADES** |
| 5 | Trino 481 | distributed MPP (JVM) | generic SQLite | **WINDOWLESS** | 0.286 | 50 | 1.0 / 0 FP | **SILENTLY-DEGRADES** |
| 6 | StarRocks 4.1.1 | MPP OLAP (C++) | generic SQLite | **WINDOWLESS** | 0.286 | 50 | 1.0 / 0 FP | **SILENTLY-DEGRADES** |
| 7 | Dremio OSS 26.0 | federation / Arrow | generic SQLite | **WINDOWLESS** | 0.286 | 50 | 1.0 / 0 FP | **SILENTLY-DEGRADES** |

Each engine ran the pySigma-emitted windowless query AND a hand-written correct windowed control (10-min
tumbling bucket, `intDiv`/`DIV`/`FLOOR` per dialect). Every windowed control fires exactly the 20 true bursts
(precision 1.0, 0 FP) — capability is not in doubt; **every engine can express the window**. The emitted query
drops it and over-fires identically.

Emitted SQL verbatim (so the windowless call is auditable, not asserted):
- **ClickHouse** (dedicated): `SELECT actor_user, count(*) AS event_count FROM (SELECT * FROM logs WHERE outcome='FAILURE') AS subquery GROUP BY actor_user HAVING event_count >= 10`
- **StarRocks** (generic, ran verbatim): `SELECT actor_user, COUNT(*) AS event_count FROM (SELECT * FROM logs WHERE outcome='FAILURE') AS subquery GROUP BY actor_user HAVING event_count >= 10`
- **Dremio** (generic, ran verbatim): same shape over `$scratch.logs`.
- **Trino** (generic): same emitted SQL, but Trino's Calcite **rejected the verbatim alias-in-HAVING** (`COLUMN_NOT_FOUND` on `event_count`), so the windowless-equivalent (`HAVING count(*) >= 10`) was executed — same windowless query, Trino-legal. Recorded as a dialect note, not asserted as verbatim.

### Dialect footnote (secondary finding)
The generic SQLite-backend emit (`HAVING <alias>`) is **not portable verbatim**: StarRocks and Dremio accept
the alias-in-HAVING (MySQL/Calcite-lenient), Trino rejects it (strict). So beyond the silent window-drop, the
generic emit needs per-dialect repair to even execute on a strict engine — a second, independent reason the
generic path is fragile across SQL engines.

## The full 7-backend picture (this leg + the two prior legs)

| Backend | Class | Compile path | event_count emit | Three-band |
|---|---|---|---|---|
| OpenSearch PPL | search | dedicated PPL | WINDOWLESS | SILENTLY-DEGRADES |
| SQLite | embedded file | generic SQLite | WINDOWLESS | SILENTLY-DEGRADES |
| DuckDB | embedded columnar | generic SQLite | WINDOWLESS | SILENTLY-DEGRADES |
| ClickHouse | columnar OLAP (C++) | **dedicated** | WINDOWLESS | SILENTLY-DEGRADES |
| Trino | distributed MPP (JVM) | generic SQLite | WINDOWLESS | SILENTLY-DEGRADES |
| StarRocks | MPP OLAP (C++) | generic SQLite | WINDOWLESS | SILENTLY-DEGRADES |
| Dremio | federation / Arrow | generic SQLite | WINDOWLESS | SILENTLY-DEGRADES |

**Seven architecturally-distinct backends, two independent compile paths (one dedicated, one generic), one
result.** Every SQL-family backend silently drops the `event_count` 10-minute window and over-fires.

## The mechanism is per-correlation-type, not per-engine (the precise basis for the c5 re-score)

A compile-only probe across both backends isolates *where* the drop lives:

| Correlation type | generic SQLite emit | dedicated ClickHouse emit |
|---|---|---|
| `event_count` (`timespan: 10m`) | **WINDOWLESS** (`HAVING count >= N`) | **WINDOWLESS** (`HAVING count >= N`) |
| `value_count` (`timespan: 10m`) | **WINDOWLESS** (`COUNT(DISTINCT …)`) | **WINDOWLESS** (CH-native `uniqExact`) |
| `temporal_ordered` (`timespan: 10m`) | **WINDOWED** (`ORDER BY timestamp` + span) | **WINDOWED** (`max(last)-min(first) <= 600`) |

The window-drop is a property of how pySigma's correlation→SQL conversion handles **each correlation type**,
**identical** across the generic and the dedicated ClickHouse backend: `event_count` and `value_count` drop
the `timespan`; `temporal_ordered` carries it. The engine and the dedicated-vs-generic choice are
**irrelevant** to count-family survivability.

(Note on the temporal emit: it carries the 600s constant via a `max(last)-min(first) <= 600` span over the
whole group — window-*aware*, but a coarse min/max span rather than a true sliding window, so "WINDOWED" here
means "the timespan survives compilation," not "the windowing is semantically ideal." That nuance doesn't
affect the count-family finding.)

## Verdict against the pre-registration: the FALSIFIER fires

The pre-reg's falsifier (verbatim): *"If all five engines emit windowless and over-fire identically to
PPL/SQLite, then the silent window-drop is a pySigma-SQL-emission problem, uniform across SQL backends — the
engines do not differ on detection-survivability by the window primitive, and the Move #3
`detection_survivability_band` scores (which currently rank Trino/Dremio above ClickHouse partly on the
temporal surface) are wrong and must be revised."*

All five lakehouse engines (plus the two prior backends) emitted windowless and over-fired identically.
**The falsifier condition is met.** And it is met *more strongly* than the pre-reg anticipated: the one engine
with a mature, dedicated, engine-native backend (ClickHouse) **also** drops the `event_count` window, so even
"does a dedicated backend exist" is too coarse a differentiator. The count-family window-drop is uniform at
the pySigma conversion layer.

The **inversion finding survives** (best-performance ≠ best-detection-survivability — a fast columnar engine
silently over-fires a brute-force rule), but its **mechanism changes**: from *temporal-primitive presence per
engine* to *per-correlation-type emission fidelity in pySigma*, uniform across engines.

## What this does to Matrix Move #3 c5 (owner-gated re-score — NOT auto-applied)

The Move #3 c5 detection-survivability build (`securitydataworks/scoring/matrix-c5-detection-survivability-*.yaml`)
currently ranks SQL lakehouse engines against each other on the temporal surface (Trino/Dremio above
ClickHouse), extrapolated Tier-C from documented window-function support and capped at band 4. This
measurement refutes that **per-engine** ranking for the count-correlation family:

1. For `event_count` / `value_count` correlations, the survivability band should be **uniform-low across all
   SQL engines** — the window is dropped at the pySigma conversion layer regardless of engine or dedicated
   backend. No engine-vs-engine differentiation is supported by measurement.
2. The differentiation that does exist is **per-correlation-type** (`temporal_ordered` survives;
   `event_count`/`value_count` do not) and belongs to `sigma_sql_compilation_fidelity`, **not**
   `temporal_correlation_primitive`.
3. H-SIGMA-01 advances **3 → 4** (executed on five lakehouse backends across two compile paths, including a
   dedicated engine-native backend).

This is the named c5 `revalidation_trigger`. **Surface it to the owner as a c5 re-score routed through an MDR
(status Proposed); do not auto-edit the paid Matrix YAMLs.**

## Scope guards (do NOT overclaim)

- **Over-fire rate is not transferable.** The 0.286 precision / 50-decoy-FP tracks the planted 50:20
  decoy:true ratio by construction. The transferable claims are (a) the **mechanism** (windowless emit on
  every SQL backend → over-fire regardless of engine capability), (b) the **three-band** classification
  (SILENTLY-DEGRADES, uniform), and (c) the **per-correlation-type** locus of the drop.
- Tier B, single host, synthetic planted corpus, n=1 corpus shape. Not a production detection-efficacy claim.
- **Dremio scope (DeWitt):** this leg records Dremio **firing-correctness only** — no Dremio performance
  numbers (latency/throughput), and it is **independent of the answer-equality reader-count benchmark** where
  Dremio is the withheld participant. The pre-reg lists Dremio as backend 7 and firing-correctness is exactly
  the survivability measurement, so it is in scope here; perf stays withheld.
- **Versions:** ClickHouse 26.5.1.882, Trino 481, StarRocks 4.1.1-14b7e3f, Dremio image `dremio-oss:26.0`
  (the in-engine `version()` string returns an internal build id `3.1.1-dremio-2024…`; the image tag is the
  authoritative product version). pySigma 1.3.3, pySigma-backend-sqlite 1.1.3, pySigma-backend-clickhouse
  1.0.0 (run on Python 3.13 — the ClickHouse backend requires ≥3.13).
- Backends 4-7 are now **run**; no backend remains not-run for this pre-registration.

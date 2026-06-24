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
| 5 | Trino 481 | distributed MPP (JVM) | generic SQLite | **WINDOWLESS** | 0.286† | 50 | 1.0 / 0 FP | **SILENTLY-DEGRADES** |
| 6 | StarRocks 4.1.1 | MPP OLAP (C++) | generic SQLite | **WINDOWLESS** | 0.286 | 50 | 1.0 / 0 FP | **SILENTLY-DEGRADES** |
| 7 | Dremio OSS 26.0 | federation / Arrow | generic SQLite | **WINDOWLESS** | 0.286 | 50 | 1.0 / 0 FP | **SILENTLY-DEGRADES** |

† Trino's firing numbers are from the windowless-*equivalent* repair (`HAVING count(*) >= 10`): pySigma's
verbatim emit (`HAVING event_count >= 10`, the alias) was **rejected** by Trino (`COLUMN_NOT_FOUND`). The
WINDOWLESS classification is computed from the verbatim emit; the repair is the same windowless query made
Trino-legal (see the dialect footnote). The other three engines ran pySigma's emit verbatim.

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

**The independent unit here is the compile path, not the engine.** There are two paths — the generic SQLite
backend (SQLite/DuckDB/Trino/StarRocks/Dremio all compile through it and emit the byte-identical windowless
string) and the dedicated ClickHouse backend — and both drop the `event_count` window. So the strong evidence
is "two independent emission codebases, same drop," confirmed to *execute and over-fire* on seven
architecturally-distinct engines. The four new engines' identical 70-flagged / 0.286 / 50-decoy-FP rows are
**corpus-determined** (the same windowless query over the same 4093-event corpus must return the same set) —
they confirm the windowless emit runs and over-fires on each engine/dialect, they are **not** four
independent firing draws. The transferable claim is the mechanism + the three-band, not the rate.

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

**Correction to the pre-reg's own phrasing (verified against the YAMLs 2026-06-23):** the pre-reg quote above
says the current bands "rank Trino/Dremio above ClickHouse partly on the temporal surface." That phrase is
imprecise. In the actual scoring files (`02-projects/securitydataworks/scoring/matrix-c5-detection-survivability-{A,B,C}.yaml`),
`temporal_correlation_primitive` is scored **5 for Trino, Dremio, AND ClickHouse alike** — temporal does
**not** differentiate them. The Archetype-A per-engine gap (Trino/Dremio 4.20 vs ClickHouse 3.95) comes
**entirely from `sigma_sql_compilation_fidelity`** (Trino/Dremio 4 vs ClickHouse 3). So the falsifier's bite
does not land on a temporal *ranking* (there isn't one); it lands on the uniform `detection_survivability_band`
= 4 itself, whose band-4 value bakes in a "the window survives on these SQL engines" assumption that this
measurement falsifies for the count family.

## What this does to Matrix Move #3 c5 (owner-gated re-score — NOT auto-applied)

The Move #3 c5 detection-survivability build (`02-projects/securitydataworks/scoring/matrix-c5-detection-survivability-{A,B,C}.yaml`)
scores each engine on four weighted criteria; the headline `detection_survivability_band` is **uniform 4**
across Trino/Dremio/ClickHouse (Archetype A), Tier C, capped at band 4 because correct execution on these
engines was unmeasured (SIGMA-EXEC had run only PPL+SQLite). This leg is the named `revalidation_trigger`.
What it refutes, precisely:

1. The uniform `detection_survivability_band` = 4 for the **count-correlation family** (`event_count` /
   `value_count`) is unsupported — the window is dropped at the pySigma conversion layer regardless of engine
   or dedicated backend, so the band should go **uniform-low** for that family. The band-4 value encoded a
   window-survives assumption that measurement falsifies.
2. The per-engine spread the build already assigns to `sigma_sql_compilation_fidelity` (Trino/Dremio 4 vs
   ClickHouse 3) is the **correct locus** of engine differentiation and stands — the measurement *confirms*
   that the real difference is compilation/dialect fidelity, not the temporal primitive (which is tied at 5
   and should arguably drop for the count family too, since no SQL engine's temporal primitive is actually
   reached by the count-correlation emit). This is a refinement of the criterion's role, not a new criterion.
3. The confirming engine bands move **Tier C → Tier B** (measured) per the licensing rule, but **downward**
   (the trigger's "lift the band-4 cap" assumed confirmation; this is the refute branch, so the bands fall,
   not rise). H-SIGMA-01 advances **3 → 4** on the tracker's execution-breadth convention (five lakehouse
   backends, two compile paths, one dedicated engine-native — not a fresh rubric, the existing per-stage
   increment).

A deployed private page (`~/securitydataworks/src/pages/matrix/private/detection-survivability.astro`)
restates the per-engine totals and must be re-checked against any ratified re-score. This is routed through
**MDR-0034** (`project1/02-projects/securitydataworks/decisions/MDR-0034-c5-detection-survivability-band-rescore.md`,
status **Proposed**, owner-gated); do not auto-edit the paid Matrix YAMLs or the page.

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

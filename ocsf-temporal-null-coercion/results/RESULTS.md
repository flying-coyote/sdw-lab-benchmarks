# Cross-engine NULL / type-coercion / timezone correctness

**Tier B · single machine · deterministic.** The shapes where security answers silently diverge across engines
aren't count/sum on point-lookups — they're NULL three-valued logic, type coercion, and timezone handling.
Byte-identical Parquet, SQL-standard (or known-UTC) ground truth, session timezone forced to
`America/New_York`. SQL engines: pyarrow `23.0.1`, duckdb `1.5.3`, datafusion `53.0.0`, chdb `4.1.8`.

## Arm B — NULL semantics + type coercion

| query | truth | duckdb | datafusion | chdb | security note |
|---|---|---|---|---|---|
| `count(*)` | 370 | ✅ | ✅ | ✅ | all rows |
| `count(s) excludes NULL` | 330 | ✅ | ✅ | ✅ | count(col) drops the 40 NULLs |
| `s = 'allow1'` | 100 | ✅ | ✅ | ✅ | baseline equality |
| `s <> 'allow1'` | 230 | ✅ | ✅ | ✅ | <> silently excludes the 40 NULLs |
| `s NOT IN (allow1,allow2)` | 80 | ✅ | ✅ | ✅ | excludes NULLs too (evil+empty=80) |
| `s NOT IN (...,NULL) TRAP` | 0 | ✅ | ✅ | ❌ (80) | a NULL in the allowlist => matches NOTHING (detection bypass) |
| `s IS NULL` | 40 | ✅ | ✅ | ✅ | the NULLs |
| `s = '' (empty != NULL)` | 30 | ✅ | ✅ | ✅ | empty string is not NULL |
| `s IN (allow1,allow2)` | 250 | ✅ | ✅ | ✅ | IN excludes NULLs (inverse check) |
| `i = 5 (int literal)` | 60 | ✅ | ✅ | ✅ | baseline |
| `i = '5' (string literal)` | 60 | ✅ | ✅ | ✅ | coercion: standard coerces '5'->5; engines may differ/err |

✅ = matches the SQL-standard answer · ❌ = diverges (engine's answer in parens) · ⚠️ err = raised.

## Arm A — timezone handling: naive vs UTC-adjusted timestamps

The same 1,200 instants written UTC-adjusted (`timestamp[us, tz=UTC]`) and naive (`timestamp[us]`); each engine
runs the identical `count(*) WHERE col >= TIMESTAMP '2026-06-06 12:00:00' AND col < '...13:00:00'` with session
TZ = `America/New_York`. The UTC-correct window holds 600 rows.

| engine | UTC-adjusted col | naive col |
|---|---|---|
| duckdb | **0** ⚠️ | **600** ✅ |
| datafusion | **600** ✅ | **600** ✅ |
| chdb | **0** ⚠️ | **0** ⚠️ |

**Engines agree on the window count: False.** UTC-adjusted column → [0, 600]; naive column → [0, 600] (the UTC-correct count is 600).

The numbers are each engine's row count (✅ = equals the UTC-correct 600). They **do not
agree**: under a non-UTC session, DataFusion treats the tz-aware column and the literal as UTC and gets it
right; DuckDB compares the tz-aware column against the *naive literal cast into the session zone* (shifting the
window to empty) while reading the naive column directly (correct); chDB applies the session zone on both and
lands on neither. No engine is "buggy" in isolation — the SQL standard leaves naive-timestamp and naive-literal
tz-resolution to the engine — but the **same time-window query over the same bytes returns different counts on
different engines**, which is the answer-equivalence break that matters for any time-bucketed detection.

## Reading

The allowlist footgun is the one to internalise: `col NOT IN (a, b, NULL)` is empty by SQL three-valued logic,
so the instant an allowlist picks up a NULL, a "flag everything not allowlisted" detection matches nothing and
says so with a clean zero — the same silent-wrong-answer failure mode as the engine bugs, but in the *query
semantics* rather than the reader. Two patterns came out of the run. Some traps are **portable**: the everyday
NULL behaviors (`<>` and `NOT IN` and `IN` all silently dropping NULL rows, `count(col)` excluding them, `''`
not being NULL) and the string-to-int coercion (`i = '5'` → 60) behaved identically across DuckDB, DataFusion
and chDB — so they're silent the same way everywhere, which is its own hazard. Others **diverge**: chDB does
not apply the SQL three-valued-logic emptying to `NOT IN (..., NULL)` (it returned 80 where DuckDB and
DataFusion returned 0), and the time-window counts disagree three ways under a non-UTC session — so the same
detection rule gives a different answer depending on the engine. Verify-the-answer therefore has to cover NULL
logic, coercion, and timezone, not just whether two engines agree on a clean count, and the safe defaults fall
out of it: pin sessions to UTC, store tz-aware (UTC) timestamps, and never let an allowlist carry a NULL. Tier
B, single machine; the per-engine behavior table is the transferable finding and is version-bound.

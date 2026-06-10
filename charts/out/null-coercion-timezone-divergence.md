# Cross-engine NULL / coercion / timezone divergence

*Where the silent break is in query semantics, not the reader: the same byte-identical Parquet, queried under session TZ `America/New_York`, against SQL-standard (or known-UTC) ground truth.*

*Tier B · single machine · deterministic · version-bound: pyarrow 23.0.1, duckdb 1.5.3, datafusion 53.0.0, chdb 4.1.8 — the per-engine behavior is the transferable finding; re-run on upgrade.*

## NULL semantics + type coercion

| query | truth | duckdb | datafusion | chdb | note |
|---|---:|:---:|:---:|:---:|---|
| `count(*)` | 370 | ✅ | ✅ | ✅ | all rows |
| `count(s)` excludes NULL | 330 | ✅ | ✅ | ✅ | `count(col)` drops the 40 NULLs |
| `s = 'allow1'` | 100 | ✅ | ✅ | ✅ | baseline equality |
| `s <> 'allow1'` | 230 | ✅ | ✅ | ✅ | `<>` silently excludes the 40 NULLs |
| `s NOT IN (allow1, allow2)` | 80 | ✅ | ✅ | ✅ | excludes NULLs too (evil + empty = 80) |
| `s NOT IN (..., NULL)` **TRAP** | 0 | ✅ | ✅ | ❌ (80) | a NULL in the allowlist ⇒ matches nothing |
| `s IS NULL` | 40 | ✅ | ✅ | ✅ | the NULLs |
| `s = ''` (empty ≠ NULL) | 30 | ✅ | ✅ | ✅ | empty string is not NULL |
| `s IN (allow1, allow2)` | 250 | ✅ | ✅ | ✅ | IN excludes NULLs (inverse check) |
| `i = 5` (int literal) | 60 | ✅ | ✅ | ✅ | baseline |
| `i = '5'` (string literal) | 60 | ✅ | ✅ | ✅ | coercion: standard coerces `'5'` → 5 |

*✅ = matches the SQL-standard answer · ❌ = diverges (engine's answer in parens).*

## Timezone handling — naive vs UTC-adjusted timestamps

The same 1,200 instants written UTC-adjusted (`timestamp[us, tz=UTC]`) and naive (`timestamp[us]`); each engine runs the identical one-hour window count under session TZ `America/New_York`. The UTC-correct window holds **600** rows.

| engine | UTC-adjusted col | naive col |
|---|:---:|:---:|
| duckdb | **0** ⚠️ | **600** ✅ |
| datafusion | **600** ✅ | **600** ✅ |
| chdb | **0** ⚠️ | **0** ⚠️ |

*The numbers are each engine's row count (✅ = equals the UTC-correct 600). The engines do not agree: the same time-window query over the same bytes returns different counts on different engines — the answer-equivalence break that matters for any time-bucketed detection.*

**Security-relevant cell: the `s NOT IN (..., NULL)` allowlist footgun.** By SQL three-valued logic, `col NOT IN (a, b, NULL)` is empty, so the instant an allowlist picks up a NULL, a "flag everything not allowlisted" detection matches nothing and reports a clean silent zero — a detection bypass with no error. chDB does not apply that emptying (it returned 80 where DuckDB and DataFusion returned 0), so the same allowlist rule gives a different answer per engine. Pin sessions to UTC, store tz-aware (UTC) timestamps, and never let an allowlist carry a NULL.

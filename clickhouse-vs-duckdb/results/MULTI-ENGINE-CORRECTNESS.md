# Cross-engine Parquet answer-equality — does the R3 undercount generalize? (Phase E)

**Tier B · single machine · ground-truth-verified.** 13 engines (plus controls) read the **same**
Parquet file (10,000,000 rows, 814 row groups — the R3 trigger structure),
every count checked against the generator's ground truth (the corpus is a pure function of the row index,
so the true count of each `user_name` value is computable without any engine). 8
pre-registered probe values × 3 predicate classes (`=`, `IN`, `LIKE`) =
24 cells per engine. Engines were selected by *distinct
Parquet reader* (see `ENGINE-LANDSCAPE-SURVEY.md`).

## Engines

- **duckdb** — DuckDB C++ (own) — `1.5.3`
- **chdb_parquet** — ClickHouse C++ v3 reader (embedded chDB; CH 26.3, v3 default) — `4.1.8`
- **datafusion** — arrow-rs parquet (Rust) — `53.0.0`
- **polars** — polars-parquet (Rust, own) — `1.41.2`
- **pyarrow** — Arrow C++ (Acero) — `23.0.1`
- **daft** — Daft (Rust; arrow-rs-derived I/O) — `0.7.14`
- **fastparquet** — fastparquet (pure-Python, non-Arrow) — `2026.5.0`
- **clickhouse_server** — ClickHouse C++ older reader (server 25.10; v3 not default) — `25.10.2.65`
- **spark** — parquet-mr Java (the reference reader) — `3.5.0`
- **starrocks** — StarRocks C++ (own) — `4.1.1-14b7e3f`
- **trino** — Trino Java (own, not parquet-mr) — `481`
- **dremio** — Dremio Java (own vectorized) — `26.0.5-202509091642240013-f5051a07`
- **postgres** — Postgres heap (corpus loaded — independent executor, NOT a Parquet read) — `PostgreSQL 17.10`
- **chdb_mergetree** — ClickHouse MergeTree native store (within-engine control, not Parquet) — `4.1.8`

## Ground-truth scorecard (passers named as loudly as failers)

| engine | Parquet reader | role | cells correct | verdict |
|---|---|---|--:|---|
| duckdb | DuckDB C++ (own) | shared bytes | 24/24 | ✓ all correct |
| chdb_parquet | ClickHouse C++ v3 reader (embedded chDB; CH 26.3, v3 default) | shared bytes | 11/24 | ✗ −108 on 13 cell(s) |
| datafusion | arrow-rs parquet (Rust) | shared bytes | 24/24 | ✓ all correct |
| polars | polars-parquet (Rust, own) | shared bytes | 24/24 | ✓ all correct |
| pyarrow | Arrow C++ (Acero) | shared bytes | 24/24 | ✓ all correct |
| daft | Daft (Rust; arrow-rs-derived I/O) | shared bytes | 24/24 | ✓ all correct |
| fastparquet | fastparquet (pure-Python, non-Arrow) | shared bytes | 0/24 | ✗ −102 on 24 cell(s) |
| clickhouse_server | ClickHouse C++ older reader (server 25.10; v3 not default) | shared bytes | 24/24 | ✓ all correct |
| spark | parquet-mr Java (the reference reader) | shared bytes | 24/24 | ✓ all correct |
| starrocks | StarRocks C++ (own) | shared bytes | 24/24 | ✓ all correct |
| trino | Trino Java (own, not parquet-mr) | shared bytes | 24/24 | ✓ all correct |
| dremio | Dremio Java (own vectorized) | shared bytes | 24/24 | ✓ all correct |
| postgres | Postgres heap (corpus loaded — independent executor, NOT a Parquet read) | shared bytes | 24/24 | ✓ all correct |
| chdb_mergetree | ClickHouse MergeTree native store (within-engine control, not Parquet) | control | 24/24 | ✓ all correct |

**Passes ground truth on every cell: clickhouse_server, daft, datafusion, dremio, duckdb, polars, postgres, pyarrow, spark, starrocks, trino.**
**Returns a wrong answer on ≥1 cell: chdb_parquet, fastparquet** — spanning **2 distinct
reader(s)**: ClickHouse C++ v3 reader, fastparquet.

## Where the engines diverged

| value | predicate | truth | duckdb | chdb_parquet | datafusion | polars | pyarrow | daft | fastparquet | clickhouse_server | spark | starrocks | trino | dremio | postgres |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `user42` | `=` | 5099 | 5099 | **5092** | 5099 | 5099 | 5099 | 5099 | **5096** | 5099 | 5099 | 5099 | 5099 | 5099 | 5099 |
| `user42` | `IN` | 5099 | 5099 | **5092** | 5099 | 5099 | 5099 | 5099 | **5096** | 5099 | 5099 | 5099 | 5099 | 5099 | 5099 |
| `user42` | `LIKE` | 5099 | 5099 | 5099 | 5099 | 5099 | 5099 | 5099 | **5096** | 5099 | 5099 | 5099 | 5099 | 5099 | 5099 |
| `user1337` | `=` | 4972 | 4972 | **4966** | 4972 | 4972 | 4972 | 4972 | **4971** | 4972 | 4972 | 4972 | 4972 | 4972 | 4972 |
| `user1337` | `IN` | 4972 | 4972 | **4966** | 4972 | 4972 | 4972 | 4972 | **4971** | 4972 | 4972 | 4972 | 4972 | 4972 | 4972 |
| `user1337` | `LIKE` | 4972 | 4972 | 4972 | 4972 | 4972 | 4972 | 4972 | **4971** | 4972 | 4972 | 4972 | 4972 | 4972 | 4972 |
| `user7` | `=` | 5108 | 5108 | **5101** | 5108 | 5108 | 5108 | 5108 | **5102** | 5108 | 5108 | 5108 | 5108 | 5108 | 5108 |
| `user7` | `IN` | 5108 | 5108 | **5101** | 5108 | 5108 | 5108 | 5108 | **5102** | 5108 | 5108 | 5108 | 5108 | 5108 | 5108 |
| `user7` | `LIKE` | 5108 | 5108 | 5108 | 5108 | 5108 | 5108 | 5108 | **5102** | 5108 | 5108 | 5108 | 5108 | 5108 | 5108 |
| `user999` | `=` | 5055 | 5055 | 5055 | 5055 | 5055 | 5055 | 5055 | **5050** | 5055 | 5055 | 5055 | 5055 | 5055 | 5055 |
| `user999` | `IN` | 5055 | 5055 | 5055 | 5055 | 5055 | 5055 | 5055 | **5050** | 5055 | 5055 | 5055 | 5055 | 5055 | 5055 |
| `user999` | `LIKE` | 5055 | 5055 | 5055 | 5055 | 5055 | 5055 | 5055 | **5050** | 5055 | 5055 | 5055 | 5055 | 5055 | 5055 |
| `user1500` | `=` | 5106 | 5106 | **5096** | 5106 | 5106 | 5106 | 5106 | **5100** | 5106 | 5106 | 5106 | 5106 | 5106 | 5106 |
| `user1500` | `IN` | 5106 | 5106 | 5106 | 5106 | 5106 | 5106 | 5106 | **5100** | 5106 | 5106 | 5106 | 5106 | 5106 | 5106 |
| `user1500` | `LIKE` | 5106 | 5106 | 5106 | 5106 | 5106 | 5106 | 5106 | **5100** | 5106 | 5106 | 5106 | 5106 | 5106 | 5106 |
| `user256` | `=` | 5000 | 5000 | **4988** | 5000 | 5000 | 5000 | 5000 | **4997** | 5000 | 5000 | 5000 | 5000 | 5000 | 5000 |
| `user256` | `IN` | 5000 | 5000 | **4988** | 5000 | 5000 | 5000 | 5000 | **4997** | 5000 | 5000 | 5000 | 5000 | 5000 | 5000 |
| `user256` | `LIKE` | 5000 | 5000 | 5000 | 5000 | 5000 | 5000 | 5000 | **4997** | 5000 | 5000 | 5000 | 5000 | 5000 | 5000 |
| `user1023` | `=` | 5022 | 5022 | **5012** | 5022 | 5022 | 5022 | 5022 | **5019** | 5022 | 5022 | 5022 | 5022 | 5022 | 5022 |
| `user1023` | `IN` | 5022 | 5022 | **5012** | 5022 | 5022 | 5022 | 5022 | **5019** | 5022 | 5022 | 5022 | 5022 | 5022 | 5022 |
| `user1023` | `LIKE` | 5022 | 5022 | 5022 | 5022 | 5022 | 5022 | 5022 | **5019** | 5022 | 5022 | 5022 | 5022 | 5022 | 5022 |
| `user64` | `=` | 5144 | 5144 | **5137** | 5144 | 5144 | 5144 | 5144 | **5137** | 5144 | 5144 | 5144 | 5144 | 5144 | 5144 |
| `user64` | `IN` | 5144 | 5144 | **5137** | 5144 | 5144 | 5144 | 5144 | **5137** | 5144 | 5144 | 5144 | 5144 | 5144 | 5144 |
| `user64` | `LIKE` | 5144 | 5144 | 5144 | 5144 | 5144 | 5144 | 5144 | **5137** | 5144 | 5144 | 5144 | 5144 | 5144 | 5144 |

(bold = wrong answer; — = engine errored on that cell)

## Attempted but unavailable

- **feldera** — RuntimeError: feldera SDK not installed; skipping (reader rides arrow-rs, redundant with DataFusion per survey — high-setup, low reader-distinctness). [No module named 'feldera']
- **risingwave** — RuntimeError: risingwave file_scan: no working signature — file_scan('parquet', 'posix_fs', '', '/d: Failed to run the query

Caused by:
  Bind error: file_scan function supports th | file_scan('parquet', 'posix_fs', '/data/: Failed to run the query

Caused by:
  Bind error: file_scan function suppo

## Cross-engine agreement *without* ground truth (the alternative-hypothesis test)

The open question in H-ENGINE-ANSWER-EQUIVALENCE-01 is whether *cross-engine* comparison suffices or you
need *ground truth*. In this run: every divergence was a single engine against a unanimous rest, so **cross-engine majority catches it without a generator**.

- Any cross-engine divergence at all: **True**
- Any ambiguous split (engines can't resolve it among themselves): **False**

If divergences are always one-engine-vs-the-rest, running ≥3 engines and taking the majority is a
practical control even with no generator. The moment two engines agree on a wrong answer, the majority is
wrong and only ground truth saves you — so the durable control is **validate against ground truth where
you can; use cross-engine majority (≥3 engines) where you can't**, and never trust a single engine's
`count(*) WHERE` as self-evidently correct.

## Reading

This is the generalization R3 asked for, run across distinct Parquet readers rather than one engine. The
narrow claim — *answer-equivalence across engines is not free, so verify it* — holds regardless of the
count of failers: the verification is what catches a fast, silent, wrong answer, and the engines that pass
show the verification is cheap to satisfy, not unnecessary. On the broad claim (*do readers disagree?*):
this run found **2 distinct reader(s)** return a silently wrong answer over a
Parquet file the others read correctly, so the honest statement is **"more than a single isolated engine,
but not most"** — concentrated, not universal. For security data a `count(*) WHERE` is a detection
threshold or a compliance figure, so an engine that is fast and silently wrong is worse than one that is
slow and right. Single machine, deterministic reproduction; the method is the transferable finding, not any
one engine's name.

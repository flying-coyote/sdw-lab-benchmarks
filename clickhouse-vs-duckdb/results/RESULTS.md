# Results — ClickHouse vs DuckDB on OCSF-shaped event data (C3)

- DuckDB: `1.5.3`  ·  ClickHouse engine: `chDB (embedded ClickHouse)` (`chdb 4.1.8`)  
- Host: 12 vCPU, `Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39`  
- Corpus reproducible (fingerprint matches on re-generation): **True**  
- Cross-engine answers identical (every query, every config): **True**  
- Evidence tier: B (reproducible corpus + cross-engine-verified answers; latencies are machine-specific, not a production claim)

Latencies are wall-clock **medians** (min/max in the JSON) over repeated trials after warmup, on one machine. They are not deterministic and not a universal constant — read them as *which engine wins which query shape*, not as absolute milliseconds you should expect on other hardware. The corpus and the answers are the reproducible parts; see `METHODOLOGY.md`.

## 1,000,000 events  (Parquet 35 MB, fingerprint `c571ad0c5cac1871`)

### Config A — both engines query the same Parquet file in place

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 11.6 | 11.8 | duckdb | 1.02 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 41.7 | 54.6 | duckdb | 1.31 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 5.1 | 13.4 | duckdb | 2.62 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 10.4 | 11.5 | duckdb | 1.11 |
| Failed-auth burst: filter + group + having | 50 | yes | 4.0 | 8.4 | duckdb | 2.1 |

_Per-query winners: DuckDB 5, ClickHouse 0, tie 0 (of 5)._

### Config B — each engine queries its own native store

Load time (median): DuckDB native `CREATE TABLE` **61.6 ms** · ClickHouse MergeTree insert **430.0 ms**.

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 9.7 | 8.9 | clickhouse | 1.09 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 29.0 | 50.7 | duckdb | 1.75 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 2.3 | 5.5 | duckdb | 2.35 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 12.1 | 11.7 | clickhouse | 1.04 |
| Failed-auth burst: filter + group + having | 50 | yes | 5.0 | 8.9 | duckdb | 1.78 |

_Per-query winners: DuckDB 3, ClickHouse 2, tie 0 (of 5)._

## 10,000,000 events  (Parquet 354 MB, fingerprint `84f3460b5c922450`)

### Config A — both engines query the same Parquet file in place

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 74.7 | 90.2 | duckdb | 1.21 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 427.2 | 546.9 | duckdb | 1.28 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 39.2 | 81.8 | duckdb | 2.08 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 66.1 | 71.6 | duckdb | 1.08 |
| Failed-auth burst: filter + group + having | 50 | yes | 18.6 | 39.6 | duckdb | 2.13 |

_Per-query winners: DuckDB 5, ClickHouse 0, tie 0 (of 5)._

### Config B — each engine queries its own native store

Load time (median): DuckDB native `CREATE TABLE` **457.1 ms** · ClickHouse MergeTree insert **3934.4 ms**.

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 47.3 | 61.6 | duckdb | 1.3 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 290.9 | 588.5 | duckdb | 2.02 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 12.6 | 17.2 | duckdb | 1.36 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 48.0 | 41.7 | clickhouse | 1.15 |
| Failed-auth burst: filter + group + having | 50 | yes | 23.2 | 43.7 | duckdb | 1.88 |

_Per-query winners: DuckDB 4, ClickHouse 1, tie 0 (of 5)._


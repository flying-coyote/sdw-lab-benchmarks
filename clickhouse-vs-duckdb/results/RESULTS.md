# Results — ClickHouse vs DuckDB on OCSF-shaped event data (C3)

- DuckDB: `1.5.3`  ·  ClickHouse engine: `chDB (embedded ClickHouse)` (`chdb 4.1.8`)  
- Host: 14 vCPU, `Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39`  
- Corpus reproducible (fingerprint matches on re-generation): **True**  
- Cross-engine answers identical (every query, every config): **True**  
- Evidence tier: B (reproducible corpus + cross-engine-verified answers; latencies are machine-specific, not a production claim)

Latencies are wall-clock **medians** (min/max in the JSON) over repeated trials after warmup, on one machine. They are not deterministic and not a universal constant — read them as *which engine wins which query shape*, not as absolute milliseconds you should expect on other hardware. The corpus and the answers are the reproducible parts; see `METHODOLOGY.md`.

## 1,000,000 events  (Parquet 35 MB, fingerprint `c571ad0c5cac1871`)

### Config A — both engines query the same Parquet file in place

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 11.9 | 12.3 | duckdb | 1.03 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 44.2 | 53.9 | duckdb | 1.22 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 5.1 | 13.2 | duckdb | 2.61 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 11.6 | 11.9 | duckdb | 1.03 |
| Failed-auth burst: filter + group + having | 50 | yes | 6.0 | 8.5 | duckdb | 1.4 |

_Per-query winners: DuckDB 5, ClickHouse 0, tie 0 (of 5)._

### Config B — each engine queries its own native store

Load time (median): DuckDB native `CREATE TABLE` **64.2 ms** · ClickHouse MergeTree insert **434.7 ms**.

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 8.1 | 8.7 | duckdb | 1.08 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 28.0 | 49.5 | duckdb | 1.77 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 2.3 | 5.9 | duckdb | 2.51 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 8.7 | 7.3 | clickhouse | 1.19 |
| Failed-auth burst: filter + group + having | 50 | yes | 4.3 | 8.8 | duckdb | 2.04 |

_Per-query winners: DuckDB 4, ClickHouse 1, tie 0 (of 5)._

## 10,000,000 events  (Parquet 354 MB, fingerprint `84f3460b5c922450`)

### Config A — both engines query the same Parquet file in place

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 67.5 | 78.0 | duckdb | 1.16 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 395.1 | 512.0 | duckdb | 1.3 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 29.8 | 79.8 | duckdb | 2.68 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 64.9 | 74.1 | duckdb | 1.14 |
| Failed-auth burst: filter + group + having | 50 | yes | 16.5 | 39.3 | duckdb | 2.39 |

_Per-query winners: DuckDB 5, ClickHouse 0, tie 0 (of 5)._

### Config B — each engine queries its own native store

Load time (median): DuckDB native `CREATE TABLE` **481.3 ms** · ClickHouse MergeTree insert **4047.2 ms**.

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 52.0 | 56.1 | duckdb | 1.08 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 282.6 | 587.0 | duckdb | 2.08 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 13.1 | 18.9 | duckdb | 1.45 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 50.5 | 41.1 | clickhouse | 1.23 |
| Failed-auth burst: filter + group + having | 50 | yes | 19.9 | 44.6 | duckdb | 2.23 |

_Per-query winners: DuckDB 4, ClickHouse 1, tie 0 (of 5)._


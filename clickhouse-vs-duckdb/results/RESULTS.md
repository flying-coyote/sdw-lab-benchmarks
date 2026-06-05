# Results — ClickHouse vs DuckDB on OCSF-shaped event data (C3)

- DuckDB: `1.5.3`  ·  ClickHouse engine: `chDB (embedded ClickHouse)` (`chdb 4.1.8`)  
- Host: 14 vCPU, `Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39`  
- Corpus reproducible (fingerprint matches on re-generation): **True**  
- Cross-engine answers identical (every query, every config): **False**  
- Evidence tier: B (reproducible corpus + cross-engine-verified answers; latencies are machine-specific, not a production claim)

Latencies are wall-clock **medians** (min/max in the JSON) over repeated trials after warmup, on one machine. They are not deterministic and not a universal constant — read them as *which engine wins which query shape*, not as absolute milliseconds you should expect on other hardware. The corpus and the answers are the reproducible parts; see `METHODOLOGY.md`.

## 1,000,000 events  (Parquet 35 MB, fingerprint `c571ad0c5cac1871`)

### Config A — both engines query the same Parquet file in place

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 13.0 | 12.9 | clickhouse | 1.01 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 44.9 | 55.2 | duckdb | 1.23 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 5.4 | 14.1 | duckdb | 2.62 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 11.7 | 12.6 | duckdb | 1.08 |
| Failed-auth burst: filter + group + having | 50 | yes | 4.3 | 9.4 | duckdb | 2.19 |

_Per-query winners: DuckDB 4, ClickHouse 1, tie 0 (of 5)._

### Config B — each engine queries its own native store

Load time (median): DuckDB native `CREATE TABLE` **65.4 ms** · ClickHouse MergeTree insert **466.0 ms**.

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 8.2 | 8.9 | duckdb | 1.08 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 28.4 | 48.9 | duckdb | 1.72 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 2.3 | 5.9 | duckdb | 2.61 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 8.2 | 7.3 | clickhouse | 1.12 |
| Failed-auth burst: filter + group + having | 50 | yes | 4.2 | 9.0 | duckdb | 2.16 |

_Per-query winners: DuckDB 4, ClickHouse 1, tie 0 (of 5)._

## 10,000,000 events  (Parquet 354 MB, fingerprint `84f3460b5c922450`)

### Config A — both engines query the same Parquet file in place

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 67.4 | 84.6 | duckdb | 1.26 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 407.4 | 542.3 | duckdb | 1.33 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 29.7 | 84.7 | duckdb | 2.85 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 69.9 | 77.5 | duckdb | 1.11 |
| Failed-auth burst: filter + group + having | 50 | yes | 16.3 | 41.3 | duckdb | 2.54 |

_Per-query winners: DuckDB 5, ClickHouse 0, tie 0 (of 5)._

### Config B — each engine queries its own native store

Load time (median): DuckDB native `CREATE TABLE` **436.8 ms** · ClickHouse MergeTree insert **4210.4 ms**.

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 44.9 | 54.5 | duckdb | 1.21 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 274.6 | 508.2 | duckdb | 1.85 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 11.0 | 17.3 | duckdb | 1.57 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 44.2 | 35.9 | clickhouse | 1.23 |
| Failed-auth burst: filter + group + having | 50 | yes | 17.4 | 42.6 | duckdb | 2.44 |

_Per-query winners: DuckDB 4, ClickHouse 1, tie 0 (of 5)._

## 100,000,000 events  (Parquet 3544 MB, fingerprint `43e8775cf2949461`)

### Config A — both engines query the same Parquet file in place

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 437.5 | 765.6 | duckdb | 1.75 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 4317.1 | 5675.2 | duckdb | 1.31 |
| Selective lookup: one user inside a six-hour window | 1 | **NO** | 255.4 | 782.2 | duckdb | 3.06 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 367.3 | 667.0 | duckdb | 1.82 |
| Failed-auth burst: filter + group + having | 50 | yes | 124.2 | 337.7 | duckdb | 2.72 |

_Per-query winners: DuckDB 5, ClickHouse 0, tie 0 (of 5)._

### Config B — each engine queries its own native store

Load time (median): DuckDB native `CREATE TABLE` **5339.3 ms** · ClickHouse MergeTree insert **47520.3 ms**.

| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|:--:|--:|--:|:--:|--:|
| Full-scan rollup: count + bytes by class and activity | 12 | yes | 237.5 | 517.4 | duckdb | 2.18 |
| Top-20 talkers: high-cardinality group-by + order/limit | 20 | yes | 2679.6 | 4972.1 | duckdb | 1.86 |
| Selective lookup: one user inside a six-hour window | 1 | yes | 100.4 | 109.4 | duckdb | 1.09 |
| Time-bucketed rate: events per 5-minute bucket | 288 | yes | 169.8 | 272.5 | duckdb | 1.61 |
| Failed-auth burst: filter + group + having | 50 | yes | 134.6 | 321.9 | duckdb | 2.39 |

_Per-query winners: DuckDB 5, ClickHouse 0, tie 0 (of 5)._


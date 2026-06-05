# BENCH-E same-files arm — byte-identical data, two catalogs (100,000,000 rows)

**Tier B, single machine, hot/warm only.** The data files are written ONCE (DuckDB, ZSTD-3,
122,880-row groups) and the SAME bytes registered into both an Iceberg table
(pyiceberg `add_files`) and a DuckLake table (`ducklake_add_data_files`), read by the same engine
(DuckDB, memory_limit 28GB). Compression/encoding/row-group/file-size are therefore
identical by construction — every factor but the catalog/read path is accounted for.

- Bytes identical across catalogs: **True** (1.14 GB each)
- Answers identical across catalogs: **True**

| query | Iceberg ms (cv) | DuckLake ms (cv) | Iceberg/DuckLake |
|---|---|---|---|
| filtered | 45 (2%) | 47 (1%) | 0.96x |
| topn_src | 3029 (5%) | 2880 (4%) | 1.05x |
| byte_rollup | 274 (6%) | 238 (6%) | 1.15x |
| subnet_rollup | 1971 (2%) | 1980 (1%) | 1.00x |

## Reading

With the Parquet bytes literally identical in both catalogs, any latency difference here is the
metadata/read-path effect alone — the true format difference, with compression fully removed as a
confound. Read the low-CV sustained aggregations (topn_src, subnet_rollup); discount byte_rollup if its
CV is high. Compare against PARITY.md (matched-codec, different writers) and the default-config
large-scan to see how much of the original gap was the writer's compression versus the format. Tier B.

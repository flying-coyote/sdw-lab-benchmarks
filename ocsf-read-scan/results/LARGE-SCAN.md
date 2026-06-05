# BENCH-E large-scan arm — DuckLake vs Iceberg at 1,000,000,000 rows (results)

**Tier B · single machine.** 1,000,000,000 rows ingested in 20 batches of
50,000,000 (peak memory = one batch), materialized in both formats and read by the same
engine (DuckDB, memory_limit 28GB, spilling to native ext4). The only variable is the
format's read path. Latencies are machine-specific medians (warmup 1, 2 trials).

| query | Iceberg ms | DuckLake ms | Iceberg/DuckLake |
|---|---|---|---|
| full_count | 5 | 5 | 1.04× |
| filtered | 458 | 394 | 1.16× |
| topn_src | 84834 | 74144 | 1.14× |
| byte_rollup | 2805 | 1642 | 1.71× |
| subnet_rollup | 20934 | 18923 | 1.11× |

- Storage: Iceberg 13.29 GB (100 data files) ·
  DuckLake 21.62 GB (40 data files)
- Answers identical across both formats: **True**

## Reading

The open question (H-DUCKLAKE-02) was whether DuckLake's SQL-catalog advantage on small streaming
commits turns into a liability on a large full scan, where its catalog DB might become the bottleneck.
At 1,000,000,000 rows, read by one engine over the same logical data, the two formats return
identical answers and the latency column shows what the format's read path costs at this scale. The
high-cardinality aggregations (topn_src, subnet_rollup) are where a catalog or planning overhead would
surface if it existed; the byte_rollup and full_count are metadata-amortized scans. Tier B, single
machine; the answer-equality and the relative shape are the transferable findings, the magnitudes are
this host's.

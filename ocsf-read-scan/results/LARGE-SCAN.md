# BENCH-E large-scan arm — DuckLake vs Iceberg at 1,000,000,000 rows (results)

**Tier B · single machine.** 1,000,000,000 rows ingested in 20 batches of
50,000,000 (peak memory = one batch), materialized in both formats and read by the same
engine (DuckDB, memory_limit 28GB, spilling to native ext4). Latencies are medians
with CV (warmup 1, 3 trials). **This is the default-config comparison — the two writers differ in
codec/encoding, so the gap mixes the writer's compression with the format.** See SAME-FILES.md for the
byte-identical comparison that isolates the format (the read difference collapses to ~parity there).

| query | Iceberg ms (cv) | DuckLake ms (cv) | Iceberg/DuckLake |
|---|---|---|---|
| full_count | 5 (32%) | 4 (10%) | 1.15× |
| filtered | 445 (4%) | 407 (2%) | 1.09× |
| topn_src | 90514 (0%) | 79304 (5%) | 1.14× |
| byte_rollup | 2745 (3%) | 1771 (6%) | 1.55× |
| subnet_rollup | 21361 (1%) | 19435 (1%) | 1.1× |

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

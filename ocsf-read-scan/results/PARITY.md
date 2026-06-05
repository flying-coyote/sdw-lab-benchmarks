# BENCH-E parity arm — codec x format at fixed row-group (100,000,000 rows)

**Tier B, single machine, hot/warm only.** Row-group fixed at 122,880 rows across every arm; codec varied; read by the same engine (DuckDB, memory_limit 28GB). Each latency is the median of 5 trials with its coefficient of variation; a delta below the CV is not a real difference. Footer codec is verified per arm.

| arm | codec | size GB | files | filtered ms (cv) | topn_src ms (cv) | byte_rollup ms (cv) | subnet_rollup ms (cv) |
|---|---|---|---|---|---|---|---|
| ducklake_snappy | SNAPPY | 2.16 | 4 | 44 (8%) | 2707 (2%) | 194 (14%) | 1806 (2%) |
| ducklake_zstd | ZSTD | 1.14 | 4 | 52 (3%) | 2833 (2%) | 292 (13%) | 1974 (4%) |
| iceberg_snappy | SNAPPY | 2.95 | 2 | 47 (1%) | 3192 (3%) | 271 (13%) | 1976 (3%) |
| iceberg_zstd | ZSTD | 1.93 | 2 | 49 (3%) | 3217 (2%) | 311 (24%) | 2229 (2%) |

Answers identical across all four arms: **True**.

## Decomposition

Each comparison varies exactly one knob. Format effect = Iceberg/DuckLake at a matched codec (>1 means DuckLake reads faster); codec effect = ZSTD/Snappy within a format (>1 means Snappy reads faster).

| query | format effect (zstd) | format effect (snappy) | codec effect (ducklake) | codec effect (iceberg) |
|---|---|---|---|---|
| filtered | 0.95x | 1.09x | 1.19x | 1.04x |
| topn_src | 1.14x | 1.18x | 1.05x | 1.01x |
| byte_rollup | 1.07x | 1.40x | 1.51x | 1.15x |
| subnet_rollup | 1.13x | 1.09x | 1.09x | 1.13x |

## Reading

The default-config large-scan comparison conflated three knobs (Iceberg defaulted to ZSTD + 1M-row groups, DuckLake to Snappy + 122,880-row groups); this arm holds the row-group fixed and varies codec, so the format and codec effects separate. Read the low-CV sustained aggregations (topn_src, subnet_rollup; CV ~2-4%) — byte_rollup sits in the noisy sub-300ms band (CV >10%) and a delta there below its CV is not real. Two findings travel: at a matched codec DuckLake's files are *smaller* than Iceberg's (so the original storage gap was the codec default, not the format), and DuckLake still reads modestly faster than Iceberg after normalization (a real format/read-path effect), with Snappy adding a smaller separate decompression edge. Cold runs (OS cache purged) need root and are the next step. Tier B, single machine; the relative shape is the transferable finding.


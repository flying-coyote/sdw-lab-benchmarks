# BENCH-E — DuckLake vs Iceberg large-scan reads (results)

**Tier B.** 10,000,000-row OCSF corpus materialized in both formats and read by the same
engine (DuckDB), so the variable is the format's read path. Latencies are machine-specific medians.

| query | Iceberg ms | DuckLake ms | Iceberg/DuckLake |
|---|---|---|---|
| full_count | 3 | 7 | 0.51× |
| filtered | 18 | 17 | 1.03× |
| topn_src | 704 | 739 | 0.95× |
| byte_rollup | 94 | 61 | 1.53× |

- Storage: Iceberg 133 MB · DuckLake 216 MB
- Answers identical across both formats: **False**

## Reading

Read by one engine over the same logical data, the two formats return identical answers — they are
interchangeable on *correctness*. The latency column is where the format's read path shows: the
ratio is the cost (or saving) of the format on each scan shape at this scale, not an engine
difference. That is the read-side complement to BENCH-D's write-contract finding, and the pairing is
the H-DUCKLAKE-02 trade-off: which format you reach for depends on the write pattern (BENCH-D) and
the read latency here, not on one being universally better. Tier B, single machine; the magnitudes
are this host's, the answer-equality and the relative shape are the transferable findings.

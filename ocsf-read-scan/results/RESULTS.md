# BENCH-E — DuckLake vs Iceberg large-scan reads (results)

**Tier B.** 10,000,000-row OCSF corpus materialized in both formats and read by the same
engine (DuckDB). Latencies are medians with coefficient of variation. **This is the default-config
comparison and is confounded**: the two writers differ in codec and per-column encoding (pyiceberg
ZSTD/dictionary vs DuckDB ZSTD/PLAIN), so the gap mixes the writer's compression with the format. See
[PARITY.md](PARITY.md) (matched codec) and [SAME-FILES.md](SAME-FILES.md) (byte-identical data) for the
controlled result that isolates the format — where the read difference collapses to ~parity.

| query | Iceberg ms (cv) | DuckLake ms (cv) | Iceberg/DuckLake |
|---|---|---|---|
| full_count | 2 (4%) | 4 (2%) | 0.43× |
| filtered | 9 (3%) | 11 (2%) | 0.84× |
| topn_src | 346 (5%) | 278 (2%) | 1.25× |
| byte_rollup | 47 (10%) | 22 (9%) | 2.18× |

- Storage: Iceberg 133 MB · DuckLake 216 MB
- Answers identical across both formats: **True**

## Reading

Read by one engine over the same logical data, the two formats return identical answers — they are
interchangeable on *correctness*. The latency column is where the format's read path shows: the
ratio is the cost (or saving) of the format on each scan shape at this scale, not an engine
difference. That is the read-side complement to BENCH-D's write-contract finding, and the pairing is
the H-DUCKLAKE-02 trade-off: which format you reach for depends on the write pattern (BENCH-D) and
the read latency here, not on one being universally better. Tier B, single machine; the magnitudes
are this host's, the answer-equality and the relative shape are the transferable findings.

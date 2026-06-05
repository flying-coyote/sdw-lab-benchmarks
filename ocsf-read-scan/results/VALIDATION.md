# BENCH-E large-scan arm — cross-run validation

**Tier B, single machine.** Each scale run twice with frozen code; the corpus is seeded so
it is identical across runs and formats. Latencies are medians (warmup 1, 2 trials) and drift
run-to-run; the validated claim is that the Iceberg/DuckLake relative shape reproduces and that
both formats return identical answers on every run.

## 100M (100,000,000 rows, 2 batches, memory_limit 28GB)

| query | run1 ice ms | run1 dl ms | run1 ice/dl | run2 ice ms | run2 dl ms | run2 ice/dl |
|---|---|---|---|---|---|---|
| byte_rollup | 354 | 167 | 2.12x | 384 | 163 | 2.35x |
| filtered | 50 | 45 | 1.13x | 48 | 45 | 1.08x |
| full_count | 3 | 5 | 0.57x | 3 | 6 | 0.48x |
| subnet_rollup | 2192 | 1870 | 1.17x | 2081 | 1868 | 1.11x |
| topn_src | 3327 | 2917 | 1.14x | 3221 | 3012 | 1.07x |

- answers identical, both runs: **True**
- run1 storage: Iceberg 1.33 GB (10 files) · DuckLake 2.16 GB (4 files)
- run2 storage: Iceberg 1.33 GB (10 files) · DuckLake 2.16 GB (4 files)

## 1B (1,000,000,000 rows, 20 batches, memory_limit 28GB)

| query | run1 ice ms | run1 dl ms | run1 ice/dl | run2 ice ms | run2 dl ms | run2 ice/dl |
|---|---|---|---|---|---|---|
| byte_rollup | 2789 | 1677 | 1.66x | 2805 | 1642 | 1.71x |
| filtered | 480 | 382 | 1.26x | 458 | 394 | 1.16x |
| full_count | 9 | 4 | 1.90x | 5 | 5 | 1.04x |
| subnet_rollup | 20696 | 18659 | 1.11x | 20934 | 18923 | 1.11x |
| topn_src | 95170 | 81419 | 1.17x | 84834 | 74144 | 1.14x |

- answers identical, both runs: **True**
- run1 storage: Iceberg 13.29 GB (100 files) · DuckLake 21.62 GB (40 files)
- run2 storage: Iceberg 13.29 GB (100 files) · DuckLake 21.62 GB (40 files)

## Verdict

- Answer-equality held on **every run at every scale**: True.
- On every non-trivial query at both scales, DuckLake reads at or faster than Iceberg (ice/dl >= 1.0); the only reversal is the sub-10ms `full_count`, which is timing noise.
- Largest run-to-run drift in the Iceberg/DuckLake ratio on a non-trivial query: **0.22** (100M byte_rollup), so the relative shape is stable; absolute latencies drift more (most on the big out-of-core aggregation).
- The H-DUCKLAKE-02 worry that DuckLake's catalog DB becomes a large-scan bottleneck does not appear at 1B: DuckLake holds its small-commit advantage into full scans, while using more storage (looser default compression / row-group sizing) than Iceberg.

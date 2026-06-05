# BENCH-D — hot-tier write contract: results (first pass)

**Tier B, two of three arms.** Single machine, synthetic OCSF ingest. Commit latencies are
machine-specific medians, not constants. The never-write arm (Streambased ISK) has no
independent deployment to measure and is recorded as pending, not estimated.

## Headline (small-commit rung)

- Iceberg file-write costs **4.02 files per commit** vs DuckLake's
  **1.0** — the metadata churn the file-write contract pays on every
  small batch.
- Small-commit latency ratio (Iceberg p50 / DuckLake p50): **2.32×**.
- Read-contract coherence (one engine reads both tiers, identical answers): **True**.

## Rungs

### small_batch (50 commits × 100 rows)

| contract | commit p50 | p95 | p99 | files/commit | storage bytes |
|---|---|---|---|---|---|
| Iceberg (file-write) | 27.04 | 36.01 | 81.02 | 4.02 | 1,638,924 |
| DuckLake (SQL-txn) | 11.66 | 12.79 | 33.44 | 1.0 | 200,036 |

### large_batch (10 commits × 5000 rows)

| contract | commit p50 | p95 | p99 | files/commit | storage bytes |
|---|---|---|---|---|---|
| Iceberg (file-write) | 18.43 | 19.16 | 19.16 | 4.1 | 1,099,782 |
| DuckLake (SQL-txn) | 13.43 | 14.67 | 14.67 | 1.0 | 1,166,824 |


## Reading

The write contract differentiates exactly where the streaming case lives — small commits.
File-write pays a per-commit metadata-and-manifest tax (a new data file, a manifest, and a
fresh metadata.json every commit), so on a stream of small batches it writes many files per
commit; the SQL-transaction contract amortizes that. On large batches the gap narrows,
because the per-commit overhead is paid once over many rows — which is the honest shape: the
contract matters for streaming, not for bulk load. The read-contract-coherence check is the
load-bearing systems finding: a single engine reads both tiers and returns identical
answers for the same logical data, so the unified-read-contract premise holds here for these
two backends at this scale.

Caveats: single machine; latencies are medians on this host, not universal; the ISK
never-write arm is unmeasured (vendor-blocked); one OCSF shape; Tier B. The integrating
"tiering beats one backend" claim and the Iceberg-V4 efficient-materialization null both
need the third arm and a production-volume run.

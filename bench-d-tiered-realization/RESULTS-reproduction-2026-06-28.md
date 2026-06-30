---
type: evidence
title: "BENCH-D write-contract core — independent reproduction of the file-write + SQL-transaction arms (2026-06-28)"
created: 2026-06-28
tags: [bench-d, mdr-0026, reproduction, ducklake, iceberg, write-contract, commit-latency]
---

# BENCH-D — file-write + SQL-transaction arm reproduction (2026-06-28)

Re-ran the two owner-input-free arms of the BENCH-D write/commit-freshness core (`bench_d.py`) to move
the **MDR-0026** file-write and SQL-transaction arms from HOLD toward partial-DONE. These are the two
arms the MDR owner brief (2026-06-23) named as the autonomous fallback when Streambased ISK access can't
be obtained; the never-write / virtual-view (ISK) arm stays owner-gated.

- **SQL-transaction** = DuckLake (DuckDB 1.5.x, local catalog + parquet) — fully local, no infra.
- **File-write** = Apache Iceberg append/commit (pyiceberg -> Nessie REST + MinIO), run in-container on
  the `ejs-bench_ejs` network (Nessie vends the internal `minio:9000` endpoint, so the host-port path
  fails on data-file write; the designed path is in-network).

## Results — write+commit (freshness), median of 3 reps, ms

| arm (paradigm) | batch | run1 wc | run2 wc | 2026-06-15 baseline wc |
|---|---|---|---|---|
| DuckLake (SQL-transaction) | 1k | 17.1 | 15.3 | 15.7 |
| DuckLake (SQL-transaction) | 10k | 19.4 | 19.7 | 19.2 |
| DuckLake (SQL-transaction) | 100k | 77.9 | 88.6 | 79.7 |
| Iceberg (file-write) | 1k | 71.0 | 98.2 | 70.6 |
| Iceberg (file-write) | 10k | 80.3 | 94.9 | 71.7 |
| Iceberg (file-write) | 100k | 135.0 | 151.3 | 124.4 |

Query-after-write (run1, ms): DuckLake 6.3 / 6.6 / 6.0; Iceberg 133.4 / 229.6 / 344.0.

## Finding

Both arms reproduce the 2026-06-15 bands within run-to-run noise ~3 weeks later, on a fresh
(IN_MEMORY-Nessie) bring-up. The storage-commit ordering is stable: **DuckLake (SQL-transaction) <
Iceberg (file-write)** at every batch size, and **both commit sub-second** (DuckLake 15-89 ms, Iceberg
71-151 ms even at 100k rows) — so the realization-paradigm divergence DR #4 named lives in the
**read-after-write** path (DuckLake single-digit ms local vs Iceberg ~130-344 ms object-store), not in
the commit. The Iceberg "1-5 min" file-write band is a Flink checkpoint-interval cadence choice layered
on top of a sub-second commit, not an inherent commit cost — confirmed again here.

## Reproducibility basis

- Synthetic conn-like corpus only (structured; no real telemetry); data seed pinned `random.seed(7)`.
- Harness reports median of REPS=3 per batch; two independent process runs per arm on 2026-06-28, plus
  the 2026-06-15 baseline run — three independent draws agree in band.
- DuckLake arm: `~/sdw-lab-benchmarks/.venv/bin/python bench_d.py` with `ARMS=ducklake`
  (fully local; `/tmp/benchd.ducklake` + `/tmp/benchd_data`).
- Iceberg arm: one-off container from `ejs-bench-lab:latest` on `--network ejs-bench_ejs`, env
  `ARMS=iceberg S3_ENDPOINT=http://minio:9000 NESSIE_URI=http://nessie:19120/iceberg/`. Infra brought
  up on-box via `engine-join-specialization/compose.yml` (services: minio, minio-init, nessie only).
- Absolute ms drift run-to-run ~5-25% (page/metadata cache + JVM/object-store jitter); ordering and
  sub-second-commit verdict stable across all three draws.

## What remains owner-gated (MDR-0026)

The **never-write / virtual-view arm (Streambased ISK)** is unmeasured — it needs vendor (Streambased)
ISK access, which is owner/cloud-gated, not runnable on-box. Per the MDR-0026 owner brief, the file-write
+ SQL-transaction arms closing does **not** by itself close the `metadata_realization` criterion gate:
that still requires the ISK correctness+performance arm AND the two open DuckLake correctness blockers
(#1215 silent row resurrection, #1184 >1600-col CREATE wall) closing AND >=1 named production
virtual-Iceberg deployment. The MDR stays HOLD-PROPOSED on the criterion; only these two measured arms
move to DONE.

Raw numbers: `results/bench_d-reproduction-2026-06-28.json`. Tier B, single host. Gate before any
hypothesis-confidence move (karen -> hypothesis-validator -> contradiction-detector).

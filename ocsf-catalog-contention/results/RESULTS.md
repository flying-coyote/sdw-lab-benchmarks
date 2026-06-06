# Concurrent-writer catalog contention (T1.3) — H-DUCKLAKE-02's untested adverse leg

**Tier B · single machine · PostgreSQL 17 (shared, port 5434) for both engines.** N writer processes commit 20
batches of 200 rows each, concurrently, to the SAME table, swept over writers
[1, 4, 8, 16]. R6/R7 only ran a single writer; the hypothesis's original "DuckLake loses at scale
because the catalog DB bottlenecks" claim is a *concurrent-write* mode, tested here for the first time.
Adverse to both: Iceberg's optimistic concurrency conflicts-and-retries; DuckLake's commits serialize on
the shared SQL catalog.

## DuckLake (catalog = Postgres)

| writers | rows/s | commit p50 (ms) | commit p95 (ms) | retries | hard errors |
|--:|--:|--:|--:|--:|--:|
| 1 | 10770 | 11.1 | 14.47 | 0 (0.0/commit) | 0 |
| 4 | 9391 | 10.81 | 19.67 | 0 (0.0/commit) | 0 |
| 8 | 8706 | 11.23 | 303.83 | 0 (0.0/commit) | 0 |
| 16 | 9531 | 10.95 | 662.38 | 0 (0.0/commit) | 0 |

## Iceberg (catalog = Postgres)

| writers | rows/s | commit p50 (ms) | commit p95 (ms) | retries | hard errors |
|--:|--:|--:|--:|--:|--:|
| 1 | 7836 | 21.92 | 25.58 | 0 (0.0/commit) | 0 |
| 4 | 5323 | 34.29 | 52.6 | 45 (0.562/commit) | 3 |
| 8 | 3355 | 70.85 | 109.54 | 303 (1.894/commit) | 23 |
| 16 | 2450 | 131.57 | 185.57 | 1505 (4.703/commit) | 116 |

## Scaling 1 → 16 writers

- **DuckLake**: commit p95 grows **45.78×**, throughput at max writers 9531 rows/s, 0 retries, 0 hard errors total.
- **Iceberg**: commit p95 grows **7.25×**, throughput at max writers 2450 rows/s, 1505 retries, 142 hard errors total.

## Reading

This is the leg R6/R7 left open and the one the hypothesis's load-bearing claim actually rests on. The
table above is the honest adverse test of both formats under concurrency: whichever degrades — DuckLake by
catalog-commit serialization (p95 growth, eventually errors) or Iceberg by optimistic-concurrency conflicts
(retry storms) — is measured rather than assumed. Single machine, one catalog backend (Postgres), small
batches to maximise commit pressure; the transferable finding is the *shape of each format's degradation
as writers scale*, not the absolute rows/s on this host.

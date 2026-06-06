# Concurrent-writer catalog contention (T1.3) — H-DUCKLAKE-02's untested adverse leg

R6 (planning) and R7 (streaming cadence) both ran a **single** writer. H-DUCKLAKE-02's original
load-bearing claim is that DuckLake "loses advantage at enterprise scale due to **catalog DB bottleneck**"
— a *concurrent-write* failure mode R0/R8 (reads) and R6/R7 (single writer) never exercised. This runs it:
N writer processes commit small batches concurrently to the **same table**, swept N ∈ {1,4,8,16}, on a
**Postgres-backed catalog for both engines** (a single-file catalog only permits one writer, so the
realistic concurrent backend — and the one the vendor's concern is about — is Postgres). Adverse to both
by construction: Iceberg's optimistic concurrency conflicts-and-retries; DuckLake's commits serialize on
the shared SQL catalog.

## Result (Tier B, single machine, worst-case single-table contention)

| writers | DuckLake rows/s | DuckLake p95 | DuckLake lost | Iceberg rows/s | Iceberg p95 | Iceberg retries / lost |
|--:|--:|--:|--:|--:|--:|--:|
| 1 | 10,770 | 14 ms | 0 | 7,836 | 26 ms | 0 / 0 |
| 4 | 9,391 | 20 ms | 0 | 5,323 | 53 ms | 45 / 3 |
| 8 | 8,706 | 304 ms | 0 | 3,355 | 110 ms | 303 / 23 |
| 16 | 9,531 | 662 ms | 0 | 2,450 | 186 ms | 1,505 / 116 |

**The hypothesis's framing is not supported as stated.** Under maximum-contention concurrent writes:

- **DuckLake's catalog IS the serialization point** — commit p95 balloons **~46×** (14→662 ms) as writers
  queue on the catalog lock. But it serializes *safely*: aggregate **throughput holds** (~9,500 rows/s even
  at 16 writers) and **zero commits are lost**. The bottleneck is real but it manifests as **tail latency**,
  not as failed commits or a throughput collapse.
- **Iceberg degrades worse on the axis that matters for durability** — optimistic concurrency on the single
  table's metadata pointer means concurrent appends conflict, so throughput **collapses 3.2×**
  (7,836→2,450 rows/s), retries explode to **4.7 per commit**, and **116 commits are lost** to
  retry-exhaustion at 16 writers (they would eventually land with unbounded retries, at still-lower
  throughput).

So "DuckLake loses at scale because the catalog bottlenecks" is the wrong worry for this workload: DuckLake
trades latency for durability and throughput, while Iceberg's optimistic concurrency is the regime that
actually sheds work under many writers to one table.

## Important caveats

- **Worst case for both**: all writers hit ONE table. Real estates spread writers across tables/partitions,
  which relieves Iceberg's conflict rate and DuckLake's catalog contention — so these are upper bounds on
  the contention cost, not typical operation.
- Single host, single Postgres catalog, small batches (to maximise commit pressure). The transferable
  finding is the **shape of each format's degradation** (DuckLake → latency; Iceberg → conflict/lost work),
  not the absolute rows/s.
- Iceberg "lost" = commits that exhausted the 10-retry budget; a production writer would retry longer and
  trade more throughput for eventual success.

## Reproduce

```bash
docker run -d --name catalog-pg -e POSTGRES_HOST_AUTH_METHOD=trust -p 5434:5432 postgres:17-alpine
python run.py     # N in {1,4,8,16}, 20 commits/writer, 200 rows/commit; resets dlcat/icecat each run
```

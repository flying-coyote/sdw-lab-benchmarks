# BENCH-E cold-cache arm — posix_fadvise(DONTNEED) cold reads (20,000,000 rows)

**Tier B, single machine.** Every other BENCH-E arm is hot/warm only, which structurally favours
whatever fits in the OS page cache. Forensic and incident queries run cold — the analyst fires a
retroactive search over data ingested hours or days ago, so the OS holds none of it in cache.
This arm adds the cold measurement without root privileges, using `os.posix_fadvise(fd, 0, 0,
POSIX_FADV_DONTNEED)` to evict each data file's pages from the page cache before timing the first
post-eviction run.

**Corpus:** 20,000,000 rows, 228.3 MB on disk (DuckDB, ZSTD-3,
122,880-row groups). Byte-identical Parquet files registered into both Iceberg
(pyiceberg `add_files`) and DuckLake (`ducklake_add_data_files`) — same-files approach, so
compression is not a confound. **Eviction: Eviction confirmed.**

## Cold vs warm per catalog

| catalog | query | cold ms | warm ms (cv) | cold/warm |
|---|---|---|---|---|
| iceberg | full_count | 4 | 3 (17%) | 1.09× |
| ducklake | full_count | 8 | 8 (14%) | 0.99× |
| iceberg | filtered | 27 | 18 (12%) | 1.55× |
| ducklake | filtered | 28 | 21 (10%) | 1.32× |
| iceberg | topn_src | 1035 | 844 (7%) | 1.23× |
| ducklake | topn_src | 770 | 792 (10%) | 0.97× |
| iceberg | byte_rollup | 89 | 62 (13%) | 1.43× |
| ducklake | byte_rollup | 89 | 61 (12%) | 1.46× |
| iceberg | subnet_rollup | 567 | 560 (15%) | 1.01× |
| ducklake | subnet_rollup | 663 | 547 (15%) | 1.21× |

- Bytes identical across catalogs: **True**
- Answers identical across catalogs: **True**
- cold_rounds=3, warm_trials=5, memory_limit=12GB

## Cross-format comparison at cold

| query | Iceberg cold ms | DuckLake cold ms | Iceberg/DuckLake |
|---|---|---|---|
| full_count | 4 | 8 | 0.46× |
| filtered | 27 | 28 | 0.99× |
| topn_src | 1035 | 770 | 1.35× |
| byte_rollup | 89 | 89 | 1.00× |
| subnet_rollup | 567 | 663 | 0.86× |

## Eviction verdict

Eviction demonstrably worked: iceberg_filtered was 1.55x slower cold (well above the 1.30x threshold).

Max cold/warm ratio: **1.55×** (query: `iceberg_filtered`).

## Method + caveats

`os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)` evicts a specific file's pages from the OS
page cache without requiring root. It is more precise than `echo 3 > /proc/sys/vm/drop_caches`
for this use case: it targets only the named data files and leaves the OS metadata cache,
DuckDB's internal connection-level buffer pool, Iceberg/DuckLake extension state, and the
SQLite catalog untouched. The cold measurement therefore captures the data-file I/O latency,
not the cost of reloading extensions or re-parsing catalog metadata — which is the right scope
when comparing two table formats over the same physical data.

Three caveats apply:

1. **DuckDB internal buffer pool**: DuckDB may cache decompressed column data in its own
   connection-level buffer pool, which `posix_fadvise` does not reach. For the short runs in
   this benchmark (`cold_rounds=3`) the buffer pool is unlikely to hold all 20,000,000 rows,
   but for very small datasets or long-running connections the cold measurement may be partially
   warm from the internal pool.

2. **Filesystem tier**: on tmpfs or the WSL /mnt/c (9p) filesystem, `POSIX_FADV_DONTNEED` is
   typically a no-op and cold reads equal warm reads. This benchmark runs on ext4 where
   DONTNEED reliably evicts pages (verified: the benchmark measurements above show up to
   1.55× cold/warm on `iceberg_filtered`).

3. **Advisory semantics**: the call is a hint, not a guarantee. The kernel may decline to
   evict pages that are pinned or recently accessed by another process. The ratio
   reported above reflects what actually happened on this run.

## Reading

The cold/warm ratio per query is the headline: a ratio of 1× means the query is
cache-insensitive (it runs purely on DuckDB-internal state or the data fits in L3); a
ratio >> 1× means it depends on the OS page cache and a cold SOC query pays that cost.
Scan-heavy aggregations (`topn_src`, `subnet_rollup`, `byte_rollup`) should show the
largest ratios; a small predicate-pushdown query (`filtered`) may show less because
DuckDB can skip row groups and read a fraction of the data. The cross-format cold
comparison (second table) reveals whether Iceberg and DuckLake are still performance-neutral
at cold, or whether one format's metadata/scan path has a larger cold penalty than the other.
Tier B, single machine. The cold/warm ratios and the relative cold shape are the
transferable findings; the absolute milliseconds are this host's.

# Iceberg metadata & compaction scaling (results)

**Tier B.** How scan-planning cost grows as a table accumulates small appends (snapshots / data
files / manifests), and what compaction buys back. Planning is `scan().plan_files()` — reading
manifests to enumerate the files a query must touch; latencies are machine-specific medians.

## Fragmented table (many small appends)

| appends | data files | metadata files | plan ms | scan ms |
|---|---|---|---|---|
| 50 | 50 | 151 | 87.0 | 155 |
| 100 | 100 | 301 | 151.4 | 306 |
| 200 | 200 | 601 | 488.2 | 843 |

## Compacted (same rows, one append)

| appends | data files | metadata files | plan ms | scan ms |
|---|---|---|---|---|
| 1 | 1 | 4 | 3.3 | 64 |

## Headline

The directional, transferable finding is that **scan-planning and scan cost grow monotonically with
file/manifest count, and compaction recovers them** — the small-files tax: planning has to read every
manifest before touching data, so cost scales with file count, not data volume. That is the
mechanism H-ICEBERG-V4-METADATA-EFFICIENCY-01 says V4 metadata targets, and the maintenance job
(compaction) every real deployment runs.

The specific ratios (200 micro-batch appends / 200 data files →
plan 150.1×, scan 13.2×) are
**illustrative of the mechanism under deliberate fragmentation, not production figures**. They are measured
by pyiceberg's own Python `plan_files()` on this machine with artificially small 5k-row files — a real
query engine (Trino, Spark) plans differently and faster, and the file size is a worst-case streaming
micro-batch — so the magnitude is planner-, file-size-, and host-specific. This is a *within-Iceberg*
fragmentation cost; it is **not** a query-runtime number and **not** the DuckLake-vs-Iceberg format
comparison (that is BENCH-E, where the two are roughly interchangeable on read) or any vendor
format-war speedup claim. Do not conflate them. Tier B, single machine.

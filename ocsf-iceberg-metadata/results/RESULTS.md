# Iceberg metadata & compaction scaling (results)

**Tier B.** How scan-planning cost grows as a table accumulates small appends (snapshots / data
files / manifests), and what compaction buys back. Planning is `scan().plan_files()` — reading
manifests to enumerate the files a query must touch; latencies are machine-specific medians with CV.

## Fragmented table (many small appends)

| appends | data files | metadata files | plan ms (cv) | scan ms (cv) |
|---|---|---|---|---|
| 50 | 50 | 151 | 52.7 (3%) | 108 (4%) |
| 100 | 100 | 301 | 106.6 (1%) | 207 (1%) |
| 200 | 200 | 601 | 208.7 (2%) | 400 (1%) |

## Compacted (same rows, one append)

| appends | data files | metadata files | plan ms (cv) | scan ms (cv) |
|---|---|---|---|---|
| 1 | 1 | 4 | 1.4 (3%) | 41 (11%) |

## Real-engine cross-check (DuckDB iceberg_scan)

A filtered scan through DuckDB's iceberg reader over the same two tables — a production query engine, not
pyiceberg's Python planner:

| table | DuckDB iceberg_scan ms (cv) |
|---|---|
| fragmented (200 files) | 72 (3%) |
| compacted (1 file) | 6 (4%) |

DuckDB is **11.7×** faster on the compacted table —
so the small-files tax is real on a production engine too, not a pyiceberg artifact. The magnitude differs
from the Python planner's (a real engine prunes and parallelizes), which is exactly why the pyiceberg
ratios below are framed as illustrative.

## Headline

The directional, transferable finding is that **scan-planning and scan cost grow monotonically with
file/manifest count, and compaction recovers them** — the small-files tax: planning has to read every
manifest before touching data, so cost scales with file count, not data volume. That is the
mechanism H-ICEBERG-V4-METADATA-EFFICIENCY-01 says V4 metadata targets, and the maintenance job
(compaction) every real deployment runs.

The specific ratios (200 micro-batch appends / 200 data files →
plan 145.5×, scan 9.9×) are
**illustrative of the mechanism under deliberate fragmentation, not production figures**. They are measured
by pyiceberg's own Python `plan_files()` on this machine with artificially small 5k-row files; the
real-engine cross-check above (DuckDB) confirms the tax exists on a production engine but at a different
magnitude, because a real engine prunes and parallelizes — so the pyiceberg ratio is planner-, file-size-,
and host-specific. This is a *within-Iceberg*
fragmentation cost; it is **not** a query-runtime number and **not** the DuckLake-vs-Iceberg format
comparison (that is BENCH-E, where the two are roughly interchangeable on read) or any vendor
format-war speedup claim. Do not conflate them. Tier B, single machine.

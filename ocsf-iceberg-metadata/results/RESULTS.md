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

A table fed by 200 small appends carries 200 data files, and
compacting it back to one file makes scan-planning **150.1× faster** and the
scan **13.2× faster**. That gap is the small-files tax that streaming
ingest into Iceberg pays if compaction doesn't keep up: planning has to read every manifest before it
can touch data, so the cost scales with file count, not data volume. It's the practical reason a
naive streaming-append pattern degrades, the maintenance job (compaction) every real deployment runs,
and the planning-speed gap H-ICEBERG-V4-METADATA-EFFICIENCY-01 says V4 metadata targets. Tier B,
single machine; the magnitudes are this host's, the monotone growth and the compaction recovery are
the transferable findings.

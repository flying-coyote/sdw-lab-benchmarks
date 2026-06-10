# RESULTS — the flagship, re-measured: the index wins the lookups, loses the hunt

**Tier B · single host (Beelink 5800H, WSL2, High Performance plan) · 10M-row synthetic Zeek
conn corpus · 7 trials/query, CV-gated · answer-equality verified · 2026-06-10**

This supersedes the legacy "145×" flagship for every surface that cites it. It is a new
measurement (OpenSearch 2.18.0 foil, ClickHouse 26.5.1, same-process HTTP timing for all
arms), not a reproduction — see the pre-registration in `../README.md` for the declared
deviations.

## Headline

Average of per-query medians across the 5 standardized queries:

| Arm | avg of medians | vs foil |
|---|---|---|
| OpenSearch 2.18.0 (schema-on-read foil, best_compression, 1 segment) | 2.854 s | 1× |
| ClickHouse-over-Iceberg (zstd Parquet on MinIO, `icebergS3()`) | 0.282 s | **10.1×** |
| ClickHouse native MergeTree (default LZ4, sorted layout) | 0.061 s | **46.8×** |

But the average hides the real finding, which is a clean split by query shape:

| Query | OpenSearch | CH Iceberg | CH native | Who wins |
|---|---|---|---|---|
| count_all | 0.003 s | 0.011 s | 0.002 s | ~floor for OS and native; Iceberg pays planning |
| protocol_distribution | **0.005 s** | 0.040 s | 0.017 s | **OpenSearch, 3.4× over native** (CLAIMABLE) |
| long_duration_connections | **0.011 s** | 0.217 s | 0.019 s | **OpenSearch, 1.8× over native** (CLAIMABLE) |
| top_source_ips_by_bytes | 1.179 s | 0.218 s | **0.056 s** | **native 21×, Iceberg 5.4× over OS** (CLAIMABLE) |
| port_scan_detection | 13.071 s | 0.925 s | **0.211 s** | **native 62×, Iceberg 14× over OS** (CLAIMABLE) |

**The index answers index-shaped questions instantly and loses the computational
aggregations by 21–62×.** Counts, filtered top-k by an indexed field, doc-count
distributions: the inverted index serves these from metadata in milliseconds, and the
columnar engines cannot beat that by much (or at all). The byte-sum GROUP BY and the
distinct-port scan — the queries shaped like threat hunting — invert the picture by one to
two orders of magnitude. That split is the two-regime thesis in one table: the question is
never "which is faster," it is "which regime does your workload live in."

Every CLAIMABLE above passes the methodology gate (gap % > the larger of the two arms' CVs;
full pairwise table in `comparison.json`). Sub-10 ms medians sit near the HTTP client's
floor (~1–2 ms), so the count_all ratios, while formally gated, should not be quoted as
findings.

## What happened to 145×?

Three things, all of which this run was designed to expose rather than hide:

1. **The foil got honest.** The legacy baseline (27.52 s avg) was a different schema-on-read
   system under a different access path. OpenSearch 2.18.0, bulk-loaded, force-merged, and
   queried over DSL, averages 2.85 s on the same five queries — the foil itself is ~10×
   faster than the legacy baseline, so every multiplier shrinks accordingly.
2. **The timing got honest.** All arms are now timed from one Python process over HTTP; the
   legacy run timed ClickHouse through `docker exec` subprocess spawns inside sub-second
   measurements.
3. **The separation is now the headline, not a footnote.** Native 46.8× / Iceberg 10.1× on
   the average, with the per-query split above. The legacy run's conflated "145×" stopped
   being quotable the day the separated numbers existed; this run replaces it with numbers
   that are CV-gated and answer-verified.

What did NOT change: the open-format tax (native beats Iceberg 4.6× on the average here;
6.1× in the legacy run) and the order-of-magnitude gap on hunting-shaped aggregations.

## Storage (same 10M rows in every arm)

| Form | Bytes | vs raw JSONL |
|---|---|---|
| Raw JSONL | 3,743 MB | 1× |
| OpenSearch index (best_compression, 1 segment) | 1,868 MB | 2.0× |
| ClickHouse MergeTree (default LZ4) | 685 MB | 5.5× |
| Iceberg Parquet (pyiceberg zstd defaults) | 440 MB | **8.5×** |

The open-format table is the smallest artifact in the comparison — the read-latency tax
buys back 1.6× of storage vs native LZ4 and 4.2× vs the index.

## Answer equality — ALL IDENTICAL

All five queries return identical extracted answers across all three arms (values, not row
counts; `comparison.json` carries the per-arm answers). Two notes the legacy run never
recorded:

- **port_scan_detection returns an empty set on this corpus — in the legacy run too.** The
  generator's service→port map caps distinct ports per source at exactly 10, so
  `HAVING unique_ports > 10` can never fire. The aggregation work being timed is real
  (grouping 8.9M TCP rows and distinct-counting two columns); the detection semantics are
  hollow. A corpus with actual scan behavior is the fix if this query's *semantics* ever
  matter to a claim.
- OpenSearch needed two declared exactness fixes to even be comparable (terms size 20000,
  cardinality precision_threshold 3000, both ground-truthed exact for this corpus) — the
  default DSL would have produced approximate answers that no one would have caught.

## Conditions

Hot/warm only (no passwordless sudo for an OS page-cache drop; methodology §3 labelling).
Engine-cold (container restart, OS cache warm) ran one pass per arm and is within noise of
hot on every query — the page cache, not engine state, is what matters on this host.
Loads: OpenSearch 282.6 s bulk + 34.3 s forcemerge; ClickHouse 24.6 s; Iceberg 6.0 s write.
Environment, image digests, and the Iceberg footer parity record: `env.json`.

## What this licenses (and what it does not)

- **Licenses:** "On hunting-shaped aggregations over 10M events, the lakehouse engines beat
  the schema-on-read foil by 5–62× depending on query and realization, CV-gated, with
  identical answers verified" — and the two-regime split table itself, which is the more
  defensible and more interesting claim.
- **Licenses:** the native-vs-open-format separation (4.6× avg) as the honest cost of
  swappability, alongside the storage inversion (Iceberg smallest).
- **Does NOT license:** any blanket "N× faster than your SIEM" claim; cluster or
  petabyte-scale extrapolation (single host, 10M rows); production-SIEM comparison (the
  foil is a bare OpenSearch index, not a SIEM product with its pipeline overhead).
- **Supersedes:** the bare 145× on every citing surface (thesis/research/engagements +
  pitch material). H3-PERFORMANCE-01 should re-tier on these numbers; the legacy result
  stays in `~/splunk-db-connect-benchmark` as a historical single-run measurement.

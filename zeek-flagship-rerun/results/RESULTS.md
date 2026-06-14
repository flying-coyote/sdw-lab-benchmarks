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

---

## B-DREMIO addendum — the real engine, in place on the same Iceberg files (2026-06-14)

**Tier B · same single host · same pinned 10M-row corpus (sha256-matched) · same 5 queries ·
same OpenSearch 2.18.0 foil · 7 trials/query + 1 warmup, CV-gated · answer-equality verified ·
Dremio OSS 26.0.5 (`26.0.5-202509091642240013-f5051a07`).**

The flagship above measured the open-in-place pattern through a ClickHouse-over-Iceberg
proxy. This arm replaces the proxy with the engine the proxy stood in for: Dremio querying
the *same* pyiceberg-written Iceberg files on MinIO in place (registered into a Nessie REST
catalog with `register_table`, byte-identical, no rewrite — the same five 84 MiB data files
the `clickhouse_iceberg` arm reads), Reflections OFF as the honest apples-to-apples baseline.
Answer-equality holds across all four arms now (`ALL IDENTICAL`, including Dremio).

| Arm | avg of medians | vs foil |
|---|---|---|
| OpenSearch 2.18.0 (foil) | 2.854 s | 1× |
| **Dremio-over-Iceberg, Reflections OFF** | **0.787 s** | **3.6×** |
| ClickHouse-over-Iceberg | 0.282 s | 10.1× |
| ClickHouse native MergeTree | 0.061 s | 46.8× |

The same two-regime split the flagship found holds for Dremio, and the per-query table is
where the honest story lives — the 3.6× average is carried almost entirely by the one heavy
query:

| Query | OpenSearch | Dremio (OFF) | Who wins (CV-gated) |
|---|---|---|---|
| count_all | 0.003 s | 0.161 s | OpenSearch (REST-floor — see caveat) |
| protocol_distribution | 0.005 s | 0.398 s | OpenSearch |
| long_duration_connections | 0.011 s | 0.439 s | OpenSearch |
| top_source_ips_by_bytes | 1.179 s | 0.909 s | **Dremio 1.3×** (gap 29.7% > gate 21.8%) |
| port_scan_detection | 13.071 s | 2.025 s | **Dremio 6.5×** |

So Dremio reading open Iceberg in place beats the schema-on-read index by **6.5× on the
heaviest hunting-shaped aggregation** (the distinct-port scan over 8.9M TCP rows, the query
that costs OpenSearch 13 s) and ties-to-edges it on the byte-sum GROUP BY, while the index
keeps winning the cheap, index-served lookups. That is the same regime split as the flagship,
at Dremio's own latency — and it is a more modest, more credible number than the ClickHouse
proxy implied (the proxy showed 10.1× average / 14× on port_scan; the real engine shows
3.6× / 6.5×). On Dremio's own conference, the honest smaller number is the stronger one.

**Measurement caveat that matters for the cheap-query rows.** Every arm is timed as
client-side wall time, but Dremio's REST path is a *job lifecycle* — submit, poll `jobState`,
fetch result pages — which carries a ~150 ms floor that the direct-HTTP ClickHouse and
OpenSearch clients never pay. So Dremio's sub-200 ms numbers (count_all 0.161 s,
protocol_distribution 0.398 s) are dominated by the REST round-trip, not by query execution:
Dremio's actual engine work for a `COUNT(*)` it reads from Iceberg metadata is near-instant.
The cheap-query losses to OpenSearch are therefore partly a client-path artifact, while the
heavy-query *wins* (port_scan 6.5×, top_source 1.3×) are execution-bound and real — the REST
floor is noise against a 2 s query. The honest reading is "the index wins the cheap lookups
and the engine wins the heavy hunt"; the *magnitude* of the cheap-lookup loss should not be
quoted, the same way the flagship's sub-10 ms ratios were flagged not-quotable.

**Open-format engine tax (Dremio vs ClickHouse over byte-identical Iceberg files).** Reading
the exact same five Parquet files, ClickHouse-over-Iceberg is 2–15× faster than
Dremio-over-Iceberg per query (2.0× on long_duration, 2.2× on port_scan, 4.2× on top_source,
~10–15× on the cheap REST-floored queries). The engine matters as much as the format: open
files do not make two engines equal, and on this workload ClickHouse's vectorized execution
beats Dremio's on identical bytes. This is the within-open-format counterpart to the flagship's
native-vs-Iceberg tax.

### Reflections-ON — blocked over the Nessie-versioned read path (a finding, not a number)

Reflections are Dremio's flagship acceleration feature and the legacy "Dremio 1.0 s" number
was a Reflections-ON result, so the ON arm was pre-registered to be reported separately. It
does not produce a usable number here, and the reason is itself the finding. A raw reflection
on the registered table materializes (the 10M-row scan completes) but **expires instantly**:
`sys.reflections` shows `status=CANNOT_ACCELERATE_SCHEDULED`, `acceleration_status=NONE`,
`available_until=1970-01-01` (epoch 0), `last_failure="Successful materialization already
expired"`, with the failure count climbing 1→2→3 on each refresh — it never reaches
`CAN_ACCELERATE`. This reproduces with both the REST- and SQL-created reflection, so it is a
Dremio-26 + Nessie-*versioned*-table friction, not a harness bug: Dremio cannot compute a
valid freshness/expiry for a `BRANCH main` Iceberg table registered via `register_table`, so
the materialization is born already-stale and the ON arm would run un-accelerated (a duplicate
of OFF). Reported honestly: **Dremio 26's Reflections do not work over a Nessie-versioned
`register_table` table** on this path. Making ON real would need a non-versioned read path
(Dremio's own Iceberg catalog, or a Hadoop-tables source with a `version-hint`) — a separate
write that breaks the byte-identical-files constraint the OFF baseline rests on, so it is left
as documented future work, not blended into the OFF result.

### What B-DREMIO licenses (and what it does not)

- **Licenses for Subsurface / the deck:** a current, Dremio-specific, CV-gated number —
  "Dremio querying open Iceberg tables in place beats a schema-on-read index 6.5× on the
  heaviest hunting aggregation and 3.6× on the five-query average, single host, Tier B,
  identical answers verified; the index still wins the cheap indexed lookups." This resolves
  the Subsurface CFP DECISION-A: the real Dremio number replaces the open-in-place proxy.
- **Licenses:** the open-format engine-tax point (the engine matters even on identical open
  files) and the honest fair-broker regime split.
- **Does NOT license:** any Reflections-accelerated Dremio number (blocked here); any blanket
  "Dremio beats your SIEM" claim (same two-regime caveat as the flagship); cluster or
  petabyte extrapolation (single host, 10M rows); a production-SIEM comparison (the foil is a
  bare OpenSearch index). The legacy bare 27× / 0.19 s / 27.52 s Reflections figures stay
  superseded and do not go in the abstract.

# Flagship revalidation — 2026-06-14 (independent fresh draw vs the published 06-10 number)

The load-bearing performance number (the 145×→two-regime supersession) was re-run as a full
independent draw 4 days after the published baseline, same host, same pinned corpus
(sha256-matched), same one-engine-at-a-time isolation + 7-trial CV-gated protocol. The
published `results/comparison.json` (06-10 for OS/CH, 06-14 for the Dremio arm) stays
canonical; this draw is the validation evidence (preserved in `results_revalidation_2026-06-14/`).

## The cited multiples reproduce within ~5%

| arm | published ×foil (06-10) | revalidation ×foil (06-14) |
|---|--:|--:|
| ClickHouse-native MergeTree | 46.8× | **45.1×** |
| ClickHouse-over-Iceberg | 10.1× | **10.6×** |
| Dremio-over-Iceberg (Reflections OFF) | 3.6× | **3.4×** |

**Answer-equality: ALL IDENTICAL** across all four arms (the silent-wrong check passes again).

## The two-regime split is identical

| query | OpenSearch | ClickHouse-native | winner (both draws) |
|---|--:|--:|---|
| count_all | 0.003 s | 0.002 s | ClickHouse |
| protocol_distribution | 0.006 s | 0.017 s | **OpenSearch** (cheap cached agg) |
| long_duration_connections | 0.016 s | 0.021 s | **OpenSearch** (cheap cached) |
| top_source_ips_by_bytes | 1.145 s | 0.062 s | ClickHouse (18×) |
| port_scan_detection | 11.7 s | 0.18 s | ClickHouse (the heavy hunt) |

The index wins the cheap, index-served lookups; the engine wins the heavy hunting aggregations.
Same pattern, same per-query winners, both draws — the two-regime thesis is robust.

## What drifted, and the lesson for how to cite it

Absolute latencies came in **4–14% faster** on this draw (OpenSearch foil 2.854 s → 2.582 s,
−9.5%; every arm faster). Because all arms drifted in the same direction (common-mode host /
page-cache state, hot/warm, single host), the **ratios stayed stable within ~5%**. That is
exactly why the literature cites the **multiples and the two-regime split**, not absolute
milliseconds: the absolute ms carry ~10% single-host run-to-run variance, the ratios do not.
The published multiples are validated as stable; a reader quoting "≈10× / ≈47× over a
schema-on-read index, with the index winning the cheap lookups" is on solid, reproduced ground.

## Software versions at validation time

ClickHouse 26.5.1.882, OpenSearch 2.18.0, Dremio OSS 26.0.5, pyiceberg 0.11.1, DuckDB 1.5.3,
clickhouse-connect 1.1.1, opensearch-py 3.2.0 (see `results/env.json`). A version-currency pass
(updating to latest where behind, then re-validating) is tracked separately per the 2026-06-14
directive — this draw establishes the number reproduces on the as-installed stack.

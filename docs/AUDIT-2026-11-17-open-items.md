---
type: reference
title: "Open items from the 2026-11-17 audit: unstamped timings and chart captions"
created: 2026-11-17
tags: [lab-benchmarks, audit, rig-stamp, charts]
---

# Open items from the 2026-11-17 audit

Two lists that the methodology and the chart manifest point to, kept here so a reader of this repository
can follow the pointer. Both are snapshots taken on 2026-11-17, before the per-bench pass of the same audit
finished, so a file listed here may since have gained its stamp or its corrected caption; the bench's own
README and RESULTS file are the current word.

## RESULTS files with absolute timings and no rig stamp (principle 7b)

Principle 7b of [`BENCHMARKING-METHODOLOGY.md`](../BENCHMARKING-METHODOLOGY.md) asks every RESULTS file
that reports an absolute duration to carry a rig stamp (host, power plan, engine versions and clock
state). The count behind the note there is a pattern match: a `RESULTS*.md` file counts as latency-bearing
when it holds a number followed by a time or rate unit (ms, µs, seconds, min, rows/s, MB/s and the like),
and as stamped when it says "rig stamp" or names both the clock state (chrony or timesyncd) and the power
plan. The frozen `ontology-vs-schema-gate/` and the five copies kept under `verification/` or `verify/`
subfolders (`t1-shadow-ai-discovery`, `t4-interdiction` and three in `t7-idp-delegation-logging`, all
stamped, each a copy or re-run of the bench's main RESULTS file) are left out, as is
`agent-telemetry-retention/RESULTS.md`, whose only duration is the clock offset itself. A file can be
listed here because its only unit-bearing number is incidental, so each one is confirmed before a stamp
is added.

These 45 files carry neither a rig stamp nor both clock state and power plan:

- `agent-toolcall-schemas/RESULTS-EX2-POSTHOC-2026-11-16.md`
- `bench-d-tiered-realization/RESULTS-2026-06-15.md`
- `bench-d-tiered-realization/RESULTS-integrating-2026-06-16.md`
- `bench-d-tiered-realization/RESULTS-reproduction-2026-06-28.md`
- `clickhouse-vs-duckdb/results/RESULTS.md`
- `concurrency-multiuser/RESULTS-2026-06-15.md`
- `concurrency-multiuser/RESULTS-shard-sweep-2026-06-15.md`
- `deterministic-routing-noncircular/RESULTS-QUIET-2026-11-16.md`
- `deterministic-routing-sim/RESULTS-2026-06-15.md`
- `duckdb-edge-floor/RESULTS-2026-06-15.md`
- `duckdb-edge-floor/RESULTS-QUIET-2026-11-16.md`
- `edr-two-regime/RESULTS-2026-06-15.md`
- `engine-join-specialization/results/RESULTS.md`
- `iceberg-compaction/RESULTS-MANIFEST-ARM-2026-11-16.md`
- `mcp-manifest-drift/RESULTS-RELEASE-ARM-2026-11-16.md`
- `mv-rewrite-freshness/RESULTS-2026-06-15.md`
- `ocsf-1.9-rescore/RESULTS.md`
- `ocsf-catalog-contention/results/RESULTS.md`
- `ocsf-context-collapse-apt29/results/RESULTS-QUERY-COST.md`
- `ocsf-sigma-detection/RESULTS-evidenceforge-arm-2026-07-04.md`
- `ocsf-sigma-detection/RESULTS-temporal-execution-2026-06-16.md`
- `ocsf-sigma-detection/RESULTS-value-count-2026-06-16.md`
- `ocsf-zorder-pruning/RESULTS-multifile-bloom-2026-06-15.md`
- `ocsf-zorder-pruning/results/RESULTS.md`
- `parquet-checksum-integrity/RESULTS-RERUN-2026-11-16.md`
- `polaris-catalog-dryrun/RESULTS-2026-06-15.md`
- `sdpp-ingest-throughput/results/RESULTS.md`
- `soc-query-shapes/RESULTS-beaconing-2026-06-15.md`
- `soc-query-shapes/RESULTS-ueba-planted-2026-06-15.md`
- `soc-query-shapes/RESULTS-ueba-rare-2026-06-15.md`
- `stream-complexity/results/RESULTS-freshness-2026-11-06.md`
- `stream-complexity/results/RESULTS-v2-2026-11-03.md`
- `stream-complexity/results/RESULTS-v3-risingwave-2026-11-07.md`
- `stream-complexity/results/RESULTS.md`
- `t3-guardrail-adaptive/RESULTS.md`
- `t5-model-artifact-scanning/RESULTS.md`
- `t6-finetune-memorization/RESULTS.md`
- `t8b-telemetry-injection/RESULTS-2026-11-15.md`
- `t8c-trifecta-detection/RESULTS-MIXED-CASE-PROBE-2026-11-16.md`
- `t8c-trifecta-detection/RESULTS.md`
- `t9-pretooluse-hook-enforcement/RESULTS.md`
- `text-search-regex/RESULTS-2026-06-15.md`
- `workload-interference/results/RESULTS.md`
- `zeek-flagship-rerun/results/RESULTS-bm25-fulltext-2026-07-07.md`
- `zeek-flagship-rerun/results/RESULTS.md`

## Chart captions that repeat numbers under review

Most chart scripts in [`charts/`](../charts/) carry their numbers as constants copied from the RESULTS
file named in a `# Source:` comment, so a correction to a bench result reaches a chart only when its
script is edited and re-rendered. These rows of [`CHART-MANIFEST.md`](../charts/CHART-MANIFEST.md) repeat
a number that the audit was checking on 2026-11-17, and each waits on its bench's outcome before any
re-render.

- `data-health-recovery-donut.png`, `data-health-recovery.png` and `ext-1-robustness-parameter-sweep.png` (the 75.6% cross-tool recovery and the 47.7, +27.9 and 24.4 split), from `ocsf-data-health`.
- `three-mechanisms-of-silent-detection-loss.png` (absence-collapses-to-NULL, recall 1.00 to 0.00), from `flattening-fidelity`, where the drop follows from how the corpus was built.
- `detection-coarsening-s-two-failure-modes.png` (c2_domain recall 1 to 0, nomfa_privesc 1 to 268), from `ocsf-sigma-detection`, whose rules match values the generator planted.
- `per-mechanism-context-collapse-decomposi.png` (five adversary-tail queries at delta +1.000), from `bench-a-context-collapse`.
- `sigma-correlation-rule-fidelity-across-4.png` (pySigma 1.3.3 compiler output), from `sigma-portability`, against the later pySigma re-run.
- `deterministic-schema-constrained-mapper.png` (silent errors go to zero by construction, phi3 at 60 to 99%), from `ocsf-deterministic-mapper`.
- `schema-grounding-cuts-invented-paths.png` (the capability ladder), from `ocsf-mapping-oracle`, whose 2026-11-16 re-score chart has no manifest row yet.
- `per-source-ocsf-coverage-vs-lossiness-ac.png` (Palo Alto typed count of 46, a constant in the chart script), from `ocsf-mapping-fidelity`, where the strict OCSF 1.8.0 re-score in `ocsf-1.9-rescore/` found two PAN-OS paths invalid.
- `13-reader-answer-equivalence.png`, `answer-equivalence-donut.png` and `chdb-parquet-equality-silent-undercount.png` ("10 of 12 readers" and chDB 4.1.8's v3 reader), which hold for chDB 4.1.8 and not for 4.1.9, where the undercount is fixed.

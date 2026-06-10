# Benchmark chart asset manifest

Built 34 lab charts + 5 correctness tables from first-party `sdw-lab-benchmarks` results, plus 7 campaign graphics (2026-06-10, `_p*`/`_pb*` scripts) and 6 book figures (2026-06-10, `_bk*` scripts, MOAr restructure Wave C) — see the bottom sections.
All numbers re-derived from source `RESULTS.md`; brand-styled via `chartstyle.py`; collision guards enforced (the two 96.3%s, the two storage premiums, the two recall headlines never cross).
Web-served at `securitydataworks.com/research/charts/<file>`.

## Charts

| rank | file | caption | target surface |
|---|---|---|---|
| 1 | `data-health-recovery-donut.png` | Cross-tool recovery, donut (center KPI 75.6%) | detection/cross-tool-assurance-gap ✅ |
| 1 | `data-health-recovery.png` | Cross-tool recovery, stacked bar (47.7→+27.9→24.4 of 140k cells) | detection/cross-tool-assurance-gap ✅ 📍PLACED |
| 2 | `de-gamed-recall-loss.png` | Verbatim SigmaHQ rules on real APT29 telemetry: 9 named adversary-tail detections drop to zero matches under the documented coarsening while routine rules lose  | web:/research + essay:ocsf/context-collapse-measured + litreview:figure-degamed-recall ✅ 📍PLACED |
| 3 | `13-reader-answer-equivalence.png` | Byte-identical 10M-row Parquet, 24 count(*) WHERE cells per reader checked against ground truth: 11 of 13 readers agree, chDB 4.1.8's v3 reader is silently wron | essay:trustworthy/verify-the-answer + web:/research + book:ch09-query-engine-selection |
| 3 | `answer-equivalence-donut.png` | 11-of-13 readers agree, KPI donut | (verify-the-answer essay — not yet written) |
| 4 | `context-collapse-price-of-the-fix.png` | Keeping atomic-grain OCSF fidelity on the APT29 corpus costs 1.80x storage and 1.26x query compute vs the coarsened store, but the compute premium is not flat — | essay:ocsf/context-collapse-measured + essay:economics/pricing-the-fidelity-fix + web:/research ✅ |
| 5 | `three-mechanisms-of-silent-detection-loss.png` | Three structural ways flattening OCSF silently drops a detection — absence-collapses-to-NULL (recall 1.00->0.00), grain loss (beacon-hunt F1 1.00->0.50), and fl | essay:ocsf/flattening-anti-pattern + web:/research + litreview:figure-flattening-fidelity ✅ 📍PLACED |
| 6 | `schema-grounding-cuts-invented-paths.png` | Giving a model the OCSF schema cuts its rate of inventing non-existent paths (silent-error) across a capability ladder — but the lift shrinks toward the frontie | essay:ai/schema-is-the-lever + web:/research/ai-native-vs-augmented + book:ch08-ocsf-strategy 📍PLACED (in ocsf/llm-ocsf-mapping) |
| 7 | `iceberg-manifests-vs-ducklake-sql-catalo.png` | Iceberg's manifest planning climbs 17.6x as 5M rows fragment across more commits while DuckLake's SQL-catalog lookup stays flat (1.21x) — the small-files tax Ic | essay:catalogs/small-files-planning-tax + essay:lakehouse/v4-vs-ducklake (V4 milestone #58 evidence) + essay:lakehouse/iceberg-maintenance |
| 8 | `materialized-view-three-number-accountin.png` | A materialized view trades three things: read speed (45-77x faster), compute (incremental beats recompute 2.9x but collapses to break-even as aggregate cardinal | essay:pipelines/materialized-views-soc (engines/materialized-views) + book:ch09-query-engine-selection (9.4B cites Tier-C 78x-9000x, no first-party measurement) ✅ |
| 9 | `per-mechanism-context-collapse-decomposi.png` | Per-query recall lost when a synthetic fidelity store is coarsened: five adversary-tail queries go fully blind (delta +1.000) by grain/structural/time mechanism | essay:ocsf/context-collapse + essay:detection/context-collapse-mechanisms + litreview:figure-mechanism-decomposition |
| 10 | `per-source-ocsf-coverage-vs-lossiness-ac.png` | OCSF 1.8.0 carries most fields cleanly but a third to a half lose something — per-source typed (clean) / coerced (boundary crossed) / unmapped (no home), sorted | essay:ocsf/crosswalk-corpus + web:/research (the Okta 36-mappable / 18-shipped accessibility number) |
| 11 | `nl2sql-silent-error-by-model-strength-an.png` | Silent wrong answers cluster mid-difficulty (phi3: 2 in simple_filter, 1 in group_by) while the stronger gemma3:26b is wrong more often but always loudly (0 sil | essay:ai/silent-errors-in-nl2sql (detection/silent-wrong-answer-llm-sql) + book:ch09-query-engine-selection |
| 12 | `sigma-correlation-rule-fidelity-across-4.png` | Sigma correlation rules degrade unevenly across SIEM compilers; the OpenSearch PPL silent window-drop is the cell that bites. (Tier B, pySigma 1.3.3 compiler-ou | essay:sigma/correlation-portability + litreview:table-sigma-portability |
| 13 | `detection-coarsening-s-two-failure-modes.png` | Coarsening doesn't degrade detection uniformly — it blinds the rule whose key it dropped (c2_domain recall 1→0) and makes another cry wolf (nomfa_privesc 1→268  | essay:detection/coarsening-blinds-and-cries-wolf + book:ch03-the-ground-youre-standing-on |
| 14 | `entity-resolution-tax-on-a-contested-joi.png` | Contesting the join key is part of the assurance gap: a clean-key oracle recovers 96.3% of the identity estate, contested-key 86.2% (a −10.1pp resolution tax),  | essay:trustworthy/cross-tool-assurance-gap (economics/entity-resolution-tax) + litreview:figure-resolution-tax ✅ |
| 15 | `concurrent-writer-degradation-shape.png` | Under concurrent writers each catalog fails differently: DuckLake serializes on the SQL catalog (p95 climbs 45.8× to 662ms, zero errors) while Iceberg retry-sto | essay:catalogs/concurrent-writers |
| 16 | `ducklake-vs-iceberg-read-neutrality-on-b.png` | On byte-identical Parquet the catalogs are read-neutral (3 of 4 queries at parity); the apparent format 'speedup' decomposes to the writer's codec choice (up to | essay:catalogs/format-read-neutrality + litreview:figure |
| 17 | `parquet-writer-as-a-read-lever.png` | Pick the writer not just the codec: at a matched zstd-3 codec pyiceberg writes the smallest file (212.4 MB) and reads fastest (381ms) while pyarrow's two encodi | essay:catalogs/writer-not-codec (lakehouse/same-codec-different-sizes) ✅ |
| 18 | `z-order-vs-single-sort-vs-unordered.png` | Z-order is the only layout that prunes the two-plus-dimension queries a single sort can't touch (Q3 15%, Q4 65%) but pays 5.6x the single-sort write cost — Tier | essay:engines/zorder-pruning (pipelines/zorder-pruning-tradeoff) |
| 19 | `chdb-parquet-equality-silent-undercount.png` | chDB 4.1.8's Parquet equality path silently drops 6 to 12 matching rows on 6 of 8 probe values (52 short overall) with no error, while DuckDB, chDB LIKE and chD | essay:trustworthy/verify-the-answer + essay:economics/how-to-run-a-benchmark-that-doesnt-lie |
| 20 | `schema-trained-zstd-dictionary-compression.png` | A schema-trained ZSTD dictionary takes per-event compression from 1.33x to 3.57x but its edge fades as you batch and is gone by 100 events/block, while columnar | essay:economics/cost-paradox + essay:lakehouse/same-codec-different-sizes ✅ |
| 21 | `deterministic-schema-constrained-mapper.png` | Constrain the output to the OCSF 1.8.0 schema and silent errors go to zero by construction where phi3 invents non-existent paths 60 to 99% of the time, but the  | essay:ai/schema-is-the-lever (ocsf/llm-ocsf-mapping) + book:ch08-ocsf-strategy ✅ |
| 22 | `projected-dwpd-vs-ingest.png` | Projected drive-writes-per-day stays an order of magnitude under a read-intensive drive even at 5 TB/day ingest. Tier B, single-host: write-amp is MEASURED on 5 | essay:economics/endurance-premium-security-data ✅ |
| 27 | `parquet-encoding-library-matrix.png` | Tune Parquet for size and the exotic encodings fail loud (caught errors), not silent -- zero silently-wrong cells across 6 readers. Tier B, single-host, 20k row | essay:trustworthy/encoding-decode-matrix |
| 28 | `ingest-engine-throughput-rss.png` | Throughput and memory split six measured OSS ingest engines by an order of magnitude on 1M Zeek conn.log events; teal bars are JSON-parse comparable, rsyslog ra | essay:pipelines/ingest-engine-matrix |
| 29 | `adbc-vs-jdbc-deinflated.png` | The honest columnar-vs-row win is single digits (6.3x at 100k, 8.1x at 1M ADBC vs native-JVM JDBC), not hundreds -- the Python/JPype bridge inflates the gap ~40 | essay:pipelines/arrow-transport |
| 30 | `write-contract-commit-latency.png` | The file-write tax (a data file + manifest + metadata.json per commit) bites the small streaming commit at 2.32x latency, narrowing to 1.37x on bulk load where  | essay:catalogs/write-contract |
| 32 | `mv-incremental-vs-recompute-crossover.png` | Incremental MV maintenance pays only for bounded-cardinality panels — the crossover ratio is this corpus's, the bounded-saturates-vs-unbounded-doesn't SHAPE is  | essay:pipelines/materialized-views-soc ✅ |
| 34 | `vortex-vs-parquet-footprint-scan-needle-write.png` | Vortex trades a bigger file for faster reads; Parquet for cheaper writes (Tier B, single-host, 1M rows). Emerging-format track — Vortex is not yet an Iceberg da | essay:engines/vortex-format |
| 36 | `obda-ontop-vs-llm-text-to-sql-on-adversary.png` | Neither is silently wrong here — OBDA answers a narrow set exactly and refuses loudly, the local LLM is broader-attempted but loud-broken (Tier B, single-host,  | essay:ai/obda-vs-llm |
| 38 | `engine-side-rls-overhead-by-query-shape.png` | Row-level security is not a flat tax — overhead depends on the query shape; a selective predicate can read fewer rows and run FASTER than no filter (Tier B, sin | essay:pipelines/rls-overhead |
| 39 | `cold-vs-warm-read-penalty-per-query-iceberg.png` | Forensic/IR reads run cold — the first scan pays up to a 1.55x page-cache penalty; cold/warm ratios and relative cold shape transferable, absolute ms this host' | essay:catalogs/cold-cache-reads |
| 42 | `ext-1-robustness-parameter-sweep.png` | Every cell of the 3x3 parameter sweep keeps the same ordering — cross-tool > best-single (min margin +19.4%), residual gap > 0, lever > 0 everywhere; the 75.6%  | essay:trustworthy/cross-tool-assurance-gap ✅ |

## Correctness tables (markdown)

- `null-coercion-timezone-divergence.md` —  → essay:trustworthy/null-coercion-timezone-traps + litreview:table-null-tz-coercion
- `nested-ocsf-query-portability.md` —  → essay:ocsf/nested-type-portability (nested-observables-portability) + litreview:table-nested-fidelity
- `parquet-page-checksum-three-way-split.md` —  → essay:trustworthy/verify-the-bytes
- `parquet-float-determinism-and-pme-lockout.md` —  → essay:trustworthy/determinism-and-encryption
- `airgap-local-model-agentic-hunt.md` —  → essay:ai/air-gapped-agentic-hunt

## Campaign graphics (built 2026-06-10 for the LinkedIn book-led arc)

One visual per campaign post, per `project1/02-projects/securitydataworks/linkedin-campaign-queue.md` § "Campaign visual pairing". Posted by hand to LinkedIn; not auto-placed in essays. The two measurement charts carry Tier B footers; the five diagrams carry an explicit "illustrative · mechanism, not a measurement" tier line.

| script | file | head (the claim) | campaign post |
|---|---|---|---|
| `_p15_who_may_benchmark.py` | `who-may-benchmark.png` | The SIEM you'd leave forbids the benchmark; the lakehouse you'd move to doesn't. (license texts, verified 2026-06) | Post 15 — the closing visual |
| `_p10_storage_footprint.py` | `storage-footprint-7x.png` | Same data, same answers, about a seventh of the storage. (1.6 vs 11.5 MB @ 200k events, `./moar compare`) | Post 10 |
| `_p06_five_engines_one_answer.py` | `five-engines-one-answer.png` | Five engines, one table, one answer. (1,000 rows · 125 RDP, `./moar verify`) | Post 6 |
| `_p12_time_travel_snapshots.py` | `time-travel-snapshots.png` | Three writes, three snapshots — each still queryable as it stood. | Post 12 |
| `_p05_two_streams_join.py` | `two-streams-join.png` | Neither signal is an incident; the join on source IP is. | Post 5 |
| `_pb2_pipeline_lockin_stack.py` | `pipeline-lockin-stack.png` | Open formats don't remove lock-in; they move it to the pipeline. | B2 |
| `_pb6_three_journeys.py` | `three-architect-journeys.png` | Same framework, three estates, three different right answers. | B6 |

Collision guards honored: `storage-footprint-7x` is the MOAR footprint measurement, never the 1.80×/1.93× fidelity premiums; no campaign graphic touches the 96.3% or recall-headline families.

## Book figures (built 2026-06-10 — MOAr restructure task #28 Wave C, builds #1–#6)

Each replaces repeated template prose in the restructured book; placements are the `<!-- FIGURE: name (build #N) -->` comments already in the chapters. Every number is carried exactly from the named book source (no lab data); the framing/process diagrams carry an explicit "framing diagram / framework-derived / illustrative — not a measurement" tier line instead of a Tier letter. Each ships as a web PNG plus a grayscale 300-dpi `-print` variant for the PDF build.

| script | file | head (the claim) | book destination · source |
|---|---|---|---|
| `_bk1_adoption_bar_two_axis.py` | `adoption-bar-two-axis.png` | A move has to win large on BOTH axes (technical × operational) or the risk doesn't make sense. FRAMING diagram, no data points. | ch01 Executive Summary · ch01 line 7 |
| `_bk2_vendor_filtering_funnel.py` | `vendor-filtering-funnel.png` | 80+ vendors → 10-15 viable → 3-5 finalists → 1 validated selection; Tier 1 does ~87% of the work. | ch03 §3.1 · the Filtering Effect table |
| `_bk3_workload_engine_grid.py` | `workload-engine-grid.png` | One grid replaces five capability matrices; every Tier 1 workload disqualifies someone (Athena/PostgreSQL/Splunk). Unrated cells shown honestly as "not assessed in §3.3". | ch03 §3.3 · worked threat-hunting matrix + decision-implication prose |
| `_bk4_five_phase_timeline.py` | `five-phase-decision-timeline.png` | Requirements → documented decision in roughly seven weeks; four belong to the POC; gate outputs per phase + per-phase reality check. | ch03 §3.5 · phase headings + week spans |
| `_bk5_three_journeys_pathab.py` | `three-journeys-comparison.png` | Extends `_pb6_three_journeys` with the Marcus Path-A→B pivot; $380K / $2.9M / $12M / $1.8M and the $9.1M/yr premium carried character-exact. | ch04 §4.5 · comparison table |
| `_bk6_phased_roadmap_swimlanes.py` | `phased-roadmap-swimlanes.png` | Integrated org: pilot M1-3 → production M4-6 → optimization/sunset M7-9 with gates; federated: 7 staggered BU bars to M12 ("12 months against the 6 to 9"). | ch06 §6.3 · phase spans + Appendix L.4 rollout table |

Collision guard: `three-journeys-comparison` (book figure, carries the §4.5 dollar figures) is distinct from `three-architect-journeys.png` (campaign B6, no dollar figures) — don't swap them.

✅ = target essay exists today (existence only, says nothing about placement). 📍PLACED = chart is deployed into a live essay (the first four placed 2026-06-09, securitydataworks c40ac51); where the placed essay isn't the row's named target, the marker names it. Rows with neither are staged for placement or need the essay written first.

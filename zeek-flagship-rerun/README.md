# zeek-flagship-rerun — the 145× flagship, re-measured under the methodology

**PRE-REGISTRATION (2026-06-10, committed before any scored run).** This bench re-measures
the program's most-cited number — the legacy "145× vs the schema-on-read SIEM" flagship from
`splunk-db-connect-benchmark` (Nov–Dec 2025) — with the rigor that benchmark predates: repeat
trials, CV-gated claims, answer-equality checks, and the native-vs-open-format separation
reported instead of a single conflated headline.

**This is a new measurement that supersedes the old one, not a reproduction.** The foil
changes (OpenSearch 2.18.0 replaces the original SIEM, per the standing public-language
genericization to "schema-on-read SIEM"), the timing client changes (see Deviations), and the
host differs. The old result stays what it was: a single-run measurement against a different
baseline.

## Hypothesis

H3-PERFORMANCE-01. Expected outcome, stated before the run: ClickHouse native MergeTree
beats the schema-on-read foil by a large multiple on these 5 queries, ClickHouse-over-Iceberg
beats the foil by a clearly smaller multiple, and the native-vs-Iceberg gap is itself large
(the original measured 6.1×). If the foil lands much closer than the original's 27.5 s
baseline — plausible, since OpenSearch aggregations are not the original SIEM's search
pipeline — the honest headline shrinks, and that is an acceptable result. The number we
publish is whatever survives the CV gate.

## Arms

| Arm | Storage | Load path | Query path |
|---|---|---|---|
| `opensearch` | OpenSearch 2.18.0 index, 1 shard / 0 replicas, `best_compression`, forcemerged to 1 segment | `helpers.parallel_bulk` from JSONL, `refresh_interval: -1` during load | opensearch-py DSL, `request_cache=false` |
| `clickhouse_native` | MergeTree, **default LZ4, no per-column codecs** (the default-config arm) | `insert_arrow` from the pinned Parquet + `OPTIMIZE FINAL` | clickhouse-connect HTTP SQL, `use_query_cache=0` |
| `clickhouse_iceberg` | Iceberg on MinIO (pyiceberg defaults: zstd Parquet), 5 data files (2M-row appends) | pyiceberg SqlCatalog → `s3://zfr-bench/iceberg` | same client, `icebergS3()` table function (write-once table, so catalog-less metadata resolution is safe) |

Declared layout choice: the native table keeps the original benchmark's
`PARTITION BY toDate(ts)`, `ORDER BY (orig_h, resp_h, ts)` — a sorted-layout advantage the
Iceberg table does not get (it is written unsorted). That asymmetry is part of what
"native vs open format" honestly means here and is reported, not hidden.

## Corpus (pinned)

10,000,000 rows from the ported `zeek_generator.py` (verbatim copy from the archived repo),
seed 42, streamed to one JSONL (foil load) + one Parquet (CH/Iceberg loads), flattened to the
same 16 columns in every arm (`id.orig_h`→`orig_h` etc., always-empty `tunnel_parents`
dropped). The corpus is pinned by sha256 in `_work/corpus_fingerprint.json` (methodology #9).

## Queries

The 5 standardized queries, verbatim from the original suite (`queries.py`): count_all,
top_source_ips_by_bytes, protocol_distribution, long_duration_connections,
port_scan_detection.

## Protocol (per methodology)

- Per arm × query: **1 discarded warmup + 7 timed trials**; report all durations, median,
  mean, CV. (Methodology §4 minimum is 3; we run 7.)
- **Claims gate:** a delta is claimable only when the gap % exceeds the larger CV of the two
  arms being compared (`run_bench.py --compare` computes every pairwise gate).
- **Answer equality:** every query's extracted answer must be identical across all three arms
  (exact values, not row counts). A mismatch invalidates that query's comparison — this is
  the silent-wrong check the original lacked (its native average even contained a
  `success: False` query).
- **Isolation:** one arm timed at a time; the other containers are stopped during timing
  passes. Windows power plan verified High Performance before runs (`powercfg /getactivescheme`).
- **Conditions:** hot/warm only (no passwordless sudo for an OS page-cache drop — labelled
  per methodology §3). `--engine-cold` additionally reports one engine-restart run per query
  (engine-cold / OS-warm), separately, ungated.
- **Storage:** captured per arm at load time (`_work/load_*.json`): OS store size after
  forcemerge; CH `system.parts` compressed/uncompressed; Iceberg data-file bytes from
  `table.inspect.files()`; raw JSONL size as the uncompressed reference.

## Declared deviations from the original

1. **Foil:** OpenSearch 2.18.0 replaces the original schema-on-read SIEM (license posture +
   public genericization). Headlines therefore do not transfer backward.
2. **Timing client:** all arms timed as client-side wall time from one Python process over
   HTTP. The original timed ClickHouse via `docker exec clickhouse-client` subprocess, which
   adds process-spawn overhead inside sub-second measurements; this run removes it.
3. **OS DSL exactness:** port_scan terms `size` 10000→20000 (exhaustive over the corpus's
   ~14.8k distinct `orig_h`, matching SQL GROUP BY semantics) and `precision_threshold:
   40000` on the cardinality aggs (exact below threshold; default HLL would fail
   answer-equality by design). Both make the foil do the same work the SQL arms do.
4. **Iceberg write:** pyiceberg 0.11.1 defaults (zstd) rather than the original's
   hive-metastore path; footer/properties recorded in the load metadata.

## Run order

```bash
# 0. containers + corpus
docker compose up -d            # opensearch + clickhouse + minio
.venv/bin/python generate_data.py

# 1. loads (any order)
.venv/bin/python load_arms.py opensearch
.venv/bin/python load_arms.py clickhouse
.venv/bin/python load_arms.py iceberg

# 2. timed passes — one arm at a time, others stopped
docker stop zfr-clickhouse && docker start zfr-opensearch
.venv/bin/python run_bench.py --arm opensearch --engine-cold
docker stop zfr-opensearch && docker start zfr-clickhouse
.venv/bin/python run_bench.py --arm clickhouse_native --engine-cold
.venv/bin/python run_bench.py --arm clickhouse_iceberg --engine-cold   # minio must be up

# 3. report
.venv/bin/python run_bench.py --compare
```

## Outputs

`results/raw_<arm>.json` (every trial + answers), `results/comparison.json` (answer-equality
+ CV-gated pairwise speedups), `results/RESULTS.md` (written after the run; every claim
CV-gated). Consumers: H3-PERFORMANCE-01 re-tiering, /thesis + LAB.md + book ch01/07 number
refresh, the four website pages citing the legacy 145×.

---

## Layout and audit notes (added 2026-11-17)

Everything above this line is the bench's pre-registration as committed in `05ddf47` and is left unchanged, including its wording (the text above the divider matches that commit apart from one blank line before the divider); errata go here, below it.

### Erratum to the pre-registration

*(corrected 2026-11-17: Declared deviation 3 above gives `precision_threshold: 40000` on the cardinality aggregations; the code that ran uses 3000 (`queries.py:9,94`), which `results/RESULTS.md` also states. The terms `size` of 20000 is as written.)*

### Result, and whether it is measured

Measured and answer-checked, with each per-query pair CV-gated. From `results/comparison.json`, the average of per-query medians is 2.854 s for OpenSearch 2.18.0, 0.282 s for ClickHouse over Iceberg and 0.061 s for ClickHouse native, so 10.1× and 46.8× over the OpenSearch baseline, with an open-format cost of 4.6× between the two ClickHouse arms. One query carries that average: `port_scan_detection` is 13.07 s of the 14.27 s OpenSearch total (92%, `results/raw_opensearch.json`), and without it the same averages give 2.5× (Iceberg) and 12.7× (native). Its answer check compares two empty sets (see below), so the per-query table is the result to cite and the average is a summary of it; the CV gate applies to the per-query pairs, not to the average (added 2026-11-22). Per query, the hunting-shaped aggregations run 5.4× to 62× faster on the columnar arms, while OpenSearch wins the two index-served lookups. Per-query CVs run from 1.8% to 14.4%.

### What would have made it fail

The pairwise claims gate (gap above the larger CV) and the answer-equality check, both computed by `run_bench.py --compare`. Two caveats the RESULTS file states: `port_scan_detection` returns an empty set on this corpus, because the generator caps distinct ports per source at 10, so its timing is real work with hollow detection semantics; and sub-10 ms medians sit near the client's floor.

### Pre-registration

The text above the divider is the pre-registration. There is no hash file, but the repository history confirms the order: the pre-registration was committed in `05ddf47` at 2026-06-10T09:25:47Z, 15 minutes before the first scored arm started (`started_unix` 09:41:02Z in `results/raw_opensearch.json`) (checked 2026-11-22).

### Results: which file to read, and which draw the published numbers come from

- **Entry point: `results/RESULTS.md`.** Every published 46.8×, 10.1× and 5–62× figure comes from draw 1, the files directly under `results/` (`raw_*.json`, `comparison.json`, `env.json`), which ran on 2026-06-10 against OpenSearch 2.18.0.
- `results/REVALIDATION-2026-06-14.md` documents draw 2, a full re-run four days later captured in `results_revalidation_2026-06-14/` by `revalidate.sh` (45.1× and 10.6×).
- `FLAGSHIP-TRIPLE-BAND-2026-06-14.md` documents draw 3, captured in `results_revalidation3_2026-06-14/`. `draw3_proper.sh` restarts MinIO and Nessie, re-registers the Iceberg table and then calls `revalidate.sh`; its ClickHouse arms succeeded and its OpenSearch and Dremio arms did not, so `finish_draw3.sh` re-ran OpenSearch (and attempted Dremio) with readiness gating and re-captured the draw. The band across the three draws is 10.12×, 10.59× and 11.35× (baseline over ClickHouse-Iceberg) and 4.62×, 4.25× and 4.24× (open-format cost). That file labels all three OpenSearch columns 3.7.0, which is wrong for draws 1 and 2 (2.18.0); draw 3 records no version. A dated note at the top of that file says so.
- `results_version_currency_2026-06-14/` holds one OpenSearch 3.7.0 pass compared against draw 1's ClickHouse arms (`comparison_os37_mixeddraw.json`); `VERSION-CURRENCY-2026-06-14.md` at the repository root reads it as no material change.
- `results/NEEDLE-FINDINGS-2026-06-14.md` (`needle.py`, `results/needle.json`) covers point lookups, on OpenSearch 3.7.0.
- `results/RESULTS-bm25-fulltext-2026-07-07.md` (`run_bm25_bench.py`, `results/bm25_execution.json`) covers full-text and ranked search; `bm25_execution_partial.json` is an earlier partial capture.
- `results/starrocks_trino_arms.json` (`starrocks_trino_arms.py`) is not part of the flagship result. It ran StarRocks and Trino over a copy of the corpus on a different stack, divides by draw 1's 2.854 s OpenSearch time taken in a different session, and records medians with no CV and no answer check: StarRocks 0.343 s (8.3×) and Trino 0.795 s (3.6×).
- `dremio-prior-art.md`, `dremio_arm.py` and `raw_dremio_iceberg.json` belong to the Dremio arm, whose measured results are withheld under that engine's benchmark-publication terms.

### Versions and pins

Draw 1 recorded ClickHouse 26.5.1.882, OpenSearch 2.18.0, pyiceberg 0.11.1, clickhouse-connect 1.1.1 and opensearch-py 3.2.0, with image digests (`results/env.json`). `compose.yml` has since moved OpenSearch to 3.7.0 and keeps ClickHouse, MinIO and Nessie on `:latest` (ClickHouse deliberately, with the version read back at run time), so running the compose file today does not reproduce the published baseline without pinning OpenSearch back to 2.18.0. pyiceberg and numpy are not pinned in the root `requirements.txt` and this folder has no requirements file of its own (other benches pin pyiceberg 0.11.1, for example `ocsf-iceberg-metadata/requirements.txt`, and numpy, for example `delegation-chain-query/requirements.txt`); opensearch-py and faker are not pinned in any requirements file in the repository. `revalidate.sh` refers to a `results_published_backup/` directory that is not in the tree.

### Evidence tier and limits

Tier B, one host, 10M synthetic Zeek connection rows, hot and warm cache only (no OS page-cache drop). The baseline is a bare OpenSearch index, not a SIEM product with its pipeline.

### Corrections

- 2026-11-17: erratum above (`precision_threshold`); dated notes added to `results/RESULTS.md` (engine-cold wording, the StarRocks and Trino file) and to `FLAGSHIP-TRIPLE-BAND-2026-06-14.md` (OpenSearch version labels).

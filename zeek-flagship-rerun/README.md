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

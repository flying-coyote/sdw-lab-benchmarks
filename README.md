# SDW Lab benchmarks

First-party, reproducible benchmarks behind [securitydataworks.com/lab](https://securitydataworks.com/lab).
The site's premise is that security-data claims should be measured rather than
asserted — these are the measurements. Each is a small, deterministic experiment
that a skeptic can re-run, scored against a known ground truth or checked
engine-against-engine, and labelled at an honest evidence tier.

## The benchmarks

| dir | what it measures | tier | state |
|---|---|---|---|
| [`flattening-fidelity/`](flattening-fidelity/) | which detections silently break when semi-structured OCSF/CloudTrail logs are flattened or rolled up to a coarse grain | B | published |
| [`clickhouse-vs-duckdb/`](clickhouse-vs-duckdb/) | whether ClickHouse and DuckDB are interchangeable over OCSF-shaped data — same answers? what does swapping cost in latency? | B | published |
| [`sigma-portability/`](sigma-portability/) | how much of a Sigma correlation rule survives compilation to four open backends (Splunk SPL, ES&#124;QL, Lucene, OpenSearch PPL) | B | published |
| [`ocsf-mapping-fidelity/`](ocsf-mapping-fidelity/) | how completely and how losslessly real vendor schemas (Okta, CrowdStrike) map into OCSF 1.8.0 — typed vs coerced vs unmapped, field by field | B | published |
| [`bench-a-context-collapse/`](bench-a-context-collapse/) | whether normalizing multi-source telemetry into one coarse OCSF store degrades adversary-relevant queries more than routine ones (two stores, one planted-chain corpus, 16 frozen queries) | B | first pass |
| [`ocsf-semantic-testbed/`](ocsf-semantic-testbed/) | the shared planted-chain corpus + ground truth feeding BENCH-A/B/C — the build-once foundation, not a benchmark itself | — | foundation |
| [`ocsf-mapping-oracle/`](ocsf-mapping-oracle/) | does schema / formal grounding / an ontology-thinking discipline cut the OCSF attributes a model invents — silent-error rate across four conditions on a local model | B | first pass (local leg) |
| [`ocsf-semantic-query/`](ocsf-semantic-query/) | OBDA vs GraphRAG vs text-to-SQL on adversary-tail concept queries — silent-error rate the decisive metric (text-to-SQL arm first; OBDA/GraphRAG pending) | B | first pass (1 of 3 arms) |
| [`ocsf-write-contract/`](ocsf-write-contract/) | hot-tier write contract under streaming OCSF ingest: file-write (Iceberg) vs SQL-transaction (DuckLake) — commit latency, write amplification, read-contract coherence (ISK never-write arm pending) | B | first pass (2 of 3 arms) |
| [`ocsf-fsi-compliance/`](ocsf-fsi-compliance/) | human-hours to produce a §1003(b)/Reg-SCI evidence report on a lakehouse vs a schema-on-read SIEM — corpus + frozen spec + defensibility demonstrated; human-hours pending an operator run | B | scaffold |
| [`ocsf-arrow-transport/`](ocsf-arrow-transport/) | the connectivity layer for moving OCSF result sets — ADBC (Arrow columnar) vs JDBC (row-oriented) + a Parquet encoding sweep + an edge-case type battery | B | first pass |
| [`ocsf-iceberg-metadata/`](ocsf-iceberg-metadata/) | the small-files tax — scan-planning cost grows with file/manifest count and compaction recovers it (within-Iceberg; pyiceberg-planner microbench, illustrative not production) | B | first pass |
| [`ocsf-read-scan/`](ocsf-read-scan/) | BENCH-E: DuckLake vs Iceberg large-scan reads (10M rows, same engine) — interchangeable on read, latencies within ~2× by query shape | B | first pass |
| [`ocsf-sigma-detection/`](ocsf-sigma-detection/) | do compiled Sigma rules *fire correctly* over the OCSF store — detection of the planted chain (recall) + precision, the execution complement to sigma-portability | B | first pass |

## How they are kept honest

- **One determinism core.** [`lib/common.py`](lib/common.py) holds a single
  `MASTER_SEED`, a fixed epoch anchor, and the scoring/timing helpers every
  benchmark shares. No `datetime.now()`, no unseeded randomness in any corpus
  generator, so a re-run reproduces the corpus — and therefore the answers —
  exactly.
- **The reproducible part vs the measured part.** Where a benchmark produces a
  deterministic result (a recall, an F1, an answer-set), `run.py` re-runs it and
  asserts the output is identical. Where it produces a wall-clock latency, that is
  reported as a median on named hardware, never as a constant.
- **Tier B, stated plainly.** These are controlled measurements on synthetic
  corpora, not production telemetry. Each benchmark's `METHODOLOGY.md` states the
  tier, the corpus design, and every magnitude that is a corpus parameter (a
  ratio chosen for the experiment) rather than a universal constant.

## Reproduce

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt                 # duckdb + chdb (the two engine/fidelity benchmarks)
cd flattening-fidelity && python run.py          # or clickhouse-vs-duckdb/
```

`sigma-portability/` has a different dependency set (the pySigma stack), so it
carries its own `requirements.txt`:

```bash
pip install -r sigma-portability/requirements.txt
cd sigma-portability && python run.py
```

Each benchmark is self-contained and reads the shared `lib/` via a path shim, so
it runs from its own directory.

## Layout

```
lib/common.py           shared seeds, epoch anchor, scoring + timing helpers
flattening-fidelity/    benchmark: OCSF flattening fidelity (3 failure modes)
clickhouse-vs-duckdb/   benchmark: engine interchangeability on OCSF data
sigma-portability/      benchmark: Sigma correlation-rule portability across 4 backends
ocsf-mapping-fidelity/  benchmark: vendor-schema (Okta, CrowdStrike) -> OCSF 1.8.0 fidelity
ocsf-semantic-testbed/  shared planted-chain corpus + ground truth (feeds BENCH-A/B/C)
bench-a-context-collapse/  benchmark: OCSF context-collapse (Store F vs Store N)
ocsf-mapping-oracle/    benchmark: BENCH-B mapping oracle (4 conditions, silent-error)
ocsf-semantic-query/    benchmark: BENCH-C semantic-query head-to-head (text-to-SQL arm)
ocsf-write-contract/    benchmark: BENCH-D hot-tier write contract (Iceberg vs DuckLake; own reqs)
ocsf-fsi-compliance/    scaffold:  BENCH-F §1003(b) human-hours (corpus + spec + defensibility)
ocsf-arrow-transport/   benchmark: ADBC vs JDBC transport + Parquet encoding (own reqs)
ocsf-iceberg-metadata/  benchmark: Iceberg metadata/compaction scaling (own reqs)
ocsf-read-scan/         benchmark: BENCH-E DuckLake vs Iceberg large-scan reads (own reqs)
ocsf-sigma-detection/   benchmark: Sigma rules executed over the OCSF store (own reqs)
requirements.txt        duckdb, chdb (pinned) — sigma-portability + ocsf-write-contract have their own
```

# concurrency-multiuser: does a single-query advantage survive many analysts at once?

## What it measures

Closed-loop concurrency on one host: N identical clients, N in 1, 2, 4, 8, 16 and 32, each issuing the flagship top-talkers scan-aggregation and waiting for the full result before the next. Each engine gets one untimed warmup, then one 20 s window per level that records QPS and per-query latency, for ClickHouse over Iceberg, StarRocks, Trino and an OpenSearch baseline (a Dremio arm ran too and its results are withheld under that engine's benchmark-publication terms). A second pass, `shard_sweep.py`, re-runs the OpenSearch curve at 1, 2, 4 and 8 shards.

## Result, and whether it is measured

Measured. The columnar Iceberg engines have almost no concurrency headroom on this host: QPS at its best is 1.10× (ClickHouse-Iceberg), 1.27× (StarRocks) and 1.32× (Trino) of QPS at N=1, because one heavy aggregation already spreads across all 14 cores (re-derived from `results/conc_*.json`). The OpenSearch baseline looked like it scaled 6.73× in the first pass, but the shard sweep shows that is mostly a single-shard artefact: with 4 or 8 shards its N=1 query runs about 3.8× faster and the curve reaches the same ceiling of roughly 7.1 to 7.7 QPS, scaling only 1.7× to 2.0× (`results/shard_sweep_summary.json`). The host's cores set the ceiling for every engine.

## What would have made it fail

The N=1 level is the baseline for each engine's headroom, and an engine with idle cores at N=1 would have scaled. No repeat of any level was run, so none of the QPS figures carries a CV, and a small difference between engines at one level is not a finding.

## Pre-registration

None.

## Reproduce

```bash
# Iceberg engines from inside the ejs-lab container (it reaches Nessie and MinIO); one engine under load at a time
cd concurrency-multiuser
python3 concurrency_bench.py <engine> <out.json>
python3 shard_sweep.py          # OpenSearch shard sweep, from the host against :9200
```

Each engine's curve takes about two minutes of timed windows plus one warmup. The harness reuses `soc-query-shapes/ejs_clients.py`.

## Results

- Entry point: `RESULTS-2026-06-15.md`, with the 2026-11-17 note at the top marking its finding 2 as superseded.
- `RESULTS-shard-sweep-2026-06-15.md`, the shard sweep that supersedes the OpenSearch scaling reading.
- Data: `results/conc_{clickhouse_iceberg,starrocks,trino,opensearch}.json`, `results/conc_dremio.json` (a withholding notice), `results/shardsweep_s{1,2,4,8}.json`, `results/shard_sweep_summary.json`. The 2-shard run is a cold-cache artefact and its N=1 baseline is excluded in that file.

## Versions and pins

Engine versions are not recorded in the result files. The ejs stack images are those in `engine-join-specialization/compose.yml`, several on `:latest` tags.

## Evidence tier and limits

Tier B, one host and one engine process per arm, so this answers single user against many users and leaves single host against cluster open. The Iceberg arms query `soc.conn` at 10.3M rows while the OpenSearch index holds 10M documents. Aggregate output only.

## Corrections

- 2026-11-17: dated note added to `RESULTS-2026-06-15.md` marking finding 2 superseded by the shard sweep and recording that no level was repeated.

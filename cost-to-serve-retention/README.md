# cost-to-serve-retention — $/effective-GB at retention, measured layer vs priced layer

**PRE-REGISTRATION (2026-06-10, committed before the scored measurement).** The Matrix's
cost-to-serve axis and H1-COST-08/H-COST-09/H-FSI-03 all turn on one quantity nothing
first-party measures: what a day of telemetry costs to keep queryable at retention, per
storage realization. The published multiples (130–227×) are desk pricing; this bench builds
the measured base under them and keeps the two layers visibly separate, per the
2026-06-10 benchmark-alignment audit (ranked test #2).

## Design — two layers, never blended

**Layer 1 (MEASURED, this host):** bytes-per-event for the SAME pinned 10M-row Zeek conn
corpus (`../zeek-flagship-rerun/_work/corpus_fingerprint.json`, sha256-pinned) in five
storage realizations:

| Realization | Source | Status |
|---|---|---|
| OpenSearch 2.18.0 index (best_compression, forcemerged) | `../zeek-flagship-rerun/results/load_opensearch.json` | measured 2026-06-10 |
| ClickHouse native MergeTree, default LZ4 | `../zeek-flagship-rerun/results/load_clickhouse.json` | measured 2026-06-10 |
| Iceberg Parquet, pyiceberg zstd defaults (warm tier) | `../zeek-flagship-rerun/results/load_iceberg.json` | measured 2026-06-10 |
| ClickHouse MergeTree, blanket ZSTD(22) (tuned-hot arm; declared tuning — the legacy "extreme" arm also used per-column specialty codecs, this one deliberately does not) | `measure.py` | NEW |
| Single-file Parquet, zstd level 19, 1M-row groups (cold/compacted tier) | `measure.py` | NEW |

Raw reference: the pinned JSONL (3,742,877,526 B for 10M events = 374.3 B/event).

**Layer 2 (PRICED, desk-derived, labelled):** published list prices applied to the measured
ratios at a reference workload of **1 TB/day raw** across retention points **30 / 90 / 365 /
2,555 days** (2,555 = the 7-year 17a-4/FSI horizon, tying H-FSI-03's retention leg). The
price menu (as-of date recorded in `results/cost_curves.json`; re-verify before any
publication) maps realizations to the storage class they actually run on, because that
mapping is half the finding: a hot search index lives on block storage (EBS gp3-class), the
lakehouse tables live on object storage (S3-class) — the index pays both a bytes multiplier
AND a $/byte multiplier, and they compound.

Steady-state storage cost at retention D for raw daily volume W and measured ratio r:
`stored = W × D / r`, `monthly $ = stored × price_per_GB_month`. No egress, compute,
licensing, or ops cost is modelled — this is the storage floor, stated as such.

## What this can and cannot license

Can: "the same events cost N× more per month to keep queryable in realization A than B at
retention D, where the byte ratios are measured and the prices are AWS list" — with both
layers shown. Can move: H1-COST-08 (toward first-party on the storage mechanism),
H-COST-09 (the tier curve), H-FSI-03 (the 7-year point), Matrix cost-to-serve axis (its
first retention-scale entry). Cannot: full TCO (compute/license/ops out of scope), non-AWS
pricing, compression behavior of other corpora (ratios are corpus parameters — this corpus
is synthetic Zeek conn, and its ratios should be re-measured per engagement workload).

## Run

```bash
.venv/bin/python measure.py      # captures all 5 footprints (builds the 2 new arms live)
.venv/bin/python cost_model.py   # priced layer -> results/cost_curves.json + table
```

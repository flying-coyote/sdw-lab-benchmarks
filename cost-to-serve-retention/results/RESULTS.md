# RESULTS — the index pays twice: 4.2× the bytes at 3.5× the price

**Measured layer: Tier B · single host · same sha256-pinned 10M-row Zeek conn corpus as
`zeek-flagship-rerun` · 2026-06-10. Priced layer: AWS us-east-1 list, verified 2026-06-10
against the live AWS rate-card feeds. The two layers are reported separately and must be
cited separately.**

## Layer 1 — measured footprints (same 10M events in every realization)

| Realization | bytes/event | reduction vs raw |
|---|---|---|
| Raw JSONL | 374.3 | 1× |
| OpenSearch 2.18.0 index (best_compression, forcemerged) | 186.8 | 2.0× |
| ClickHouse MergeTree, default LZ4 | 68.5 | 5.5× |
| Iceberg Parquet, pyiceberg zstd defaults (warm) | 44.0 | 8.5× |
| ClickHouse MergeTree, blanket ZSTD(22) (tuned-hot) | 41.5 | 9.0× |
| Single-file Parquet, zstd-19, 1M-row groups (cold) | 38.6 | 9.7× |

## Layer 2 — priced at retention (1 TB/day raw, steady state, storage only)

Each realization is priced on the storage class it actually runs on — a hot search index
or hot OLAP table lives on block storage (gp3, $0.08/GB-mo), lakehouse tables live on
object storage (S3 Standard $0.023, Glacier IR $0.004) — because that mapping is half the
cost story.

| Realization · class | 30 d | 90 d | 365 d | 7 y (2,555 d) |
|---|---|---|---|---|
| OpenSearch index · gp3 | $1,200/mo | $3,600/mo | $14,600/mo | $102,200/mo |
| CH LZ4 · gp3 | $439/mo | $1,316/mo | $5,338/mo | $37,367/mo |
| CH ZSTD-22 · gp3 | $266/mo | $797/mo | $3,234/mo | $22,636/mo |
| Iceberg zstd · S3 | $81/mo | $244/mo | $988/mo | $6,914/mo |
| Cold Parquet · S3 | $71/mo | $214/mo | $866/mo | $6,064/mo |
| Cold Parquet · Glacier IR | $12/mo | $37/mo | $151/mo | $1,055/mo |

Compounded multipliers (constant across retention — both layers are linear in days):

- **Index-on-gp3 vs warm-Iceberg-on-S3: 14.8×** (4.2× bytes × 3.5× $/byte)
- Index-on-gp3 vs cold-Parquet-on-S3: 16.9×
- **Index-on-gp3 vs cold-Parquet-on-Glacier-IR: 96.7×** (storage only — Glacier IR charges
  $0.03/GB on retrieval, so this tier is for data you rarely touch, and any claim citing it
  must stay storage-only or model retrieval frequency)
- Hot-OLAP-LZ4-on-gp3 vs warm-Iceberg-on-S3: 5.4×

## The two findings worth keeping

1. **The multiplier is mostly the storage class, not the codec.** Tuned ZSTD-22 ClickHouse
   compresses *better* than Iceberg's zstd default (9.0× vs 8.5×) and still costs 3.3× more
   per month, because its bytes sit on block storage. Compression tuning moves the bill by
   tens of percent; moving bytes from gp3 to S3 moves it by 3.5×, and to Glacier IR by 20×.
   The architecture decision (where can old data live?) dominates the engineering decision
   (how hard do we squeeze it?).
2. **Retention is the lever that makes the difference existential.** At 30 days the
   index-vs-lakehouse gap is ~$1,100/month — annoying. At the 7-year 17a-4/DORA horizon it
   is ~$95K/month per TB/day of ingest — which is why retention-heavy regulated estates are
   where the lakehouse case writes itself (H-FSI-03's retention leg, now first-party).

## Scope, honestly

This is the **storage floor**, not TCO: no compute, no licensing, no ops labor, no egress,
no IOPS/throughput add-ons (gp3 baseline only). The byte ratios are parameters of THIS
corpus (synthetic Zeek conn; flat 16-column schema) — nested OCSF or long-message logs
compress differently, so re-measure per workload in an engagement. A real architecture
keeps a hot tier for recent data in any case; the honest comparison this table enables is
*tiered* (hot 7–30 d + warm/cold for the rest) vs *all-hot*, and that arithmetic is exactly
what `cost_curves.json` supports. The legacy desk-derived 130–227× (H1-COST-08) measured a
different thing (full platform economics incl. compute and license) — these numbers neither
confirm nor replace it; they put a measured storage floor of 15–97× under the storage share
of that claim.

## What this moves

H1-COST-08 (storage mechanism now first-party at retention scale) · H-COST-09 (the tier
curve, measured ratios + verified prices) · H-FSI-03 (the 7-year point) · **Matrix
cost-to-serve axis: its first retention-scale measured entry** (update
`matrix-bench-coverage-map.md`'s GAP row). Consumers: Matrix, book ch07/14, the migration
assessment's TCO model.

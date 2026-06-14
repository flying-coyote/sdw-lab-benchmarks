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

## Second corpus — byte-ratio sensitivity (2026-06-14)

The README above flags the byte ratios as corpus parameters to re-measure per workload. This
checks how far they move on a structurally different schema: a synthetic **EDR/Sysmon
process-creation** corpus (long command lines, process GUIDs, high-cardinality user/host) at
the same 10M-row scale, so the comparison isolates schema/content, not parquet overhead
(`second_corpus.py`, deterministic content; machine-readable in `results/second_corpus.json`).

| corpus | raw B/event | Parquet zstd-default ratio | Parquet zstd-19 ratio |
|---|--:|--:|--:|
| Zeek conn (flat 16-col, the Layer-1 corpus) | 374.3 | 8.5× | 9.69× |
| EDR/Sysmon proc-creation (`second_corpus.py`) | 600.1 | **7.94×** (0.93× Zeek) | **9.25×** (0.95× Zeek) |
| High-entropy (base64 payload + full SHA-256 + per-event GUID, `high_entropy_corpus.py`) | 416.5 | **2.57×** (0.30× Zeek) | **2.75×** (0.28× Zeek) |

Two things the second + third corpora settle. (1) For *moderate-entropy* schemas the
**compression ratio transfers within ~5–7%** — flat-Zeek 8.5× vs EDR 7.94×, so the 8.5× is not
an artifact that wildly inflates the ratio. (2) But the ratio is **strongly workload-dependent at
the tails**: a genuinely high-entropy stream (encoded-PowerShell / packet payloads, full hashes,
per-event GUIDs) compresses only **2.6×** — *0.30× the flat-Zeek ratio, ~3.3× worse*. So the
storage-cost ratio spans **~2.6× to 8.5×** across security-telemetry shapes, and the cost model
must **re-measure the byte ratio per workload** (NOT assume 8.5×) — high-entropy ingest can
triple the stored-byte cost at a given retention versus a flat Zeek-conn estimate. Also the **absolute
$/event is higher for EDR**: it carries more content (600 vs 374 raw B/event) and still stores
75.6 vs 44.0 compressed B/event at zstd-default, so at a given retention the EDR corpus costs
~1.7× the Zeek corpus per event even though its compression ratio is similar. So the priced
curves' *shape* (the storage-class compounding) transfers, but the per-event magnitude must be
re-based on the workload's own raw bytes/event — re-measure the ratio AND the raw B/event per
engagement, not just the ratio. Genuinely high-entropy streams (full hashes, base64 blobs, raw
packet payloads) would compress less still; this EDR corpus is a moderate case, not the floor.

## Run

```bash
.venv/bin/python measure.py         # captures all 5 footprints (builds the 2 new arms live)
.venv/bin/python cost_model.py      # priced layer -> results/cost_curves.json + table
.venv/bin/python second_corpus.py       # 2026-06-14 EDR/Sysmon byte-ratio sensitivity (10M rows)
.venv/bin/python high_entropy_corpus.py # 2026-06-14 high-entropy floor (base64/hashes/GUIDs, 10M rows)
```

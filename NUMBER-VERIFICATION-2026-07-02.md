---
repo: sdw-lab-benchmarks
date: 2026-07-02
source: story-spine audit follow-up — compression-ratio number verification (B3-adjacent)
evidence-tier: B (all cited measurements)
---

# Number verification — "8.5× smaller on disk" vs the "~8.2× ZSTD-22" canon (2026-07-02)

The audit asked whether the essay claim that the open Iceberg table holds the same data
**"8.5× smaller on disk than the raw logs"** conflicts with canon carrying **~8.2×
compression (ZSTD-22, ClickHouse-side, Zeek benchmark)**. Both numbers were traced to
source. The premise is inverted:

**Verdict: 8.5× is the correctly sourced number. The "~8.2× canon" figure is unsourced
drift — it corresponds to no measurement in this repo. The real ClickHouse-side ZSTD(22)
measurement is 9.03×, not 8.2×.** These are not two legitimate measurements to reconcile;
one is real and one is orphaned.

## Provenance of 8.5× — real, sourced

- Result file: `cost-to-serve-retention/results/measured_footprints.json`
  (`measured_2026_06_10`), on the sha256-pinned 10M-row synthetic Zeek `conn` corpus
  shared with `zeek-flagship-rerun`:
  - `raw_jsonl.bytes = 3,742,877,526`
  - `iceberg_zstd_default.bytes = 440,175,792` (Iceberg table, pyiceberg defaults —
    Parquet + ZSTD — on MinIO/S3; load recorded in
    `zeek-flagship-rerun/results/load_iceberg.json`)
  - 3,742,877,526 / 440,175,792 = **8.5013** → recorded as `ratio_vs_raw: 8.5`
- Echoed in `zeek-flagship-rerun/results/RESULTS.md` storage table ("Iceberg Parquet
  (pyiceberg zstd defaults) | 440 MB | **8.5×**") and propagated consistently through
  `cost-to-serve-retention/` (README, RESULTS.md, `second_corpus.py`,
  `high_entropy_corpus.py`), each flagging it as corpus-specific, not universal.
- What it measures: **Iceberg/Parquet table size vs raw JSONL** — an open-format,
  lakehouse-side measurement. The essay's sentence ("open Iceberg table … 8.5× smaller
  on disk than the raw logs") matches this measurement exactly.

## Provenance of "~8.2×" — unsourced

- Repo-wide grep for `8.2x` / `8.2×`: **exactly one occurrence**, and it is not a
  measurement — `charts/_r20_schema-trained-zstd-dictionary-compression.py:22`, a tier
  caption reading "… per-event ingest regime, NOT the lakehouse 8.2x Zeek number". It
  cites the figure defensively; no result JSON, RESULTS.md, README, or cost model
  produces 8.2× anywhere.
- The measurement "8.2×" gestures at — ClickHouse-side blanket ZSTD(22) on the same
  corpus — exists and is: `ch_zstd22.bytes = 414,722,162` →
  3,742,877,526 / 414,722,162 = **9.0250** → recorded as `ratio_vs_raw: 9.03`,
  reported as 9.0× in `cost-to-serve-retention/results/RESULTS.md`. No revision history
  ever held 8.2 (the file was added once in `f95c12d` and never modified).
- Conclusion: "8.2×" is stale institutional memory sitting between the two real values
  (8.5× Iceberg, 9.0× ClickHouse-ZSTD22) while matching neither. It should not be quoted;
  the `_r20` chart caption is the one place carrying it (follow-up, out of scope here —
  this audit changes nothing outside this report).

## Correct usage going forward

- Iceberg/open-format footprint vs raw: **8.5×** (`iceberg_zstd_default`, 8.5013).
- ClickHouse MergeTree blanket ZSTD(22) vs raw: **9.0×** (`ch_zstd22`, 9.0250).
- The two are different systems measured against the same raw baseline; do not average
  or reconcile them.

---

## Appendix — B3 chart audit item (Dremio bar), same audit

The audit also flagged `charts/_r29_engine_two_regime.py` as "currently includes a
'Dremio Iceberg 3.6×' bar". Verified 2026-07-02: **the flag is stale** and that Dremio result is withheld. The Dremio arm
was removed from the script and the PNG re-rendered Dremio-free in commit `c00084d`
(2026-06-16 DeWitt sweep). A fresh render from the current script is byte-identical to
the committed `charts/out/benchmark-8-engine.png`; visual inspection confirms the arms
are foil 1×, Trino 3.6×, StarRocks 8.3×, ClickHouse-Iceberg 10.1×, ClickHouse native
46.8×, with the point-lookup regime named in the subtitle and the Tier-B/single-host
footer intact. The bar the audit saw is **Trino** at 3.6× (0.795 s,
`zeek-flagship-rerun/results/starrocks_trino_arms.json`) — an independent, legitimate
measurement that coincidentally lands at the same rounded multiple as the withheld
Dremio result (0.787 s, now a `{withheld}` stub in `raw_dremio_iceberg.json`). No
change was made; removing the Trino bar would delete a real non-Dremio result.

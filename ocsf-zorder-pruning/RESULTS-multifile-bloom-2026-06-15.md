---
type: evidence
title: "Z-Order Pruning: Multi-File Cross-File Pruning and Bloom-Filter Alternative (2026-06-15)"
created: 2026-06-15
tags: [z-order, parquet, bloom-filter, iceberg, h-lakehouse-zorder-01, cross-file-pruning]
---

# Z-order owed legs: multi-file cross-file pruning + Bloom/page-index (2026-06-15)

The within-file leg (`run.py` / canonical RESULTS) + the row-group-sensitivity leg
(`RESULTS-rowgroup-sensitivity-2026-06-15.md`) left two registered legs owed before
H-LAKEHOUSE-ZORDER-01 could move past the narrow within-file claim: **(1) multi-file cross-file
pruning** (does sort-order pruning extend across data files, additive to within-file — the
Iceberg/DuckLake claim) and **(2) Bloom-filter / page-index** (the registered Alternative: does a
tuned stack's Bloom filters make z-order redundant). Both ran here. Tier B, single host, DuckDB
1.5.3 / pyarrow 24.0.0, the same seeded 2M-row OCSF Network Activity corpus + the same four
multi-predicate queries as the within-file leg. `multifile_bloom.py`; raw `results/multifile_bloom.json`.

## Leg 1 — multi-file cross-file pruning (8 files/layout, 50k row groups)

Each layout written as 8 Parquet files (the corpus sorted per layout, then split into contiguous
chunks — what a compaction-time sort produces). Counts: files skippable by file-level min/max
(the catalog signal), then within-file row-group skips on the files that are read.

| query | layout | files pruned | row-groups pruned | rows scanned |
|---|---|--:|--:|--:|
| Q1 src_ip /24 + time 1h | single_sort | **6/8** | 95.0% | **5.0%** |
| | zorder | 3/8 | 72.5% | 27.5% |
| | unordered | 0/8 | 0% | 100% |
| Q2 dst_port IN + src_ip /25 | single_sort | **7/8** | 97.5% | **2.5%** |
| | zorder | 2/8 | 65.0% | 35.0% |
| | unordered | 0/8 | 0% | 100% |
| Q3 dst_endpoint block + dst_port=22 | single_sort | 0/8 | 0% | 100% |
| | zorder | 0/8 | 15.0% | 85.0% |
| | unordered | 0/8 | 0% | 100% |
| Q4 time window only | single_sort | 0/8 | 0% | 100% |
| | zorder | **4/8** | 65.0% | 35.0% |
| | unordered | 0/8 | 0% | 100% |

**Cross-file pruning is real and additive** (the catalog skips whole files by file-level min/max,
then the engine skips row groups inside the files it reads), confirming the owed Iceberg/DuckLake
claim — at the *effect* level. **The depth-vs-breadth tradeoff holds at the file/catalog level, same
shape as within-file:** single-sort prunes its one sort dimension *deepest* (Q1/Q2 down to 2.5–5% of
rows) but prunes nothing on the dimensions it abandons (Q3 dst_endpoint, Q4 time → 100% scanned);
z-order prunes *across* its three dimensions — and is **the only layout that prunes the pure-time
query Q4 (65% row-groups) where single-sort prunes 0%** — but shallower per dimension. So z-order is
for estates with diverse multi-dimensional query patterns; if every query filters on one column,
single-sort on that column prunes deeper. Unordered prunes nothing cross-file (as expected).

## Leg 2 — Bloom-filter / page-index (the Alternative)

Each layout written single-file via DuckDB COPY with vs without Bloom filters on the equality columns
(`dst_port`, `src_ip_int`), writer otherwise constant; median of 7 warm trials.

| layout | query | no-Bloom | +Bloom |
|---|---|--:|--:|
| unordered | Q2 (dst_port IN + src_ip) | 8.8 ms (cv13) | 7.0 ms (cv6) |
| unordered | Q3 (dst_endpoint + dst_port=22) | 4.8 ms (cv32) | 4.9 ms (cv1) |
| single_sort | Q2 | 2.2 ms | 2.0 ms |
| single_sort | Q3 | 4.8 ms | 4.9 ms |
| zorder | Q2 | 4.4 ms | 3.9 ms |
| zorder | Q3 | 4.5 ms | 4.5 ms |

Bloom costs ~408 KB per file (+1.2% size) and moves the equality-ish Q2 by 1–2 ms (mostly within CV)
and Q3 not at all. **The Alternative is not supported:** Bloom serves *equality* predicates while
sort/z-order serve *range / multi-dimensional* predicates — different predicate classes, so Bloom is
**complementary, not a substitute**, and does not make z-order redundant. The dominant latency lever
is the **layout** itself (single-sort Q1/Q2 ~2 ms vs unordered ~9 ms vs z-order ~4 ms), not Bloom —
consistent with the narrow claim that z-order is a *pruning/coverage* lever, not (and Bloom is barely)
a latency lever at this scale.

## What it does to the hypothesis

Closes the two registered owed legs at the *effect* level: cross-file pruning is additive and keeps
the depth-vs-breadth shape; Bloom does not redundant-ize z-order. The narrow within-file claim is now
robust across row-group size (prior leg) **and** extends additively across files, with the Alternative
addressed.

## Caveats (Tier B)

- **Cross-file is simulated, not catalog-measured.** The "8 files" are contiguous-chunk Parquet files
  with file-level min/max replayed by the same conservative footer method as the within-file leg — it
  demonstrates the *effect* a real Iceberg/DuckLake catalog would exploit, but it is **not** a
  catalog-mediated scan over a real table with manifest-level partition/file pruning. That real
  catalog-scale leg remains the final owed test before any High-confidence claim.
- Single host, one seeded corpus, N=8 files, 50k row groups; pruning counts are conservative
  footer-replay lower bounds; Bloom latency deltas are mostly within CV at this sub-10 ms scale.
- Bloom on `dst_port` is low-selectivity (port 22 matches many rows), which limits the equality gain;
  a high-cardinality equality column would show more — noted, not measured here.

# Z-order pruning vs single-sort vs unordered (OCSF Network Activity)

**Tier B.** 2,000,000-row seeded OCSF Network Activity corpus written three ways to Parquet
(50,000-row row groups → ~40 row groups per file), then queried with four
multi-predicate selective queries. Z-order key: (src_ip_int, dst_port, time_bucket_1h), bit-interleaved to a 48-bit
Morton code. Engine: DuckDB; Parquet ZSTD-3; single host. Environments: duckdb `1.5.3`, pyarrow `23.0.1`.

The hypothesis: multi-dimensional clustering places nearby events in the same row groups,
so a conjunction like `src_ip IN /24 AND time IN 1h` prunes most row groups by min/max
statistics — a gain SINGLE_SORT can't replicate because its row-group ranges for the
non-sort column span the whole domain. Q4 (single dimension) tests whether Z-order costs
anything on queries that don't exercise the extra dimensions.

**Answers identical across all three layouts: True**

## Write cost

| layout | size | write ms | sort key |
|---|---|---|---|
| unordered | 49.1 MB | 2656.6 ms | src_ip_int, dst_port, time_bucket_1h |
| single_sort | 40.7 MB | 2058.7 ms | sorted by src_ip_int |
| zorder | 46.8 MB | 11564.2 ms | src_ip_int, dst_port, time_bucket_1h |

Row-group size 50,000 (stated here; pruning effectiveness scales with group size — larger
groups prune wider but read more rows per retained group).

## Pruning (row-group min/max statistics)

| query | layout | total rgs | prunable rgs | % pruned | rows skipped |
|---|---|---|---|---|---|
| Q1_src_ip_and_time | unordered | 40 | 0 | 0.0% | 0 |
| Q1_src_ip_and_time | single_sort | 40 | 38 | 95.0% | 1,900,000 |
| Q1_src_ip_and_time | zorder | 40 | 29 | 72.5% | 1,450,000 |
| Q2_dst_port_and_src_ip | unordered | 40 | 0 | 0.0% | 0 |
| Q2_dst_port_and_src_ip | single_sort | 40 | 39 | 97.5% | 1,950,000 |
| Q2_dst_port_and_src_ip | zorder | 40 | 26 | 65.0% | 1,300,000 |
| Q3_dst_endpoint_and_port | unordered | 40 | 0 | 0.0% | 0 |
| Q3_dst_endpoint_and_port | single_sort | 40 | 0 | 0.0% | 0 |
| Q3_dst_endpoint_and_port | zorder | 40 | 6 | 15.0% | 300,000 |
| Q4_time_window_only | unordered | 40 | 0 | 0.0% | 0 |
| Q4_time_window_only | single_sort | 40 | 0 | 0.0% | 0 |
| Q4_time_window_only | zorder | 40 | 26 | 65.0% | 1,300,000 |

Pruning counts are a conservative lower bound computed from the per-column min/max statistics
in the Parquet footer — the same signals DuckDB's Parquet reader uses for row-group skipping.
A row group is "prunable" when the predicate definitively excludes it (e.g. `rg.max < lo`
for a range predicate). Actual engine pruning may be higher with page-index pushdown.

## Query latency (median + CV)

| query | layout | median ms | cv % | real delta vs unordered? |
|---|---|---|---|---|
| Q1_src_ip_and_time | unordered | 12.5 | 5.2 | baseline |
| Q1_src_ip_and_time | single_sort | 3.7 | 11.5 | ✓ real (70% gap > 11.5% CV) |
| Q1_src_ip_and_time | zorder | 4.8 | 5.3 | ✓ real (62% gap > 5.3% CV) |
| Q2_dst_port_and_src_ip | unordered | 9.7 | 5.8 | baseline |
| Q2_dst_port_and_src_ip | single_sort | 2.7 | 4.3 | ✓ real (72% gap > 5.8% CV) |
| Q2_dst_port_and_src_ip | zorder | 5.8 | 9.7 | ✓ real (40% gap > 9.7% CV) |
| Q3_dst_endpoint_and_port | unordered | 8.5 | 30.8 | baseline (noisy: CV 30.8%) |
| Q3_dst_endpoint_and_port | single_sort | 9.3 | 12.8 | ✗ within noise (9% gap < 30.8% CV) |
| Q3_dst_endpoint_and_port | zorder | 6.0 | 9.5 | ✗ NOT claimable (29% gap < 30.8% CV) |
| Q4_time_window_only | unordered | 11.1 | 4.4 | baseline |
| Q4_time_window_only | single_sort | 10.2 | 7.5 | ~ marginal (8% gap ≈ 7.5% CV — treat as no) |
| Q4_time_window_only | zorder | 5.9 | 8.6 | ✓ real (47% gap > 8.6% CV) |

A delta below the CV is not a real difference. Per [`BENCHMARKING-METHODOLOGY.md`](../BENCHMARKING-METHODOLOGY.md):
report CV alongside every median; claim a win only when the gap exceeds the CV. The
"real delta?" column was filled in 2026-06-10 (full re-derivation against `results.json`):
gap = (baseline median − layout median) / baseline median, claimed real only when it
exceeds the larger of the two CVs. Two consequences worth stating: Q3's z-order latency
win is NOT claimable (the unordered baseline's CV is 30.8%, wider than the 29% gap) even
though its 15% pruning is real — pruning and latency are separate claims here; and on
Q1/Q2 single-sort beats z-order outright (3.7 vs 4.8 ms, 2.7 vs 5.8 ms — gaps exceed both
CVs), so z-order's case rests on Q3/Q4 coverage, not on winning the queries a single sort
already serves.

## Interpretation

Z-order's pruning win appears most clearly on multi-predicate queries that touch two or
more of the clustering dimensions (Q1, Q2, Q3). Q4 (time-window only) measures whether
Z-order's interleaving hurts the single-dimension case: if Z-order distributes time
across the sort order, it can lose to SINGLE_SORT on a pure-time range predicate, which
is the expected trade-off to state honestly.

The write cost (Z-value computation + sort) is the price. At this scale (Parquet, single
file, in-memory sort) it is proportionate; at Iceberg/DuckLake scale the cost is amortised
across many data files and the Z-sort can be done at compaction time.

**Iceberg / DuckLake relevance:** these formats can carry Z-ordered data files and track
the sort order in metadata, so a catalog-mediated scan can prune *across files* as well as
within them — additive to the within-file row-group pruning this bench measures.

## Caveats

- Tier B, single machine (Beelink WSL2, High-Performance power plan). Latency magnitudes
  are this host's; the pruning ratios and the relative ordering of layouts are the
  transferable findings.
- Row-group size governs pruning granularity. This bench uses 50,000-row groups; at
  122,880-row DuckDB defaults the effect is proportionally weaker (fewer, wider groups).
  State the row-group size in any claim.
- The Z-order sort here is computed on the full table in Python then written to a single
  Parquet file. Production Z-ordering (Iceberg V3 write-ordering, DuckLake data file
  compaction) applies it across multiple files with catalog tracking.
- DuckDB's Parquet reader uses min/max statistics and the optional page index for pruning.
  Bloom filters (not written here) add a separate layer for equality predicates.

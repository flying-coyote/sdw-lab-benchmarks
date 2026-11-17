# Z-order pruning — does multi-dimensional clustering of OCSF data improve selective queries?

## What it measures

A SOC analyst running `src_ip IN /24 AND time IN 1h` over a 20M-event lakehouse table
should see most row groups pruned by statistics: those events sit in a well-defined
region of the src_ip × time plane, so row groups that don't overlap that region can
be skipped entirely. SINGLE_SORT by src_ip gives tight src_ip ranges per row group but
scattered time ranges, so the time predicate can't help. UNORDERED gives neither.
Z-order (Morton code over src_ip_int × dst_port × time_bucket) places multi-dimensionally
nearby events together, so the conjunction prunes more row groups than either alternative.

This bench measures how much.

## Design

Same seeded 2M-row OCSF Network Activity corpus written three ways to Parquet
(50,000-row row groups, ZSTD-3):

| layout | sort key |
|---|---|
| UNORDERED | generator order — no sort |
| SINGLE_SORT | sorted by `src_ip_int` ascending |
| ZORDER | sorted by Z-value: bit-interleaved `(src_ip_int, dst_port, time_bucket_1h)` scaled to [0, 65535] |

Z-value is computed in pure Python (stdlib only, no external library) by scaling each
dimension independently to [0, 2^16) so a high-cardinality column (src_ip_int, ~32k
distinct /24s) doesn't dominate a low-cardinality one (dst_port, 10 distinct), then
applying a 3D Morton-code bit-interleave.  The Z-value column is not written to the
output file — only the row order carries the clustering.

## Metrics

For each layout × query:

- **prunable row groups** — row groups the engine can definitively skip using min/max
  statistics in the Parquet footer (conservative lower bound; actual DuckDB pruning
  also uses the page index)
- **rows in prunable groups** — total rows that would be skipped
- **% pruned** — prunable_rgs / total_rgs
- **query latency** — median + coefficient of variation over 7 warm trials
  (`lib.common.time_trials`, warmup=2)
- **write latency** — wall-clock time to generate + sort + write each layout
- **on-disk size** — byte footprint of each Parquet file (all same ZSTD-3, so size
  difference reflects sort-induced compression, not codec choice)

## Queries

| id | predicate | Z-order dimensions touched |
|---|---|---|
| Q1_src_ip_and_time | `src_ip_int IN /24 AND time IN 1h` | src_ip_int, time |
| Q2_dst_port_and_src_ip | `dst_port IN (22,443) AND src_ip_int IN /25` | src_ip_int, dst_port |
| Q3_dst_endpoint_and_port | `dst_endpoint_int IN block-of-32 AND dst_port=22` | dst_endpoint_int, dst_port |
| Q4_time_window_only | `time IN 1h` (single dimension) | time only |

Q4 is the reference case: a single-dimension query where SINGLE_SORT on src_ip offers
nothing and Z-order's value depends on how well it preserved time locality.  If Z-order
distributes time across the sort order, Q4 may lose to UNORDERED — that is the expected
trade-off to state honestly rather than hide.

## Expected finding

Z-order should prune more row groups than UNORDERED or SINGLE_SORT on Q1, Q2, Q3 because
the conjunction spans multiple clustering dimensions.  SINGLE_SORT dominates Z-order on
predicates that hit only `src_ip_int` (where its tight ranges match or beat Z-order's
slightly coarser interleaved ranges).  Q4 (time only) tests the cost: Z-order may trail
SINGLE_SORT_time or UNORDERED depending on how time distributes after the interleave.

Whether the pruning gain translates to a measurable latency gap depends on whether
DuckDB's Parquet reader actually skips row groups (not just whether the statistics allow
it) and whether the skipped I/O dominates over other query costs at this scale.  A delta
below the CV is not a real difference — state that.

## Result (Tier B, 2,000,000 rows, 50,000-row groups, DuckDB 1.5.3, pyarrow 23.0.1)

The expectation above was half right. On the two queries whose predicates include the single sort's key,
single-sort pruned more than z-order (Q1 95.0% against 72.5% of row groups, Q2 97.5% against 65.0%), and
on the two that do not, z-order was the only layout that pruned anything (Q3 15.0%, Q4 65.0%, against 0%
for single-sort and unordered); z-order did not trail on the time-only Q4, it led
([results/RESULTS.md](results/RESULTS.md)). Latency followed the pruning where the gap cleared the CV:
single-sort beat z-order on Q1 and Q2 (3.7 against 4.8 ms, 2.7 against 5.8 ms), z-order's Q4 gain over
unordered was claimable (5.9 against 11.1 ms) and its Q3 gain was not (the unordered baseline's CV was
30.8%). Z-order cost 5.6× the single sort's write time (11,564 against 2,059 ms). So z-order buys
pruning coverage across dimensions a single sort abandons and pays for it in depth on the sort's own
column and in write time. Pruning counts are measured from footer statistics and are deterministic, and the
row-group sensitivity leg reproduced them exactly; latencies are medians of 7 warm trials.

## What would have made it fail

The pruning comparison could have come out any way, and its expected direction on Q1 and Q2 did fail. The
unordered layout is the baseline that prunes nothing, and answers are checked identical across the three
layouts. The "real delta" column applies the methodology's CV rule to every latency claim.

## Pre-registration

None. No pre-registration file exists in this folder, and the expected-finding section is not dated
separately from the results (both first appear in the same commit, 9eee851 on 2026-06-08), so it cannot be
shown to predate the run and is not a frozen design.

## Reproduce

```bash
# activate the shared venv
source ~/sdw-lab-benchmarks/.venv/bin/activate

# default 2M-row corpus (~5–10 min including write + timing trials)
python ocsf-zorder-pruning/run.py

# larger corpus for stronger pruning signal
python ocsf-zorder-pruning/run.py --rows 5000000

# re-render RESULTS.md after a run without re-running
python ocsf-zorder-pruning/run.py --render-only
```

Box must be IDLE (no concurrent DuckDB workloads) before running — see
[`BENCHMARKING-METHODOLOGY.md §5`](../BENCHMARKING-METHODOLOGY.md) (isolation).
Use the High-Performance Windows power plan.  See `READINESS.md` for the exact
pre-run checklist and expected runtime.

## Evidence tier and limits

- Row-group size governs pruning granularity (stated in every result as `row_group_size`).
  The 50,000-row groups here are tighter than DuckDB's default 122,880; pruning is more
  visible but absolute retained-I/O is smaller.  Restate when comparing across benchmarks.
- Z-value is computed on a single in-memory sort.  Production Z-ordering at Iceberg or
  DuckLake scale applies across files at compaction time — the pruning mechanism is the same
  (row-group min/max statistics + optional metadata-level file pruning), the write cost
  profile differs.
- Tier B, single machine (Beelink WSL2, High-Performance power plan).  Latency magnitudes
  are this host's; pruning ratios and the relative ordering of layouts transfer.
- Answer equality is verified across all three layouts before results are written.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json` (2026-06-08), the within-file run,
  rewritten by `run.py`.
- [RESULTS-rowgroup-sensitivity-2026-06-15.md](RESULTS-rowgroup-sensitivity-2026-06-15.md), pruning at
  122,880-row groups (z-order still the only layout pruning Q3 and Q4, at 11.8% and 47.1%).
- [RESULTS-multifile-bloom-2026-06-15.md](RESULTS-multifile-bloom-2026-06-15.md) and
  `results/multifile_bloom.json`, the eight-file and Bloom-filter legs (simulated cross-file pruning,
  not a catalog scan).
- [READINESS.md](READINESS.md), the pre-run checklist.

## Versions and pins

No requirements file; the commands above use a shared venv. `results/results.json` records DuckDB 1.5.3
and pyarrow 23.0.1; the two 2026-06-15 legs record pyarrow 24.0.0. The root `requirements.txt` pins DuckDB
1.5.3 and pyarrow 23.0.1.

## Corrections

- *(corrected 2026-11-17: the "Interpretation" paragraph in `results/RESULTS.md` says z-order's pruning
  win is clearest on Q1, Q2 and Q3 and that z-order can lose on the time-only Q4; the table in the same
  file shows the opposite on Q1, Q2 and Q4 (single-sort prunes more on Q1 and Q2, z-order alone prunes
  Q4). That paragraph is template prose in `run.py`, which rewrites the file, so the Result section above
  is the reading to use. The write-cost table in the same file lists the z-order key as the sort key of
  the unordered layout, a rendering slip; the unordered file is in generator order.)*
- *(2026-11-17: Result, failure condition, pre-registration, results and versions sections added; no
  number changed.)*

## Hypothesis mapping

Advances **H-LAKEHOUSE-ZORDER-01** (Z-order / multi-dimensional clustering improves
selective OCSF query pruning): provides a quantified Tier-B measurement of the pruning
gain and its dependency on row-group size and query dimensionality.

Connects to:
- `ocsf-pruning-correctness` — soundness of row-group / page-index / bloom pruning
- `ocsf-read-scan` — format-level read performance (Z-ordering is additive to format choice)
- `ocsf-parquet-determinism` — logical fingerprint discipline (used here for artifact pinning)
- Iceberg V3 write-ordering / DuckLake data-file compaction: the catalog layer that makes
  Z-ordering across files first-class

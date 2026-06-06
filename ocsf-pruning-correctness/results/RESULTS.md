# Does pruning ever drop the needle? (lower-level bake-off #3)

**Tier B · single machine · identical-data A/B.** A Parquet reader prunes row groups and pages it believes
can't match — by min/max statistics, the page index, and optionally bloom filters — and the optimization is
only safe if it *never* skips a block that actually contains a matching row. When it isn't, a needle-in-a-
haystack detection query (one IOC value among 1,000,000) silently under-counts. This is the exact layer
the chDB Bloom-pushdown undercount lived in. Engines: pyarrow `23.0.1`, duckdb `1.5.3`, polars `1.41.2`, datafusion `53.0.0`, chdb `4.1.8`.

## Arm 1 — min/max + page-index pruning (sorted vs shuffled A/B)

The same key multiset (1,000,000 keys, each once) is written two ways: **sorted** (each row group a tight
slice, so an equality predicate prunes to one row group) and **shuffled** (every row group spans nearly the
whole domain, so nothing prunes). Only the row order differs, so any sorted-vs-shuffled disagreement isolates
a pruning bug. Needles cluster on row-group boundaries (where off-by-one pruning bites). Present needle truth
= 1, absent = 0.

A/B is real: 100 row groups; sorted rg0 covers `[0, 9999]` (a tight slice an
equality predicate can prune around), shuffled rg0 covers `[88, 999993]` (≈ the whole domain —
unprunable).

| engine | sorted file (pruning engaged) |
|---|---|
| duckdb | ✅ all correct |
| pyarrow | ✅ all correct |
| polars | ✅ all correct |
| datafusion | ✅ all correct |
| chdb | ✅ all correct |

| engine | shuffled file (no pruning possible — reference) |
|---|---|
| duckdb | ✅ all correct |
| pyarrow | ✅ all correct |
| polars | ✅ all correct |
| datafusion | ✅ all correct |
| chdb | ✅ all correct |

## Arm 2 — bloom-filter pushdown (the chDB-specific structure)

chDB wrote a bloom-filtered file; every engine counts present + absent needles over it.

| engine | result |
|---|---|
| duckdb | ✅ all correct |
| pyarrow | ✅ all correct |
| polars | ✅ all correct |
| datafusion | ✅ all correct |
| chdb | ✅ all correct |

A bloom filter permits false positives but never false negatives, so a *present* needle returning 0 over a
bloom-filtered file is a hard correctness failure in the bloom decode/probe path — precisely the original bug.

## Reading

Pruning is the optimization that makes a lakehouse competitive on selective security queries, and it is exactly
where a fast wrong answer hides: the engine that skips the row group holding the one matching event returns
zero in milliseconds and looks healthy. The A/B isolates it cleanly — identical data, identical predicate,
only the physical layout differs, so the sorted file and the shuffled file must agree, and they must both
equal the ground truth. That is the same verify-the-answer discipline as the cross-engine, page-checksum, and
encoding benches, aimed at the planner's skip logic rather than the decoder's bytes. The per-engine result is
version-bound and is the transferable finding; re-run it on any engine upgrade, because pushdown paths
(bloom, page-index, late-materialization) are where new optimizations land and where a soundness regression
would first show up as a quiet under-count on a detection query.

# Does pruning ever drop the needle?

Lower-level bake-off #3 — the exact layer the chDB Bloom-pushdown undercount lived in. A Parquet reader prunes
row groups and pages it believes can't match a predicate, using min/max statistics, the page index, and
optionally bloom filters. That optimization is what makes a lakehouse competitive on selective security
queries, and it is only safe if it never skips a block that actually contains a matching row. When it isn't
sound, a needle-in-a-haystack detection query (one IOC value among a million) silently under-counts: the
engine returns 0 where the truth is 1, fast and confident and wrong.

## Result (Tier B)

Two arms, five engines (DuckDB, pyarrow, Polars, DataFusion, chDB), exact ground truth (each key appears once,
so a present needle counts 1 and an absent one 0):

- **Arm 1 — min/max + page-index pruning, sorted-vs-shuffled A/B.** The same million-key multiset is written
  **sorted** (each row group a tight slice, so an equality predicate prunes to one row group) and **shuffled**
  (every row group spans nearly the whole domain, so nothing prunes). Only the row order differs, so any
  sorted-vs-shuffled disagreement isolates a pruning bug. Needles cluster on row-group boundaries, where
  off-by-one pruning bites. **Every engine is sound** — identical correct counts on both files.
- **Arm 2 — bloom-filter pushdown.** chDB writes a Parquet file *with* bloom filters (the structure the
  original bug decoded); every engine counts present and absent needles over it. **Every engine is sound** — a
  bloom filter can false-positive but never false-negative, and no present needle was dropped.

The honest headline is a clean negative: on these pinned versions the chDB-bug class does not reproduce, and
row-group / page-index / bloom pruning is sound across all five engines. That is worth measuring rather than
assuming — pushdown paths are where new optimizations land and where a soundness regression would first show
up as a quiet under-count, so this bench is most useful as a standing regression guard to re-run on upgrades.
Full tables in [results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
pip install -r ocsf-pruning-correctness/requirements.txt
python ocsf-pruning-correctness/run.py
```

1,000,000 rows, 10,000-row groups (100 row groups), seeded shuffle. The A/B is self-verifying: the writeup
records the sorted vs shuffled row-group ranges so you can confirm pruning genuinely engaged on one file and
not the other. Tier B, single machine.

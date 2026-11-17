# Does pruning ever drop the needle?

## What it measures

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
row-group / page-index / bloom pruning is sound across all five engines. *(corrected 2026-11-17: the
first clause overstates what the bloom arm can show, since chDB 4.1.8 passed it while its known
string-equality Bloom defect stays unbuilt here; read it as min/max and page-index pruning sound across the
five engines and chDB's int64 bloom filters read soundly, see Corrections.)* That is worth measuring rather than
assuming — pushdown paths are where new optimizations land and where a soundness regression would first show
up as a quiet under-count, so this bench is most useful as a standing regression guard to re-run on upgrades.
Full tables in [results/RESULTS.md](results/RESULTS.md).

The counts are measured against an exact truth (each key appears once), so a dropped needle would have
shown as a 0 where the answer is 1; what the bench cannot show is anything about the conditions it did not
build, which matters for the bloom arm (see Corrections).

## What would have made it fail

Arm 1 fails if any engine returns a different count on the sorted file than on the shuffled one, or a
count other than the truth on either; the row-group ranges recorded in the results show pruning engaged
on the sorted file and could not engage on the shuffled one, so the shuffled file is a working negative
control. Arm 2 fails if a present needle returns 0 over the bloom-filtered file. It has no positive
control: the known bloom-pushdown undercount in chDB 4.1.8 was observed on a DuckDB-written,
high-cardinality string column with Bloom filters across about 800 row groups or more (the exact
trigger is not established), and this arm writes an int64 key with
chDB's own writer at 100 row groups, so a pass here is consistent with that defect being present, and chDB
4.1.8 did pass.

## Pre-registration

None. No pre-registration file exists in this folder.

## Reproduce

```bash
pip install -r ocsf-pruning-correctness/requirements.txt
python ocsf-pruning-correctness/run.py
```

1,000,000 rows, 10,000-row groups (100 row groups), seeded shuffle. The A/B is self-verifying: the writeup
records the sorted vs shuffled row-group ranges so you can confirm pruning genuinely engaged on one file and
not the other. Tier B, single machine. `run.py` rewrites `results/RESULTS.md`, so dated corrections live
in this README.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json`, the 2026-06-06 run, the only one.

## Versions and pins

`requirements.txt` pins pyarrow 23.0.1, DuckDB 1.5.3, Polars 1.41.2, DataFusion 53.0.0 and chDB 4.1.8,
which match the `environment` block of `results/results.json`.

## Evidence tier and limits

Tier B, single machine, one integer key column, 16 needles. No timings are reported.

## Corrections

- *(corrected 2026-11-17: "on these pinned versions the chDB-bug class does not reproduce" overstates what
  the bloom arm can show. The arm passed chDB 4.1.8, the version whose Bloom-filter pushdown undercounts a
  DuckDB-written high-cardinality string column with many row groups
  (`../clickhouse-vs-duckdb/results/CORRECTNESS-DIVERGENCE.md`), because it builds none of those
  conditions. Read the headline as "min/max and page-index pruning are sound across the five engines on
  this file, and chDB's own bloom filters on an int64 key are read soundly"; it says nothing about the
  string-equality Bloom path where the known defect lives.)*

## Hypothesis mapping

Advances **H-ENGINE-ANSWER-EQUIVALENCE-01**: pruning soundness is the pushdown layer of the
answer-equivalence question — an unsound skip is precisely an engine returning a different
answer for the same bytes. The clean negative here is a standing regression guard. *(ID
recorded 2026-06-10 per the benchmark-alignment audit.)*

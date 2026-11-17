# DuckLake inlining vs Iceberg — the small-files problem at the source

## What it measures

Isolates one claim made for DuckLake: it inlines small streaming batches into the catalog instead of
writing a data file per commit, so it "never creates tiny files in the first place" — versus Iceberg's
write-a-file-then-compact-later model. Same seeded stream of 100 small commits to three arms; the metric
is data files left behind.

## Result (Tier B)

Inlining off, both DuckLake and Iceberg write **one data file per commit** (100 each; Iceberg also
accumulates a manifest + metadata.json each time → 301 metadata files). Inlining on, DuckLake writes
**0 data files** for the same stream — rows live in the catalog until a flush threshold — and the data is
queryable after the last commit. That's the difference between "create tiny files, then compact" (the
maintenance job measured in `ocsf-iceberg-metadata`) and not creating them. Full numbers in
[results/RESULTS.md](results/RESULTS.md).

This is a demonstration of a documented feature rather than a measured rate. The file counts are
counted from disk, and the 0 follows from the configuration: the inlining limit is set to 10,000 rows and
every commit carries 200, so each commit is below the limit and inlines, which is what the
`DATA_INLINING_ROW_LIMIT` setting is for. What the run shows is that the ducklake extension installed
under the pinned DuckDB 1.5.3 (its own version is not recorded) does what its setting says, and
that Iceberg through pyiceberg writes one data file per append.

## What would have made it fail

The inline arm would have failed if DuckLake had written Parquet files despite commits under the limit,
and the no-inline arm is the control that shows the same stream does write 100 files when inlining is off.
Nothing in the bench measures the other side of the trade: DuckLake's `metadata_files` is set to 0 in the
code rather than counted, so the growth of the catalog database that holds the inlined rows is not
measured, and no flush to Parquet happens within the run.

## Pre-registration

None. No pre-registration file exists in this folder.

## Reproduce

```bash
pip install -r ocsf-write-inlining/requirements.txt
python ocsf-write-inlining/run.py
```

Tier B, single machine; file counts are deterministic, the inline threshold is a configured parameter.
It isolates the file-avoidance claim; it doesn't settle warehouse-scale trade-offs (inlined rows trade
file count for catalog growth). Complements the BENCH-D write-contract and iceberg-metadata benchmarks.
`run.py` rewrites `results/RESULTS.md`, so dated corrections live in this README; it installs the ducklake
extension at run time. Seconds to run.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json`, the only run.

## Versions and pins

`requirements.txt` pins DuckDB 1.5.3, pyiceberg 0.11.1 and pyarrow 24.0.0. `results/results.json` records
no versions, and the ducklake extension version is not recorded.

## Evidence tier and limits

Tier B, single machine, local disk, 100 commits of 200 rows. No timings are measured, although the
script's docstring mentions latencies. A related run on MinIO object storage, quoted in the
write-pattern essay with ingest and planning times, is a different run and is not in this folder.

## Corrections

- *(corrected 2026-11-17: "the data is immediately queryable throughout" is replaced by "queryable after
  the last commit", since `run.py` counts rows once, after the hundredth commit. The DuckLake metadata-file
  count of 0 in the results table is a value set in `run.py`, not a count; the Iceberg figure of 301 is
  counted. The 0 data files with inlining on follows from the configured limit, so the result is labelled a
  demonstration.)*

## Hypothesis mapping

Advances **H-DUCKLAKE-02**: the inlining file-count result is one side of the
DuckLake-vs-Iceberg write-contract trade-off that hypothesis tracks. *(ID recorded
2026-06-10 per the benchmark-alignment audit.)*

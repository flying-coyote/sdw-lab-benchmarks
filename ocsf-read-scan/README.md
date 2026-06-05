# BENCH-E — DuckLake vs Iceberg large-scan reads

Read-side sibling to BENCH-D. Same 10M-row OCSF corpus materialized in both formats, read by the
same engine (DuckDB), so the variable is the format's read path. Four scan shapes: full count,
filtered scan, top-N aggregation, byte rollup.

## Result (Tier B)

The two formats are **largely interchangeable on read** at this scale — identical answers, and
latencies within ~1.5× either way depending on query shape (Iceberg faster on metadata-only count,
DuckLake faster on the byte rollup, parity on filter and top-N). No universal winner; which you
reach for depends on the write pattern (BENCH-D) plus these read latencies — the H-DUCKLAKE-02
trade-off, measured on both sides now. Full numbers in [results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
pip install -r ocsf-read-scan/requirements.txt
python ocsf-read-scan/run.py
```

Iceberg read via DuckDB's iceberg extension (a written version-hint that pyiceberg doesn't emit is
added automatically); DuckLake via the ducklake extension. Latencies are machine-specific medians;
the corpus is seeded and identical across both formats. Tier B, single machine. Advances H-DUCKLAKE-02.

## Large-scan arm (>1B rows) — validated

`large_scan.py` pushes the same comparison to 1B rows, the scale H-DUCKLAKE-02 actually poses — where
DuckLake's SQL catalog might turn from a small-commit advantage into a large-scan bottleneck. Ingestion
is batched so peak memory is one batch rather than a tens-of-GB Arrow table, and a high-cardinality
`subnet_rollup` is added to stress the aggregator (it spills under DuckDB's `memory_limit`). Each scale
(100M, 1B) was run twice with frozen code to validate: both runs return identical answers and the
Iceberg/DuckLake relative shape reproduces (largest run-to-run drift in the ratio on a non-trivial query
is 0.22; absolute latencies drift more, mostly on the ~80s out-of-core top-N). The catalog-bottleneck
worry does not appear at 1B — DuckLake reads at or faster than Iceberg on every non-trivial query, while
using *more* storage (21.6 GB / 40 files vs Iceberg's 13.3 GB / 100 files at 1B; looser default
compression and row-group sizing). Cross-run table in [results/VALIDATION.md](results/VALIDATION.md).

```bash
python ocsf-read-scan/large_scan.py --rows 1000000000   # long-running; background it
python ocsf-read-scan/validate_runs.py                  # renders the cross-run comparison
```

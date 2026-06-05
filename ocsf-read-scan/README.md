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

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

## Parity arm — codec vs format, controlled (the methodology redo)

The arms above compare each engine at its **default** write config, which `config_probe.py` showed is
confounded: pyiceberg defaults to ZSTD + 1M-row groups, DuckDB/DuckLake to Snappy + 122,880-row groups,
so codec, row-group, and format all differed at once. `parity_scan.py` holds the row-group fixed at
122,880 and runs a 2×2 of {Iceberg, DuckLake} × {Snappy, ZSTD}, footer-verified, with CV per
[`BENCHMARKING-METHODOLOGY.md`](../BENCHMARKING-METHODOLOGY.md). Two findings (100M, low-CV sustained
queries topn_src / subnet_rollup at CV ~2–4%):

- **The storage gap was the codec, not the format.** At a matched codec, DuckLake's files are *smaller*
  than Iceberg's (zstd 1.14 vs 1.93 GB; snappy 2.16 vs 2.95 GB), so the original "Iceberg is smaller"
  was entirely Iceberg defaulting to ZSTD while DuckLake defaulted to Snappy.
- **The read advantage is real but smaller than it looked.** At matched codec + row-group, DuckLake
  still reads ~1.1–1.18× faster than Iceberg on the heavy aggregations — a genuine format/read-path
  effect — with Snappy adding a separate ~5–13% decompression edge. The default-config gap was those
  two stacking. Full table + decomposition in [results/PARITY.md](results/PARITY.md).

So the headline for the **format** question is the parity arm; the default-config large-scan numbers are
retained as out-of-the-box behavior, explicitly labelled confounded.

```bash
python ocsf-read-scan/config_probe.py                  # what codec/row-group each default path emits
python ocsf-read-scan/parity_scan.py --rows 100000000  # the controlled 2x2
```

## Same-files arm — byte-identical data, two catalogs (definitive)

`compression_probe.py` showed the two writers can't be config-matched: at the same codec, level, and
dictionary setting, DuckDB writes 114 MB where PyArrow/pyiceberg writes 193 MB on identical 10M-row data,
because PyArrow dictionary-encodes high-cardinality columns (id/time/bytes_out) while DuckDB uses PLAIN +
ZSTD — and pyiceberg exposes no per-column encoding control. The only way to remove compression as a
variable is to remove the writer: `same_files_scan.py` writes the Parquet once (DuckDB ZSTD-3), registers
the **same bytes** into both catalogs (Iceberg `add_files`, DuckLake `ducklake_add_data_files`), and reads
both with DuckDB. Verified byte-identical (1.14 GB each) and answer-identical.

Result (100M): with compression fully controlled, the format effect **collapses to parity** — subnet_rollup
1.00× (CV ~1–2%, the most stable query), topn_src 1.05× (within CV), filtered 0.96× (Iceberg slightly
ahead), byte_rollup 1.15× (noisiest, CV ~6%). Full table in [results/SAME-FILES.md](results/SAME-FILES.md).

### The decomposition (the answer to "DuckLake reads faster")

| rung | what still differs | DuckLake vs Iceberg, heavy aggregations |
|---|---|---|
| default-config (large_scan, 1B) | codec + row-group + writer + format | DuckLake ~1.1–1.7× faster *(confounded)* |
| parity (matched codec + row-group) | writer encoding + format | DuckLake ~1.1–1.18× faster |
| same-files (byte-identical data) | catalog / read-path only | **~parity (1.00–1.05×)** |

The original "DuckLake reads faster" was almost entirely the **Parquet writer**, not the table format:
DuckDB's writer produces smaller, cheaper-to-scan files than PyArrow's, and DuckLake got that for free by
writing with DuckDB. When both formats read the exact same bytes, Iceberg and DuckLake are
read-performance-neutral — the read-speed lever is the encoder, not the format.

```bash
python ocsf-read-scan/compression_probe.py             # why same-codec sizes still differ
python ocsf-read-scan/same_files_scan.py --rows 100000000  # the definitive byte-identical comparison
```

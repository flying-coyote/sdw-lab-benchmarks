# BENCH-E — DuckLake vs Iceberg large-scan reads

## What it measures

Read-side sibling to BENCH-D. Same 10M-row OCSF corpus materialized in both formats, read by the
same engine (DuckDB), so the variable is the format's read path. Four scan shapes: full count,
filtered scan, top-N aggregation, byte rollup.

## Result (Tier B)

The two formats are **largely interchangeable on read** at this scale — identical answers, and
latencies within ~1.5× either way depending on query shape (Iceberg faster on metadata-only count,
DuckLake faster on the byte rollup, parity on filter and top-N). No universal winner; which you
reach for depends on the write pattern (BENCH-D) plus these read latencies — the H-DUCKLAKE-02
trade-off, measured on both sides now. Full numbers in [results/RESULTS.md](results/RESULTS.md).
*(corrected 2026-11-17: the default-config spread in `results/RESULTS.md` is wider than ~1.5×: Iceberg
is 2.3× faster on the metadata-only count (1.743 against 4.078 ms) and DuckLake 2.2× faster on the byte
rollup (46.852 against 21.535 ms), re-derived from `results/results.json`; filter and top-N are 0.84× and
1.25× (Iceberg time over DuckLake time, 9.119 against 10.817 ms and 346.154 against 277.921 ms). The controlled arms below are what bring the format difference to about parity.)*

Every number in this folder is a measured latency or size; none follows from construction. Which result
is current depends on the question. For the format question, the same-files arm is current (parity at 1B
on three of four queries, with topn_src the exception discussed below); for the writer question, see the
writer-lever correction at the end of this file before quoting that arm.

## Reproduce

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
*(corrected 2026-11-17: those 100M ratios re-derive from `results/same-files-100m.json`, but
`results/SAME-FILES.md` now renders the later 1B run (`results/same-files.json`, 11.41 GB each), where
filtered, byte_rollup and subnet_rollup sit at 1.00×, 1.01× and 1.01× and topn_src at 1.30× (1,280,927
against 986,384 ms, DuckLake CV 9%). The 1.30× did not reproduce at 100M in
[results/TOPN-ISOLATION.md](results/TOPN-ISOLATION.md) (0.93× without spill, 1.15× with forced spill),
which points to a 1B spill effect rather than a format difference; it is not settled.)*

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

## Cold-cache arm — posix_fadvise(DONTNEED), no root required

Every arm above is hot/warm only, which structurally favours whatever fits in the OS page cache.
Forensic and incident queries in a SOC run genuinely cold. `cold_cache_scan.py` adds the cold
measurement without root, using `os.posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED)` to evict each
data file's pages from the page cache before timing the first post-eviction run.  It is more
precise than `echo 3 > /proc/sys/vm/drop_caches` because it isolates eviction to the named data
files, leaving DuckDB's connection state and the SQLite catalog intact.

Method: write data once (DuckDB, ZSTD-3) and register byte-identical copies into both Iceberg and
DuckLake (same-files approach — compression not a confound), then for each query run COLD_ROUNDS
evict+cold-shot cycles followed by WARM_TRIALS warm runs; report cold median, warm median,
cold/warm ratio, and CV on warm.

Results at 20M rows: eviction confirmed (max cold/warm 1.55× on `filtered`); scan-heavy queries
(`filtered`, `byte_rollup`) show 1.3–1.55× cold penalty; `full_count` and `topn_src` show little
or no cold gap, consistent with Iceberg's metadata-only count path and DuckDB caching the
high-cardinality sort internally.  Full table in [results/COLD-CACHE.md](results/COLD-CACHE.md).

```bash
python ocsf-read-scan/cold_cache_scan.py               # default 20M rows
python ocsf-read-scan/cold_cache_scan.py --rows 50000000
```

Eviction is judged from the measured cold/warm ratio itself (1.55× on the largest query), not from an
independent check of the page cache, and on WSL2 the Windows host can still hold the file in its own
cache after the guest evicts it, so "cold" here means guest-cold.

## Writer-lever and top-N isolation arms

`writer_read_lever.py` writes one 20M-row table with four writers (DuckDB, PyArrow default, PyArrow
dictionary-forced, pyiceberg) at a matched zstd-3 codec and 122,880-row groups and reads each with DuckDB
([results/WRITER-READ-LEVER.md](results/WRITER-READ-LEVER.md)). `topn_isolation.py` re-runs the 1B
same-files topn_src divergence at 100M under a high memory cap and a forced-spill cap
([results/TOPN-ISOLATION.md](results/TOPN-ISOLATION.md)). Read the writer-lever arm with the correction
below.

```bash
python ocsf-read-scan/writer_read_lever.py --rows 20000000
python ocsf-read-scan/topn_isolation.py --rows 100000000
```

## What would have made it fail

Answer equality across formats is checked on every format arm (default, parity, same-files, cold-cache)
and would have failed on any differing result. For
the format question, the parity arm and the same-files arm are the controls the default-config arm lacks:
footer-verified matched codec and row-group size, and then byte-identical files, so a format effect that
survived them would have shown as a ratio outside the CV. topn_src at 1B came out at 1.30×, outside the
CV, though the 100M isolation run points to spill rather than format, so that case is unsettled. The
writer-lever arm has no answer check across writers, which is how the defect described under Corrections
passed.

## Pre-registration

None. No pre-registration file exists in this folder.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json`, the 10M default-config arm, the
  entry point.
- [results/LARGE-SCAN.md](results/LARGE-SCAN.md) and [results/VALIDATION.md](results/VALIDATION.md),
  with `results/large-scan*.json`, the 100M and 1B default-config arm and its two-run validation.
- [results/PARITY.md](results/PARITY.md), with `results/parity.json` and `results/parity-100m.json`, the
  matched-codec arm.
- [results/SAME-FILES.md](results/SAME-FILES.md), with `results/same-files.json` (1B, rendered) and
  `results/same-files-100m.json` (100M), the byte-identical arm, current for the format question.
- [results/TOPN-ISOLATION.md](results/TOPN-ISOLATION.md) and `results/topn-isolation.json`.
- [results/COLD-CACHE.md](results/COLD-CACHE.md) and `results/cold-cache.json`, at 20M.
- [results/WRITER-READ-LEVER.md](results/WRITER-READ-LEVER.md) and `results/writer-read-lever.json`,
  see Corrections.

## Versions and pins

`requirements.txt` pins DuckDB 1.5.3, pyiceberg 0.11.1 and pyarrow 24.0.0. The ducklake and iceberg DuckDB
extensions are installed at run time, and their versions are not recorded in any results file. Most
results JSON files record no library versions.

## Evidence tier and limits

Tier B, single machine, hot/warm except the cold-cache arm, medians with CV on every arm (2 trials per
scale in the 1B validation runs, 3 to 5 elsewhere). No RESULTS file in this folder carries a rig stamp
(methodology §7b), so read absolute durations under §7a; the ratios are within-run and do not need one.

## Corrections

- *(2026-11-17: two inline corrections above, on the default-config spread and on which run
  `results/SAME-FILES.md` renders.)*
- *(corrected 2026-11-17: the writer-lever arm's pyiceberg row covers 55% of the table.
  `writer_read_lever.py` writes the 20M rows through pyiceberg and then times only the largest data file it
  finds (`max(files, key=os.path.getsize)`). A replica of that write with the same generator, pyiceberg
  0.11.1, DuckDB 1.5.3 and pyarrow 24.0.0, run on 2026-11-17 into a temporary directory, produced two data
  files, 11,000,000 rows in 212.4 MB and 9,000,000 rows in 173.7 MB, and 212.4 MB is the published
  pyiceberg size to the tenth. So "pyiceberg 212.4 MB, topn_src 381 ms, smallest and fastest" compares 11M
  rows with 20M, and the whole pyiceberg table is 386.1 MB, the largest of the four writers. Among the three
  rows that do read the full table, the read spread on topn_src is PyArrow default 708.1 ms against DuckDB
  628.9 ms, 1.13×, and the size spread is 365.1 against 228.3 MB, 1.60×. The arm checks no answers across
  writers, which is why this passed. The script, its JSON and the chart built from it are left as they are
  until the arm is re-run with every pyiceberg file read and answers compared;
  `results/WRITER-READ-LEVER.md` carries the same note.)*

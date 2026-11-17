# Same data, different file: Parquet reproducibility under DuckDB

## What it measures

Whether writing the same logical rows to Parquet twice gives the same file. The probe builds a small
coalesced event store in DuckDB (a network rollup through `GROUP BY`, unioned with two other sources, the
shape of a normalized SIEM table), writes it to Parquet three times under each of four settings (default
multi-threaded, `SET threads=1`, an explicit `ORDER BY` before `COPY`, and a plain scan with no
aggregation), and compares an order-independent hash of the rows with the size and SHA-256 of the file.
It is methodology infrastructure rather than a hypothesis test: it is why the lab fingerprints logical
content instead of file bytes, and what to set when a byte-stable file is needed.

## Result (Tier B)

The rows are identical on every write, and the file is not: under the default multi-threaded path with
an aggregation, three writes of the same 500,000 rows gave 2,788,104, 2,788,326 and 2,869,621 bytes and
three different file hashes, while one thread, an explicit `ORDER BY`, or a scan with no aggregation each
gave a byte-stable file ([RESULTS.md](RESULTS.md)). The cause is row order, since the parallel hash
aggregation and `UNION ALL` hand rows to the writer in thread-finish order and Parquet's dictionary,
run-length and compression encodings all depend on which rows sit next to each other. The 2026-11-16
row-group check ([RESULTS-ROWGROUP-CHECK-2026-11-16.md](RESULTS-ROWGROUP-CHECK-2026-11-16.md)) is the
current result: the files still differ on DuckDB 2.0.0 as on 1.5.3, most row groups hold a different set
of rows from one write to the next, and the number of row groups can change (6, 5 and 5 on 2.0.0), so the
June finding holds and is more than a reordering of fixed row groups. Both outcomes are measured.

## What would have made it fail

The default-setting arm would have failed if the three file hashes had matched, and each of the three
stable settings would have failed if its hashes had differed; the logical-content hash is the control
that shows the data never changed. The bench says nothing about how often the effect occurs on other
engines or writers.

## Pre-registration

None. No pre-registration file exists in this folder, and the row-group check is labelled post hoc in its
header.

## Reproduce

```bash
pip install duckdb==1.5.3 pyarrow==23.0.1
python ocsf-parquet-determinism/determinism_probe.py          # prints the table; writes scratch files to /tmp
python -I -B ocsf-parquet-determinism/rowgroup_check_2026_11_16.py current   # writes rowgroup-check-2026-11-16-current.json here
```

The probe prints its table and keeps no results file, so the June byte counts are recorded only in
`RESULTS.md`. Byte counts move from run to run by design; the mechanism is what reproduces. Seconds to
run.

## Results

- [RESULTS.md](RESULTS.md), the 2026-06-05 probe (the table above; printed output, no JSON).
- [RESULTS-ROWGROUP-CHECK-2026-11-16.md](RESULTS-ROWGROUP-CHECK-2026-11-16.md), with
  `rowgroup-check-2026-11-16-current.json` (DuckDB 2.0.0, pyarrow 26.0.1) and
  `rowgroup-check-2026-11-16-june-pins.json` (DuckDB 1.5.3, pyarrow 23.0.1), the current result. The two
  JSON files sit at the folder root rather than under `results/`; they are not moved.

## Versions and pins

No requirements file. The June probe's DuckDB version is not recorded in `RESULTS.md`; the row-group
check records DuckDB 2.0.0 and 1.5.3 with pyarrow 26.0.1 and 23.0.1 in its two JSON files. The install
line above uses the June-pin versions the lab ran elsewhere at the time.

## Evidence tier and limits

Tier B, single machine, one synthetic corpus, DuckDB only. The magnitudes belong to this corpus; the
mechanism (parallel row order turned into bytes by order-sensitive encodings) is the transferable claim.
No timings are reported.

## Corrections

- *(2026-11-17: README written; no number changed.)*

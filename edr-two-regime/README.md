# Two-regime split on EDR/Sysmon: ClickHouse vs OpenSearch

## What it measures

The flagship Zeek benches found a two-regime split: a columnar engine wins hunting aggregations and an
inverted index wins selective lookups and text search. This folder asks whether that split holds on a
structurally different log shape, a synthetic EDR/Sysmon process-creation stream (image, parent image,
command line, process GUID, SHA-256, integrity level), loaded into ClickHouse (MergeTree) and OpenSearch
(force-merged to one segment, request cache off). It runs in three legs: cheap terms aggregations and
lookups at 3M rows, the flagship's heavy scan-and-compute aggregations at 10M rows, and BM25 relevance
ranking at 10M rows.

## Result (Tier B)

From [RESULTS-2026-06-15.md](RESULTS-2026-06-15.md), re-derived from the three JSON files in `results/`:

- At 3M rows the index wins or ties all five queries: top hosts 2.8x, integrity histogram 5.1x, the
  high-cardinality distinct count a tie, GUID lookup 1.9x, and command-line text search 34.7x (55.5 ms
  against 1.6 ms), with both lookups answer-equal (1 = 1 and 375,264 = 375,264).
- At 10M rows with numeric measures, ClickHouse wins all three heavy aggregations (8.6x and 4.7x on the
  two numeric sums, 356.8x on an average computed over the text field, which OpenSearch has to script
  over `_source`) while the index keeps the text lookup at 144x.
- BM25: OpenSearch ranks natively in 17.7 to 23.6 ms; ClickHouse has no native relevance ranking and
  takes 248.9 to 303.9 ms for a full-scan term count without IDF.

These are measured and could have come out otherwise; the first leg in fact contradicted the split as
originally stated, and the second leg showed that was a query-shape effect. The template command lines
make BM25 scores nearly uniform (1.05 and 2.66), so ranking quality is not demonstrated, only the
capability and the latency.

## What would have made it fail

A different winner on any query. The two engines answer the same question on the same rows, so each is
the other's baseline. Two parity limits apply to the heavy leg: the aggregation answers were not
checked for equality (`answer_equal` is recorded only for the lookups), and the top-hosts query is not
quite the same on both sides, since ClickHouse orders by `sum(bytes_sent + bytes_recv)` while the
OpenSearch request orders by the sum of `bytes_sent` alone and computes `bytes_recv` as a second sum
(`edr_heavy_scan_agg.py:99-100`).

## Pre-registration

None. No file in the folder records a design frozen before the runs.

## Reproduce

```bash
python edr-two-regime/edr_two_regime.py 3000000      # 3M-row leg
python edr-two-regime/edr_heavy_scan_agg.py          # 10M-row heavy-aggregation leg
python edr-two-regime/bm25_relevance.py              # reuses the loaded 10M table
```

The scripts expect ClickHouse on `localhost:8323` and OpenSearch on `localhost:9200` with the lab's
local credentials, generate the corpus in DuckDB, and write their JSON to a fixed path under the home
directory (`~/sdw-lab-benchmarks/edr-two-regime/results/`), so a clone elsewhere needs that path edited.

## Results

- [RESULTS-2026-06-15.md](RESULTS-2026-06-15.md): all three legs; the heavy-aggregation and BM25 sections are the current reading.
- `results/edr_two_regime.json`, `results/edr_heavy_scan_agg.json`, `results/bm25_relevance.json`.

## Versions and pins

No `requirements.txt`. The scripts import `duckdb`, `pyarrow` and `clickhouse_connect`, which the root
`requirements.txt` pins. `results/edr_two_regime.json` records ClickHouse 26.5 and OpenSearch 3.7.0; the
other two JSON files record no versions.

## Evidence tier and limits

Tier B: one host, synthetic EDR data, five trials per query in the code (`timeit(fn, trials=5)`) with
only the summary latency written to the JSON and no CV recorded, so the smaller ratios (1.9x, 2.8x)
carry less weight than the 34.7x and 144x text results.

## Corrections

None before this README was written on 2026-11-17.

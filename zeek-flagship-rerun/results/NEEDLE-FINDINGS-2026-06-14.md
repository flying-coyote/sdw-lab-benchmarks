# Needle-in-haystack arm — the index's home turf, measured (2026-06-14)

The flagship 5-query suite measured the lakehouse on its best ground (scan-heavy aggregations).
This arm measures the OTHER regime — random high-cardinality **point lookups** that defeat
Parquet min/max pruning — so the two-regime claim is symmetric (we test where the index wins,
not only where the lakehouse wins). Same 10M-row Zeek conn corpus; OpenSearch 3.7.0 (term query)
vs ClickHouse-native MergeTree (sorted by orig_h,resp_h,ts) vs ClickHouse-over-Iceberg
(unsorted). 1 warmup + 7 trials, hot/warm, answer-equality verified. `results/needle.json`.

| point lookup | OpenSearch 3.7 (index) | ClickHouse-native (sorted) | ClickHouse-Iceberg (unsorted) | answers |
|---|--:|--:|--:|:--:|
| `uid = <one row>` | 3.5 ms | 3.5 ms | 145 ms | identical (1) |
| `orig_h = <rare IP>` (570 rows) | 5.7 ms | 4.5 ms | 50 ms | identical (570) |

Index advantage: **41× over unsorted Iceberg** on the uid needle, **8.8×** on the rare-IP
needle — but **~1× (tie) vs the sorted native store** (native actually edged it on the IP).

## The honest finding: it's *indexed/sorted vs unsorted-scan*, not "index vs lakehouse"

The inverted index does win point lookups hard — but so does the **sorted** columnar store. Both
OpenSearch's inverted index and ClickHouse's sorted MergeTree primary index serve these lookups
in 3–5 ms; what loses (9–41×) is the **unsorted open-format Iceberg table**, which has no index
and isn't clustered on the looked-up columns, so it full-scans. So the lakehouse's point-lookup
weakness is a **layout choice, not a fundamental limit**:

- It completes the two-regime symmetry honestly: the index wins the cheap point lookups (vs an
  unsorted lakehouse) just as the lakehouse wins the heavy hunting aggregations (the flagship) —
  the question is which regime the workload lives in.
- And it ties directly to **B-COMPACT's sort-clustered arm**: a sort/Z-order on the looked-up
  columns gave a measured ~1.7× pruning gain there, and would similarly close this point-lookup
  gap. The native MergeTree result here (tie with the index) is the proof: a sorted lakehouse
  layout matches the index on its home turf.

## Scope / caveats

Hot/warm (the warm full-scan time for the unsorted arm; a cold S3 read would be slower still),
single host, Tier B, the same single-host caveat as the flagship. BM25 fuzzy full-text — the
other half of the index's home turf — is **not** measured here: the Zeek conn corpus has no rich
text field, so a fair BM25 arm needs a corpus with one (future work). The uid/orig_h exact-match
needles are the point-lookup half, which the existing corpus supports.

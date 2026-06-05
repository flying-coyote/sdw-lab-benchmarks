# DuckLake inlining vs Iceberg — the small-files problem at the source (results)

**Tier B.** 100 small commits of 200 rows each, identical seeded stream
to three arms; the metric is how many data files each leaves behind (and whether the data is queryable).

| arm | data files | metadata files | queryable |
|---|---|---|---|
| iceberg | 100 | 301 | True |
| ducklake_no_inline | 100 | 0 | True |
| ducklake_inline | 0 | 0 | True |

## Reading

The inlining claim holds, concretely: with inlining off, both DuckLake and Iceberg write one data file
per small commit (100 and 100 respectively, Iceberg
also accumulating a manifest and metadata.json each time), so a streaming workload leaves a pile of tiny
files that has to be compacted later. With inlining on, DuckLake writes
**0 data files** for the same stream — the rows live in the catalog until a
flush threshold — so the small files are never created in the first place rather than created and cleaned
up. Both remain immediately queryable. This is the difference between "create tiny files, then compact"
(the Iceberg maintenance job measured in the iceberg-metadata bench) and "don't create them" — a real
architectural distinction for hot-tier streaming ingest. Tier B, single machine; file counts are
deterministic, the threshold is a configured parameter. It does not by itself say which is better at
warehouse scale (inlined rows trade file-count for catalog growth) — it isolates the file-avoidance claim.

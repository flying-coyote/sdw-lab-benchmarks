# Planning cost vs fragmentation — Iceberg manifests vs DuckLake catalog (R6)

**Tier B · single machine.** 5,000,000 rows ingested into each format across a ladder of
commit counts (each commit = one data file), then read end-to-end by the **same engine** (DuckDB) so the
only variable is how each format's metadata layer resolves which files to scan. Latencies are medians
with CV; file counts are exact.

| commits | data files ice/dl | DuckDB e2e — Iceberg ms (cv) | DuckDB e2e — DuckLake ms (cv) | plan — pyiceberg ms (cv) | plan — DuckLake catalog ms (cv) |
|---|---|--:|--:|--:|--:|
| 10 | 10/10 | 20 (2%) | 14 (8%) | 13.0 (1%) | 2.94 (7%) |
| 50 | 50/50 | 36 (2%) | 15 (3%) | 59.0 (3%) | 3.57 (10%) |
| 200 | 200/200 | 128 (6%) | 20 (5%) | 228.4 (10%) | 3.56 (12%) |

- End-to-end growth across the ladder (same engine): Iceberg **6.53×**,
  DuckLake **1.43×**.
- Native planning-proxy growth: pyiceberg `plan_files()` **17.6×**, DuckLake
  `ducklake_list_files` **1.21×**.

## Reading

The same data, read by the same engine, fragments into more and more files as the commit count grows —
and the two formats answer "which files do I scan" very differently. Iceberg enumerates them by reading
manifests, so its end-to-end query latency and especially its planning cost climb as files accumulate;
that climb is the small-files tax, and it is the mechanism the Iceberg V4 metadata work targets. DuckLake
resolves the same question with a query against its SQL catalog, an indexed lookup whose cost barely
moves with file count, so its planning stays roughly flat across the ladder. The planning-proxy columns
use each format's native mechanism (pyiceberg's Python manifest planner vs DuckLake's catalog query), so
their absolute milliseconds aren't directly comparable — the transferable finding is the *shape*: one
grows with fragmentation, the other doesn't, which is an architectural property of where the metadata
lives (in files vs in a database), not a tuning detail. Both formats return identical answers throughout.
Tier B, single machine; magnitudes are this host's, the scaling shapes are the finding.

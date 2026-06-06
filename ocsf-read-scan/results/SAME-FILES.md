# BENCH-E same-files arm — byte-identical data, two catalogs (1,000,000,000 rows)

**Tier B, single machine, hot/warm only.** The data files are written ONCE (DuckDB, ZSTD-3,
122,880-row groups) and the SAME bytes registered into both an Iceberg table
(pyiceberg `add_files`) and a DuckLake table (`ducklake_add_data_files`), read by the same engine
(DuckDB, memory_limit 28GB). Compression/encoding/row-group/file-size are therefore
identical by construction — every factor but the catalog/read path is accounted for.

- Bytes identical across catalogs: **True** (11.41 GB each)
- Answers identical across catalogs: **True**

| query | Iceberg ms (cv) | DuckLake ms (cv) | Iceberg/DuckLake |
|---|---|---|---|
| filtered | 9367 (0%) | 9388 (1%) | 1.00x |
| topn_src | 1280927 (1%) | 986384 (9%) | 1.30x |
| byte_rollup | 10181 (0%) | 10112 (1%) | 1.01x |
| subnet_rollup | 31561 (1%) | 31178 (2%) | 1.01x |

## Reading

With the Parquet bytes literally identical in both catalogs, any latency difference here is the
metadata/read-path effect alone — the true format difference, with compression fully removed as a
confound. Most queries sit at parity within CV (filtered, byte_rollup, subnet_rollup) — the expected format-neutrality result on identical bytes. But **topn_src** diverged **1.30×** toward DuckLake, a gap wider than the combined CV. With compression removed and (for a full-scan aggregate) no predicate to plan around, the residual isolates to the two DuckDB extensions' scan/spill path over identical bytes, not the format's data. Treat the mechanism as a candidate, not isolated: a heavy high-cardinality aggregate can spill to the temp dir at this memory cap, and the elevated CV on the diverging arm is consistent with variable spill — a bare `read_parquet(glob)` arm and a no-spill re-run would separate scan-path from spill. Read each query's ratio against its own CV; compare against PARITY.md (matched-codec,
different writers) and the default-config large-scan to see how much of the original gap was the writer's
compression versus the format. Tier B.

# Vortex vs Parquet on OCSF data — PENDING (install-blocked)

Intended benchmark: the Vortex columnar format's vendor claims (large random-access and scan speedups vs
Parquet) stress-tested on **security-data** edge cases — high-cardinality OCSF fields, time-range hunt
scans — measuring write time, file size/compression, and scan latency (native and via DuckDB), and
capturing the OOM/integration failures practitioners have reported on the DuckDB-Vortex bridge.

## Why it's pending, not built

The Vortex Python package is not installable from PyPI as of 2026-06: every published `vortex-array`
version is yanked and `pip install` resolves to no matching distribution. Rather than fabricate numbers or
hand-build a partial reader, this is recorded as blocked — the same honesty posture as the ISK never-write
arm (BENCH-D) and the GraphRAG arm (BENCH-C). `run.py` checks for the library and exits with setup
guidance if it's absent.

## When unblocked

Same OCSF result-set corpus the arrow-transport bench uses, written to Vortex and Parquet (zstd):
- write time and on-disk size (compression) per format
- scan latency: full scan, time-range filter, high-cardinality group-by — native Vortex vs Parquet/DuckDB
  vs the Vortex→DuckDB bridge
- explicit capture of OOM / type-handling failures on the bridge (the reported rough edge)

Format-war angle; would sit alongside BENCH-E (DuckLake vs Iceberg) as another open-format datapoint.

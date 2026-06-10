# R6 — planning cost vs fragmentation: Iceberg manifests vs DuckLake SQL catalog

See the docstring in [`run.py`](run.py) for the design: same DuckDB engine reads both
formats as the table fragments into more files, isolating how each format's metadata
layer resolves "which files must I scan."

## Hypothesis mapping

Advances **H-DUCKLAKE-02**: the planning-cost scaling shape (manifest traversal vs SQL
catalog lookup) is the metadata-layer side of the DuckLake-vs-Iceberg trade-off that
hypothesis tracks. *(ID recorded 2026-06-10 per the benchmark-alignment audit.)*

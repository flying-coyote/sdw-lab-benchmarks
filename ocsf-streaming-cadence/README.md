# R7 — streaming write cadence: throughput, commit latency, and where DuckLake inlining inverts

See the docstring in [`run.py`](run.py) for the design: micro-batch cadence swept across
5/50/500 rows per commit over three arms (Iceberg file-write, DuckLake inlining off,
DuckLake inlining on), measuring throughput, commit-latency p50/p95, footprint, and
read-while-write coherence to find where the inlining advantage inverts.

## Hypothesis mapping

Advances **H-DUCKLAKE-02**: the cadence sweep finds where the inlining write-contract
advantage holds and where it inverts — the dynamic dimension of the DuckLake-vs-Iceberg
trade-off that hypothesis tracks.
*(ID recorded 2026-06-10 per the benchmark-alignment audit.)*

# Dremio arm — prior-art / two-regime expectation (external context, verified 2026-06-13)

**This is framing, not measurement.** It records the published architectural roles behind the
Dremio-vs-ClickHouse-vs-OpenSearch comparison so the scored `results/RESULTS.md` can cite the
expectation it tested. No number here is adopted as a finding; the only claimable numbers are
the ones the bench produces under the methodology gate (7 trials, CV-gated, answer-equality).
Verified against primary and vendor docs in the Gemini DR #2 reconciliation.

## The two-regime expectation (Tier A on the roles)

- **ClickHouse** (C++ vectorized engine) tends to win raw, un-cached columnar scans. It
  processes columnar blocks of up to 65,536 values with SIMD AVX/AVX-512, ~5–20× per scanned
  byte versus JVM engines (ClickHouse academic-overview + vectorized-execution docs). This is
  the engine the flagship already measured winning the hunting-shaped aggregations.
- **OpenSearch** (Lucene inverted index) tends to win full-text / keyword search and
  index-shaped lookups (OpenSearch intro docs), which matches the flagship's split: the index
  answers index-shaped questions from metadata in milliseconds.
- **Dremio** (federated structured SQL, Arrow + LLVM codegen) targets cross-source SQL without
  data movement, accelerated by **Reflections**, which are materialized query accelerations
  persisted as **Apache Iceberg / Parquet tables on object storage (S3)** (Dremio
  live-reflections-on-Iceberg blog; Reflections docs). So the Dremio arm tests a third regime,
  federated SQL with a materialization layer, on the same open Iceberg substrate the rest of
  the bench uses.

## The vendor claim to NOT adopt (Tier C)

Dremio markets "**40–60% lower compute vs Snowflake**" (Dremio blog, "cut your Snowflake bill
40–60%"). This is a vendor marketing claim, not an independent benchmark: it is contingent on
80%+ Reflection hit rates and BI-shaped workloads, with no third-party audit or control group
(the blog's own illustrative case nets ~35–50%). The bench does not adopt it. If Dremio cost
ever enters a model it has to be a scenario-specific Reflection-hit-rate estimate, not this
headline. Vendor warm-cache / pre-aggregated benchmarks are the standard trap with this class
of claim.

## Why it matters to this bench

The flagship already showed the two-regime split (the index wins lookups, the columnar engine
wins the hunt). Adding Dremio asks whether a federated-SQL-plus-Reflections arm lands in the
columnar regime on hunting-shaped aggregations once its accelerations are materialized. The
Reflections-ON path is currently blocked by the Dremio-26 + Nessie-versioned-table
instant-expiry finding, so the OFF path is what the first scored pass measures. The
single-host, Tier-B, no-cluster-extrapolation caveats from the flagship carry over unchanged.

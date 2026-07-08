---
type: evidence
title: "Arrow Transport: ADBC vs JDBC Latency and Parquet Encoding Results"
created: 2026-06-05
tags: [arrow, adbc, jdbc, transport, parquet-encoding, duckdb]
---

# Arrow transport — ADBC vs JDBC, + Parquet encoding (results)

**Tier B.** Same DuckDB query feeds both transports; the only variable is the connectivity API.
Latencies are machine-specific medians, not constants. ODBC is a pending third leg.

## Transport: ADBC (Arrow, columnar) vs JDBC (row-oriented)

| rows | ADBC ms | JDBC native-JVM ms | JDBC Python/JPype ms | ADBC vs native | ADBC vs Python |
|---|---|---|---|---|---|
| 100000 | 35 | 222 | 3049 | 6.3× | 86.9× |
| 1000000 | 158 | 1285 | 32505 | 8.1× | 205.2× |

The honest columnar-vs-row advantage is **ADBC vs native-JVM JDBC** — single digits, not hundreds:
ADBC returns Arrow record batches with no per-row marshaling, where JDBC deserializes row by row. The
Python/JPype JDBC column is the cautionary one: running JDBC through the Python bridge inflates the gap by
roughly 40× (the per-row JNI crossing), which is why the first pass's ~276× was overstated — that number
measured the bridge, not the transport. A cross-runtime caveat remains and is stated plainly: ADBC here is
Python-Arrow and the native JDBC is Java-rows, so the ratio is the columnar-vs-row paradigm difference in
each one's idiomatic runtime, not a single-language isolation. Row counts matched across transports.

## Parquet encoding / compression (1M-row OCSF result set)

| codec | file MB | compression | scan ms |
|---|---|---|---|
| uncompressed | 94.2 | 1.0× | 3 |
| snappy | 45.2 | 2.08× | 3 |
| zstd | 25.6 | 3.68× | 5 |

## Edge-case battery (Hunter's "important errors early on")

Fetching awkward types — HUGEINT, DECIMAL, microsecond timestamp, NULL, a 5KB string, an array,
and a map — through each transport, reporting where the driver path breaks rather than only the
happy path:

- **adbc**: OK
- **jdbc**: OK

## Reading

The columnar transport wins on bulk analytical fetches because it returns Arrow record batches
with no per-row marshaling, and the win scales with result-set size — but the honest magnitude is
**single digits (~5–10×), not hundreds**. The native-JVM JDBC baseline added here is what de-inflates
the first pass: running JDBC through the Python/JPype bridge had reported ~234× at a million rows, but
that measured the per-row JNI crossing of the bridge, not the transport — a native Java JDBC client over
the same driver is ~40–50× faster than the Python path, leaving ADBC ~5–10× ahead of *it*. That
remaining gap is the real columnar-vs-row advantage. The one caveat left is cross-runtime: ADBC here is
Python-Arrow and the native JDBC is Java-rows, so the ratio is the paradigm difference in each one's
idiomatic runtime, not a single-language isolation. The edge-case battery (HUGEINT, DECIMAL, microsecond
timestamp, NULL, a 5KB string, an array, a map) came back clean on both transports, so the "important
errors early on" a practitioner hit are driver-/version-/backend-specific (the ADBC ecosystem's maturity
varies) rather than universal — this bench found none against DuckDB's ADBC path and says so. The encoding
sweep shows the ordinary trade: zstd is ~3.7× smaller than uncompressed but scans slower (decompression
cost). Tier B, single machine; ODBC pending (needs a DuckDB ODBC driver). Advances H-ARROW-SECURITY-STACK-01.

## Same-runtime isolation (A2 · DuckDB leg) — added 2026-07-08

The cross-runtime caveat above is now closed for the one backend where both transports run in a
single language runtime: DuckDB from the same Python process, DB-API rows vs ADBC Arrow vs the
in-process native Arrow reference. On the bare-window re-run (moar-* containers stopped; docker
environment empty for the full timed span), the rows/ADBC gap is **3.7× at 100k rows and 7.8× at
1M** — inside the pre-registered [2×, 15×] survives-band, so the cross-runtime table's
single-digit framing SURVIVES runtime isolation — and ADBC runs at **0.84×/0.89× of the native
in-process Arrow path**, i.e. no ADBC tax (slightly faster than the deprecated-wrapper-free
native reference, by more than the run-to-run spread). Every arm CV ≤ 2.5% against the any-arm
<5% gate (worst: native_arrow 2.5% at 1M). This supersedes the 2026-07-04 run 1, which was
PROVISIONAL-DISCARDED by its own CV gate (reference arm 5.1%) and whose JSON stays as the
discarded record. Tier B, single host (Beelink 5800H, WSL2 48GB/14 vCPU), same-runtime scope
only. Full adjudication + methodology: `RESULTS-samruntime-duckdb-rerun-2026-07-08.md`.

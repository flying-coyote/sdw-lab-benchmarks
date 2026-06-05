# Arrow transport — ADBC vs JDBC, + Parquet encoding (results)

**Tier B.** Same DuckDB query feeds both transports; the only variable is the connectivity API.
Latencies are machine-specific medians, not constants. ODBC is a pending third leg.

## Transport: ADBC (Arrow, columnar) vs JDBC (row-oriented)

| rows | ADBC ms | JDBC ms | ADBC speedup | correct |
|---|---|---|---|---|
| 100000 | 56 | 6435 | 114.3× | True |
| 1000000 | 295 | 81625 | 276.3× | True |

ADBC returns Arrow record batches with no per-row marshaling; JDBC deserializes row by row over
the JVM bridge, and the gap widens with result-set size — which is the columnar-transport
advantage for analytical bulk fetches, measured rather than asserted.

## Parquet encoding / compression (1M-row OCSF result set)

| codec | file MB | compression | scan ms |
|---|---|---|---|
| snappy | 45.2 | 2.08× | 7 |
| uncompressed | 94.2 | 1.0× | 4 |
| zstd | 25.6 | 3.68× | 14 |

## Edge-case battery (Hunter's "important errors early on")

Fetching awkward types — HUGEINT, DECIMAL, microsecond timestamp, NULL, a 5KB string, an array,
and a map — through each transport, reporting where the driver path breaks rather than only the
happy path:

- **adbc**: OK
- **jdbc**: OK

## Reading

The columnar transport wins on bulk analytical fetches because it returns Arrow record batches
with no per-row marshaling, and the win scales with result-set size. Two honest caveats travel
with the magnitude. First, the JDBC leg here is **Python-mediated** (jaydebeapi over JPype), which
pays a per-row JNI crossing that a native JVM-to-JVM JDBC client would not, so the measured 100–275×
gap overstates what a pure-Java JDBC path would see — the *structural* advantage (columnar bulk
transfer vs row-by-row deserialization) is the robust finding, the exact multiplier is
transport-and-binding-specific. Second, the edge-case battery (HUGEINT, DECIMAL, microsecond
timestamp, NULL, a 5KB string, an array, a map) came back clean on **both** transports here, so the
"important errors early on" a practitioner hit are most likely driver-, version-, or backend-specific
(the ADBC driver ecosystem's maturity varies by backend) rather than universal — this bench found
none against DuckDB's ADBC path, and says so rather than manufacturing a failure. The encoding sweep
shows the ordinary trade: zstd is ~3.7× smaller than uncompressed but scans slower (decompression
cost), snappy sits in between. Tier B, single machine; ODBC pending (needs a DuckDB ODBC driver).
Advances H-ARROW-SECURITY-STACK-01.

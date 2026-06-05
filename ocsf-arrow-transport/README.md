# Arrow transport — ADBC vs JDBC (+ Parquet encoding)

Measures the **connectivity layer**, not the engine: when a tool pulls a large OCSF result set out
of the store, what does the API cost? ADBC returns Arrow record batches (columnar, no per-row
marshaling); JDBC/ODBC hand back rows deserialized one at a time. Same DuckDB query feeds both.

## Result (Tier B)

ADBC is **~5–10× faster than a native-JVM JDBC client** (5.0× at 100k rows, 9.6× at 1M), scaling with
size — the honest columnar-vs-row advantage. The first pass reported ~276× by timing JDBC through the
Python/JPype bridge; the **native-JVM JDBC baseline added here de-inflates that** — a Java JDBC client over
the same driver is ~40–50× faster than the Python path, so the bridge, not the transport, was most of the
gap. The one remaining caveat is cross-runtime (ADBC-Python-Arrow vs JDBC-Java-rows). The edge-case battery
(HUGEINT/DECIMAL/timestamp/NULL/wide-string/array/map) came back clean on both transports, so the "early
errors" a practitioner hit are driver/version/backend-specific — this bench found none against DuckDB's
ADBC path and says so. Encoding sweep: zstd ~3.7× smaller than uncompressed, scans slower (decompression
cost). Full numbers in [results/RESULTS.md](results/RESULTS.md).

The native-JVM arm uses Java's single-file source launcher (`java JdbcBench.java`), so it needs a JDK's
`java` (no separate compile step) and the DuckDB JDBC driver in `.jars/` (or `DUCKDB_JDBC_JAR`).

## Run it

```bash
# fetch the DuckDB JDBC driver once, point DUCKDB_JDBC_JAR at it
curl -sL -o duckdb_jdbc.jar https://repo1.maven.org/maven2/org/duckdb/duckdb_jdbc/1.1.3/duckdb_jdbc-1.1.3.jar
pip install -r ocsf-arrow-transport/requirements.txt
DUCKDB_JDBC_JAR=$PWD/duckdb_jdbc.jar python ocsf-arrow-transport/run.py
```

ODBC is a pending third leg (needs a DuckDB ODBC driver + unixODBC). Latencies are machine-specific
medians; cross-runtime memory isn't directly comparable and is reported as the Arrow table size only.
Advances H-ARROW-SECURITY-STACK-01.

# Arrow transport — ADBC vs JDBC (+ Parquet encoding)

Measures the **connectivity layer**, not the engine: when a tool pulls a large OCSF result set out
of the store, what does the API cost? ADBC returns Arrow record batches (columnar, no per-row
marshaling); JDBC/ODBC hand back rows deserialized one at a time. Same DuckDB query feeds both.

## Result (Tier B, first pass)

ADBC is ~114× faster at 100k rows and ~276× at 1M (295ms vs 81.6s) — the columnar-transport
advantage, scaling with size. **Caveat:** the JDBC leg is Python-mediated (jaydebeapi/JPype), whose
per-row JNI overhead inflates the multiplier; the structural columnar-vs-row advantage is the robust
finding, the exact ratio is binding-specific. The edge-case battery (HUGEINT/DECIMAL/timestamp/NULL/
wide-string/array/map) came back clean on both transports, so the "early errors" a practitioner hit
are likely driver/version/backend-specific — this bench found none against DuckDB's ADBC path and
says so. Encoding sweep: zstd ~3.7× smaller than uncompressed, scans slower (decompression cost).
Full numbers in [results/RESULTS.md](results/RESULTS.md).

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

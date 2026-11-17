# Arrow transport — ADBC vs JDBC (+ Parquet encoding)

## What it measures

Measures the **connectivity layer**, not the engine: when a tool pulls a large OCSF result set out
of the store, what does the API cost? ADBC returns Arrow record batches (columnar, no per-row
marshaling); JDBC/ODBC hand back rows deserialized one at a time. Same DuckDB query feeds both.

## Result (Tier B)

ADBC is **~6–8× faster than a native-JVM JDBC client** (6.3× at 100k rows, 8.1× at 1M, from
`results/results.json`), scaling with size — the honest columnar-vs-row advantage. The first pass
reported a gap in the hundreds by timing JDBC through the Python/JPype bridge (205× at 1M in the current
JSON); the **native-JVM JDBC baseline added here de-inflates that** — a Java JDBC client over the same
driver is ~14–25× faster than the Python path in the current JSON (3,048.8 against 222 ms, 32,504.8
against 1,285 ms), so the bridge, not the transport, was most of the gap. The cross-runtime caveat
(ADBC-Python-Arrow vs JDBC-Java-rows) was closed for DuckDB by the pre-registered same-runtime re-run of
2026-07-08: with both transports in one Python process, the row-over-ADBC gap is 3.7× at 100k rows and
7.8× at 1M, inside the frozen [2×, 15×] band, and ADBC takes 0.84× and 0.89× of the time of DuckDB's
in-process Arrow path, so there is no ADBC overhead to report. The edge-case battery
(HUGEINT/DECIMAL/timestamp/NULL/wide-string/array/map) came back clean on both transports, so the "early
errors" a practitioner hit are driver/version/backend-specific — this bench found none against DuckDB's
ADBC path and says so. Encoding sweep: zstd ~3.7× smaller than uncompressed, scans slower (decompression
cost). Full numbers in [results/RESULTS.md](results/RESULTS.md). Every ratio is measured.

The native-JVM arm uses Java's single-file source launcher (`java JdbcBench.java`), so it needs a JDK's
`java` (no separate compile step) and the DuckDB JDBC driver in `.jars/` (or `DUCKDB_JDBC_JAR`).

## What would have made it fail

The pre-registered same-runtime leg had a stated failure: a gap under 2× at 1M would have turned the
cross-runtime table's caveat into a correction, and a gap over 15× would have stopped publication, with an
any-arm CV over 5% discarding the run (which happened to run 1). The cross-runtime table has no stated
failure line; its native-JVM JDBC arm is the practitioner baseline that cut the first pass's figure down.
Row counts are checked across transports.

## Pre-registration

[`PRE-REG-samruntime-duckdb-2026-07-04.md`](PRE-REG-samruntime-duckdb-2026-07-04.md), for the same-runtime
DuckDB leg only. It has no hash file, so the freeze rests on in-file evidence: registered 2026-07-04
before the scored run, a condition amendment appended before scoring, run 1 discarded by the frozen CV
gate, and an erratum lifted after the 2026-07-08 re-run. The verdict (7.8× at 1M) sits inside the frozen
band, and the one deviation (`to_arrow_table()` in place of the deprecated wrapper) is declared in the
re-run JSON and was prescribed by the erratum. The cross-runtime table and the encoding sweep were not
pre-registered.

## Reproduce

```bash
# fetch the DuckDB JDBC driver once, point DUCKDB_JDBC_JAR at it
curl -sL -o duckdb_jdbc.jar https://repo1.maven.org/maven2/org/duckdb/duckdb_jdbc/1.1.3/duckdb_jdbc-1.1.3.jar
pip install -r ocsf-arrow-transport/requirements.txt
DUCKDB_JDBC_JAR=$PWD/duckdb_jdbc.jar python ocsf-arrow-transport/run.py
python ocsf-arrow-transport/transport_same_runtime_duckdb.py    # same-runtime leg, run-1 harness
```

The 2026-07-08 re-run harness, `transport_same_runtime_duckdb_rerun.py`, is not in the repo (its RESULTS
file lists it among files kept outside the tree), so the published same-runtime numbers cannot be
regenerated from this folder as it stands; `transport_same_runtime_duckdb.py` is the run-1 harness, which
still calls the deprecated `fetch_arrow_table()` the erratum replaced. ODBC is a pending third leg (needs
a DuckDB ODBC driver + unixODBC). Latencies are machine-specific medians; cross-runtime memory isn't
directly comparable and is reported as the Arrow table size only. `run.py` rewrites `results/RESULTS.md`,
so dated corrections also live here.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json`, the cross-runtime table and the
  encoding sweep (2026-06-05), with the same-runtime section appended 2026-07-08.
- [RESULTS-manageability-2026-06-15.md](RESULTS-manageability-2026-06-15.md) and
  `results/adbc_manageability.json`, `results/m3_type_fidelity.json`; the Dremio same-runtime leg
  (`results/transport_same_runtime.json`) is withheld under that vendor's publication terms.
- [results/RESULTS-samruntime-duckdb-rerun-2026-07-08.md](results/RESULTS-samruntime-duckdb-rerun-2026-07-08.md)
  and `results/transport_same_runtime_duckdb-rerun-2026-07-08.json`, the adjudicated same-runtime result;
  `results/transport_same_runtime_duckdb.json` is the discarded run 1.

## Versions and pins

`requirements.txt` pins DuckDB 1.5.3, adbc_driver_manager 1.11.0 and jaydebeapi 1.2.3; `pyarrow` is
unpinned. `results/results.json` records only DuckDB 1.5.3. The JDBC driver version is not recorded in any
results file. The command above fetches `duckdb_jdbc` 1.1.3, which embeds DuckDB 1.1.3, so if that jar was
the one used, the JDBC arm ran an older DuckDB engine than the ADBC arm, a parity gap (methodology
principle 1) the results do not declare. `m3_type_fidelity.py` imports `adbc_driver_flightsql`,
`clickhouse_connect` and a container-local `ejs_clients` module, none of them in the requirements file.

## Evidence tier and limits

Tier B, single machine. The ADBC and Python-JDBC arms report CV (1.5–4.2%); the native-JVM JDBC arm
reports one median over 3 trials with no spread. The main RESULTS file has no rig stamp (methodology
§7b); the same-runtime re-run names its host (Beelink 5800H, WSL2, 14 vCPU). Advances
H-ARROW-SECURITY-STACK-01.

## Corrections

- *(corrected 2026-11-17: this README said 5.0× at 100k rows and 9.6× at 1M; `results/results.json` and
  `results/RESULTS.md` both say 6.3× and 8.1×, so the headline above now reads ~6–8× and the old figures
  have no results file behind them. The bridge figure appeared as ~276× here and ~234× in RESULTS.md's
  reading; the current JSON gives 205.2× at 1M and 86.9× at 100k, so "~40–50×" for the bridge overhead is
  replaced by the ratios of the current JSON, about 14× and 25×.)*
- *(corrected 2026-11-17: a local scratch path in
  `results/RESULTS-samruntime-duckdb-rerun-2026-07-08.md` was replaced with a plain description.)*

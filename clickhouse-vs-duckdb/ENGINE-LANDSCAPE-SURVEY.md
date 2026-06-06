# Cross-engine answer-equality study — the query-engine landscape (2026)

Survey behind the engine selection for `multi_engine_correctness.py` (the Phase-E generalization of the
R3 chDB silent-undercount finding, H-ENGINE-ANSWER-EQUIVALENCE-01). Compiled 2026-06-06 via a web-grounded
research pass; the analytical lens and the include/exclude calls are recorded here so the selection is
defensible rather than ad hoc.

## The lens: distinct Parquet *readers*, not engine names

The bug we found (chDB silently undercounts an equality filter in the tail row groups of a many-row-group
Parquet file) is a *reader* defect — it survives because most test files have one row group. So the study's
value is in exercising **distinct Parquet decode paths** against the same many-row-group file, and the
pruning principle is: an engine that wraps a reader we already test adds ~zero value, and an engine that
ingests Parquet into its own segment format and then queries *that* isn't testing a Parquet reader at all.

The genuinely distinct production decode paths: **DuckDB** (own C++), **ClickHouse** (own C++; chDB,
clickhouse-local, and clickhouse-server all share it), **Arrow C++** (pyarrow/Acero), **arrow-rs `parquet`**
(DataFusion, and most Rust engines ride it — RisingWave, Feldera, GlareDB, pg_parquet, historically Daft),
**Polars** (own `polars-parquet`, forked from arrow2, since diverged), **parquet-mr** (Spark — the Java
*reference* reader everyone else was validated against), **Trino** (own Java reader, a rewrite, not
parquet-mr), **Dremio** (own Java vectorized reader), **StarRocks** (own C++), **Impala** (own C++),
**Velox** (Presto C++ / Spark Gluten), **fastparquet** (pure-Python/Cython, non-Arrow), **Hyper** (Tableau,
proprietary C++), **cuDF** (GPU kernels). Most other "engines" map onto one of these.

## Included

| Engine | Reader | Why in |
|---|---|---|
| DuckDB | own C++ | reference / passer |
| chDB | ClickHouse C++ | the engine that failed (R3) |
| ClickHouse server | ClickHouse C++ (same as chDB) | **disambiguation** — proves the bug is in ClickHouse core, not the chDB embedding (or that chDB lags a core fix) |
| DataFusion | arrow-rs | canonical Rust decode path |
| Polars | own polars-parquet | genuinely independent of arrow-rs |
| pyarrow / Acero | Arrow C++ | **top add** — foundational independent reader; `count_rows(filter=…)` hits the row-group-stats pushdown path the bug exploits |
| fastparquet | pure-Python (non-Arrow) | the only non-Arrow row-group reader — cleanest outsider cross-check |
| Daft | Rust (verify arrow-rs vs native I/O) | AI/dataframe relevance, near-free to wire |
| Trino | own Java | distinct JVM reader (already in set) |
| Spark | parquet-mr | the Java *reference* reader; essential |
| StarRocks | own C++ | independent MPP reader, easy `FILES()` |
| Dremio | own Java | independent reader; also the H-MV-SECURITY-01 baseline engine |
| RisingWave | arrow-rs (streaming engine) | breadth: the streaming-incremental class (Postgres-wire); reader not distinct, labeled |
| Postgres (native load) | n/a — row store | the "just use Postgres" baseline; an independent executor/storage oracle (data loaded, not a Parquet read) |
| Feldera | arrow-rs (streaming DBSP) | breadth: distinct *compute model*; reader not distinct, labeled — attempted, high-setup |

chDB MergeTree is kept as a within-engine control (chDB reading its own native store, not Parquet).

## Considered and excluded — with the reason

- **Presto (Java, prestodb)** — shares Trino's pre-2019 lineage; correlated answers. (Velox/Prestissimo is the distinct-but-high-effort exception — stretch.)
- **GlareDB** — built on DataFusion → arrow-rs reader, duplicate decode path; tiny team.
- **Apache Doris** — fork-sibling of StarRocks (already included); lower marginal value, harder FE+BE+`LOCAL()` backend_id setup.
- **pg_duckdb** (= DuckDB reader) / **pg_parquet** (= arrow-rs reader) — Postgres-wire over a reader we already test; noted under the Postgres baseline rather than counted as new readers.
- **Materialize / ksqlDB** — no first-class local-Parquet batch read (Kafka/CDC-shaped).
- **Apache Pinot / Apache Druid** — ingest Parquet into proprietary segments then query the *segments*, not the Parquet row groups; heaviest setups; wrong shape for answer-equality on a file.
- **pandas (default) / Modin / Vaex** — delegate to pyarrow (= duplicate); Vaex also stale.
- **BlazingSQL** (archived ~2021), **Quokka** (dormant), **Rockset** (OpenAI-acquired, shut down) — dead.
- **Vortex** — a different *file format*; testing it means converting the Parquet first, which changes the file under test. Tracked for the lakehouse-format thread, not here.
- **cuDF** — genuinely distinct GPU reader, but needs a CUDA GPU (not on this box).
- **Velox/Prestissimo, Impala, Hyper, Databend, Drill, Bodo** — distinct readers worth a future pass; held as stretch on setup effort (Prestissimo native workers; Impala needs HMS; Hyper proprietary; Databend stage setup; Drill storage-plugin config; Bodo's reader likely Arrow-C++-correlated).

## Cloud-only (would extend the study; need an account, can't run on one local box)

Snowflake, BigQuery, Athena (Presto/Trino-lineage), Redshift Spectrum, Databricks SQL/**Photon** (distinct C++ reader — high value if cloud access appears), Firebolt, ClickHouse Cloud (= local CH reader), MotherDuck (= DuckDB reader).

## Implementation outcomes (2026-06-06)

What actually wired into `multi_engine_correctness.py`, after building each runner:

- **Wired and passing ground truth:** DuckDB, DataFusion, Polars, pyarrow, Daft, Trino, ClickHouse-server,
  Spark, StarRocks, Dremio, Postgres (native-load baseline). 13 distinct readers/executors counting the
  controls.
- **Wired and FAILING (the findings):** chDB Parquet (`=`/`IN` undercount via default-on Bloom-filter
  pushdown — `CHDB-UPSTREAM-BUG-REPORT.md`); fastparquet (mis-decodes DuckDB's `PLAIN_DICTIONARY` —
  `FASTPARQUET-DECODE-NOTE.md`). Two *distinct readers* return silently wrong answers.
- **Attempted, deferred with a concrete reason (recorded as unavailable in the artifact, not skipped
  silently):**
  - **RisingWave** — its `file_scan()` table function supports only `s3`, `gcs`, `azblob` backends in
    2.8.4; there is **no local-filesystem (`posix_fs`) backend**, so a local-Parquet read isn't possible
    without standing up an S3 shim (seaweedfs is on the box, but its reader is arrow-rs — no distinct decode
    path, so the shim buys nothing for this study). Postgres-wire, single-container, otherwise ready.
  - **Feldera** — needs a per-file SQL program compiled into a running pipeline to ingest the file and a
    materialized view to read the count back; its Parquet ingest rides arrow-rs (re-confirms DataFusion).
    High setup, no distinct reader — deliberately deferred.

## Note on the streaming engines (the Feldera/RisingWave ask)

Feldera and RisingWave are genuinely interesting — distinct *execution models* (incremental DBSP / streaming
materialized views) — but their Parquet *ingestion* rides the **arrow-rs** reader, so for catching a reader
bug they re-confirm DataFusion rather than adding a new decode path. They're included for audience breadth
and labeled accordingly, not counted as independent readers. RisingWave is the lower-effort of the two
(single container, Postgres wire, `file_scan('parquet', …)`); Feldera requires authoring + compiling a SQL
program per file and reading the count back as a materialized view over its REST API.

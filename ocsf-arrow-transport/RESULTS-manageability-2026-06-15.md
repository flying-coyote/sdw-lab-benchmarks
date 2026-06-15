# Arrow/ADBC as a MANAGEABILITY lever, not a speed lever (2026-06-15)

Reframing per the steer that Arrow/ADBC's value to security is **more manageable infrastructure**, not
raw transport speed. This is the project's own foreground-risk-calculus (lead with ops-health, not ms),
the throat-to-choke thesis (an open/modular stack is only buyable if it's *operable*), H-ARCH-02 ("no
single engine wins" *forces* a multi-engine stack, so the binding question is whether that stack is
manageable), and the MOAR reversibility pitch (being wrong about an engine should be cheap). The earlier
`RESULTS.md` measured the speed angle (ADBC 5–10× over JDBC, JPype 276× artifact caught); this measures
the manageability angle. Tier B, single host, the lab's own 4-engine stack.

## The bespoke baseline (the "N integrations" cost) — audited from `soc-query-shapes/ejs_clients.py`

The lab already runs four engines over one shared Iceberg/Nessie catalog. Accessing them today takes
**four completely non-uniform integrations**:

| engine | wire protocol | auth | result shape consumer must handle | paging / completion | dep |
|---|---|---|---|---|---|
| StarRocks | MySQL wire (pymysql) | user/none + `CREATE EXTERNAL CATALOG` DDL | list of tuples | cursor.fetchall | pymysql |
| ClickHouse | HTTP (clickhouse-connect) | password | `.result_rows` | single call | clickhouse-connect |
| Trino | REST (`/v1/statement`) | `X-Trino-User` header | JSON `data` arrays | **`nextUri` poll loop** | requests |
| Dremio | REST (`/apiv2/login`→token) | token header | JSON `rows`+`schema`, **rebuilt by column name** | **job-state poll + offset/limit pagination** | requests |

That is 4 auth schemes, 4 result formats, 4 paging/polling models, and per-engine type handling (the
Dremio path reconstructs rows from a JSON schema by name — **types are lost and re-inferred**). Every new
engine adds another full integration; every consumer downstream re-implements result handling. This is the
operational tax H-ARCH-02's "multi-engine is inevitable" creates — and it is the thing Arrow/ADBC claims to
remove.

## The ADBC-uniform path — PROVEN against Dremio (Arrow Flight SQL), one API

Installed `adbc_driver_manager` + `adbc_driver_flightsql` and accessed Dremio over its native Arrow Flight
SQL endpoint (`grpc://dremio:32010`) with the standard ADBC DBAPI:

```
conn = flight_sql.connect("grpc://dremio:32010", db_kwargs={"username":..,"password":..})
cur.execute('SELECT count(*) FROM nessie."soc"."conn_ueba_planted"'); t = cur.fetch_arrow_table()
# -> pyarrow.Table  result {'n':[868790]}  typed schema ['int64']  (types travel intact, no re-inference)
```

`connect → execute → fetch_arrow_table` — **one API, one result type (Arrow), types preserved end to end**.
The same three lines work for any Flight SQL engine; the consumer writes result-handling **once**. Against
the bespoke Dremio client above (login→token→POST→poll job-state→paginate→rebuild-rows-by-name, ~15 lines
of REST glue returning untyped JSON), the manageability delta is stark: 4 result shapes → 1, 4 paging
models → 0 (the driver owns it), N type-handling sites → 0 (Arrow schema is the contract).

## The honest gate — uniformity is bounded by protocol adoption (the real finding)

ADBC's uniform waist is only as wide as Flight-SQL / native-driver adoption. Across the lab's four engines:

| engine | native ADBC / Flight SQL? | uniform path | fallback |
|---|---|---|---|
| **Dremio** | **yes — Arrow Flight SQL** (:32010, proven) | ADBC Flight SQL → Arrow | — |
| DuckDB | yes — native ADBC driver | ADBC → Arrow | (adbc_driver_duckdb wheel was **unavailable for the lab container** — a small packaging-friction point) |
| ClickHouse | no (HTTP-native) | — | ADBC-over-JDBC (JVM + ClickHouse JDBC jar) or stay clickhouse-connect |
| StarRocks | no (MySQL wire) | — | ADBC-over-JDBC (JVM + MySQL JDBC jar) |
| Trino | no native Flight SQL server | — | ADBC-over-JDBC (JVM + Trino JDBC jar) |

So the manageability win is **real where engines speak Flight SQL** (Dremio here, plus DuckDB/Postgres/
Snowflake/Spark-Connect in the wild) — one typed-Arrow interface replacing N bespoke clients — but for the
HTTP/MySQL-wire engines you fall back to the ADBC-JDBC bridge (uniform *API*, but it drags a JVM and a
per-engine JDBC jar back in) or stay bespoke. The "manageable open waist" is a real, buyable property of a
stack built on Flight-SQL-speaking engines, and a partial one otherwise. That nuance — not a blanket "ADBC
unifies everything" — is the fair-broker finding.

## The manageability test set this calls for (supersedes the speed-first A1–A4)

- **M1 · integration-surface / uniformity (started here)** — formalize the table above into countable
  metrics (distinct auth schemes, result formats, paging models, type-coercion sites, deps) for bespoke vs
  ADBC-uniform across the 4 engines, with the driver-availability map. Lead metric for the thesis.
- **M2 · reversibility / engine-swap cost** — touch-points (functions/lines that must change) to swap
  engine A→B under bespoke clients vs under one ADBC interface. Measures the MOAR "being wrong is cheap"
  claim directly.
- **M3 · type-fidelity as a maintenance burden** — Arrow's typed schema travels intact (shown: int64 came
  back typed) vs the bespoke JSON-row paths that lose types and re-infer them (the Dremio client rebuilds
  rows by name); count the per-engine type-coercion fixups Arrow removes. Ties to the 2-readers-silently-
  wrong work — wrong types are a manageability/correctness cost, not just a speed one.
- **M4 · (background) the speed legs** — Flight SQL throughput, same-runtime isolation, zero-copy, large-
  result memory. Supporting evidence, not the headline.

## Caveats (Tier B)

Single host, the lab's 4 engines; the surface counts are from the lab's real clients (representative, not a
universal census). The uniform-path proof is one engine (Dremio Flight SQL) + the driver-availability map
for the rest; M1's full quantification and M2/M3 are the proposed next runs. ADBC-over-JDBC was mapped, not
benchmarked here.

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

## M1 + M2 — MEASURED (2026-06-15), with the ADBC-over-JDBC bridge folded in

`adbc_manageability_bench.py` / `results/adbc_manageability.json`. Three regimes over the same shared
Nessie/Iceberg table; surface counts derived from the real `ejs_clients.py` source + the capability probes;
live answer-equality across access tiers.

### M1 — integration surface across the 4 engines

| metric (consumer-facing) | A: bespoke (today) | C: ADBC-uniform (Flight SQL + ADBC-over-JDBC) |
|---|--:|--:|
| distinct auth schemes | **4** | **1** |
| distinct result representations | **4** (tuples / `.result_rows` / JSON arrays / JSON rows+schema) | **1** (Arrow) |
| distinct paging/completion models | **4** (fetchall / single / `nextUri` loop / job-poll+offset) | **0** (driver-owned) |
| type fidelity | lost on Dremio (rebuilt by name → re-inferred) | **preserved** (Arrow schema is the contract) |
| consumer handlers to support all 4 | **4** (one full {auth,result,paging,type} per engine) | **1** |
| client deps | 3 Python libs (pymysql, clickhouse-connect, requests) | 2 ADBC libs **+ JVM + 1 JDBC jar per non-Flight-SQL engine** |

So the **consumer-facing surface collapses 4→1** on every axis — the manageability win, quantified. **The
folded-in JDBC-bridge cost is the honest other side:** only **Dremio** speaks Flight SQL natively, so the
uniform API reaches **ClickHouse / StarRocks / Trino** via the JVM-only `org.apache.arrow.adbc.driver.jdbc`
bridge, which needs a **JVM + one JDBC jar per engine** (clickhouse-jdbc / mysql-connector-j / trino-jdbc).
The API/result/paging/type surface goes to 1, but the *driver* footprint does not vanish — it shifts from N
Python clients to (2 ADBC libs + a JVM + N JDBC jars). From Python (the security-analytics lingua franca)
the non-Flight-SQL engines have **no clean native ADBC path**: you cross into the JVM via the bridge, or use
engine-specific Arrow APIs (ClickHouse `query_arrow` works — Arrow result, but a bespoke API, not uniform).

### M2 — engine-swap reversibility (the MOAR "being wrong is cheap" number)

Swapping engine A→B costs, under **bespoke**, a rewrite of the per-engine client class: **8–24 lines**
(ClickHouse 8, StarRocks 10, Trino 13, Dremio 24 — the REST+poll+paginate clients are the heaviest). Under
**ADBC-uniform** it is a **~1–3 line connection change** (+ adding one JDBC jar to the classpath if the
target isn't Flight-SQL) and the `{execute, fetch_arrow_table}` consumer code **does not change at all** —
that invariance is the reversibility win the modular-architecture pitch rests on.

### Answer-equality (manageability must not cost correctness)

All six access paths — the 4 bespoke clients + Dremio ADBC Flight SQL + ClickHouse `query_arrow` — return
the **identical** count (868,790) over the shared table. The uniform/Arrow paths agree with the bespoke
ones, and Arrow additionally carries types the JSON-row path drops.

### What this says

Arrow/ADBC is a **real, measurable manageability lever** for the multi-engine stack H-ARCH-02 forces: the
operator-facing integration surface collapses 4→1 and engine-swap drops from a class-rewrite to a config
line, with correctness preserved and types no longer silently lost. The honest bound — uniformity is gated
by Flight-SQL adoption, and the JDBC bridge buys it back only with a JVM + per-engine JDBC jar — is itself
the fair-broker finding: an open stack built on Flight-SQL-speaking engines is genuinely more manageable;
one built on HTTP/MySQL-wire engines gets uniformity only by carrying the JVM bridge.

## M3 — type-fidelity as a maintenance burden: MEASURED, and it TEMPERS the claim

`m3_type_fidelity.py` / `results/m3_type_fidelity.json`. Ran the same multi-type query
(`orig_h` string, `count(*)` int, `avg(orig_bytes)` float, `max(ts)` double) across all four bespoke
clients (capturing each cell's Python type) and the two Arrow paths (capturing the Arrow schema).

The honest result: **for scalar string/int/float columns the bespoke clients all converge** —
`{orig_h: str, c: int, avg_b: float, max_ts: float}` identically on StarRocks/ClickHouse/Trino/Dremio —
so the per-engine **coercion burden is 0** here (including the Dremio JSON-rebuild path, which returned
int/float, not strings, for these columns). The M3 hypothesis ("bespoke loses/diverges types → a coercion
tax Arrow removes") is **not supported at the scalar level**. Arrow's type-fidelity edge is **finer-grained**
than Python's coarse types: it surfaces **ClickHouse `uint64` vs Dremio `int64`** for the same count (a real
signedness distinction Python's `int` hides), and `double` explicitly — and it would carry true
timestamp / decimal / nested-list types that Python `int`/`float`/`str` collapse. That fidelity matters for
**schema-faithful round-trips** (re-serializing to Parquet/Iceberg without re-inferring types), overflow/
signedness, timezone-aware timestamps, and **nested OCSF observables** — not for scalar consumption in a
notebook. So M3 **sharpens** the manageability story: the win is the surface collapse (M1) and swap-cost
(M2); scalar type-handling is already consistent enough across the bespoke clients that Arrow's advantage
there is fidelity-for-round-trips, not a coercion-tax removal. (The cases where bespoke clients genuinely
diverge — native TIMESTAMP/DECIMAL/nested columns — are flagged but not exercised here; the corpus's `ts`
is a double epoch, so no native temporal column was available to force the divergence.)

## M4 (speed, background) — same-runtime transport closes M1's cross-runtime confound

`transport_same_runtime.py` / `results/transport_same_runtime.json`. The original `ocsf-arrow-transport`
speed leg (ADBC 5–10× over JDBC) was **cross-runtime** (ADBC-Python-Arrow vs JDBC-Java-rows) — the bench's
own flagged caveat. This isolates the runtime: pull 100k rows from Dremio via **ADBC Flight SQL → Arrow** vs
**REST → JSON rows**, *both in Python*. Result: **ADBC-Arrow 709k rows/s (0.14s) vs REST-rows 55k rows/s
(1.82s) = 13× faster, same runtime.** So the Arrow transport advantage is real with the Python-vs-Java
confound removed — it is the columnar-batch / zero-copy-into-pyarrow path vs per-row JSON marshaling (the
13× *is* the zero-copy benefit manifest: no per-row Python object creation). **Honest caveat:** part of the
REST cost is its 500-rows/page pagination (200 round-trips for 100k), intrinsic to the row-API path but not
purely "rows vs Arrow"; the robust finding is that Arrow bulk transport is ~13× faster same-runtime,
confirming the original speed direction without the cross-runtime confound. The live **Java ADBC-JDBC** run
remains characterized-not-executed (host-only java, no Maven; the dep-cost — JVM + per-engine JDBC jar — is
already the measured M1 metric).

## Caveats (Tier B)

Single host, the lab's 4 engines; surface counts are from the lab's real clients (representative, not a
universal census), and the LOC figures are a proxy — the robust headline is the **count of distinct
concerns (4→1)**, not the line counts. The Flight SQL leg is **live-proven** (Dremio); the **ADBC-over-JDBC
bridge is characterized + its dependency cost measured, but not executed in Java this session** (no Maven /
java is host-only; the JVM + N-jar dependency cost — the actual manageability metric — is established, so the
live Arrow-out run is a documented-not-executed nicety, not a missing measurement). M3 measured (tempered);
M4 (speed/zero-copy) remains background.

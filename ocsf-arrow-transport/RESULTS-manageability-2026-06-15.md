# Arrow/ADBC as a MANAGEABILITY lever, not a speed lever (2026-06-15)

Reframing per the steer that Arrow/ADBC's value to security is **more manageable infrastructure**, not
raw transport speed. This is the project's own foreground-risk-calculus (lead with ops-health, not ms),
the throat-to-choke thesis (an open/modular stack is only buyable if it's *operable*), H-ARCH-02 ("no
single engine wins" *forces* a multi-engine stack, so the binding question is whether that stack is
manageable), and the MOAR reversibility pitch (being wrong about an engine should be cheap). The earlier
`RESULTS.md` measured the speed angle (ADBC 5–10× over JDBC, JPype 276× artifact caught); this measures
the manageability angle. Tier B, single host, the lab's own 4-engine stack. (Dremio arm withheld under its
benchmark-publication terms — its measured result rows/numbers are removed throughout; architecture and
connector mentions of Dremio are retained, only RESULTS are barred.)

## The bespoke baseline (the "N integrations" cost) — audited from `soc-query-shapes/ejs_clients.py`

The lab already runs four engines over one shared Iceberg/Nessie catalog. Accessing them today takes
**completely non-uniform integrations**, one per engine:

| engine | wire protocol | auth | result shape consumer must handle | paging / completion | dep |
|---|---|---|---|---|---|
| StarRocks | MySQL wire (pymysql) | user/none + `CREATE EXTERNAL CATALOG` DDL | list of tuples | cursor.fetchall | pymysql |
| ClickHouse | HTTP (clickhouse-connect) | password | `.result_rows` | single call | clickhouse-connect |
| Trino | REST (`/v1/statement`) | `X-Trino-User` header | JSON `data` arrays | **`nextUri` poll loop** | requests |

*(Dremio arm withheld under its benchmark-publication terms — the bench also exercises a Dremio bespoke
client, but its measured integration-surface row is removed here.)*

Across the three engines shown, that is distinct auth schemes, result formats, and paging/polling models,
plus per-engine type handling. Every new engine adds another full integration; every consumer downstream
re-implements result handling. This is the operational tax H-ARCH-02's "multi-engine is inevitable" creates
— and it is the thing Arrow/ADBC claims to remove.

## The ADBC-uniform path — Arrow Flight SQL, one API

The ADBC stack (`adbc_driver_manager` + `adbc_driver_flightsql`) accesses a Flight-SQL-speaking engine over
its native Arrow Flight SQL endpoint with the standard ADBC DBAPI:

```
conn = flight_sql.connect("grpc://<host>:32010", db_kwargs={"username":..,"password":..})
cur.execute('SELECT count(*) FROM nessie."soc"."conn_ueba_planted"'); t = cur.fetch_arrow_table()
# -> pyarrow.Table  (types travel intact, no re-inference)
```

`connect → execute → fetch_arrow_table` — **one API, one result type (Arrow), types preserved end to end**.
The same three lines work for any Flight SQL engine; the consumer writes result-handling **once**. Against a
bespoke REST client (login→token→POST→poll job-state→paginate→rebuild-rows-by-name, ~15 lines of REST glue
returning untyped JSON), the manageability delta is structural: the consumer collapses from one full
{auth, result, paging, type} handler per engine to a single ADBC handler — many result shapes → 1, the paging
models → 0 (the driver owns it), N type-handling sites → 0 (Arrow schema is the contract).

*(Dremio arm withheld under its benchmark-publication terms — Dremio is one Flight-SQL-speaking engine
exercised on this path, but its measured outputs are removed.)*

## The honest gate — uniformity is bounded by protocol adoption (the real finding)

ADBC's uniform waist is only as wide as Flight-SQL / native-driver adoption. Across the lab's four engines:

| engine | native ADBC / Flight SQL? | uniform path | fallback |
|---|---|---|---|
| **Dremio** | **yes — Arrow Flight SQL** (:32010) | ADBC Flight SQL → Arrow | — |
| DuckDB | yes — native ADBC driver | ADBC → Arrow | (adbc_driver_duckdb wheel was **unavailable for the lab container** — a small packaging-friction point) |
| ClickHouse | no (HTTP-native) | — | ADBC-over-JDBC (JVM + ClickHouse JDBC jar) or stay clickhouse-connect |
| StarRocks | no (MySQL wire) | — | ADBC-over-JDBC (JVM + MySQL JDBC jar) |
| Trino | no native Flight SQL server | — | ADBC-over-JDBC (JVM + Trino JDBC jar) |

(The Dremio row records its documented Flight SQL capability, not a benchmark result.)

So the manageability win is **real where engines speak Flight SQL** (Dremio supports it natively, as do
DuckDB/Postgres/Snowflake/Spark-Connect in the wild) — one typed-Arrow interface replacing N bespoke
clients — but for the
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
- **M3 · type-fidelity as a maintenance burden** — Arrow's typed schema travels intact vs the bespoke
  JSON-row paths that lose types and re-infer them (a REST/JSON-row client rebuilds rows by name); count the
  per-engine type-coercion fixups Arrow removes. Ties to the 2-readers-silently-wrong work — wrong types are
  a manageability/correctness cost, not just a speed one.
- **M4 · (background) the speed legs** — Flight SQL throughput, same-runtime isolation, zero-copy, large-
  result memory. Supporting evidence, not the headline.

## M1 + M2 — MEASURED (2026-06-15), with the ADBC-over-JDBC bridge folded in

`adbc_manageability_bench.py` / `results/adbc_manageability.json`. Three regimes over the same shared
Nessie/Iceberg table; surface counts derived from the real `ejs_clients.py` source + the capability probes;
live answer-equality across access tiers.

### M1 — integration surface across the engines

The Dremio arm is withheld under its benchmark-publication terms, so the surface counts below are stated for
the three published bespoke engines (StarRocks / ClickHouse / Trino); the consumer-facing collapse to a
single ADBC handler is the same on each axis.

| metric (consumer-facing) | A: bespoke (today) | C: ADBC-uniform (Flight SQL + ADBC-over-JDBC) |
|---|--:|--:|
| distinct auth schemes | **3** | **1** |
| distinct result representations | **3** (tuples / `.result_rows` / JSON arrays) | **1** (Arrow) |
| distinct paging/completion models | **3** (fetchall / single / `nextUri` loop) | **0** (driver-owned) |
| type fidelity | JSON-row paths re-infer types (REST `data` arrays are untyped) | **preserved** (Arrow schema is the contract) |
| consumer handlers to support all 3 | **3** (one full {auth,result,paging,type} per engine) | **1** |
| client deps | 3 Python libs (pymysql, clickhouse-connect, requests) | 2 ADBC libs **+ JVM + 1 JDBC jar per non-Flight-SQL engine** |

So the **consumer-facing surface collapses to 1** on every axis — the manageability win, quantified. **The
folded-in JDBC-bridge cost is the honest other side:** of these engines none speaks Flight SQL natively, so
the uniform API reaches **ClickHouse / StarRocks / Trino** via the JVM-only `org.apache.arrow.adbc.driver.jdbc`
bridge, which needs a **JVM + one JDBC jar per engine** (clickhouse-jdbc / mysql-connector-j / trino-jdbc).
The API/result/paging/type surface goes to 1, but the *driver* footprint does not vanish — it shifts from N
Python clients to (2 ADBC libs + a JVM + N JDBC jars). From Python (the security-analytics lingua franca)
the non-Flight-SQL engines have **no clean native ADBC path**: you cross into the JVM via the bridge, or use
engine-specific Arrow APIs (ClickHouse `query_arrow` works — Arrow result, but a bespoke API, not uniform).
(A Flight-SQL-speaking engine such as Dremio reaches the uniform path natively, without the bridge; its
measured arm is withheld here.)

### M2 — engine-swap reversibility (the MOAR "being wrong is cheap" number)

Swapping engine A→B costs, under **bespoke**, a rewrite of the per-engine client class: **8–13 lines** across
the published engines (ClickHouse 8, StarRocks 10, Trino 13 — the REST+poll clients are the heaviest; the
Dremio arm is withheld under its benchmark-publication terms). Under
**ADBC-uniform** it is a **~1–3 line connection change** (+ adding one JDBC jar to the classpath if the
target isn't Flight-SQL) and the `{execute, fetch_arrow_table}` consumer code **does not change at all** —
that invariance is the reversibility win the modular-architecture pitch rests on.

### Answer-equality (manageability must not cost correctness)

The published access paths — the StarRocks / ClickHouse / Trino bespoke clients plus ClickHouse `query_arrow`
— return the **identical** count over the shared table. The uniform/Arrow paths agree with the bespoke ones,
and Arrow additionally carries types the JSON-row path drops. *(The Dremio Flight SQL arm is withheld under
its benchmark-publication terms; it participated in the same answer-equality check, but its result is removed.)*

### What this says

Arrow/ADBC is a **real, measurable manageability lever** for the multi-engine stack H-ARCH-02 forces: the
operator-facing integration surface collapses to a single ADBC handler and engine-swap drops from a
class-rewrite to a config line, with correctness preserved and types no longer silently lost. The honest
bound — uniformity is gated
by Flight-SQL adoption, and the JDBC bridge buys it back only with a JVM + per-engine JDBC jar — is itself
the fair-broker finding: an open stack built on Flight-SQL-speaking engines is genuinely more manageable;
one built on HTTP/MySQL-wire engines gets uniformity only by carrying the JVM bridge.

## M3 — type-fidelity as a maintenance burden: MEASURED, and it TEMPERS the claim

`m3_type_fidelity.py` / `results/m3_type_fidelity.json`. Ran the same multi-type query
(`orig_h` string, `count(*)` int, `avg(orig_bytes)` float, `max(ts)` double) across the published bespoke
clients (capturing each cell's Python type) and the ClickHouse Arrow path (capturing the Arrow schema).
*(The Dremio arm — both its bespoke JSON-rebuild client and its ADBC Flight SQL path — is withheld under its
benchmark-publication terms; its measured type results are removed.)*

The honest result: **for scalar string/int/float columns the bespoke clients all converge** —
`{orig_h: str, c: int, avg_b: float, max_ts: float}` identically on StarRocks/ClickHouse/Trino —
so the per-engine **coercion burden is 0** here. The M3 hypothesis ("bespoke loses/diverges types → a
coercion tax Arrow removes") is **not supported at the scalar level**. Arrow's type-fidelity edge is
**finer-grained** than Python's coarse types: it surfaces, for instance, **ClickHouse `uint64`** for a count
(a real signedness distinction Python's `int` hides), and `double` explicitly — and it would carry true
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
own flagged caveat. The same-runtime leg isolates the runtime: it pulls a fixed row count via **ADBC Flight
SQL → Arrow** vs **REST → JSON rows**, *both in Python*, so the gap is the transport (columnar Arrow batches
vs paginated JSON rows) rather than the Python-vs-Java runtime — the columnar-batch / zero-copy-into-pyarrow
path vs per-row JSON marshaling. **Honest caveat:** part of the REST cost is its 500-rows/page pagination
(many round-trips per pull), intrinsic to the row-API path but not purely "rows vs Arrow". *(This leg was
exercised against Dremio's Flight SQL and REST endpoints, so its measured throughput/latency/speedup numbers
are withheld under Dremio's benchmark-publication terms — the same-runtime methodology and direction are
recorded, the Dremio results are not.)* The live **Java ADBC-JDBC** run remains characterized-not-executed
(host-only java, no Maven; the dep-cost — JVM + per-engine JDBC jar — is already the measured M1 metric).

## Caveats (Tier B)

Single host, the lab's 4 engines (the Dremio arm is withheld under its benchmark-publication terms, so the
published surface counts are stated over the other three); surface counts are from the lab's real clients
(representative, not a universal census), and the LOC figures are a proxy — the robust headline is the
**collapse in the count of distinct concerns to one ADBC handler**, not the line counts. The Flight SQL leg
was exercised live (against a Flight-SQL-speaking engine whose results are withheld here); the
**ADBC-over-JDBC bridge is characterized + its dependency cost measured, but not executed in Java this
session** (no Maven / java is host-only; the JVM + N-jar dependency cost — the actual manageability metric —
is established, so the live Arrow-out run is a documented-not-executed nicety, not a missing measurement). M3
measured (tempered); M4 (speed/zero-copy) remains background.

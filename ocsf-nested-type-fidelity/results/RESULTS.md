# Cross-engine nested-OCSF type fidelity

**Tier B · single machine · deterministic.** OCSF events are nested — `src_endpoint`/`dst_endpoint` structs and
an `observables[]` list of structs — and a real hunt filters on exactly those. This asks whether the SAME nested
data returns the SAME answer across engines, and how far nested access stays portable. One byte-identical Parquet
file, explicit ground-truth counts, each engine given its fair best expression (probe-verified). Engines: pyarrow `23.0.1`, duckdb `1.5.3`, datafusion `53.0.0`, chdb `4.1.8`, polars `1.41.2`.

The artifact is pinned (the [methodology](../BENCHMARKING-METHODOLOGY.md) rule): logical fingerprint
`10c8b03e4c8bcae971cc6aa829bddaaf`, 1000 rows in 1 row group(s), columns
`time, class_uid, src_endpoint, dst_endpoint, observables`, sha256 `1718ddac89567358…`.

## Results

| question | kind | truth | duckdb | datafusion | chdb | polars |
|---|---|---|---|---|---|---|
| `count(*)` | baseline | 1000 | ✅ | ✅ | ✅ | ✅ |
| `src_endpoint.ip = '10.0.0.1'` | struct string | 500 | ✅ | ✅ | ✅ | ✅ |
| `dst_endpoint.port = 3389` | struct int | 125 | ✅ | ✅ | ✅ | ✅ |
| `src_endpoint.port = 30000` | struct int | 250 | ✅ | ✅ | ✅ | ✅ |
| `len(observables) = 3` | list length | 250 | ✅ | ✅ | ✅ | ✅ |
| `any observable.type_id = 21` | list<struct> predicate | 250 | ✅ | ⚠️ err (Exception: DataFusion error: type_coercion caused by Execution error: Cannot access field at argument) | ✅ | ✅ |
| `any observable.type_id = 2` | list<struct> predicate | 1000 | ✅ | ⚠️ err (Exception: DataFusion error: type_coercion caused by Execution error: Cannot access field at argument) | ✅ | ✅ |

✅ = matches the ground-truth count · ❌ = diverges (engine's count in parens) · ⚠️ err = the engine could not
express the nested access (detail in parens).

## Reading

Scalar access into a struct (`src_endpoint.port`, `dst_endpoint.ip`) and list cardinality (`len(observables)`)
are **portable**: DuckDB, DataFusion, chDB, and Polars all read the same nested bytes and return the same count,
so the open read contract holds through one level of nesting. The boundary is the **list-of-struct field
predicate** — "does any observable carry `type_id = 21`", which is the natural way to ask an OCSF `observables[]`
question. DuckDB (`list_filter` with a lambda), chDB (`arrayExists`), and Polars (`list.eval`) all express it and
agree; DataFusion cannot apply a per-element struct-field predicate inside a `WHERE` clause (it errors on field
access across the list), so the same hunt that runs on three engines doesn't run on the fourth without rewriting
it as an `UNNEST` subquery.

Portable here: `count(*)`, `src_endpoint.ip = '10.0.0.1'`, `dst_endpoint.port = 3389`, `src_endpoint.port = 30000`, `len(observables) = 3`.

Not portable across all four:
- `any observable.type_id = 21` — datafusion errored (Exception: DataFusion error: type_coercion caused by Execution error: Cannot access field at argument)
- `any observable.type_id = 2` — datafusion errored (Exception: DataFusion error: type_coercion caused by Execution error: Cannot access field at argument)

The transferable point: an open table format guarantees every engine can *read the bytes*, not that every engine
can *ask the same nested question the same way*. This is a concrete reason teams flatten OCSF observables into
their own columns or a side table before querying — flattening trades schema fidelity for query portability, and
the trade is real, measured here at the list-of-struct boundary. The per-engine table is version-bound (the
divergence is a DataFusion capability gap on this version, not a law); re-run on upgrade.

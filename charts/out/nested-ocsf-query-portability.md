# Cross-engine nested-OCSF query portability

*Whether the same nested OCSF data (`src_endpoint`/`dst_endpoint` structs, an `observables[]` list of structs) returns the same answer across engines, and how far nested access stays portable — one byte-identical Parquet file, explicit ground-truth counts, each engine given its fair best expression.*

*Tier B · single machine · deterministic · version-bound: pyarrow 23.0.1, duckdb 1.5.3, datafusion 53.0.0, chdb 4.1.8, polars 1.41.2 (logical fingerprint `10c8b03e4c8bcae971cc6aa829bddaaf`, 1000 rows). The divergence is a DataFusion capability gap on this version, not a law; re-run on upgrade.*

| question | kind | truth | duckdb | datafusion | chdb | polars |
|---|---|---:|:---:|:---:|:---:|:---:|
| `count(*)` | baseline | 1000 | ✅ | ✅ | ✅ | ✅ |
| `src_endpoint.ip = '10.0.0.1'` | struct string | 500 | ✅ | ✅ | ✅ | ✅ |
| `dst_endpoint.port = 3389` | struct int | 125 | ✅ | ✅ | ✅ | ✅ |
| `src_endpoint.port = 30000` | struct int | 250 | ✅ | ✅ | ✅ | ✅ |
| `len(observables) = 3` | list length | 250 | ✅ | ✅ | ✅ | ✅ |
| `any observable.type_id = 21` | list&lt;struct&gt; predicate | 250 | ✅ | ⚠️ err | ✅ | ✅ |
| `any observable.type_id = 2` | list&lt;struct&gt; predicate | 1000 | ✅ | ⚠️ err | ✅ | ✅ |

*✅ = matches the ground-truth count · ⚠️ err = the engine could not express the nested access. DataFusion's error on both list-of-struct predicates: `type_coercion caused by Execution error: Cannot access field at argument`.*

**Security-relevant cell: the `any observable.type_id = 21` list-of-struct predicate — the DataFusion nested-predicate gap.** Scalar struct access (`src_endpoint.port`, `dst_endpoint.ip`) and list cardinality (`len(observables)`) are portable across all four engines, so the open read contract holds through one level of nesting. The boundary is asking "does any observable carry `type_id = 21`" — the natural way to query an OCSF `observables[]` field. DuckDB (`list_filter` with a lambda), chDB (`arrayExists`), and Polars (`list.eval`) all express it and agree on 250; DataFusion cannot apply a per-element struct-field predicate inside a `WHERE` clause, so the same hunt that runs on three engines doesn't run on the fourth without rewriting it as an `UNNEST` subquery. An open table format guarantees every engine can read the bytes, not that every engine can ask the same nested question the same way — a concrete reason teams flatten OCSF observables into their own columns before querying.

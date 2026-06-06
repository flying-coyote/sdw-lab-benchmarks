# Cross-engine nested-OCSF type fidelity

The answer-equivalence work so far stayed on flat scalar columns — `count`, `sum`, equality point-lookups. But
OCSF events aren't flat: an event carries `src_endpoint`/`dst_endpoint` structs and an `observables[]` list of
structs, and a real hunt filters on exactly those (`dst_endpoint.port = 3389`, "is any observable a flagged
indicator"). So this bench asks the nested version of the same question: does the SAME nested data return the
SAME answer across engines, and how far does nested access stay portable? One byte-identical Parquet file,
explicit ground-truth counts, and each engine given its fair best expression (probe-verified per engine, so a
divergence is a real capability gap rather than a syntax strawman).

## Result (Tier B)

Engines: DuckDB `1.5.3`, DataFusion `53.0.0`, chDB `4.1.8` (SQL), and Polars `1.41.2` (the dataframe API).

**Portable through one level of nesting.** Scalar access into a struct (`src_endpoint.ip`, `dst_endpoint.port`,
`src_endpoint.port`) and list cardinality (`len(observables)`) return the identical count on all four engines.
The open read contract holds here: the same nested bytes, the same answer, whether you reach the field with
DuckDB's dot, DataFusion's bracket, chDB's tuple dot, or Polars' `struct.field`.

**The boundary is the list-of-struct field predicate.** "Does any observable carry `type_id = 21`" is the
natural way to ask an OCSF `observables[]` question, and it is *not* portable. DuckDB (`list_filter` with a
lambda), chDB (`arrayExists`), and Polars (`list.eval`) all express it and agree (250, and 1000 for the
present-in-every-row case); **DataFusion cannot apply a per-element struct-field predicate inside a `WHERE`
clause** — it errors with `Cannot access field at argument` on field access across the list, so the same hunt
that runs on three engines doesn't run on the fourth without rewriting it as an `UNNEST` subquery.

The transferable point: an open table format guarantees every engine can *read the bytes*, not that every engine
can *ask the same nested question the same way*. That gap at the list-of-struct boundary is a concrete reason
teams flatten OCSF observables into their own columns or a side table before querying — flattening trades schema
fidelity for query portability, and the trade is real, measured here rather than asserted. Full table in
[results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
pip install -r ocsf-nested-type-fidelity/requirements.txt
python ocsf-nested-type-fidelity/run.py
```

Deterministic; the corpus is seeded off `lib.common` and the artifact is pinned (logical fingerprint +
structural manifest + byte hash, per [BENCHMARKING-METHODOLOGY.md](../BENCHMARKING-METHODOLOGY.md) §9). The
per-engine table is version-bound — the DataFusion gap is a capability of this release, not a law, so re-run on
upgrade. Tier B, single machine. Extends H-ENGINE-ANSWER-EQUIVALENCE-01 from reader bugs and query semantics
into the nested type system: a third class of where the same question gets a different (or no) answer.

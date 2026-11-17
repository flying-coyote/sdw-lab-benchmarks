# Cross-engine nested-OCSF type fidelity

## What it measures

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

### What changed on current builds (2026-11-16, the current result)

The June table holds for the June versions and was reproduced on them exactly. On current builds two
cells move, and both are about how the question is written rather than what the engine reads
([results/RESULTS-RERUN-2026-11-16.md](results/RESULTS-RERUN-2026-11-16.md)). DuckDB 2.0.0 rejects the
harness's `x -> x.type_id = 21` lambda as deprecated syntax, and the `lambda x:` form returns 250 on both
1.5.3 and 2.0.0. DataFusion 55.0.0 answers the list-of-struct predicate with `array_any_match` when its
SQL parser dialect is set to `duckdb`, `databricks` or `clickhouse`, and still errors under the default
`generic` dialect; on 53.0.0 that function does not exist, and an `UNNEST` rewrite returns the right count
on both. So "DataFusion cannot apply a per-element struct-field predicate" holds for 53.0.0, and for 55.0.0
under its default dialect only. The scalar-struct and list-length rows are unchanged.

## What would have made it fail

Each cell compares an engine's count with a truth the generator fixes, so a wrong count or an error is a
real outcome, and the engine-specific expressions were probed per engine so that an error reflects the
engine rather than a malformed query. The 2026-11-16 probe shows the limit of that guard: the June probe
did not try every dialect, so a "cannot express" cell means "not with the expressions tried".

## Pre-registration

None. No pre-registration file exists in this folder; the dialect probe is labelled post hoc.

## Reproduce

```bash
pip install -r ocsf-nested-type-fidelity/requirements.txt
python ocsf-nested-type-fidelity/run.py
python ocsf-nested-type-fidelity/dialect_probe_2026_11_16.py <parquet built by run.py> <out.json>
```

`run.py` rewrites `results/RESULTS.md` and `results/results.json`, so dated corrections live in this
README.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json` (2026-06-06).
- [results/RESULTS-RERUN-2026-11-16.md](results/RESULTS-RERUN-2026-11-16.md), with
  `results/rerun-2026-11-16-{june-pins,current}.json` and `results/dialect-probe-2026-11-16-*.json`, the
  current result. `rerun-2026-11-16-june-pins.json` is byte-identical to the June `results.json`.

## Versions and pins

`requirements.txt` pins the June set (pyarrow 23.0.1, DuckDB 1.5.3, DataFusion 53.0.0, chDB 4.1.8, Polars
1.41.2). The 2026-11-16 current set was pyarrow 26.0.1, DuckDB 2.0.0, DataFusion 55.0.0, chDB 4.4.0 and
Polars 2.1.0. The run did not record its `chdb-core`; the session's other 2026-11-16 re-run venvs resolved
`chdb-core` 26.11.1 under both wrappers (`../parquet-checksum-integrity/requirements-rerun-2026-11-16-*.txt`),
so the chDB rows are most likely bound to that core and not to the June one. *(corrected 2026-11-17: this
sentence earlier stated the 26.11.1 core as recorded for this folder's run.)*

## Evidence tier and limits

Tier B, single machine, a 1,000-row file in one row group. No timings are reported.

## Corrections

- *(corrected 2026-11-17: added the 2026-11-16 results as current; the June statement that DataFusion
  cannot express the list-of-struct predicate is now bound to DataFusion 53.0.0, and to 55.0.0 under its
  default parser dialect.)*

## Determinism and hypothesis mapping

Deterministic; the corpus is seeded off `lib.common` and the artifact is pinned (logical fingerprint +
structural manifest + byte hash, per [BENCHMARKING-METHODOLOGY.md](../BENCHMARKING-METHODOLOGY.md) §9). The
per-engine table is version-bound — the DataFusion gap is a capability of this release, not a law, so re-run on
upgrade. Tier B, single machine. Extends H-ENGINE-ANSWER-EQUIVALENCE-01 from reader bugs and query semantics
into the nested type system: a third class of where the same question gets a different (or no) answer.

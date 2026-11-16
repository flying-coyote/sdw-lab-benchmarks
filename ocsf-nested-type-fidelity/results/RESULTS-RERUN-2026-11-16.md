---
type: evidence
title: "Cross-engine nested-OCSF type fidelity: re-run on current builds (2026-11-16)"
created: 2026-11-16
tags: [ocsf, nested-types, query-portability, datafusion, duckdb, parquet, rerun]
---

# Re-run on current builds (2026-11-16)

Unmodified `run.py`, executed from a scratch copy so the June `RESULTS.md` stays the historical record, in two
fresh venvs. June pins (pyarrow 23.0.1, DuckDB 1.5.3, DataFusion 53.0.0, chDB 4.1.8, Polars 1.41.2) reproduce
June `RESULTS.md` exactly. Current builds: pyarrow 26.0.1, DuckDB 2.0.0, DataFusion 55.0.0, chDB 4.4.0,
Polars 2.1.0. Raw: `rerun-2026-11-16-current.json`. Tier B, single machine, deterministic.

| question | truth | DuckDB 2.0.0 | DataFusion 55.0.0 | chDB 4.4.0 | Polars 2.1.0 |
|---|---|---|---|---|---|
| `count(*)` | 1000 | 1000 | 1000 | 1000 | 1000 |
| `src_endpoint.ip = '10.0.0.1'` | 500 | 500 | 500 | 500 | 500 |
| `dst_endpoint.port = 3389` | 125 | 125 | 125 | 125 | 125 |
| `src_endpoint.port = 30000` | 250 | 250 | 250 | 250 | 250 |
| `len(observables) = 3` | 250 | 250 | 250 | 250 | 250 |
| any `observables[].type_id = 21` | 250 | error (harness form) | error | 250 | 250 |
| any `observables[].type_id = 2` | 1000 | error (harness form) | error | 1000 | 1000 |

**DuckDB 2.0.0.** The harness's `list_filter(observables, x -> x.type_id = 21)` raises `Binder Error: Deprecated
lambda arrow (->) detected`, with `SET lambda_syntax='ENABLE_SINGLE_ARROW'` named as the revert. The new form
`list_filter(observables, lambda x: x.type_id = 21)` returns 250 on DuckDB 2.0.0 and also on 1.5.3 (side
probe, 2026-11-16), so it is the form that works across both versions. This is an upgrade break that fails
loudly, not a capability gap.

**DataFusion 55.0.0.** Still raises `Cannot access field at argument 1: type List(Struct(...)) is not Struct,
Map, or Null` for `array_has(observables['type_id'], 21)` in a `WHERE` clause, as 53.0.0 did. An `UNNEST`
rewrite returns 250 (`SELECT count(DISTINCT r) FROM (SELECT row_number() OVER () r, unnest(observables) o FROM t)
WHERE o['type_id'] = 21`, side probe 2026-11-16).

## Post hoc dialect probe (2026-11-16, added after review; not pre-registered)

`dialect_probe_2026_11_16.py`, raw JSON `dialect-probe-2026-11-16-june-pins.json` and
`dialect-probe-2026-11-16-current.json`. The re-run above only retried the June DataFusion expression. On
DataFusion 55.0.0, `array_any_match(observables, x -> x['type_id'] = 21)` (and the `lambda x:` form) returns 250
(and 1000 for `type_id = 2`) with `datafusion.sql_parser.dialect` set to `duckdb`, `databricks` or `clickhouse`
(read back with `SHOW`), and fails under the default `generic` and under `postgres` (`No field named x` / parser
error). On 53.0.0 `array_any_match` does not exist under any dialect. The `UNNEST` rewrite returns 250 / 1000 on both
builds, and DuckDB `list_filter` with `lambda x:` returns 250 / 1000 on 1.5.3 and 2.0.0 (arrow form errors on
2.0.0 only). The June-pins nested reproduction is `rerun-2026-11-16-june-pins.json`. Single pass, one machine.

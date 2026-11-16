"""POST HOC probe (2026-11-16), added after the 2026-11-16 re-run and after an adversarial review found that the
re-run only retried the June DataFusion expression. Not pre-registered; not part of run.py's battery.

Asks the list-of-struct question ("does any observable carry type_id = N") with every expression form below, on
whichever DataFusion / DuckDB build is installed, and writes raw JSON:

  * DataFusion: the June form array_has(observables['type_id'], N); array_any_match with an arrow lambda and a
    `lambda x:` lambda; an UNNEST rewrite. Each under several values of datafusion.sql_parser.dialect, with the
    dialect read back via SHOW. Plus the session-zone cast side probe (CAST(TIMESTAMP ... AS TIMESTAMPTZ)
    under America/New_York and UTC).
  * DuckDB: list_filter with the arrow lambda (x -> ...) and with `lambda x:`.

    python dialect_probe_2026_11_16.py <parquet built by run.py> <out.json>

Tier B, single machine, single pass.
"""
import json
import sys
from datetime import datetime, timezone

P, OUT = sys.argv[1], sys.argv[2]
TRUTH = {21: 250, 2: 1000}
res = {"post_hoc": True, "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "parquet": P,
       "truth": TRUTH, "datafusion": {}, "duckdb": {}}


def _err(e):
    return {"error": f"{type(e).__name__}: {' '.join(str(e).split())[:200]}"}


import datafusion  # noqa: E402

res["datafusion"]["version"] = datafusion.__version__
DF_FORMS = {
    "array_has_june": "SELECT count(*) AS c FROM t WHERE array_has(observables['type_id'], {n})",
    "array_any_match_arrow": "SELECT count(*) AS c FROM t WHERE array_any_match(observables, x -> x['type_id'] = {n})",
    "array_any_match_lambda_kw": "SELECT count(*) AS c FROM t WHERE array_any_match(observables, lambda x: x['type_id'] = {n})",
    "unnest_rewrite": "SELECT count(DISTINCT r) AS c FROM (SELECT row_number() OVER () AS r, unnest(observables) AS o FROM t) "
                      "WHERE o['type_id'] = {n}",
}
for dialect in (None, "generic", "duckdb", "databricks", "clickhouse", "postgres"):
    ctx = datafusion.SessionContext()
    ctx.register_parquet("t", P)
    key = dialect or "default(unset)"
    cell = {}
    try:
        if dialect:
            ctx.sql(f"SET datafusion.sql_parser.dialect = '{dialect}'").collect()
        cell["dialect_readback"] = list(ctx.sql("SHOW datafusion.sql_parser.dialect").to_pydict().values())[-1][0]
    except Exception as e:  # noqa: BLE001
        cell["dialect_readback"] = _err(e)
    for name, q in DF_FORMS.items():
        for n in TRUTH:
            try:
                cell[f"{name}|type_id={n}"] = int(list(ctx.sql(q.format(n=n)).to_pydict().values())[0][0])
            except Exception as e:  # noqa: BLE001
                cell[f"{name}|type_id={n}"] = _err(e)
    res["datafusion"][key] = cell

cast = {}
for z in ("UTC", "America/New_York"):
    ctx = datafusion.SessionContext()
    ctx.sql(f"SET datafusion.execution.time_zone = '{z}'").collect()
    d = ctx.sql("SELECT CAST(TIMESTAMP '2026-06-06 12:00:00' AS TIMESTAMPTZ)::varchar AS v, "
                "arrow_typeof(CAST(TIMESTAMP '2026-06-06 12:00:00' AS TIMESTAMPTZ)) AS ty").to_pydict()
    cast[z] = {"value": d["v"][0], "type": d["ty"][0]}
res["datafusion"]["timestamptz_cast_side_probe"] = cast

import duckdb  # noqa: E402

res["duckdb"]["version"] = duckdb.__version__
con = duckdb.connect()
for name, lam in (("arrow", "x -> x.type_id = {n}"), ("lambda_kw", "lambda x: x.type_id = {n}")):
    for n in TRUTH:
        q = f"SELECT count(*) FROM read_parquet('{P}') WHERE len(list_filter(observables, {lam.format(n=n)})) > 0"
        try:
            res["duckdb"][f"list_filter_{name}|type_id={n}"] = int(con.execute(q).fetchone()[0])
        except Exception as e:  # noqa: BLE001
            res["duckdb"][f"list_filter_{name}|type_id={n}"] = _err(e)

json.dump(res, open(OUT, "w"), indent=2, sort_keys=True)
print(json.dumps(res, indent=1, sort_keys=True))

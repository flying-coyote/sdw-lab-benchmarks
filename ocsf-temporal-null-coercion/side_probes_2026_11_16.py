"""POST HOC side probes (2026-11-16), added after an adversarial review of the 2026-11-16 re-run. Not
pre-registered. Uses the null_coerce.parquet written by run_rerun_2026_11_16.py (same corpus as run.py).

  * NOT IN against a SUBQUERY allowlist that contains a NULL (the lookup-table form), all three engines.
  * chDB literal-list and subquery NOT IN (..., NULL) with transform_null_in = 0 and = 1.

    python side_probes_2026_11_16.py <null_coerce.parquet> <out.json>

Tier B, single machine, single pass. SQL-standard truth for every NOT IN (..., NULL) form is 0.
"""
import json
import sys
from datetime import datetime, timezone

P, OUT = sys.argv[1], sys.argv[2]
AL = "(SELECT 'allow1' AS v UNION ALL SELECT 'allow2' UNION ALL SELECT NULL)"
LIT = "s NOT IN ('allow1','allow2',NULL)"
SUB = f"s NOT IN (SELECT v FROM {AL} AS al)"
res = {"post_hoc": True, "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "truth": 0}


def err(e):
    return {"error": f"{type(e).__name__}: {' '.join(str(e).split())[:200]}"}


import duckdb, datafusion, chdb  # noqa: E401,E402
from chdb import session as chs  # noqa: E402

res["environment"] = {"duckdb": duckdb.__version__, "datafusion": datafusion.__version__, "chdb": chdb.__version__}
try:
    res["duckdb|subquery"] = int(duckdb.connect().execute(f"SELECT count(*) FROM read_parquet('{P}') WHERE {SUB}").fetchone()[0])
except Exception as e:  # noqa: BLE001
    res["duckdb|subquery"] = err(e)
try:
    ctx = datafusion.SessionContext(); ctx.register_parquet("t", P)
    res["datafusion|subquery"] = int(list(ctx.sql(f"SELECT count(*) AS c FROM t WHERE {SUB}").to_pydict().values())[0][0])
except Exception as e:  # noqa: BLE001
    res["datafusion|subquery"] = err(e)
sess = chs.Session()
for form, pred in (("literal", LIT), ("subquery", SUB)):
    for tni in (0, 1):
        q = f"SELECT count(*) FROM file('{P}', Parquet) WHERE {pred} SETTINGS transform_null_in = {tni}"
        try:
            res[f"chdb|{form}|transform_null_in={tni}"] = int(sess.query(q, "CSV").data().strip().splitlines()[-1].strip('"'))
        except Exception as e:  # noqa: BLE001
            res[f"chdb|{form}|transform_null_in={tni}"] = err(e)
json.dump(res, open(OUT, "w"), indent=2, sort_keys=True)
print(json.dumps(res, indent=1, sort_keys=True))

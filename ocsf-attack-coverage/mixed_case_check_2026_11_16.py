"""Post-hoc check (2026-11-16, not pre-registered): do the four ocsf-attack-coverage Sigma rules lose
recall on DuckDB when the planted value's case differs from the rule's?

Background: atlas-ocsf-observables (R1, 2026-11-09) found that pySigma-backend-sqlite compiles Sigma
`contains` to LIKE '%...%', which SQLite evaluates case-insensitively (as Sigma requires) and DuckDB
evaluates case-sensitively. ocsf-attack-coverage compiles with the same backend and executes in DuckDB
(run.py l.40, l.88-89). Its committed run plants values whose case matches the rules, so the issue could
not show there. This script compiles each rule exactly as run.py does (SigmaCollection -> sqliteBackend
.convert -> SELECT event_uid / <TABLE_NAME> replace) and runs it on SQLite and DuckDB over a tiny table
holding the rule's matching value in its original case, lower case, upper case and one mixed case, plus
one non-matching row. Nothing in the bench's committed corpus, rules or results is touched.

  <venv with pysigma==2.0.3 pysigma-backend-sqlite==2.1.1 duckdb==1.5.3>/bin/python -I mixed_case_check_2026_11_16.py
Writes results/mixed-case-check-2026-11-16.json.
"""
import json, os, sqlite3, sys
from importlib.metadata import version

import duckdb
from sigma.collection import SigmaCollection
from sigma.backends.sqlite import sqliteBackend

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(HERE, "rules")

# rule file -> (columns with a fixed non-tested value, the column under test, the rule's own value,
#               the column's SQL type). Fixed columns hold the value the rule needs so only one field varies.
CASES = {
    "encoded_powershell.yml": ({"device_hostname": "WS1"}, "cmd_line",
                               "powershell.exe -EncodedCommand SQBFAFgA", "TEXT"),
    "c2_domain.yml": ({}, "query_hostname", "cdn-telemetry-sync.net", "TEXT"),
    "nomfa_privesc.yml": ({"mfa_present": False}, "api_operation", "AttachUserPolicy", "TEXT"),
    "rdp_lateral.yml": ({}, "dst_port", 3389, "INTEGER"),
}


def variants(v):
    if not isinstance(v, str):
        return [("original", v), ("non-match", v + 1)]
    mixed = "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(v))
    return [("original", v), ("lower", v.lower()), ("upper", v.upper()), ("mixed", mixed),
            ("non-match", "benign-value")]


def run(engine, ddl, rows, sql):
    if engine == "sqlite":
        con = sqlite3.connect(":memory:")
    else:
        con = duckdb.connect(":memory:")
    con.execute(ddl)
    for r in rows:
        con.execute(f"INSERT INTO t VALUES ({', '.join('?' for _ in r)})", r)
    return sorted(x[0] for x in con.execute(sql).fetchall())


def main():
    backend = sqliteBackend()
    out = {"versions": {"pySigma": version("pySigma"), "pySigma-backend-sqlite": version("pySigma-backend-sqlite"),
                        "duckdb": duckdb.__version__, "sqlite": sqlite3.sqlite_version,
                        "python": sys.version.split()[0]}, "rules": {}}
    for rule, (fixed, col, val, typ) in CASES.items():
        coll = SigmaCollection.from_yaml(open(os.path.join(RULES, rule)).read())
        sql = backend.convert(coll)[0]
        # run.py replaces "<TABLE_NAME>", the placeholder older pySigma-backend-sqlite emitted; 2.1.1 emits
        # "FROM logs" instead (as atlas-ocsf-observables/run_planted.py l.38 handles), so replace both.
        run_sql = sql.replace("SELECT *", "SELECT event_uid").replace("<TABLE_NAME>", "t").replace(" FROM logs", " FROM t")
        fcols = list(fixed)
        ddl = "CREATE TABLE t (event_uid INTEGER, " + ", ".join(
            [f"{c} {'BOOLEAN' if isinstance(fixed[c], bool) else 'TEXT'}" for c in fcols] + [f"{col} {typ}"]) + ")"
        vs = variants(val)
        rows = [tuple([i] + [fixed[c] for c in fcols] + [v]) for i, (_, v) in enumerate(vs)]
        res = {}
        for eng in ("sqlite", "duckdb"):
            try:
                hit = run(eng, ddl, rows, run_sql)
                res[eng] = {lab: (i in hit) for i, (lab, _) in enumerate(vs)}
            except Exception as e:  # recorded, not hidden
                res[eng] = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
        out["rules"][rule] = {"compiled_sql": sql, "column": col, "planted": {lab: v for lab, v in vs},
                              "matched": res,
                              "engines_disagree_on": [lab for lab, _ in vs if res["sqlite"].get(lab) != res["duckdb"].get(lab)]}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    p = os.path.join(HERE, "results", "mixed-case-check-2026-11-16.json")
    json.dump(out, open(p, "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()

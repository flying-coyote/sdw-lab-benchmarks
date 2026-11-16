"""Post-hoc probe (2026-11-16, not pre-registered): are R1's two DETECTED rules case-fragile on DuckDB?

R1 found the pySigma SQLite backend's LIKE is case-insensitive in SQLite and case-sensitive in DuckDB (RESULTS.md
l.125-132) and applied that only to the prompt-injection rule. This probe compiles the two rules that scored
DETECTED (T0049 SQL injection, T0050 inline decode-and-exec) exactly as run_planted.py does (compile_rule:
sqliteBackend().convert(...)[-1]; single_sql: SELECT event_uid / FROM <table>) and runs each over a one-column
table of case variants of a matching value, on SQLite and on DuckDB. The planted corpus, rules and results of R1
are untouched. Raw output: results/probe-detected-rules-case-2026-11-16.json.

  <venv with pysigma==2.0.3 pysigma-backend-sqlite==2.1.1 duckdb==1.5.3>/bin/python -I probe_detected_rules_case_2026_11_16.py
"""
import json, os, sqlite3, sys
from importlib.metadata import version

import duckdb
from sigma.collection import SigmaCollection
from sigma.backends.sqlite import sqliteBackend

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = {
    "T0049_sqli_union.yml": ("query_info_query_string", [
        ("as_planted_upper", "SELECT name FROM users WHERE id='x' UNION SELECT user,password FROM creds --"),
        ("lower", "select name from users where id='x' union select user,password from creds --"),
        ("mixed", "SELECT name FROM users WHERE id='x' UnIoN SeLeCt user,password FROM creds --"),
        ("benign", "SELECT name FROM users WHERE id=42")]),
    "T0050_python_exec_b64.yml": ("process_cmd_line", [
        ("as_planted", "python3 -c \"import base64;exec(base64.b64decode('cHJpbnQoMSk='))\""),
        ("upper_b64decode", "python3 -c \"import base64;exec(base64.B64DECODE('cHJpbnQoMSk='))\""),
        ("benign", "python3 -c \"print(1)\"")]),
}


def run(engine, col, values, sql):
    con = sqlite3.connect(":memory:") if engine == "sqlite" else duckdb.connect(":memory:")
    con.execute(f"CREATE TABLE t (event_uid INTEGER, {col} TEXT)")
    for i, (_, v) in enumerate(values):
        con.execute("INSERT INTO t VALUES (?, ?)", (i, v))
    hit = {r[0] for r in con.execute(sql).fetchall()}
    return {lab: (i in hit) for i, (lab, _) in enumerate(values)}


def main():
    out = {"versions": {"pySigma": version("pySigma"), "pySigma-backend-sqlite": version("pySigma-backend-sqlite"),
                        "duckdb": duckdb.__version__, "sqlite": sqlite3.sqlite_version, "python": sys.version.split()[0]},
           "rules": {}}
    for rule, (col, values) in CASES.items():
        sql = sqliteBackend().convert(SigmaCollection.from_yaml(open(os.path.join(HERE, "rules", rule)).read()))[-1]
        run_sql = sql.replace("SELECT *", "SELECT event_uid", 1).replace(" FROM logs", " FROM t")
        res = {e: run(e, col, values, run_sql) for e in ("sqlite", "duckdb")}
        out["rules"][rule] = {"compiled_sql": sql, "values": dict(values), "matched": res,
                              "engines_disagree_on": [l for l, _ in values if res["sqlite"][l] != res["duckdb"][l]]}
    p = os.path.join(HERE, "results", "probe-detected-rules-case-2026-11-16.json")
    json.dump(out, open(p, "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()

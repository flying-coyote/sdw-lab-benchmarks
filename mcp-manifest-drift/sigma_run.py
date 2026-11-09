"""Compile the frozen R5 Sigma rules with one pySigma backend and execute them over the OCSF events.
Paths: a = pySigma-backend-duckdb -> DuckDB; b = pySigma-backend-sqlite -> sqlite3; c = sqlite SQL verbatim on DuckDB.
Usage: python -I sigma_run.py a|b|c   (a in .venv, b/c in .venv-sqlite)
"""
import json, re, sqlite3, sys, time
from pathlib import Path
from importlib.metadata import version

import duckdb
from sigma.collection import SigmaCollection

HERE = Path(__file__).resolve().parent
PATH = sys.argv[1] if len(sys.argv) > 1 else "a"


def load_events(var):
    return [json.loads(l) for l in (HERE / f"events/events-{var}.jsonl").read_text().splitlines()]


def coltype(vals):
    vals = [v for v in vals if v is not None]
    if vals and all(isinstance(v, bool) for v in vals):
        return "BOOLEAN"
    if vals and all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
        return "BIGINT"
    if vals and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
        return "DOUBLE"
    return "VARCHAR"


def build(events, engine):
    cols = sorted({k for e in events for k in e})
    types = {c: coltype([e.get(c) for e in events]) for c in cols}
    if engine == "duckdb":
        con = duckdb.connect(":memory:")
        q = lambda c: '"' + c + '"'
    else:
        con = sqlite3.connect(":memory:")
        con.create_function("REGEXP", 2, lambda pat, s: 1 if s is not None and re.search(pat, s) else 0)
        q = lambda c: "`" + c + "`"
        types = {c: {"BOOLEAN": "INTEGER", "BIGINT": "INTEGER", "DOUBLE": "REAL"}.get(t, "TEXT") for c, t in types.items()}
    con.execute(f"CREATE TABLE logs ({', '.join(q(c) + ' ' + types[c] for c in cols)})")
    ph = ", ".join(["?"] * len(cols))
    rows = [tuple(e.get(c) for c in cols) for e in events]
    if engine == "duckdb":
        con.executemany(f"INSERT INTO logs VALUES ({ph})", rows)
    else:
        con.executemany(f"INSERT INTO logs VALUES ({ph})", rows)
    return con


def backend():
    if PATH == "a":
        from sigma_backend_duckdb import DuckDBBackend
        return DuckDBBackend(), {"pySigma": version("pySigma"), "backend": "pySigma-backend-duckdb " + version("pySigma-backend-duckdb")}
    from sigma.backends.sqlite import sqliteBackend
    return sqliteBackend(), {"pySigma": version("pySigma"), "backend": "pySigma-backend-sqlite " + version("pySigma-backend-sqlite")}


def main():
    be, vers = backend()
    vers["duckdb"] = duckdb.__version__
    vers["sqlite3"] = sqlite3.sqlite_version
    engine = "sqlite" if PATH == "b" else "duckdb"
    out = {"path": PATH, "engine": engine, "versions": vers, "rules": {}}
    cons = {var: build(load_events(var), engine) for var in ("D0", "D1")}
    for rf in sorted((HERE / "rules").glob("*.yml")):
        r = {"compiled": None, "compile_error": None, "sql": None, "results": {}}
        try:
            r["sql"] = be.convert(SigmaCollection.from_yaml(rf.read_text()))[0]
            r["compiled"] = True
        except Exception as e:
            r["compiled"], r["compile_error"] = False, f"{type(e).__name__}: {str(e)[:300]}"
        if r["compiled"]:
            sql = r["sql"].replace("SELECT *", 'SELECT "metadata.uid"' if engine == "duckdb" else "SELECT `metadata.uid`", 1)
            for var, con in cons.items():
                try:
                    t0 = time.monotonic_ns()
                    uids = sorted(row[0] for row in con.execute(sql).fetchall())
                    r["results"][var] = {"ok": True, "uids": uids, "ms": (time.monotonic_ns() - t0) / 1e6}
                except Exception as e:
                    r["results"][var] = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}
        out["rules"][rf.stem] = r
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / f"results/sigma-path-{PATH}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for k, r in out["rules"].items():
        print(PATH, k, "compiled" if r["compiled"] else r["compile_error"],
              {v: (len(x["uids"]) if x["ok"] else x["error"][:120]) for v, x in r["results"].items()})


if __name__ == "__main__":
    main()

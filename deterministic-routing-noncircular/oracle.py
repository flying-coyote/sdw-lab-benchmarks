#!/usr/bin/env python3
"""DuckDB answer oracle for the frozen corpus (host .venv, DuckDB 1.5.3, over the pinned parquet).

Runs every corpus query once against read_parquet() of the same pinned files the engines read through
Iceberg, normalises with the original bench's normalize(), and writes results/oracle.json. No timing is
recorded or used. memory_limit 8GB / 4 threads because a sibling DuckDB bench may share the host.
  ../.venv/bin/python oracle.py            # write oracle
  ../.venv/bin/python oracle.py --explain  # bind check only (pre-freeze)
"""
import json
import sys
from pathlib import Path

import duckdb

from ejs_queries import normalize

HERE = Path(__file__).parent
EJS = HERE.parent / "engine-join-specialization" / "_work"
NS = {"lineitem": "tpch", "orders": "tpch", "customer": "tpch", "supplier": "tpch", "nation": "tpch",
      "region": "tpch", "part": "tpch", "partsupp": "tpch", "conn": "soc", "dns": "soc", "assets": "soc",
      "ioc": "soc", "conn_enriched": "soc"}


def render_duckdb(sql):
    for n in sorted(NS, key=len, reverse=True):
        sql = sql.replace("$" + n, f"read_parquet('{EJS / NS[n] / (n + '.parquet')}')")
    return sql


def main():
    explain = "--explain" in sys.argv
    corpus = json.loads((HERE / "queries" / "corpus.json").read_text())["queries"]
    con = duckdb.connect()
    con.execute("SET memory_limit='8GB'; SET threads=4")
    answers, errors = {}, {}
    for q in corpus:
        s = render_duckdb(q["sql"])
        try:
            if explain:
                con.execute("EXPLAIN " + s)
            else:
                answers[q["id"]] = normalize(con.execute(s).fetchall())
                print(q["id"], len(answers[q["id"]]), "rows", answers[q["id"]][:2], flush=True)
        except Exception as e:
            errors[q["id"]] = str(e)[:300]
            print("FAIL", q["id"], str(e)[:200], flush=True)
    if not explain:
        (HERE / "results").mkdir(exist_ok=True)
        (HERE / "results" / "oracle.json").write_text(json.dumps(
            {"duckdb": duckdb.__version__, "answers": answers, "errors": errors}, indent=1, sort_keys=True))
    print("bind-check" if explain else "oracle", "done;", len(errors), "errors")


if __name__ == "__main__":
    main()

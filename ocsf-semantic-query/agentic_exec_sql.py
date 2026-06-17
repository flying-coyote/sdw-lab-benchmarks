#!/usr/bin/env python3
"""BENCH-C v2.1 Arm #1 — read-only DuckDB execution tool for the agentic self-correct loop.

The agentic text-to-SQL arm gives a subagent THIS tool and nothing else from the bench: it writes a
DuckDB SELECT against the raw Store F tables, runs it here, inspects the returned rows or the error,
and revises (up to K=5 rounds). The agent sees ONLY the schema (in its prompt) and its own query
results — never `ground_truth.json`, never gold constants. This script loads no truth file.

Usage (the agent calls it via a heredoc so multi-line SQL needs no quoting/temp file):
    python3 agentic_exec_sql.py <<'SQL'
    SELECT count(*) FROM f_api WHERE mfa_present = false
    SQL
or:  python3 agentic_exec_sql.py "SELECT 1"

Read-only by construction: an in-memory DuckDB with VIEWS over the parquet files. Any DDL the model
writes affects only its ephemeral in-memory database; the corpus on disk is never mutated.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench_c_v2_config as CFG  # noqa: E402

ROW_CAP = 50          # rows printed back to the agent
CELL_CAP = 200        # chars per cell printed back


def main():
    sql = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else sys.stdin.read().strip()
    if not sql:
        print("ERROR: no SQL provided")
        return
    import duckdb
    con = duckdb.connect()   # in-memory; views below are read-only over the parquet corpus
    for t in ("auth", "session", "network", "dns", "process", "api"):
        con.execute(f"CREATE VIEW f_{t} AS SELECT * FROM read_parquet('{CFG.STORE_F}/{t}.parquet')")
    con.execute(f"CREATE VIEW f_asset AS SELECT * FROM read_parquet('{CFG.STORE_F_V2_ASSET}')")
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return
    print(f"OK — {len(rows)} row(s) returned. columns: {cols}")
    if not rows:
        print("(empty result set)")
        return
    shown = rows[:ROW_CAP]
    for r in shown:
        cells = [str(c)[:CELL_CAP] for c in r]
        print(" | ".join(cells))
    if len(rows) > ROW_CAP:
        print(f"... ({len(rows) - ROW_CAP} more row(s) not shown; ROW_CAP={ROW_CAP})")


if __name__ == "__main__":
    main()

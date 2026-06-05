"""A small OCSF threat-hunt written as a marimo reactive notebook.

This is the artifact under test for the notebook-substrate question: a marimo notebook IS a plain
`.py` file with a deterministic reactive dataflow (cells run in dependency order, no hidden out-of-order
kernel state), so it is git-diffable, runs headless top-to-bottom, and carries no embedded outputs or
execution counts. The hunt itself is plain DuckDB SQL over the shared testbed corpus — no notebook-runtime
APIs — so it is portable to any SQL engine. `run.py` exercises both properties.
"""

import marimo

app = marimo.App()


@app.cell
def _():
    import json
    import os
    import duckdb
    return duckdb, json, os


@app.cell
def _(duckdb, os):
    # the shared planted-chain testbed corpus (raw, native-shaped); resolve robustly by
    # walking up to the repo dir that holds ocsf-semantic-testbed, so this works whether the
    # notebook runs in place or as an exported flat script in another directory
    d = os.path.dirname(os.path.abspath(__file__))
    base = None
    for _ in range(6):
        cand = os.path.join(d, "ocsf-semantic-testbed", "_work", "parquet")
        if os.path.isdir(cand):
            base = cand
            break
        d = os.path.dirname(d)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW cloudtrail AS SELECT * FROM '{base}/cloudtrail.parquet'")
    con.execute(f"CREATE VIEW zeek_conn AS SELECT * FROM '{base}/zeek_conn.parquet'")
    return (con,)


@app.cell
def _(con):
    # hunt 1 — privilege escalation with MFA absent (not merely false)
    no_mfa = con.execute(
        "SELECT count(*) FROM cloudtrail "
        "WHERE event_name = 'AttachUserPolicy' AND mfaAuthenticated IS NULL"
    ).fetchone()[0]
    # hunt 2 — low-and-slow beacon: connections to the newly-seen C2 address
    beacon = con.execute(
        "SELECT count(*) FROM zeek_conn WHERE resp_h = '203.0.113.66'"
    ).fetchone()[0]
    return beacon, no_mfa


@app.cell
def _(beacon, json, no_mfa):
    result = {"no_mfa_attachpolicy": no_mfa, "beacon_conns": beacon}
    print(json.dumps(result, sort_keys=True))
    return (result,)


if __name__ == "__main__":
    app.run()

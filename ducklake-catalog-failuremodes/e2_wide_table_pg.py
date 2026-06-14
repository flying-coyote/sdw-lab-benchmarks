#!/usr/bin/env python3
"""BENCH-E arm E2 — DuckLake >1600-column CREATE TABLE wall on a Postgres catalog
(duckdb/ducklake #1184).

DuckLake's CREATE TABLE unconditionally emits a backing
`CREATE TABLE ducklake_inlined_data_<id>_0 (<every user col> BYTEA, ...)` against the
PG catalog, in the same transaction as the metadata writes. That backing CREATE hits
Postgres's hard per-table 1600-column limit, so a wide table (the issue's reporter has
a ~1700-field healthcare dataset) cannot be created at all — even with row inlining
disabled, because disabling inlining suppresses *row* inlining but the backing-table
*schema* is still created with all user columns.

This arm measures the wall precisely:
  - control:    CREATE TABLE with N=1500 columns  -> expected SUCCESS
  - at limit:   CREATE TABLE with N=1600 columns  -> boundary probe
  - over limit: CREATE TABLE with N=1700 columns  -> expected FAIL (PG 1600-col error)
  - inlining-off variant of the over-limit case (SET ...row_limit=0) -> issue says still FAIL

Connection params come from env (PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD); the
runner brings up the postgres:17 container. Tier B, single host. Versions recorded.
"""
import json
import os
import re
import sys
import traceback

import duckdb


PGHOST = os.environ.get("PGHOST", "localhost")
PGPORT = os.environ.get("PGPORT", "5432")
PGDATABASE = os.environ.get("PGDATABASE", "ducklake_catalog")
PGUSER = os.environ.get("PGUSER", "postgres")
PGPASSWORD = os.environ.get("PGPASSWORD", "test")


def ext_versions(con):
    rows = con.execute(
        "SELECT extension_name, extension_version FROM duckdb_extensions() "
        "WHERE extension_name IN ('ducklake','postgres') AND installed"
    ).fetchall()
    return {name: ver for name, ver in rows}


def fresh_lake(con, attach_alias, dbname, data_path):
    """ATTACH a fresh ducklake-on-postgres catalog. Each probe gets its OWN Postgres
    database (created by the runner) + its own DATA_PATH, so a catalog registered by
    one probe never collides with the next (DuckLake pins DATA_PATH per catalog)."""
    con.execute(
        f"ATTACH 'ducklake:postgres:dbname={dbname} host={PGHOST} port={PGPORT} "
        f"user={PGUSER} password={PGPASSWORD}' AS {attach_alias} "
        f"(DATA_PATH '{data_path}')"
    )


def make_cols(n):
    return ", ".join(f"c{i} INTEGER" for i in range(n))


def probe(n_cols, inlining_off=False, idx=0):
    """Try CREATE TABLE with n_cols columns on a ducklake-postgres catalog. Returns
    success flag + the first error line (and whether it is the PG 1600-col error)."""
    con = duckdb.connect()
    con.execute("INSTALL ducklake; LOAD ducklake")
    con.execute("INSTALL postgres; LOAD postgres")
    alias = f"lake{idx}"
    dbname = f"ducklake_e2_{idx}"   # one fresh PG database per probe (runner creates these)
    data_path = f"/tmp/ducklake_e2_{idx}"
    err = None
    is_1600_error = False
    created = False
    try:
        if inlining_off:
            # the issue reporter set this and still hit the wall
            con.execute("SET ducklake_default_data_inlining_row_limit = 0")
        fresh_lake(con, alias, dbname, data_path)
        con.execute(f"USE {alias}")
        con.execute(f"CREATE TABLE t_{n_cols} ({make_cols(n_cols)})")
        created = True
    except duckdb.Error as e:
        full = str(e)
        low = full.lower()
        is_1600_error = ("1600 columns" in low) or ("at most 1600" in low)
        # extract just the PG limit phrase (the megabyte INSERT statement that carries
        # it would balloon the result JSON), else the first line of the commit error
        m = re.search(r"ERROR:\s*tables can have at most 1600 columns", full, re.I)
        err = m.group(0) if m else full.splitlines()[0]
    finally:
        try:
            con.close()
        except Exception:
            pass
    return {
        "n_cols": n_cols,
        "inlining_off": inlining_off,
        "created": created,
        "error": err,
        "is_pg_1600_error": is_1600_error,
    }


def main():
    con = duckdb.connect()
    con.execute("INSTALL ducklake; LOAD ducklake")
    con.execute("INSTALL postgres; LOAD postgres")
    versions = {"duckdb": duckdb.__version__, **ext_versions(con)}
    con.close()

    probes = []
    plan = [
        (1500, False),   # control: under the wall, should succeed
        (1600, False),   # at the boundary
        (1700, False),   # over: should fail (issue's case)
        (1700, True),    # over + inlining disabled: issue says still fails
    ]
    for i, (n, off) in enumerate(plan):
        try:
            probes.append(probe(n, inlining_off=off, idx=i))
        except Exception:
            probes.append({"n_cols": n, "inlining_off": off,
                           "error": traceback.format_exc()})

    over = next((p for p in probes if p["n_cols"] == 1700 and not p["inlining_off"]), {})
    over_off = next((p for p in probes if p["n_cols"] == 1700 and p["inlining_off"]), {})
    control = next((p for p in probes if p["n_cols"] == 1500), {})
    wall_reproduced = (
        bool(over.get("is_pg_1600_error"))
        and bool(over_off.get("is_pg_1600_error"))
        and bool(control.get("created"))
    )

    result = {
        "arm": "E2",
        "issue": "duckdb/ducklake#1184",
        "issue_title": "CREATE TABLE with >1600 columns fails on Postgres catalog even when data inlining is disabled",
        "issue_state_at_run": "OPEN",
        "filed_against": {"ducklake": "415a9ebd", "duckdb": "1.5.2", "postgres": "Azure Flexible 17.x"},
        "run_versions": {**versions, "postgres": os.environ.get("PG_IMAGE", "postgres:17")},
        "tier": "B",
        "host": "single host (Beelink 5800H, WSL2)",
        "kind": "operability (wide-schema CREATE blocked by backing-table 1600-col CREATE)",
        "probes": probes,
        "verdict": "PERSISTS" if wall_reproduced else "NOT-REPRODUCED",
    }
    out = os.path.join(os.path.dirname(__file__), "results", "e2.json")
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
    print(f"\n[E2] verdict={result['verdict']}  -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""BENCH-E arm E3 — DuckLake Postgres-catalog connection-pool timeout
(duckdb/ducklake #1031).

`DuckLakeTransaction::GetConnection()` opens a fresh Connection per transaction; with
`pg_pool_enable_thread_local_cache=true` (default) and `pg_pool_max_connections=8`
(default), DuckDB's worker threads each cache one Postgres connection in thread-local
storage and never release it while the thread is alive. After enough catalog
operations (the reporter's minimal case: 50+ CREATE TABLE then an
`information_schema.tables` query) every pooled connection is "in use" and the next
catalog read hangs ~30s then fails with:

    Connection pool timeout: all 8 connections in use, waited 30000ms

This arm is labeled "PR submitted" upstream and the reporter notes it does NOT
reproduce on DuckDB 1.4.4 + DuckLake v0.3 — so on the *current* extension this is a
genuine version-currency question: PERSISTS or FIXED on <ver>. We create 60 tables
sequentially then run the information_schema probe, recording wall time and whether
the pool-timeout error fires.

Connection params from env; runner brings up postgres:17. Tier B, single host.
"""
import json
import os
import sys
import time
import traceback

import duckdb


PGHOST = os.environ.get("PGHOST", "localhost")
PGPORT = os.environ.get("PGPORT", "5432")
PGDATABASE = os.environ.get("PGDATABASE", "ducklake_catalog")
PGUSER = os.environ.get("PGUSER", "postgres")
PGPASSWORD = os.environ.get("PGPASSWORD", "test")
N_TABLES = int(os.environ.get("E3_N_TABLES", "60"))


def ext_versions(con):
    rows = con.execute(
        "SELECT extension_name, extension_version FROM duckdb_extensions() "
        "WHERE extension_name IN ('ducklake','postgres') AND installed"
    ).fetchall()
    return {name: ver for name, ver in rows}


def main():
    con = duckdb.connect()
    con.execute("INSTALL ducklake; LOAD ducklake")
    con.execute("INSTALL postgres; LOAD postgres")
    versions = {"duckdb": duckdb.__version__, **ext_versions(con)}

    schema = "ducklake_e3"
    con.execute(
        f"ATTACH 'ducklake:postgres:dbname={PGDATABASE} host={PGHOST} port={PGPORT} "
        f"user={PGUSER} password={PGPASSWORD}' AS lake "
        f"(DATA_PATH '/tmp/{schema}')"
    )
    con.execute("USE lake")
    con.execute("CREATE SCHEMA IF NOT EXISTS s")

    created = 0
    create_err = None
    t_create0 = time.perf_counter()
    try:
        for i in range(N_TABLES):
            con.execute(f"CREATE OR REPLACE TABLE s.t{i:03d} (id INT, val TEXT)")
            created += 1
    except duckdb.Error as e:
        create_err = str(e).splitlines()[0]
    create_wall = time.perf_counter() - t_create0

    # the trigger query
    probe_err = None
    pool_timeout = False
    probe_wall = None
    table_count = None
    t0 = time.perf_counter()
    try:
        table_count = con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 's'"
        ).fetchone()[0]
        probe_wall = time.perf_counter() - t0
    except duckdb.Error as e:
        probe_wall = time.perf_counter() - t0
        probe_err = str(e).splitlines()[0]
        low = str(e).lower()
        pool_timeout = ("connection pool timeout" in low) or ("connections in use" in low)
    try:
        con.close()
    except Exception:
        pass

    result = {
        "arm": "E3",
        "issue": "duckdb/ducklake#1031",
        "issue_title": "Connection pool timeout with postgres catalog",
        "issue_state_at_run": "OPEN (label: PR submitted)",
        "filed_against": {"ducklake": "415a9ebd (v1.0)", "duckdb": "1.5.2", "postgres": "16-alpine"},
        "does_not_reproduce_on": {"duckdb": "1.4.4", "ducklake": "v0.3 (3f1b372)"},
        "run_versions": {**versions, "postgres": os.environ.get("PG_IMAGE", "postgres:17")},
        "tier": "B",
        "host": "single host (Beelink 5800H, WSL2)",
        "kind": "operability (thread-local pool exhaustion)",
        "n_tables_requested": N_TABLES,
        "tables_created": created,
        "create_error": create_err,
        "create_wall_s": round(create_wall, 3),
        "information_schema_count": table_count,
        "probe_wall_s": round(probe_wall, 3) if probe_wall is not None else None,
        "probe_error": probe_err,
        "pool_timeout_fired": pool_timeout,
        "verdict": "PERSISTS" if pool_timeout else "NOT-REPRODUCED",
    }
    result["label"] = os.environ.get("E3_LABEL", "current")
    out = os.environ.get(
        "E3_OUT", os.path.join(os.path.dirname(__file__), "results", "e3.json"))
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
    print(f"\n[E3:{result['label']}] verdict={result['verdict']}  "
          f"duckdb={versions.get('duckdb')} ducklake={versions.get('ducklake')}  -> {out}",
          file=sys.stderr)


if __name__ == "__main__":
    main()

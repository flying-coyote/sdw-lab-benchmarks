#!/usr/bin/env python3
"""BENCH-E arm E1 — DuckLake cross-store delete-conflict gap (duckdb/ducklake #1215).

Faithful reproduction of the issue's own minimal repro. Two concurrent transactions
delete the *same row* of the same data file; one delete is <= DATA_INLINING_ROW_LIMIT
(stored as an inlined file delete), the other is > the limit (stored as a parquet
delete file). The commit-conflict check only compares parquet-vs-parquet and
inlined-vs-inlined, so the cross-store (inlined+parquet) pair both commit and the
row's position is recorded in BOTH delete stores. The read path then makes the
deleted rows reappear.

This is a CORRECTNESS bug (silent lost-conflict + resurrected deleted rows), not a
performance number, so there is no timing here — the result is a boolean: does the
overlap still get created on the *current* DuckLake extension, and does the scan
return the wrong count.

The issue was filed against DuckLake commit 415a9ebd (v1.0) on DuckDB 1.5.2. We run
on whatever is current in this venv and record both versions, so the result is a
version-bound statement: PERSISTS or FIXED on <ver>.

Needs no Postgres — a DuckDB-native catalog lets both transactions reach commit
(on a SQLite catalog the second writer is blocked by `database is locked` first, per
the issue). Tier B, single host.
"""
import json
import os
import sys
import tempfile
import traceback

import duckdb


def ext_versions(con):
    rows = con.execute(
        "SELECT extension_name, extension_version FROM duckdb_extensions() "
        "WHERE extension_name IN ('ducklake') AND installed"
    ).fetchall()
    return {name: ver for name, ver in rows}


def run_once(commit_order):
    """Run the repro in a given commit order. Returns the observed surviving-row count
    in the deleted range [50,80) and whether the second COMMIT raised a conflict.

    Expected-correct behaviour: the second commit conflicts (raises), and the final
    count is 0. Buggy behaviour: second commit succeeds and count is 29 (rows 51..79
    reappear; row 50 stays deleted by the first txn)."""
    ws = tempfile.mkdtemp(prefix="ducklake-e1-")
    db = duckdb.connect()
    db.execute("INSTALL ducklake; LOAD ducklake")
    db.execute(
        f"ATTACH 'ducklake:{ws}/catalog.ducklake' AS dl "
        f"(DATA_PATH '{ws}/data', DATA_INLINING_ROW_LIMIT 10)"
    )
    # 100 rows -> a parquet data file (100 > inlining limit), so the data lands on disk
    db.execute("CREATE TABLE dl.t AS SELECT i AS id FROM range(100) t(i)")

    c1 = db.cursor()
    c2 = db.cursor()
    c1.execute("BEGIN")
    c2.execute("BEGIN")
    # con1: single-row delete (1 <= 10) -> inlined file delete for position 50
    c1.execute("DELETE FROM dl.t WHERE id = 50")
    # con2: 30-row delete incl. value 50 (30 > 10) -> parquet delete file for 50..79
    c2.execute("DELETE FROM dl.t WHERE id >= 50 AND id < 80")

    second_conflicted = False
    err = None
    try:
        if commit_order == "inlined_first":
            c1.execute("COMMIT")
            c2.execute("COMMIT")  # the cross-store second commit; SHOULD conflict
        else:  # parquet_first
            c2.execute("COMMIT")
            c1.execute("COMMIT")  # the cross-store second commit; SHOULD conflict
    except duckdb.Error as e:
        second_conflicted = True
        err = str(e).splitlines()[0]

    # count of rows that should be deleted but may have reappeared
    survived = db.execute(
        "SELECT count(*) FROM dl.t WHERE id >= 50 AND id < 80"
    ).fetchone()[0]
    db.close()
    return {
        "commit_order": commit_order,
        "second_commit_conflicted": second_conflicted,
        "conflict_error": err,
        "deleted_range_survivors": int(survived),
        "expected_survivors": 0,
        "bug_reproduced": (not second_conflicted) and survived != 0,
    }


def main():
    con = duckdb.connect()
    con.execute("INSTALL ducklake; LOAD ducklake")
    versions = {"duckdb": duckdb.__version__, **ext_versions(con)}
    con.close()

    arms = []
    for order in ("inlined_first", "parquet_first"):
        try:
            arms.append(run_once(order))
        except Exception:
            arms.append({"commit_order": order, "error": traceback.format_exc()})

    any_repro = any(a.get("bug_reproduced") for a in arms)
    result = {
        "arm": "E1",
        "issue": "duckdb/ducklake#1215",
        "issue_title": "concurrent inlined and parquet deletes on the same row commit without conflict",
        "issue_state_at_run": "OPEN",
        "filed_against": {"ducklake": "415a9ebd (v1.0)", "duckdb": "1.5.2"},
        "run_versions": versions,
        "tier": "B",
        "host": "single host (Beelink 5800H, WSL2)",
        "kind": "correctness (silent lost-conflict + resurrected rows)",
        "arms": arms,
        "verdict": "PERSISTS" if any_repro else "NOT-REPRODUCED",
    }
    out = os.path.join(os.path.dirname(__file__), "results", "e1.json")
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
    print(f"\n[E1] verdict={result['verdict']}  -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()

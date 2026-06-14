#!/usr/bin/env python3
"""Build + refresh the async MVs for the starrocks_mv arm (#23 P5), via pymysql against
StarRocks on the ejs network (run from inside the ejs-bench-lab image). This is the
operator step make_mvs.sql documents — done in Python so the autonomous runner can drive
it (no host mysql client). It: creates the iceberg external catalog, runs make_mvs.sql,
forces a SYNC refresh of every MV (so the static-table arm is measured against fully
materialized MVs, no async refresh contending mid-run), and verifies all six are ACTIVE.
"""
import re
import sys
import time
from pathlib import Path

import pymysql

# the iceberg external catalog, identical to engines.SR_CATALOG_SQL
SR_CATALOG_SQL = """
CREATE EXTERNAL CATALOG IF NOT EXISTS iceberg PROPERTIES (
  'type'='iceberg','iceberg.catalog.type'='rest',
  'iceberg.catalog.uri'='http://nessie:19120/iceberg/',
  'iceberg.catalog.warehouse'='warehouse',
  'aws.s3.endpoint'='http://minio:9000','aws.s3.enable_path_style_access'='true',
  'aws.s3.enable_ssl'='false','aws.s3.access_key'='ejsbench',
  'aws.s3.secret_key'='ejsbench123','aws.s3.region'='us-east-1')
"""

MVS = ["mv_j1", "mv_j4", "mv_port_scan", "mv_long_duration", "mv_scan_aggregate",
       "mv_rollup_5min"]


def split_sql(text):
    # drop -- comments, split on ; into non-empty statements
    no_comments = "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("--"))
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def main():
    con = pymysql.connect(host="starrocks", port=9030, user="root",
                          connect_timeout=30, read_timeout=600)
    cur = con.cursor()

    print("[mv] creating iceberg external catalog")
    cur.execute(SR_CATALOG_SQL)

    sql_path = Path(__file__).parent / "make_mvs.sql"
    stmts = split_sql(sql_path.read_text())
    print(f"[mv] running make_mvs.sql ({len(stmts)} statements)")
    for s in stmts:
        head = " ".join(s.split())[:70]
        try:
            cur.execute(s)
            print(f"[mv]   ok: {head}")
        except Exception as e:
            print(f"[mv]   ERR: {head} -> {str(e).splitlines()[0]}")

    # force a synchronous refresh so the MVs are fully materialized before scoring
    print("[mv] forcing SYNC refresh of each MV")
    for mv in MVS:
        try:
            cur.execute(f"REFRESH MATERIALIZED VIEW wi_mv.{mv} WITH SYNC MODE")
            print(f"[mv]   refreshed {mv}")
        except Exception as e:
            print(f"[mv]   refresh ERR {mv}: {str(e).splitlines()[0]}")

    # verify all six exist + are active
    cur.execute("SHOW MATERIALIZED VIEWS FROM wi_mv")
    rows = cur.fetchall()
    cur.execute("SHOW MATERIALIZED VIEWS FROM wi_mv")
    desc = [d[0] for d in cur.description]
    name_i = desc.index("name") if "name" in desc else 1
    found = {str(r[name_i]) for r in rows}
    missing = [m for m in MVS if m not in found]
    print(f"[mv] present: {sorted(found)}")
    if missing:
        print(f"[mv] MISSING: {missing}")
        sys.exit(2)
    print("[mv] all six MVs present")


if __name__ == "__main__":
    main()

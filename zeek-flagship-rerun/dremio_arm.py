#!/usr/bin/env python3
"""B-DREMIO arm for the zeek-flagship-rerun suite (added 2026-06-13, pre-registered in
project1 BENCHMARK-BACKLOG.md).

Dremio reads the SAME pyiceberg-written Iceberg table on MinIO that the clickhouse_iceberg
arm reads (byte-identical, in place) — not a re-load. It is reached over an S3 source with
Iceberg-table promotion (Dremio 26 auto-detects Iceberg metadata under an S3 source). Two
arms, reported separately and never blended (pre-registration):

  dremio_iceberg      Reflections OFF — the honest apples-to-apples baseline vs the other arms
  dremio_reflections  Reflections ON  — the maintained-acceleration story (raw reflection)

The host process talks to Dremio's REST API on localhost:9347 (compose maps 9347->9047); the
Dremio engine reaches MinIO on the compose network as minio:9000. SQL forms mirror queries.py
ch_queries() but use standard-SQL HAVING (full expression, not the alias ClickHouse allows),
and answers are extracted with queries.extract_ch for positional equality with the SQL arms.

CLI:
  python dremio_arm.py source        # create/verify the S3 source + promote the Iceberg table
  python dremio_arm.py reflect-on    # define a raw reflection and wait until it can accelerate
  python dremio_arm.py reflect-off   # drop reflections (clean Reflections-OFF baseline)
  python dremio_arm.py smoke [--reflections]   # one untimed run of each query, prints answers
"""
import argparse
import json
import time
from pathlib import Path

import requests

from queries import extract_ch
from load_arms import COLUMNS

BASE = "http://localhost:9347"
SOURCE = "nessie"
# the table registered into Nessie below (same files as clickhouse_iceberg, no rewrite)
TABLE_PATH = [SOURCE, "zeek", "conn_10m"]
TABLE_SQL = ".".join(f'"{p}"' for p in TABLE_PATH)

# register_into_nessie() reads the CURRENT metadata pointer from the existing pyiceberg
# SqlCatalog (the same snapshot clickhouse_iceberg reads) and registers it into Nessie's
# Iceberg REST catalog — no data rewrite, byte-identical files.
NESSIE_REST = "http://localhost:19120/iceberg/"
SRC_SQLITE = f"sqlite:///{Path(__file__).parent / '_work' / 'iceberg_catalog.db'}"
S3_PROPS = {
    "s3.endpoint": "http://localhost:9000",
    "s3.access-key-id": "zfrbench",
    "s3.secret-access-key": "zfrbench123",
    "s3.region": "us-east-1",
    "s3.path-style-access": "true",
}


def register_into_nessie():
    """Register the existing pyiceberg table's CURRENT metadata.json into Nessie, no rewrite."""
    from pyiceberg.catalog.sql import SqlCatalog
    from pyiceberg.catalog.rest import RestCatalog

    src = SqlCatalog("zfr", uri=SRC_SQLITE, warehouse="s3://zfr-bench/iceberg", **S3_PROPS)
    tbl = src.load_table("zeek.conn_10m")
    meta_loc = tbl.metadata_location
    print(f"source metadata_location: {meta_loc}")

    nessie = RestCatalog("nessie", uri=NESSIE_REST, warehouse="warehouse", **S3_PROPS)
    nessie.create_namespace_if_not_exists("zeek")
    try:
        nessie.drop_table("zeek.conn_10m")
        print("dropped pre-existing nessie table registration")
    except Exception:
        pass
    nessie.register_table("zeek.conn_10m", metadata_location=meta_loc)
    t2 = nessie.load_table("zeek.conn_10m")
    snap = t2.metadata.current_snapshot()
    recs = snap.summary.get("total-records", "?") if snap else "?"
    print(f"registered zeek.conn_10m into Nessie (byte-identical, no rewrite); total-records={recs}")


def _dremio_queries(table: str) -> dict:
    """Mirror of queries.ch_queries() with standard-SQL HAVING (Calcite rejects the
    SELECT-alias in HAVING that ClickHouse accepts). extract_ch reads these positionally."""
    return {
        "count_all": f"SELECT COUNT(*) AS cnt FROM {table}",
        "top_source_ips_by_bytes": (
            "SELECT orig_h, SUM(COALESCE(orig_bytes, 0) + COALESCE(resp_bytes, 0)) AS total_bytes "
            f"FROM {table} GROUP BY orig_h ORDER BY total_bytes DESC LIMIT 10"
        ),
        "protocol_distribution": (
            f"SELECT proto, COUNT(*) AS cnt FROM {table} GROUP BY proto ORDER BY cnt DESC"
        ),
        "long_duration_connections": (
            "SELECT orig_h, resp_h, duration, orig_bytes, resp_bytes "
            f"FROM {table} WHERE duration > 60 ORDER BY duration DESC LIMIT 10"
        ),
        "port_scan_detection": (
            "SELECT orig_h, COUNT(DISTINCT resp_p) AS unique_ports, COUNT(DISTINCT resp_h) AS unique_hosts "
            f"FROM {table} WHERE proto = 'tcp' GROUP BY orig_h "
            "HAVING COUNT(DISTINCT resp_p) > 10 ORDER BY COUNT(DISTINCT resp_p) DESC LIMIT 10"
        ),
    }


class Dremio:
    """REST client (modeled on the engine-join-specialization Dremio arm)."""

    def __init__(self, base=BASE, timeout=600):
        self.base = base
        self.timeout = timeout
        self._login()

    def _login(self):
        # first-user bootstrap is idempotent (ignored once a user exists)
        requests.put(
            f"{self.base}/apiv2/bootstrap/firstuser",
            headers={"Authorization": "_dremionull", "Content-Type": "application/json"},
            json={"userName": "admin", "firstName": "Ad", "lastName": "Min",
                  "email": "admin@example.com", "password": "dremioAdmin123"},
            timeout=30,
        )
        r = requests.post(f"{self.base}/apiv2/login",
                          json={"userName": "admin", "password": "dremioAdmin123"}, timeout=30)
        r.raise_for_status()
        self.auth = {"Authorization": "_dremio" + r.json()["token"]}

    def sql(self, query: str) -> list:
        job = requests.post(f"{self.base}/api/v3/sql", json={"sql": query},
                            headers=self.auth, timeout=60).json()
        if "id" not in job:
            raise RuntimeError(f"dremio submit failed: {job}")
        jid = job["id"]
        deadline = time.time() + self.timeout
        while True:
            st = requests.get(f"{self.base}/api/v3/job/{jid}", headers=self.auth, timeout=30).json()
            state = st["jobState"]
            if state == "COMPLETED":
                break
            if state in ("FAILED", "CANCELED"):
                raise RuntimeError(f"dremio: {st.get('errorMessage', state)}")
            if time.time() > deadline:
                raise TimeoutError("dremio: timeout")
            time.sleep(0.03)
        rows, offset = [], 0
        while True:
            page = requests.get(f"{self.base}/api/v3/job/{jid}/results?offset={offset}&limit=500",
                                headers=self.auth, timeout=60).json()
            schema = page["schema"]
            batch = [[row.get(c["name"]) for c in schema] for row in page["rows"]]
            rows += batch
            offset += len(batch)
            if offset >= page["rowCount"] or not batch:
                return rows

    # ---- catalog helpers ----

    def get_by_path(self, path: list) -> dict:
        p = "/".join(requests.utils.quote(seg, safe="") for seg in path)
        r = requests.get(f"{self.base}/api/v3/catalog/by-path/{p}", headers=self.auth, timeout=60)
        return r.json() if r.status_code == 200 else {"_status": r.status_code, "_body": r.text[:300]}

    def ensure_source(self):
        existing = self.get_by_path([SOURCE])
        if existing.get("entityType") == "source":
            print(f"source '{SOURCE}' exists")
            return
        # Nessie source (adapted from engine-join-specialization; its documented corrections
        # are kept: secure:false for plain-HTTP MinIO, awsRootPath with NO leading slash).
        body = {
            "entityType": "source", "name": SOURCE, "type": "NESSIE",
            "config": {
                "nessieEndpoint": "http://nessie:19120/api/v2",
                "nessieAuthType": "NONE",
                "awsRootPath": "zfr-bench/iceberg",
                "credentialType": "ACCESS_KEY",
                "awsAccessKey": "zfrbench", "awsAccessSecret": "zfrbench123",
                "secure": False,
                "propertyList": [
                    {"name": "fs.s3a.path.style.access", "value": "true"},
                    {"name": "fs.s3a.endpoint", "value": "minio:9000"},
                    {"name": "dremio.s3.compat", "value": "true"},
                    {"name": "fs.s3a.connection.ssl.enabled", "value": "false"},
                ],
            },
        }
        r = requests.post(f"{self.base}/api/v3/catalog", headers=self.auth, json=body, timeout=60)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"source create failed {r.status_code}: {r.text[:400]}")
        print(f"source '{SOURCE}' (Nessie) created")

    def promote_table(self):
        """Trigger Iceberg auto-detection by querying the table; raise if not resolvable."""
        n = self.sql(f"SELECT COUNT(*) AS cnt FROM {TABLE_SQL}")[0][0]
        print(f"table {TABLE_SQL} resolved, COUNT(*) = {n}")
        return int(n)

    # Reflection management is SQL-based (ALTER TABLE ... REFLECTION + sys.reflections polling).
    # The REST /api/v3/reflection + /api/v3/catalog/{id} endpoints do NOT work on a Nessie-
    # *versioned* dataset (BRANCH main): the dataset id is a composite {tableKey, contentId,
    # versionContext} object, the list endpoint 405s, and catalog-by-id 404s for both the object
    # and the contentId. SQL goes through the query path, which resolves the versioned table.
    # Validated 2026-06-13: CREATE/DROP parse, sys.reflections polling works.
    #
    # KNOWN OPEN ISSUE (Reflections-ON arm) — the materialization completes but expires
    # INSTANTLY: sys.reflections shows status=CANNOT_ACCELERATE_SCHEDULED,
    # available_until=1970-01-01 (epoch 0), last_failure="Successful materialization already
    # expired". This reproduces with BOTH the REST- and SQL-created reflection, so it is a
    # Dremio-26 + Nessie-*versioned*-table friction, NOT a code bug — Dremio can't compute a
    # valid freshness/expiry for a BRANCH-main Iceberg table registered via register_table, so
    # the reflection never reaches CAN_ACCELERATE and the "ON" arm would run un-accelerated
    # (a duplicate of OFF). The Reflections-OFF arm is unaffected and is the primary number.
    # Quiet-window options to make ON real: (a) a non-versioned read path (Dremio's own Iceberg
    # catalog / Glue / Hadoop-tables with version-hint, instead of Nessie BRANCH); (b) a Dremio
    # support key / dataset refresh-policy that pins materialization validity; (c) report ON as
    # "not cleanly supported over the Nessie-versioned path" — itself an honest finding.

    def _refl_row(self):
        rows = self.sql(
            "SELECT reflection_id, status, acceleration_status, num_failures, "
            "last_failure_message, available_until FROM sys.reflections "
            "WHERE reflection_name = 'zfr_raw' AND dataset_name LIKE '%conn_10m%'")
        return rows[0] if rows else None

    def reflect_off(self):
        row = self._refl_row()
        if not row:
            print("no reflection to drop")
            return
        rid = row[0]
        # Dremio drops reflections by reflection_id (not by name, no "RAW" keyword)
        self.sql(f'ALTER TABLE {TABLE_SQL} DROP REFLECTION "{rid}"')
        print(f"dropped reflection {rid}")

    def reflect_on(self, wait_s=1800):
        self.reflect_off()
        cols = ", ".join(COLUMNS)
        self.sql(f'ALTER TABLE {TABLE_SQL} CREATE RAW REFLECTION "zfr_raw" USING DISPLAY ({cols})')
        print("raw reflection zfr_raw created via SQL; polling sys.reflections "
              "(materialization is a 10M-row scan — run this in a quiet window)...")
        deadline = time.time() + wait_s
        while time.time() < deadline:
            row = self._refl_row()
            if row is None:
                print("  (reflection not yet in sys.reflections)", flush=True)
            else:
                rid, status, accel, fails, failmsg, avail_until = row
                print(f"  status={status} acceleration={accel} failures={fails}"
                      f"{' msg=' + str(failmsg)[:120] if failmsg else ''}", flush=True)
                if accel == "CAN_ACCELERATE":
                    print("reflection CAN_ACCELERATE — Reflections-ON arm ready")
                    return
                if fails and int(fails) >= 3:
                    raise RuntimeError(f"reflection failing: {failmsg}")
            time.sleep(15)
        raise TimeoutError("reflection did not reach CAN_ACCELERATE in time")


def dremio_runner(reflections: bool):
    """Return (names, run) like ch_runner. run(name) -> (seconds, extracted_answer).
    reflections=False is the Reflections-OFF baseline; True assumes reflect_on() was run."""
    client = Dremio()
    qs = _dremio_queries(TABLE_SQL)

    def run(name):
        t0 = time.perf_counter()
        rows = client.sql(qs[name])
        dt = time.perf_counter() - t0
        return dt, extract_ch(name, rows)

    return list(qs.keys()), run


def _smoke(reflections: bool):
    names, run = dremio_runner(reflections)
    label = "reflections-ON" if reflections else "reflections-OFF"
    print(f"--- dremio smoke ({label}) ---")
    for name in names:
        dt, answer = run(name)
        print(f"  {name}: {dt:.3f}s  answer={json.dumps(answer)[:200]}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["register", "source", "promote", "reflect-on", "reflect-off", "smoke"])
    ap.add_argument("--reflections", action="store_true")
    args = ap.parse_args()
    if args.cmd == "register":
        register_into_nessie()
        return
    d = Dremio()
    if args.cmd == "source":
        d.ensure_source()
        time.sleep(2)
        d.promote_table()
    elif args.cmd == "promote":
        d.promote_table()
    elif args.cmd == "reflect-on":
        d.reflect_on()
    elif args.cmd == "reflect-off":
        d.reflect_off()
    elif args.cmd == "smoke":
        _smoke(args.reflections)


if __name__ == "__main__":
    main()

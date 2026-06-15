#!/usr/bin/env python3
"""#25 Dremio-reflection freshness probe — does a Reflection PERSIST (reach CAN_ACCELERATE
without expiring at available_until=epoch 0) when the Iceberg table is read over a NON-VERSIONED
S3 source, instead of the Nessie-versioned (BRANCH main) register_table path?

Background (zeek-flagship dremio_arm.py KNOWN-ISSUE): over the Nessie-versioned dataset, a raw
reflection materializes but Dremio cannot compute a valid freshness, so available_until=1970-01-01
and acceleration_status never reaches CAN_ACCELERATE — the "ON" arm degenerates to "OFF". The
untried fix (option a) is a non-versioned read path: point a Dremio S3 source straight at the
table's folder in MinIO so Dremio auto-promotes the Iceberg metadata without the BRANCH version
context.

This is a YES/NO unblock probe for #25's Dremio arm, NOT a timed result. If the reflection reaches
CAN_ACCELERATE with a real available_until, #25's Dremio-Reflections-vs-StarRocks-MV comparison is
viable; if it still expires at epoch 0, "Dremio Reflections don't persist over open Iceberg even via
a direct S3 source" is the documented finding and #25 runs StarRocks-MV-only + that fair-broker note.

Talks to the ejs Dremio on localhost:9347 (admin/dremioAdmin123). MinIO: minio:9000, ejsbench/
ejsbench123, bucket 'warehouse', conn table folder soc/conn_<uuid>/ (discovered at run time).
"""
import json
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

BASE = "http://localhost:9347"
S3_SOURCE = "minio_s3"          # the NON-versioned source we create for this probe
BUCKET = "warehouse"


def _req(method, path, token=None, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "_dremio" + token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt.strip() else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:500]}


def login():
    st, d = _req("POST", "/apiv2/login", body={"userName": "admin", "password": "dremioAdmin123"})
    if st != 200:
        sys.exit(f"login failed {st}: {d}")
    return d["token"]


def sql(token, query, wait=300):
    """Run SQL via the job API, poll to completion, return rows (or raise)."""
    st, d = _req("POST", "/api/v3/sql", token, {"sql": query})
    if st != 200:
        raise RuntimeError(f"sql submit {st}: {d}")
    jid = d["id"]
    deadline = time.time() + wait
    while time.time() < deadline:
        st, j = _req("GET", f"/api/v3/job/{jid}", token)
        state = j.get("jobState")
        if state == "COMPLETED":
            st, res = _req("GET", f"/api/v3/job/{jid}/results?limit=100", token)
            return res.get("rows", [])
        if state in ("FAILED", "CANCELED"):
            raise RuntimeError(f"job {state}: {j.get('errorMessage', '')[:300]}")
        time.sleep(2)
    raise TimeoutError(f"job {jid} did not finish in {wait}s")


def create_s3_source(token):
    """Create (or confirm) a non-versioned S3 source pointing at the MinIO endpoint."""
    st, existing = _req("GET", f"/api/v3/catalog/by-path/{S3_SOURCE}", token)
    if st == 200 and existing.get("entityType") == "source":
        print(f"S3 source '{S3_SOURCE}' already exists")
        return
    body = {
        "entityType": "source",
        "name": S3_SOURCE,
        "type": "S3",
        "config": {
            "credentialType": "ACCESS_KEY",
            "accessKey": "ejsbench",
            "accessSecret": "ejsbench123",
            "secure": False,
            "compatibilityMode": True,   # required for non-AWS (MinIO) S3
            "rootPath": "/",
            "propertyList": [
                {"name": "fs.s3a.endpoint", "value": "minio:9000"},
                {"name": "fs.s3a.path.style.access", "value": "true"},
                {"name": "dremio.s3.compat", "value": "true"},
            ],
        },
    }
    st, d = _req("POST", "/api/v3/catalog", token, body)
    if st not in (200, 201):
        raise RuntimeError(f"S3 source create {st}: {d}")
    print(f"S3 source '{S3_SOURCE}' created")


def find_conn_folder(token):
    """List the S3 source's warehouse/soc/ and return the conn_<uuid> folder path components."""
    st, d = _req("GET", f"/api/v3/catalog/by-path/{S3_SOURCE}/{BUCKET}/soc", token)
    if st != 200:
        raise RuntimeError(f"list soc/ {st}: {d}")
    for child in d.get("children", []):
        leaf = child["path"][-1]
        if leaf.startswith("conn_") and "enriched" not in leaf:
            return child["path"]
    raise RuntimeError("no conn_<uuid> folder found under soc/")


def promote_iceberg(token, path):
    """Promote the folder as an Iceberg dataset."""
    st, d = _req("GET", f"/api/v3/catalog/by-path/{'/'.join(path)}", token)
    if st == 200 and d.get("entityType") == "dataset":
        print("already promoted")
        return d["id"]
    fid = d.get("id")
    body = {"entityType": "dataset", "type": "PHYSICAL_DATASET", "path": path,
            "format": {"type": "Iceberg"}}
    st, d = _req("POST", f"/api/v3/catalog/{urllib.parse.quote(fid, safe='')}", token, body) \
        if fid else (400, {"error": "no folder id"})
    if st not in (200, 201):
        raise RuntimeError(f"promote {st}: {d}")
    print("promoted as Iceberg")
    return d.get("id")


def main():
    token = login()
    create_s3_source(token)
    path = find_conn_folder(token)
    tbl = '"' + '"."'.join(path) + '"'
    print(f"conn table (S3 path): {tbl}")
    promote_iceberg(token, path)   # Dremio needs the Iceberg folder promoted to a dataset first
    cnt = sql(token, f"SELECT count(*) AS c FROM {tbl}")
    print(f"row count via S3 source: {cnt}")

    # raw reflection on a few columns
    try:
        sql(token, f'ALTER TABLE {tbl} CREATE RAW REFLECTION "p25_raw" USING DISPLAY (orig_h, resp_h, proto, orig_bytes, ts)')
        print("raw reflection p25_raw created")
    except Exception as e:
        print(f"reflection create note: {str(e)[:200]}")

    # poll sys.reflections for available_until + acceleration_status
    verdict = {"reached_can_accelerate": False, "available_until": None, "status": None}
    deadline = time.time() + 1800
    while time.time() < deadline:
        rows = sql(token, "SELECT reflection_id, status, num_failures, last_failure_message, "
                          "external_reflection FROM sys.reflections WHERE reflection_name = 'p25_raw'") \
            if False else sql(token,
            "SELECT reflection_name, status FROM sys.reflections WHERE reflection_name='p25_raw'")
        # detailed status via the materialization view
        det = sql(token, "SELECT reflection_id, state, expiration FROM sys.materializations "
                         "WHERE reflection_id IN (SELECT reflection_id FROM sys.reflections "
                         "WHERE reflection_name='p25_raw') ORDER BY expiration DESC")
        print(f"  reflections={rows}  materializations={det[:2]}", flush=True)
        if det:
            exp = det[0].get("expiration")
            verdict["available_until"] = exp
            verdict["status"] = det[0].get("state")
            # epoch-0 (1970) expiration is the failure mode; a real future expiration is the win
            if exp and "1970" not in str(exp) and det[0].get("state") in ("DONE", "ACTIVE", "AVAILABLE"):
                verdict["reached_can_accelerate"] = True
                break
        time.sleep(20)

    print("\nVERDICT:", json.dumps(verdict, indent=2))
    print("S3-source reflection PERSISTS" if verdict["reached_can_accelerate"]
          else "S3-source reflection did NOT persist (still epoch-0 / not active) — documented finding")


if __name__ == "__main__":
    main()

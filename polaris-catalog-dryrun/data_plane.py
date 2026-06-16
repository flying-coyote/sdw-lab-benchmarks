"""POLARIS-AUDIT data-plane dry-run (H-CATALOG-AUDITABILITY-01 §10) — the leg the 2026-06-15
control-plane rehearsal deferred: catalog-ON-OBJECT-STORE + table data write + table-RBAC at scale,
on the open MinIO substrate. Tier B, single host, dev config (in-memory Polaris persistence).

THE INTEGRATION RECIPE (the friction the prior run flagged, now solved). Polaris 1.5.0's S3 catalog
needs THREE things to work against MinIO; missing any one walls a different way:
  1. AWS_ENDPOINT_URL_S3 + AWS_ENDPOINT_URL_STS both pointed at MinIO (Polaris vends creds via STS
     AssumeRole even for its own metadata writes; static keys alone → "Failed to get subscoped
     credentials: STS 403 invalid token").
  2. pathStyleAccess: true in the catalog storageConfigInfo (else virtual-host addressing
     `bucket.host` → UnknownHostException).
  3. an explicit DATA grant — service_admin can MANAGE the catalog but is NOT authorized for
     LOAD_TABLE_WITH_READ_DELEGATION (data plane); a catalog-role with TABLE_READ_DATA/TABLE_WRITE_DATA
     must be granted and assigned. (This separation is itself the table-RBAC finding.)

Stand Polaris up first (see README / RESULTS), then run this. Idempotent-ish: already-exists (409) is
tolerated so a re-run is safe. Boundary: synthetic structured rows only — no real telemetry.
"""
import json, os, random, sys, urllib.request, urllib.error

MGMT = os.environ.get("POLARIS_MGMT", "http://localhost:8191/api/management/v1")
CAT_URI = os.environ.get("POLARIS_CAT", "http://localhost:8191/api/catalog")
OAUTH = os.environ.get("POLARIS_OAUTH", "http://localhost:8191/api/catalog/v1/oauth/tokens")
ROOT = os.environ.get("POLARIS_ROOT", "root:s3cr3t")
S3_ENDPOINT = os.environ.get("POLARIS_S3", "http://localhost:9300")   # MinIO host port
WAREHOUSE, NS, TBL = "sdw_q3p", "soc", "events"
LOCATION = "s3://polaris-sdw/q3p"
HERE = os.path.dirname(os.path.abspath(__file__))
N = int(os.environ.get("ROWS", "100000"))


def rng_suffix():
    return "".join(random.Random().choices("abcdefghijklmnopqrstuvwxyz0123456789", k=6))


def token(creds=ROOT):
    cid, sec = creds.split(":", 1)
    body = f"grant_type=client_credentials&client_id={cid}&client_secret={sec}&scope=PRINCIPAL_ROLE:ALL"
    r = urllib.request.Request(OAUTH, data=body.encode(), method="POST")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.load(resp)["access_token"]


def api(tok, method, path, body=None, base=MGMT):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{base}{path}", data=data, method=method,
                               headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            txt = resp.read().decode()
            return resp.status, (json.loads(txt) if txt.strip() else {})
    except urllib.error.HTTPError as e:
        return e.code, {"_err": e.read().decode()[:200]}


def setup_catalog(tok):
    """Catalog-on-S3 (path-style) + namespace + a data_rw role granted to service_admin."""
    st, _ = api(tok, "POST", "/catalogs", {"catalog": {
        "name": WAREHOUSE, "type": "INTERNAL", "properties": {"default-base-location": LOCATION},
        "storageConfigInfo": {"storageType": "S3", "allowedLocations": [LOCATION],
                              "roleArn": "arn:aws:iam::000000000000:role/polaris-dryrun",
                              "pathStyleAccess": True}}})
    print(f"  catalog create: {st}")
    api(tok, "POST", "/catalogs/" + WAREHOUSE + "/catalog-roles", {"catalogRole": {"name": "data_rw"}})
    for priv in ("CATALOG_MANAGE_CONTENT", "TABLE_READ_DATA", "TABLE_WRITE_DATA"):
        api(tok, "PUT", f"/catalogs/{WAREHOUSE}/catalog-roles/data_rw/grants",
            {"grant": {"type": "catalog", "privilege": priv}})
    api(tok, "PUT", "/principal-roles/service_admin/catalog-roles/" + WAREHOUSE,
        {"catalogRole": {"name": "data_rw"}})
    print("  granted data_rw (TABLE_READ_DATA/TABLE_WRITE_DATA/CATALOG_MANAGE_CONTENT) → service_admin")


def make_reader(tok):
    """A read-only principal: hunters_ro principal-role → read_only catalog-role (TABLE_READ_DATA only).
    Fresh principal name per run so the create returns credentials (Polaris doesn't re-vend on 409)."""
    name = f"soc_reader_{rng_suffix()}"
    st, body = api(tok, "POST", "/principals", {"principal": {"name": name}})
    api(tok, "POST", "/principal-roles", {"principalRole": {"name": "hunters_ro"}})
    api(tok, "PUT", f"/principals/{name}/principal-roles", {"principalRole": {"name": "hunters_ro"}})
    api(tok, "POST", f"/catalogs/{WAREHOUSE}/catalog-roles", {"catalogRole": {"name": "read_only"}})
    api(tok, "PUT", f"/catalogs/{WAREHOUSE}/catalog-roles/read_only/grants",
        {"grant": {"type": "catalog", "privilege": "TABLE_READ_DATA"}})
    api(tok, "PUT", "/principal-roles/hunters_ro/catalog-roles/" + WAREHOUSE,
        {"catalogRole": {"name": "read_only"}})
    creds = body.get("credentials")
    return f"{creds['clientId']}:{creds['clientSecret']}" if creds else None


def pyi(creds):
    from pyiceberg.catalog.rest import RestCatalog
    return RestCatalog("sdw", **{"uri": CAT_URI, "credential": creds, "scope": "PRINCIPAL_ROLE:ALL",
                                 "warehouse": WAREHOUSE, "header.X-Iceberg-Access-Delegation": "vended-credentials",
                                 "s3.endpoint": S3_ENDPOINT, "s3.path-style-access": "true"})


def main():
    import pyarrow as pa
    res = {"benchmark": "polaris-catalog-dryrun / data-plane (H-CATALOG-AUDITABILITY-01 §10)",
           "evidence_tier": "B (single host; dev config in-memory persistence; Polaris 1.5.0 + MinIO; synthetic)",
           "recipe": "S3+STS endpoints → MinIO, pathStyleAccess=true, explicit TABLE_*_DATA grant"}
    tok = token()
    setup_catalog(tok)

    # admin (service_admin, now with data_rw) creates the table + writes data
    from pyiceberg.schema import Schema
    from pyiceberg.types import NestedField, LongType, StringType
    cat = pyi(ROOT)
    try:
        api(tok, "POST", f"/{WAREHOUSE}/namespaces", {"namespace": [NS], "properties": {}}, base=CAT_URI + "/v1")
        cat.create_table((NS, TBL), schema=Schema(
            NestedField(1, "time", LongType(), required=False),
            NestedField(2, "host", StringType(), required=False)))
    except Exception as e:
        print(f"  namespace/table exists or create skipped: {type(e).__name__}")
    tbl = cat.load_table((NS, TBL))
    rng = random.Random(7)
    data = pa.table({"time": pa.array([1_760_000_000 + i for i in range(N)], pa.int64()),
                     "host": pa.array([f"host_{rng.randint(0, 499):03d}" for _ in range(N)], pa.string())})
    tbl.append(data)
    cnt = tbl.scan().to_arrow().num_rows
    res["data_write"] = {"rows_appended": N, "scan_count": cnt, "ok": cnt >= N}
    print(f"  DATA WRITE: appended {N}, scan {cnt}")

    # table-RBAC: read-only principal must READ but not WRITE
    rcreds = make_reader(tok)
    rbac = {"reader_read_ok": None, "reader_write_blocked": None}
    if rcreds:
        rcat = pyi(rcreds); rtbl = rcat.load_table((NS, TBL))
        rbac["reader_read_ok"] = rtbl.scan().to_arrow().num_rows
        try:
            rtbl.append(pa.table({"time": pa.array([1], pa.int64()), "host": pa.array(["x"], pa.string())}))
            rbac["reader_write_blocked"] = False
        except Exception as e:
            rbac["reader_write_blocked"] = True
            rbac["reader_write_error"] = f"{type(e).__name__}: {str(e)[:80]}"
    res["table_rbac"] = rbac
    print(f"  TABLE-RBAC: reader read={rbac['reader_read_ok']} write_blocked={rbac['reader_write_blocked']}")

    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, "data_plane.json"), "w") as f:
        json.dump(res, f, indent=2, sort_keys=True)
    print("  wrote results/data_plane.json")


if __name__ == "__main__":
    main()

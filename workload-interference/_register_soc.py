"""Register the 4 SOC tables into Nessie from their persistent metadata_locations.
Nessie's version store is IN_MEMORY (compose), so a restart drops registrations while the
data files survive on minio. Cheap + idempotent — called before each server-arm in run_sweep.sh
as insurance. Run inside a container on the ejs-bench network."""
from pyiceberg.catalog.rest import RestCatalog
import json

S3 = {"s3.endpoint": "http://minio:9000", "s3.access-key-id": "ejsbench",
      "s3.secret-access-key": "ejsbench123", "s3.region": "us-east-1",
      "s3.path-style-access": "true"}
cat = RestCatalog("nessie", uri="http://nessie:19120/iceberg/", warehouse="warehouse", **S3)
locs = json.load(open("/repo/engine-join-specialization/_work/table_locations.json"))
cat.create_namespace_if_not_exists("soc")
for t in ["conn", "dns", "assets", "ioc"]:
    meta = locs[f"soc.{t}"]["metadata_location"]
    try:
        cat.load_table(f"soc.{t}")
        continue  # already registered
    except Exception:
        pass
    try:
        cat.register_table(f"soc.{t}", metadata_location=meta)
        print(f"registered soc.{t}", flush=True)
    except Exception as e:
        print(f"soc.{t} register skipped: {str(e)[:80]}", flush=True)
print("register check done")

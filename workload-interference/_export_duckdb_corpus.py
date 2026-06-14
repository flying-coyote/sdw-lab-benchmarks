"""One-off: export the 4 SOC Iceberg tables to local parquet for the duckdb_parquet arm of
#23. Run inside a container on the ejs-bench network (minio:9000 / nessie:19120 resolve)."""
from pyiceberg.catalog.rest import RestCatalog
import pyarrow.parquet as pq
import json
import os

S3 = {"s3.endpoint": "http://minio:9000", "s3.access-key-id": "ejsbench",
      "s3.secret-access-key": "ejsbench123", "s3.region": "us-east-1",
      "s3.path-style-access": "true"}
cat = RestCatalog("nessie", uri="http://nessie:19120/iceberg/", warehouse="warehouse", **S3)
locs = json.load(open("/repo/engine-join-specialization/_work/table_locations.json"))
cat.create_namespace_if_not_exists("soc")
out = "/repo/workload-interference/_work/soc"
os.makedirs(out, exist_ok=True)
# Nessie is IN_MEMORY, so a fresh stack bring-up loses registrations — re-register all soc
# tables from the persistent metadata_locations (data files survive on minio), then export.
for t in ["conn", "dns", "assets", "ioc"]:
    meta = locs[f"soc.{t}"]["metadata_location"]
    try:
        cat.drop_table(f"soc.{t}")
    except Exception:
        pass
    cat.register_table(f"soc.{t}", metadata_location=meta)
    tbl = cat.load_table(f"soc.{t}")
    arrow = tbl.scan().to_arrow()
    pq.write_table(arrow, f"{out}/{t}.parquet")
    print(f"{t}: registered + exported {arrow.num_rows:,} rows -> {os.path.getsize(f'{out}/{t}.parquet'):,} B", flush=True)
print("done")

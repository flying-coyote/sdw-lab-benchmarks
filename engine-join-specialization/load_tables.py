#!/usr/bin/env python3
"""Load all pinned parquet into Iceberg via Nessie's Iceberg-REST endpoint (runs in the
ejs-lab container: docker compose exec lab python load_tables.py [iceberg|ch_native]).

- iceberg: pyiceberg RestCatalog -> nessie, namespaces tpch + soc, 2M-row appends;
  records each table's actual S3 location (for ClickHouse icebergS3) + row counts in
  _work/table_locations.json. Idempotent: a table with the expected row count is skipped;
  a partial table is dropped, its S3 prefix purged (icebergS3 stale-snapshot discipline),
  and reloaded.
- ch_native: server-side copies into MergeTree via icebergS3 reads. Declared layout:
  ORDER BY tuple() — NO sort-key advantage; the native arm isolates the format/read-path
  difference, not a layout difference (deviation from zeek-flagship-rerun's sorted native
  table, declared in README).
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "_work"

NESSIE_REST = "http://nessie:19120/iceberg/"
S3_ENDPOINT = "http://minio:9000"
AK, SK = "ejsbench", "ejsbench123"
CH_PASSWORD = "ejsbench123"
BATCH = 2_000_000

TABLES = {  # namespace -> table -> parquet path
    "tpch": {t: WORK / "tpch" / f"{t}.parquet"
             for t in ["lineitem", "orders", "customer", "supplier", "nation", "region",
                       "part", "partsupp"]},
    "soc": {t: WORK / "soc" / f"{t}.parquet"
            for t in ["conn", "dns", "assets", "ioc", "conn_enriched"]},
}


def catalog():
    from pyiceberg.catalog.rest import RestCatalog
    return RestCatalog("ejs", **{
        "uri": NESSIE_REST, "warehouse": "warehouse",
        "py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO",
        "s3.endpoint": S3_ENDPOINT, "s3.access-key-id": AK, "s3.secret-access-key": SK,
        "s3.path-style-access": "true", "s3.region": "us-east-1",
    })


def purge_prefix(location: str):
    """Delete a table's data prefix so catalog-less icebergS3 cannot resolve stale
    metadata after a reload (reference_clickhouse_icebergs3_stale_snapshot)."""
    from pyarrow.fs import S3FileSystem
    fs = S3FileSystem(access_key=AK, secret_key=SK,
                      endpoint_override=S3_ENDPOINT.split("://")[-1],
                      scheme="http", region="us-east-1")
    prefix = location.split("://", 1)[-1]
    fs.delete_dir_contents(prefix, missing_dir_ok=True)


def load_iceberg():
    import pyarrow.parquet as pq
    cat = catalog()
    locations = {}
    if (WORK / "table_locations.json").exists():
        locations = json.loads((WORK / "table_locations.json").read_text())

    for ns, tables in TABLES.items():
        try:
            cat.create_namespace(ns)
        except Exception:
            pass
        for name, path in tables.items():
            ident = f"{ns}.{name}"
            pf = pq.ParquetFile(path)
            expected = pf.metadata.num_rows
            try:
                tbl = cat.load_table(ident)
                have = len(tbl.scan().plan_files()) and sum(
                    f.file.record_count for f in tbl.scan().plan_files())
                if have == expected:
                    locations[ident] = {"location": tbl.location(), "rows": expected}
                    print(f"{ident}: complete ({expected:,}), skip", flush=True)
                    continue
                print(f"{ident}: partial ({have:,}/{expected:,}), drop + purge + reload",
                      flush=True)
                loc = tbl.location()
                cat.drop_table(ident)
                purge_prefix(loc)
            except Exception as e:
                if "NoSuchTable" not in type(e).__name__ and "404" not in str(e):
                    pass  # table absent — create fresh
            t0 = time.time()
            tbl = cat.create_table(ident, schema=pf.schema_arrow)
            loaded = 0
            for batch in pf.iter_batches(batch_size=BATCH):
                import pyarrow as pa
                tbl.append(pa.Table.from_batches([batch]))
                loaded += batch.num_rows
                print(f"  {ident}: {loaded:,}/{expected:,}", flush=True)
            locations[ident] = {"location": tbl.location(), "rows": expected,
                                "load_seconds": round(time.time() - t0, 1)}
            (WORK / "table_locations.json").write_text(json.dumps(locations, indent=2))
    (WORK / "table_locations.json").write_text(json.dumps(locations, indent=2))
    print("iceberg load DONE", flush=True)


# ClickHouse metadata-pin discipline (declared deviation, README):
# Nessie names every metadata file 00000-<uuid>.metadata.json (no sequence numbers), so
# catalog-less icebergS3() "latest" resolution silently picks an arbitrary commit
# (observed: 54.0M of 59.99M lineitem rows). The DataLakeCatalog REST db fixed reads but
# crash-loops the server at boot (pthread mutex assertion, experimental engine). Final
# mechanism: after load, plant a byte-copy of the catalog's CURRENT metadata pointer
# under a sort-last name so icebergS3 resolution is deterministic and correct. Tables
# are write-once; the pin is planted once and verified count-exact per table.
PIN_NAME = "99999-99999999-9999-4999-8999-999999999999.metadata.json"


def pin_metadata():
    from pyarrow.fs import S3FileSystem
    cat = catalog()
    fs = S3FileSystem(access_key=AK, secret_key=SK,
                      endpoint_override=S3_ENDPOINT.split("://")[-1],
                      scheme="http", region="us-east-1")
    locations = json.loads((WORK / "table_locations.json").read_text())
    for ident, meta in locations.items():
        tbl = cat.load_table(ident)
        meta["metadata_location"] = tbl.metadata_location
        src = tbl.metadata_location.split("://", 1)[-1]
        dst = meta["location"].split("://", 1)[-1] + "/metadata/" + PIN_NAME
        with fs.open_input_stream(src) as f:
            data = f.read()
        with fs.open_output_stream(dst) as f:
            f.write(data)
        print(f"{ident}: pinned {src.rsplit('/', 1)[-1]} -> {PIN_NAME}", flush=True)
    (WORK / "table_locations.json").write_text(json.dumps(locations, indent=2))
    print("pin DONE", flush=True)


def load_ch_native():
    import clickhouse_connect
    client = clickhouse_connect.get_client(host="clickhouse", port=8123,
                                           password=CH_PASSWORD,
                                           send_receive_timeout=3600,
                                           settings={"allow_experimental_database_iceberg": 1})
    client.command("CREATE DATABASE IF NOT EXISTS bench")
    locations = json.loads((WORK / "table_locations.json").read_text())
    for ident, meta in locations.items():
        ns, name = ident.split(".")
        http_loc = meta["location"].replace("s3://", f"{S3_ENDPOINT}/")
        try:
            n = client.query(f"SELECT count() FROM bench.{name}").result_rows[0][0]
            if n == meta["rows"]:
                print(f"bench.{name}: complete ({n:,}), skip", flush=True)
                continue
            client.command(f"DROP TABLE bench.{name}")
        except Exception:
            pass
        t0 = time.time()
        client.command(
            f"CREATE TABLE bench.{name} ENGINE = MergeTree() ORDER BY tuple() "
            f"AS SELECT * FROM icebergS3('{http_loc}', '{AK}', '{SK}')"
        )
        n = client.query(f"SELECT count() FROM bench.{name}").result_rows[0][0]
        assert n == meta["rows"], f"bench.{name}: {n} != {meta['rows']}"
        print(f"bench.{name}: {n:,} rows in {time.time()-t0:.0f}s", flush=True)
    print("ch_native load DONE", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "iceberg"
    {"iceberg": load_iceberg, "ch_native": load_ch_native, "pin": pin_metadata}[mode]()

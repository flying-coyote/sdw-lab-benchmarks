#!/usr/bin/env python3
"""Load the pinned 10M corpus into each arm. Usage: load_arms.py {opensearch|clickhouse|iceberg}

All three arms get the SAME 16 flattened columns (id.orig_h -> orig_h etc.,
tunnel_parents dropped — it is always [] in this corpus). Load times and
storage sizes are captured to _work/load_<arm>.json.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import pyarrow.parquet as pq

WORK = Path(__file__).parent / "_work"
PARQUET = WORK / "zeek_conn_10m.parquet"
JSONL = WORK / "zeek_conn_10m.jsonl"

RENAME = {"id.orig_h": "orig_h", "id.orig_p": "orig_p", "id.resp_h": "resp_h", "id.resp_p": "resp_p"}
COLUMNS = ["ts", "uid", "orig_h", "orig_p", "resp_h", "resp_p", "proto", "service", "duration",
           "orig_bytes", "resp_bytes", "conn_state", "missed_bytes", "history", "orig_pkts", "resp_pkts"]


def flattened_table():
    t = pq.read_table(PARQUET)
    t = t.drop_columns(["tunnel_parents"])
    t = t.rename_columns([RENAME.get(c, c) for c in t.column_names])
    return t.select(COLUMNS)


def write_meta(arm: str, meta: dict):
    (WORK / f"load_{arm}.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


# ---------------- OpenSearch ----------------

def load_opensearch():
    from opensearchpy import OpenSearch, helpers

    client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], http_compress=True,
                        use_ssl=False, verify_certs=False, timeout=300)
    index = "zeek_conn"
    body = {
        "mappings": {"properties": {
            "ts": {"type": "double"}, "uid": {"type": "keyword"},
            "orig_h": {"type": "keyword"}, "orig_p": {"type": "integer"},
            "resp_h": {"type": "keyword"}, "resp_p": {"type": "integer"},
            "proto": {"type": "keyword"}, "service": {"type": "keyword"},
            "duration": {"type": "double"}, "orig_bytes": {"type": "long"},
            "resp_bytes": {"type": "long"}, "conn_state": {"type": "keyword"},
            "missed_bytes": {"type": "long"}, "history": {"type": "keyword"},
            "orig_pkts": {"type": "long"}, "resp_pkts": {"type": "long"},
        }},
        "settings": {"number_of_shards": 1, "number_of_replicas": 0,
                     "refresh_interval": "-1", "index": {"codec": "best_compression"}},
    }
    if client.indices.exists(index=index):
        client.indices.delete(index=index)
    client.indices.create(index=index, body=body)

    def docs():
        with open(JSONL) as f:
            for line in f:
                d = json.loads(line)
                for old, new in RENAME.items():
                    d[new] = d.pop(old)
                d.pop("tunnel_parents", None)
                yield {"_index": index, "_source": d}

    t0 = time.time()
    ok = fail = 0
    for success, _ in helpers.parallel_bulk(client, docs(), chunk_size=5000, thread_count=4,
                                            queue_size=8, raise_on_error=False):
        ok += int(success)
        fail += int(not success)
    load_s = time.time() - t0

    client.indices.refresh(index=index)
    t1 = time.time()
    client.indices.forcemerge(index=index, max_num_segments=1, params={"request_timeout": 3600})
    merge_s = time.time() - t1
    client.indices.refresh(index=index)

    stats = client.indices.stats(index=index)["indices"][index]["primaries"]
    count = client.count(index=index)["count"]
    write_meta("opensearch", {
        "docs_indexed": ok, "bulk_failures": fail, "doc_count": count,
        "bulk_load_seconds": round(load_s, 1), "forcemerge_seconds": round(merge_s, 1),
        "store_size_bytes": stats["store"]["size_in_bytes"],
        "segments": stats["segments"]["count"],
        "settings": "1 shard, 0 replicas, best_compression, forcemerged to 1 segment",
    })


# ---------------- ClickHouse native ----------------

def load_clickhouse():
    import clickhouse_connect

    client = clickhouse_connect.get_client(host="localhost", port=8123)
    client.command("CREATE DATABASE IF NOT EXISTS benchmark")
    client.command("DROP TABLE IF EXISTS benchmark.zeek_native")
    # Default compression (LZ4), no per-column codecs: this is the DEFAULT-CONFIG arm.
    # Layout (PARTITION BY day, ORDER BY (orig_h, resp_h, ts)) is ported from the original
    # benchmark's table and declared as a layout choice, not a default.
    client.command("""
        CREATE TABLE benchmark.zeek_native (
            ts Float64, uid String,
            orig_h String, orig_p UInt16, resp_h String, resp_p UInt16,
            proto String, service Nullable(String), duration Nullable(Float64),
            orig_bytes Nullable(Int64), resp_bytes Nullable(Int64),
            conn_state Nullable(String), missed_bytes Nullable(Int64),
            history Nullable(String), orig_pkts Nullable(Int64), resp_pkts Nullable(Int64)
        ) ENGINE = MergeTree()
        PARTITION BY toDate(toDateTime(ts))
        ORDER BY (orig_h, resp_h, ts)
    """)
    t = flattened_table()
    t0 = time.time()
    client.insert_arrow("benchmark.zeek_native", t)
    client.command("OPTIMIZE TABLE benchmark.zeek_native FINAL")
    load_s = time.time() - t0
    sizes = client.query(
        "SELECT sum(data_compressed_bytes), sum(data_uncompressed_bytes), count() "
        "FROM system.parts WHERE database='benchmark' AND table='zeek_native' AND active"
    ).result_rows[0]
    count = client.query("SELECT count() FROM benchmark.zeek_native").result_rows[0][0]
    write_meta("clickhouse", {
        "row_count": int(count), "load_seconds": round(load_s, 1),
        "compressed_bytes": int(sizes[0]), "uncompressed_bytes": int(sizes[1]),
        "active_parts": int(sizes[2]),
        "server_version": client.query("SELECT version()").result_rows[0][0],
        "settings": "MergeTree, default LZ4, PARTITION BY day, ORDER BY (orig_h, resp_h, ts), OPTIMIZE FINAL",
    })


# ---------------- Iceberg (pyiceberg -> MinIO; ClickHouse reads icebergS3) ----------------

def load_iceberg():
    from pyiceberg.catalog.sql import SqlCatalog

    subprocess.run(
        ["docker", "exec", "zfr-minio", "sh", "-c",
         "mc alias set local http://localhost:9000 zfrbench zfrbench123 && mc mb -p local/zfr-bench"],
        check=True, capture_output=True,
    )
    catalog_db = WORK / "iceberg_catalog.db"
    if catalog_db.exists():
        catalog_db.unlink()
    catalog = SqlCatalog(
        "zfr",
        uri=f"sqlite:///{catalog_db}",
        warehouse="s3://zfr-bench/iceberg",
        **{
            "s3.endpoint": "http://localhost:9000",
            "s3.access-key-id": "zfrbench",
            "s3.secret-access-key": "zfrbench123",
            "s3.region": "us-east-1",
            "s3.path-style-access": "true",
        },
    )
    t = flattened_table()
    catalog.create_namespace_if_not_exists("zeek")
    try:
        catalog.drop_table("zeek.conn_10m")
    except Exception:
        pass
    table = catalog.create_table("zeek.conn_10m", schema=t.schema)
    t0 = time.time()
    # append in 2M-row chunks -> several data files, a realistic layout rather than one giant file
    for i in range(0, t.num_rows, 2_000_000):
        table.append(t.slice(i, 2_000_000))
    load_s = time.time() - t0

    files = list(table.inspect.files().to_pylist())
    data_bytes = sum(f["file_size_in_bytes"] for f in files)
    write_meta("iceberg", {
        "row_count": sum(f["record_count"] for f in files),
        "data_files": len(files),
        "data_file_bytes": int(data_bytes),
        "write_seconds": round(load_s, 1),
        "write_path": "pyiceberg SqlCatalog (sqlite) -> MinIO s3://zfr-bench/iceberg/zeek.db/conn_10m",
        "write_properties": "pyiceberg defaults (zstd parquet) — footer verified in results/env.json",
        "read_path": "ClickHouse icebergS3() catalog-less; write-once table so stale-snapshot risk N/A",
    })


if __name__ == "__main__":
    {"opensearch": load_opensearch, "clickhouse": load_clickhouse, "iceberg": load_iceberg}[sys.argv[1]]()

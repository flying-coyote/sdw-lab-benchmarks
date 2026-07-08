#!/usr/bin/env python3
"""Load the synthetic (uid, text) BM25 corpus (generate_bm25_text.py) into each arm.
Usage: load_bm25_arms.py {opensearch|clickhouse|iceberg}

Mirrors load_arms.py's pattern (same metadata-capture convention) but for the text-only
extension table/index used by the NEEDLE-BM25 arm (staged-benchmark-open-track-prereg.md).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).parent
WORK = HERE / "_work"
PARQUET = WORK / "zeek_conn_10m_bm25text.parquet"
JSONL = WORK / "zeek_conn_10m_bm25text.jsonl"


def write_meta(arm: str, meta: dict):
    (WORK / f"load_bm25_{arm}.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


# ---------------- OpenSearch ----------------

def load_opensearch():
    from opensearchpy import OpenSearch, helpers

    client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], http_compress=True,
                        use_ssl=False, verify_certs=False, timeout=300)
    index = "zeek_conn_bm25text"
    body = {
        "mappings": {"properties": {
            "uid": {"type": "keyword"},
            "text": {"type": "text", "analyzer": "standard"},   # real inverted index + BM25 similarity (default)
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
        "settings": "1 shard, 0 replicas, best_compression, forcemerged to 1 segment, "
                    "text field: standard analyzer (default BM25 similarity)",
    })


# ---------------- ClickHouse native ----------------

def load_clickhouse():
    import clickhouse_connect

    client = clickhouse_connect.get_client(host="localhost", port=8123, password="zfrbench123")
    client.command("CREATE DATABASE IF NOT EXISTS benchmark")
    client.command("DROP TABLE IF EXISTS benchmark.zeek_bm25text")
    client.command("""
        CREATE TABLE benchmark.zeek_bm25text (
            uid String,
            text String,
            INDEX text_idx text TYPE text(tokenizer = 'splitByNonAlpha') GRANULARITY 1
        ) ENGINE = MergeTree()
        ORDER BY uid
        SETTINGS allow_experimental_full_text_index = 1
    """)
    t = pq.read_table(PARQUET)
    t0 = time.time()
    client.insert_arrow("benchmark.zeek_bm25text", t)
    client.command("OPTIMIZE TABLE benchmark.zeek_bm25text FINAL")
    load_s = time.time() - t0
    sizes = client.query(
        "SELECT sum(data_compressed_bytes), sum(data_uncompressed_bytes), count() "
        "FROM system.parts WHERE database='benchmark' AND table='zeek_bm25text' AND active"
    ).result_rows[0]
    count = client.query("SELECT count() FROM benchmark.zeek_bm25text").result_rows[0][0]
    write_meta("clickhouse", {
        "row_count": int(count), "load_seconds": round(load_s, 1),
        "compressed_bytes": int(sizes[0]), "uncompressed_bytes": int(sizes[1]),
        "active_parts": int(sizes[2]),
        "server_version": client.query("SELECT version()").result_rows[0][0],
        "settings": "MergeTree, ORDER BY uid, text-index (splitByNonAlpha tokenizer) on `text`, "
                    "allow_experimental_full_text_index=1, no native BM25/relevance-ranking function "
                    "(verified: system.functions has no bm25/rank hit; hasToken/hasAnyToken/hasAllTokens "
                    "only -- boolean token match, not ranked retrieval)",
    })


# ---------------- Iceberg (pyiceberg -> MinIO; ClickHouse reads icebergS3) ----------------

def load_iceberg():
    from pyiceberg.catalog.sql import SqlCatalog

    subprocess.run(
        ["docker", "exec", "zfr-minio", "sh", "-c",
         "mc alias set local http://localhost:9000 zfrbench zfrbench123 && mc mb -p local/zfr-bench"],
        check=True, capture_output=True,
    )
    catalog_db = WORK / "iceberg_catalog.db"   # SAME catalog db as load_arms.py's iceberg table
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
    t = pq.read_table(PARQUET)
    catalog.create_namespace_if_not_exists("zeek")
    try:
        catalog.drop_table("zeek.bm25text")
    except Exception:
        pass
    table = catalog.create_table("zeek.bm25text", schema=t.schema)
    t0 = time.time()
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
        "write_path": "pyiceberg SqlCatalog (sqlite) -> MinIO s3://zfr-bench/iceberg/zeek/bm25text",
        "write_properties": "pyiceberg defaults (zstd parquet)",
        "read_path": "ClickHouse icebergS3() catalog-less; write-once table; NO index of any kind "
                    "(Parquet min/max stats only, no text/inverted index support on external table function)",
    })


if __name__ == "__main__":
    {"opensearch": load_opensearch, "clickhouse": load_clickhouse, "iceberg": load_iceberg}[sys.argv[1]]()

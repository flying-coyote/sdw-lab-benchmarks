"""The 5 standardized flagship queries, per arm, plus answer extractors.

SQL forms are verbatim from the original standardized suite
(splunk-db-connect-benchmark scripts/run_clickhouse_native_benchmark.py);
OpenSearch DSL is the original translation with two DECLARED deviations made
for answer-equality (both documented in README pre-registration):
  1. port_scan terms size 10000 -> 20000 (exceeds the corpus's unique orig_h
     count, making the agg exhaustive like the SQL GROUP BY).
  2. precision_threshold 3000 on the cardinality aggs — exact below the
     threshold, and ground-truthed exact for THIS corpus via ClickHouse
     (max distinct resp_p per orig_h = 10; distinct resp_h per orig_h ≤ ~700).
     A first attempt at 40000 pre-allocated ~3.6 GB and tripped the 6 GB
     heap's circuit breaker; 3000 keeps exactness with bounded memory.

Corpus-realism note (found during ground-truthing, recorded in RESULTS.md):
max distinct ports per source is exactly 10, so port_scan_detection's
HAVING > 10 returns an EMPTY set on this corpus — in the original benchmark
too. The aggregation work being timed is real; the detection semantics are
hollow on this synthetic corpus.
"""

CH_NATIVE_TABLE = "benchmark.zeek_native"

ICEBERG_TABLE_FN = (
    "icebergS3('http://minio:9000/zfr-bench/iceberg/zeek/conn_10m', "
    "'zfrbench', 'zfrbench123')"
)


def ch_queries(table_expr: str) -> dict:
    return {
        "count_all": f"SELECT COUNT(*) AS cnt FROM {table_expr}",
        "top_source_ips_by_bytes": (
            "SELECT orig_h, SUM(COALESCE(orig_bytes, 0) + COALESCE(resp_bytes, 0)) AS total_bytes "
            f"FROM {table_expr} GROUP BY orig_h ORDER BY total_bytes DESC LIMIT 10"
        ),
        "protocol_distribution": (
            f"SELECT proto, COUNT(*) AS cnt FROM {table_expr} GROUP BY proto ORDER BY cnt DESC"
        ),
        "long_duration_connections": (
            "SELECT orig_h, resp_h, duration, orig_bytes, resp_bytes "
            f"FROM {table_expr} WHERE duration > 60 ORDER BY duration DESC LIMIT 10"
        ),
        "port_scan_detection": (
            "SELECT orig_h, COUNT(DISTINCT resp_p) AS unique_ports, COUNT(DISTINCT resp_h) AS unique_hosts "
            f"FROM {table_expr} WHERE proto = 'tcp' GROUP BY orig_h "
            "HAVING unique_ports > 10 ORDER BY unique_ports DESC LIMIT 10"
        ),
    }


OS_QUERIES = {
    "count_all": {
        "size": 0,
        "track_total_hits": True,
    },
    "top_source_ips_by_bytes": {
        "size": 0,
        "aggs": {
            "by_orig_h": {
                "terms": {"field": "orig_h", "size": 10, "order": {"total_bytes": "desc"}},
                "aggs": {
                    "total_bytes": {
                        "sum": {
                            "script": {
                                "source": "(doc['orig_bytes'].size() > 0 ? doc['orig_bytes'].value : 0) + (doc['resp_bytes'].size() > 0 ? doc['resp_bytes'].value : 0)"
                            }
                        }
                    }
                },
            }
        },
    },
    "protocol_distribution": {
        "size": 0,
        "aggs": {
            "by_proto": {"terms": {"field": "proto", "size": 10, "order": {"_count": "desc"}}}
        },
    },
    "long_duration_connections": {
        "size": 10,
        "query": {"range": {"duration": {"gt": 60}}},
        "sort": [{"duration": "desc"}],
        "_source": ["orig_h", "resp_h", "duration", "orig_bytes", "resp_bytes"],
    },
    "port_scan_detection": {
        "size": 0,
        "query": {"term": {"proto": "tcp"}},
        "aggs": {
            "by_orig_h": {
                "terms": {"field": "orig_h", "size": 20000, "min_doc_count": 1},
                "aggs": {
                    "unique_ports": {
                        "cardinality": {"field": "resp_p", "precision_threshold": 3000}
                    },
                    "unique_hosts": {
                        "cardinality": {"field": "resp_h", "precision_threshold": 3000}
                    },
                    "port_filter": {
                        "bucket_selector": {
                            "buckets_path": {"ports": "unique_ports"},
                            "script": "params.ports > 10",
                        }
                    },
                    "scan_sort": {
                        "bucket_sort": {
                            "sort": [{"unique_ports": {"order": "desc"}}],
                            "size": 10,
                        }
                    },
                },
            }
        },
    },
}


# ---- answer extractors: reduce each arm's raw response to a comparable value ----

def extract_ch(name: str, rows: list) -> object:
    if name == "count_all":
        return int(rows[0][0])
    if name == "top_source_ips_by_bytes":
        return [(r[0], int(r[1])) for r in rows]
    if name == "protocol_distribution":
        return sorted((r[0], int(r[1])) for r in rows)
    if name == "long_duration_connections":
        return [(r[0], r[1], round(float(r[2]), 6)) for r in rows]
    if name == "port_scan_detection":
        return [(r[0], int(r[1])) for r in rows]
    raise KeyError(name)


def extract_os(name: str, resp: dict) -> object:
    if name == "count_all":
        return int(resp["hits"]["total"]["value"])
    if name == "top_source_ips_by_bytes":
        return [
            (b["key"], int(round(b["total_bytes"]["value"])))
            for b in resp["aggregations"]["by_orig_h"]["buckets"]
        ]
    if name == "protocol_distribution":
        return sorted(
            (b["key"], int(b["doc_count"]))
            for b in resp["aggregations"]["by_proto"]["buckets"]
        )
    if name == "long_duration_connections":
        return [
            (h["_source"]["orig_h"], h["_source"]["resp_h"], round(float(h["_source"]["duration"]), 6))
            for h in resp["hits"]["hits"]
        ]
    if name == "port_scan_detection":
        return [
            (b["key"], int(b["unique_ports"]["value"]))
            for b in resp["aggregations"]["by_orig_h"]["buckets"]
        ]
    raise KeyError(name)

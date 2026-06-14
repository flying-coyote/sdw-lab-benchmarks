#!/usr/bin/env python3
"""Needle-in-haystack arm (added 2026-06-14): the index's home turf — the other half of the
two-regime story.

The flagship 5-query suite measured the lakehouse on scan-heavy aggregations (where it wins).
This arm measures the OTHER regime: random high-cardinality POINT LOOKUPS (a specific uid /
orig_h IP) that defeat Parquet min/max pruning and the MergeTree sort key — exactly the shape an
inverted index serves from metadata. Showing OpenSearch winning these hard makes the two-regime
claim symmetric and the fair-broker posture airtight: we test where the SIEM wins, not only
where the lakehouse wins.

Arms: OpenSearch 3.7.0 (term query → inverted index), ClickHouse-native MergeTree (sorted by
orig_h,resp_h,ts — uid is NOT in the sort key, so a uid lookup scans), ClickHouse-over-Iceberg
(unsorted, scans). 1 warmup + 7 trials/query, median + CV, answer-equality verified.

Run with opensearch + clickhouse + minio up (the flagship stack). Reads the loaded corpus.
"""
import json
import os
import statistics
import time

import clickhouse_connect
from opensearchpy import OpenSearch

import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from queries import ICEBERG_TABLE_FN as ICEBERG_FN  # icebergS3 against minio:9000 (in-network)

RESULTS = os.path.join(HERE, "results")
CHPW = "zfrbench123"


def pick_needles(ch):
    # high-cardinality values that exist exactly once / rarely — the worst case for pruning
    uid = ch.query("SELECT uid FROM benchmark.zeek_native ORDER BY ts LIMIT 1 OFFSET 5000000").result_rows[0][0]
    orig = ch.query("SELECT orig_h FROM benchmark.zeek_native GROUP BY orig_h ORDER BY count() ASC LIMIT 1").result_rows[0][0]
    return uid, orig


def time_it(fn, trials=7, warmup=1):
    for _ in range(warmup):
        fn()
    durs, ans = [], None
    for _ in range(trials):
        s = time.perf_counter(); ans = fn(); durs.append(time.perf_counter() - s)
    med = statistics.median(durs)
    cv = (statistics.stdev(durs) / statistics.fmean(durs) * 100) if len(durs) > 1 else 0.0
    return round(med, 4), round(cv, 1), ans


def main():
    ch = clickhouse_connect.get_client(host="localhost", port=8123, password=CHPW, query_limit=0)
    os_c = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], use_ssl=False, timeout=600)
    uid, orig = pick_needles(ch)
    print(f"needles: uid={uid}  orig_h={orig}", flush=True)

    needles = {
        "point_lookup_uid": {
            "os": lambda: os_c.search(index="zeek_conn", body={"query": {"term": {"uid": uid}}, "size": 0,
                                      "track_total_hits": True}, params={"request_cache": "false"})["hits"]["total"]["value"],
            "ch_native": lambda: ch.query(f"SELECT count() FROM benchmark.zeek_native WHERE uid='{uid}' SETTINGS use_query_cache=0").result_rows[0][0],
            "ch_iceberg": lambda: ch.query(f"SELECT count() FROM {ICEBERG_FN} WHERE uid='{uid}' SETTINGS use_query_cache=0").result_rows[0][0],
        },
        "point_lookup_rare_ip": {
            "os": lambda: os_c.search(index="zeek_conn", body={"query": {"term": {"orig_h": orig}}, "size": 0,
                                      "track_total_hits": True}, params={"request_cache": "false"})["hits"]["total"]["value"],
            "ch_native": lambda: ch.query(f"SELECT count() FROM benchmark.zeek_native WHERE orig_h='{orig}' SETTINGS use_query_cache=0").result_rows[0][0],
            "ch_iceberg": lambda: ch.query(f"SELECT count() FROM {ICEBERG_FN} WHERE orig_h='{orig}' SETTINGS use_query_cache=0").result_rows[0][0],
        },
    }

    out = {"benchmark": "needle-in-haystack (index home turf — point lookups)",
           "needles": {"uid": uid, "orig_h": orig}, "queries": {}}
    for qname, arms in needles.items():
        out["queries"][qname] = {}
        print(f"--- {qname} ---", flush=True)
        for arm, fn in arms.items():
            med, cv, ans = time_it(fn)
            out["queries"][qname][arm] = {"median_s": med, "cv_pct": cv, "answer": ans}
            print(f"   {arm:12} median {med:.4f}s CV {cv:.1f}%  answer={ans}", flush=True)
        a = out["queries"][qname]
        a["answer_identical"] = a["os"]["answer"] == a["ch_native"]["answer"] == a["ch_iceberg"]["answer"]
        # index speedup over the lakehouse arms
        osm = a["os"]["median_s"]
        a["index_vs_ch_native_x"] = round(a["ch_native"]["median_s"] / osm, 1) if osm else None
        a["index_vs_ch_iceberg_x"] = round(a["ch_iceberg"]["median_s"] / osm, 1) if osm else None
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(out, open(os.path.join(RESULTS, "needle.json"), "w"), indent=2)
    print("\n=== index (OpenSearch) advantage on point lookups ===")
    for qname, a in out["queries"].items():
        print(f"  {qname}: index {a['index_vs_ch_native_x']}x vs CH-native, {a['index_vs_ch_iceberg_x']}x vs CH-iceberg | answers_identical={a['answer_identical']}")
    print("wrote results/needle.json")


if __name__ == "__main__":
    main()

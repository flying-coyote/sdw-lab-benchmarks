#!/usr/bin/env python3
"""BM25 relevance ranking — the inverted index's home turf, completing the two-regime symmetry.
The EDR text-search leg showed the index wins token MATCHING (34.7x). This shows the deeper point:
relevance RANKING (BM25 = TF-IDF) is a first-class capability of the inverted index that the columnar
engine lacks natively — not just a latency gap but a capability gap. Reuses the loaded 10M edr_heavy
(OpenSearch command_line = analyzed `text`; ClickHouse command_line = plain String, no inverted index).
Host-run (OS :9200, CH :8323). Tier B, single host.
"""
import os
import json, time, urllib.request
import clickhouse_connect

OS = "http://localhost:9200"; IDX = "edr_heavy"; TBL = "edr_heavy"
CH = dict(host="localhost", port=8323, password="ejsbench123")
QUERIES = {"multiterm": "powershell -enc whoami", "common": "process call create", "mixed": "schtasks netsvcs query"}


def req(path, body):
    r = urllib.request.Request(f"{OS}{path}", data=body.encode(), method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=300) as resp:
        return json.load(resp)


def timeit(fn, trials=5):
    fn(); ds = []
    for _ in range(trials):
        t0 = time.perf_counter(); out = fn(); ds.append(time.perf_counter()-t0)
    ds.sort(); return round(ds[len(ds)//2]*1000, 1), out


def main():
    ch = clickhouse_connect.get_client(**CH, settings={"use_query_cache": 0, "max_execution_time": 300})
    out = {"bench": "edr-two-regime / BM25 relevance (two-regime symmetry, index home turf)", "tier": "B",
           "n_rows": 10_000_000, "queries": {}}
    for name, q in QUERIES.items():
        terms = [t for t in q.split() if t.isalnum() or t.replace("-", "").isalnum()]
        # OpenSearch BM25: native TF-IDF relevance ranking, inverted-index-accelerated
        os_ms, os_out = timeit(lambda: req(f"/{IDX}/_search?request_cache=false",
            json.dumps({"size": 5, "query": {"match": {"command_line": q}}})))
        os_hits = os_out.get("hits", {})
        os_scores = [round(h["_score"], 2) for h in os_hits.get("hits", [])]
        # ClickHouse: NO native BM25. Best effort = manual TF count (no IDF), full scan.
        tf = " + ".join(f"(positionCaseInsensitive(command_line,'{t}')>0)" for t in q.split())
        ch_ms, ch_out = timeit(lambda: ch.query(
            f"SELECT command_line, ({tf}) AS tf FROM {TBL} WHERE ({tf})>0 ORDER BY tf DESC LIMIT 5").result_rows)
        out["queries"][name] = {
            "query": q,
            "opensearch_bm25": {"latency_ms": os_ms, "ranked": True, "scoring": "BM25 (TF-IDF)", "top_scores": os_scores},
            "clickhouse": {"latency_ms": ch_ms, "ranked": False, "scoring": "manual TF count (no IDF), full scan",
                           "note": "columnar engine has no native relevance ranking"},
        }
        print(f"  {name:10} OS-BM25 {os_ms}ms (ranked, scores {os_scores[:3]}) | "
              f"CH {ch_ms}ms (full-scan TF count, NO IDF ranking)", flush=True)
    out["finding"] = ("OpenSearch ranks by BM25 (TF-IDF) natively via the inverted index; ClickHouse has no "
                      "native relevance ranking — it matches via full scan and any 'rank' is a hand-rolled TF "
                      "count without IDF. The index's two-regime win includes a CAPABILITY gap (relevance), not "
                      "only a latency gap.")
    json.dump(out, open(os.path.expanduser("~/sdw-lab-benchmarks/edr-two-regime/results/bm25_relevance.json"), "w"), indent=2, default=str)
    print("\n" + out["finding"])


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""NEEDLE-BM25 (staged-benchmark-open-track-prereg.md, Arm A) — BM25 fuzzy full-text vs the
OpenSearch foil. Runs 4 query classes against the (uid, text) BM25 corpus loaded by
load_bm25_arms.py into: OpenSearch (zeek_conn_bm25text, real inverted index + BM25 similarity),
ClickHouse-native (benchmark.zeek_bm25text, text/inverted index for hasToken accel, NO ranked
relevance function), ClickHouse-Iceberg (icebergS3() over zeek/bm25text, no index at all).

Query classes:
  1. token_exact    — hasToken/match on the planted RARE_TOKEN (exactly N_RARE=500 docs).
                       Deterministic -> answer-equality gate (uid-set identical across arms).
  2. phrase_exact    — match_phrase / LIKE substring on the planted PHRASE (exactly N_PHRASE=300).
                       Deterministic -> answer-equality gate.
  3. fuzzy_match     — OpenSearch `fuzzy` query (edit-distance 1, indexed FST/automaton) vs
                       ClickHouse `editDistance()` over an ARRAY JOIN of tokens (brute-force,
                       no index support for edit-distance). Capability flag + latency multiple.
  4. bm25_relevance  — OpenSearch `match` (multi-term, default BM25 similarity, ranked top-10)
                       vs ClickHouse's best-effort match-COUNT proxy (NOT real BM25: no IDF, no
                       term-frequency saturation, no length norm) — capability flag=False for
                       ClickHouse on true BM25; latency multiple reported against the proxy.

1 discarded warmup + 7 timed trials per query per arm (flagship convention); median + CV;
a latency multiple is claimed only when the gap% exceeds max(CV_a, CV_b) (methodology gate).
Tier B, single host, synthetic corpus, co-resident with the idle moar-* stack (isolation caveat
per the prereg: if CV inflates past the claimed delta, downgrade to a capability/direction claim).
"""
import json
import statistics
import time
from pathlib import Path

import clickhouse_connect
from opensearchpy import OpenSearch

HERE = Path(__file__).parent
RESULTS = HERE / "results"
CHPW = "zfrbench123"

OS_INDEX = "zeek_conn_bm25text"
CH_NATIVE = "benchmark.zeek_bm25text"
CH_ICEBERG_FN = "icebergS3('http://minio:9000/zfr-bench/iceberg/zeek/bm25text', 'zfrbench', 'zfrbench123')"

RARE_TOKEN = "zqrareplant7k"
N_RARE = 500
PHRASE = "zqplant beacon uplink"
N_PHRASE = 300
FUZZY_TARGET = "logn"        # edit-distance 1 from planted term "login"
RELEVANCE_TERMS = ["login", "session", "token", "admin", "error"]

WARMUP = 1
TRIALS = 7


def time_it(fn, trials=TRIALS, warmup=WARMUP):
    for _ in range(warmup):
        fn()
    durs, ans = [], None
    for _ in range(trials):
        s = time.perf_counter(); ans = fn(); durs.append(time.perf_counter() - s)
    med = statistics.median(durs)
    mean = statistics.fmean(durs)
    cv = (statistics.stdev(durs) / mean * 100) if len(durs) > 1 and mean > 0 else 0.0
    return {"median_s": round(med, 4), "mean_s": round(mean, 4), "cv_pct": round(cv, 1),
            "trials": trials, "durations_s": [round(d, 4) for d in durs]}, ans


def gap_claim(fast_res, slow_res):
    """Return (multiple, claimable) per the CV gate: gap% must exceed max(CV_a, CV_b)."""
    f, s = fast_res["median_s"], slow_res["median_s"]
    if f <= 0:
        return None, False
    gap_pct = (s - f) / f * 100
    gate = max(fast_res["cv_pct"], slow_res["cv_pct"])
    return round(s / f, 1) if f else None, gap_pct > gate


def main():
    ch = clickhouse_connect.get_client(host="localhost", port=8123, password=CHPW, query_limit=0)
    os_c = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], use_ssl=False, timeout=600)

    out = {
        "benchmark": "NEEDLE-BM25 (staged-benchmark-open-track-prereg.md Arm A) — "
                    "BM25 fuzzy-full-text vs OpenSearch foil",
        "evidence_tier": "B (single host, synthetic corpus, co-resident with idle moar-* stack)",
        "corpus": json.loads((HERE / "_work" / "bm25_text_fingerprint.json").read_text()),
        "queries": {},
    }

    # ---- 1. token_exact (deterministic; answer-equality gate) ----
    def os_token():
        r = os_c.search(index=OS_INDEX, body={"query": {"match": {"text": RARE_TOKEN}},
                        "size": N_RARE + 200, "_source": ["uid"]}, params={"request_cache": "false"})
        return frozenset(h["_source"]["uid"] for h in r["hits"]["hits"])

    def ch_token(table):
        rows = ch.query(f"SELECT uid FROM {table} WHERE hasToken(text, '{RARE_TOKEN}') "
                        f"SETTINGS allow_experimental_full_text_index=1").result_rows
        return frozenset(r[0] for r in rows)

    print("--- token_exact ---", flush=True)
    q = {}
    for arm, fn in (("opensearch", os_token), ("ch_native", lambda: ch_token(CH_NATIVE)),
                    ("ch_iceberg", lambda: ch_token(CH_ICEBERG_FN))):
        res, ans = time_it(fn)
        q[arm] = {**res, "doc_count": len(ans)}
        print(f"  {arm:12} median {res['median_s']:.4f}s CV {res['cv_pct']:.1f}% docs {len(ans)}", flush=True)
        q.setdefault("_ans", {})[arm] = ans
    ans_sets = q.pop("_ans")
    q["answer_identical"] = ans_sets["opensearch"] == ans_sets["ch_native"] == ans_sets["ch_iceberg"]
    q["expected_count"] = N_RARE
    q["count_matches_ground_truth"] = len(ans_sets["opensearch"]) == N_RARE
    mult, claimable = gap_claim(q["opensearch"], q["ch_native"])
    q["opensearch_vs_ch_native_x"] = {"multiple": mult, "claimable": claimable}
    mult, claimable = gap_claim(q["opensearch"], q["ch_iceberg"])
    q["opensearch_vs_ch_iceberg_x"] = {"multiple": mult, "claimable": claimable}
    out["queries"]["token_exact"] = q

    # ---- 2. phrase_exact (deterministic; answer-equality gate) ----
    def os_phrase():
        r = os_c.search(index=OS_INDEX, body={"query": {"match_phrase": {"text": PHRASE}},
                        "size": N_PHRASE + 200, "_source": ["uid"]}, params={"request_cache": "false"})
        return frozenset(h["_source"]["uid"] for h in r["hits"]["hits"])

    def ch_phrase(table):
        rows = ch.query(f"SELECT uid FROM {table} WHERE text LIKE '%{PHRASE}%' "
                        f"SETTINGS allow_experimental_full_text_index=1, "
                        f"use_text_index_like_evaluation_by_dictionary_scan=1").result_rows
        return frozenset(r[0] for r in rows)

    print("--- phrase_exact ---", flush=True)
    q = {}
    for arm, fn in (("opensearch", os_phrase), ("ch_native", lambda: ch_phrase(CH_NATIVE)),
                    ("ch_iceberg", lambda: ch_phrase(CH_ICEBERG_FN))):
        res, ans = time_it(fn)
        q[arm] = {**res, "doc_count": len(ans)}
        print(f"  {arm:12} median {res['median_s']:.4f}s CV {res['cv_pct']:.1f}% docs {len(ans)}", flush=True)
        q.setdefault("_ans", {})[arm] = ans
    ans_sets = q.pop("_ans")
    q["answer_identical"] = ans_sets["opensearch"] == ans_sets["ch_native"] == ans_sets["ch_iceberg"]
    q["expected_count"] = N_PHRASE
    q["count_matches_ground_truth"] = len(ans_sets["opensearch"]) == N_PHRASE
    mult, claimable = gap_claim(q["opensearch"], q["ch_native"])
    q["opensearch_vs_ch_native_x"] = {"multiple": mult, "claimable": claimable}
    mult, claimable = gap_claim(q["opensearch"], q["ch_iceberg"])
    q["opensearch_vs_ch_iceberg_x"] = {"multiple": mult, "claimable": claimable}
    out["queries"]["phrase_exact"] = q

    with open(RESULTS / "bm25_execution_partial.json", "w") as f:
        json.dump(out, f, indent=2, sort_keys=True, default=list)
    print("  wrote results/bm25_execution_partial.json (checkpoint after deterministic queries)", flush=True)

    # ---- 3. fuzzy_match (capability + latency multiple; NOT answer-equality gated) ----
    def os_fuzzy():
        r = os_c.search(index=OS_INDEX, body={"query": {"fuzzy": {"text": {"value": FUZZY_TARGET, "fuzziness": 1}}},
                        "size": 20, "_source": False}, params={"request_cache": "false"})
        return int(r["hits"]["total"]["value"])

    def ch_fuzzy(table, trials=TRIALS):
        sql = (f"SELECT count() FROM (SELECT uid, word FROM {table} "
               f"ARRAY JOIN splitByNonAlpha(text) AS word WHERE editDistance(word, '{FUZZY_TARGET}') <= 1)")
        return ch.query(sql).result_rows[0][0]

    print("--- fuzzy_match (probing ClickHouse cost first; brute-force ARRAY JOIN + editDistance, no index) ---", flush=True)
    probe_t0 = time.perf_counter()
    probe_ans = ch_fuzzy(CH_NATIVE)
    probe_s = time.perf_counter() - probe_t0
    print(f"  ch_native single-trial probe: {probe_s:.2f}s, matched {probe_ans}", flush=True)
    ch_trials = TRIALS if probe_s < 20 else max(3, TRIALS // 2 if probe_s < 60 else 3)
    ch_iceberg_trials = ch_trials  # iceberg is a superset-cost scan of the same shape; use the same reduced count

    q = {}
    res, ans = time_it(os_fuzzy)
    q["opensearch"] = {**res, "doc_count": ans, "capability": True,
                       "mechanism": "Lucene fuzzy query, edit-distance automaton, indexed"}
    print(f"  opensearch   median {res['median_s']:.4f}s CV {res['cv_pct']:.1f}% docs {ans}", flush=True)

    res, ans = time_it(lambda: ch_fuzzy(CH_NATIVE), trials=ch_trials, warmup=1 if ch_trials == TRIALS else 0)
    q["ch_native"] = {**res, "doc_count": ans, "capability": True,
                      "mechanism": "editDistance() over ARRAY JOIN splitByNonAlpha(text) -- brute-force scan, "
                                  "NOT accelerated by the text index (text index accelerates hasToken/LIKE only)",
                      "trials_note": ("reduced from 7 -- probe run was slow" if ch_trials < TRIALS else None)}
    print(f"  ch_native    median {res['median_s']:.4f}s CV {res['cv_pct']:.1f}% docs {ans} (trials={ch_trials})", flush=True)

    res, ans = time_it(lambda: ch_fuzzy(CH_ICEBERG_FN), trials=ch_iceberg_trials, warmup=1 if ch_iceberg_trials == TRIALS else 0)
    q["ch_iceberg"] = {**res, "doc_count": ans, "capability": True,
                       "mechanism": "editDistance() over ARRAY JOIN on icebergS3() -- brute-force scan, no index of any kind",
                       "trials_note": ("reduced from 7 -- probe was slow" if ch_iceberg_trials < TRIALS else None)}
    print(f"  ch_iceberg   median {res['median_s']:.4f}s CV {res['cv_pct']:.1f}% docs {ans} (trials={ch_iceberg_trials})", flush=True)

    q["answer_note"] = ("counts, not answer-equality-gated -- OpenSearch fuzzy and ClickHouse editDistance "
                        "are different algorithms (Damerau-Levenshtein variants may differ at the margin); "
                        "capability + latency is the claim, not exact equality")
    mult, claimable = gap_claim(q["opensearch"], q["ch_native"])
    q["opensearch_vs_ch_native_x"] = {"multiple": mult, "claimable": claimable}
    mult, claimable = gap_claim(q["opensearch"], q["ch_iceberg"])
    q["opensearch_vs_ch_iceberg_x"] = {"multiple": mult, "claimable": claimable}
    out["queries"]["fuzzy_match"] = q

    with open(RESULTS / "bm25_execution_partial.json", "w") as f:
        json.dump(out, f, indent=2, sort_keys=True, default=list)
    print("  wrote results/bm25_execution_partial.json (checkpoint after fuzzy_match)", flush=True)

    # ---- 4. bm25_relevance (capability flag + latency multiple) ----
    def os_bm25():
        r = os_c.search(index=OS_INDEX, body={"query": {"match": {"text": {"query": " ".join(RELEVANCE_TERMS), "operator": "or"}}},
                        "size": 10, "_source": ["uid"]}, params={"request_cache": "false"})
        return [(h["_source"]["uid"], round(h["_score"], 4)) for h in r["hits"]["hits"]]

    terms_hastoken = "+".join(f"hasToken(text,'{t}')" for t in RELEVANCE_TERMS)
    terms_hasany = "[" + ",".join(f"'{t}'" for t in RELEVANCE_TERMS) + "]"

    def ch_bm25_proxy(table):
        sql = (f"SELECT uid, match_count FROM (SELECT uid, ({terms_hastoken}) AS match_count FROM {table} "
               f"WHERE hasAnyToken(text, {terms_hasany})) ORDER BY match_count DESC LIMIT 10 "
               f"SETTINGS allow_experimental_full_text_index=1")
        return [(r[0], r[1]) for r in ch.query(sql).result_rows]

    print("--- bm25_relevance ---", flush=True)
    q = {}
    res, ans = time_it(os_bm25)
    q["opensearch"] = {**res, "top10": ans, "capability": True,
                       "mechanism": "native Lucene BM25 similarity (default k1/b), match query OR across 5 terms"}
    print(f"  opensearch   median {res['median_s']:.4f}s CV {res['cv_pct']:.1f}%", flush=True)

    res, ans = time_it(lambda: ch_bm25_proxy(CH_NATIVE))
    q["ch_native"] = {**res, "top10": ans, "capability": False,
                      "mechanism": "NOT BM25 -- naive matched-term COUNT proxy (no IDF, no term-frequency "
                                  "saturation, no doc-length normalization); verified no bm25/rank function "
                                  "exists in system.functions"}
    print(f"  ch_native    median {res['median_s']:.4f}s CV {res['cv_pct']:.1f}%", flush=True)

    res, ans = time_it(lambda: ch_bm25_proxy(CH_ICEBERG_FN))
    q["ch_iceberg"] = {**res, "top10": ans, "capability": False,
                       "mechanism": "same naive proxy as ch_native, run over icebergS3() (no index, full scan)"}
    print(f"  ch_iceberg   median {res['median_s']:.4f}s CV {res['cv_pct']:.1f}%", flush=True)

    mult, claimable = gap_claim(q["opensearch"], q["ch_native"])
    q["opensearch_vs_ch_native_x"] = {"multiple": mult, "claimable": claimable}
    mult, claimable = gap_claim(q["opensearch"], q["ch_iceberg"])
    q["opensearch_vs_ch_iceberg_x"] = {"multiple": mult, "claimable": claimable}
    out["queries"]["bm25_relevance"] = q

    with open(RESULTS / "bm25_execution.json", "w") as f:
        json.dump(out, f, indent=2, sort_keys=True, default=list)
    print("wrote results/bm25_execution.json", flush=True)


if __name__ == "__main__":
    main()

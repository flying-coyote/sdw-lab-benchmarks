"""H-SIGMA-01 execution leg — does PPL's dropped correlation window actually over-fire?

The compile-time finding (C4 / correlation.py): the pySigma OpenSearch **PPL** backend compiles the
`brute_force` event-count correlation rule (>=10 failed logons per actor_user within 10m) to a
RUNNABLE query that DROPS the timespan window:

    source=auth-* | where outcome="FAILURE" | stats count() as event_count by actor_user
                  | where event_count >= 10

i.e. ">=10 failures in 10 minutes" silently becomes ">=10 failures EVER". The Lucene backend instead
refuses loudly (NotImplementedError). This leg EXECUTES both the emitted windowless PPL and a correct
windowed PPL (tumbling span 10m) against a synthetic planted corpus on OpenSearch 3.7.0 and measures
the over-fire the dropped window causes.

Planted corpus (synthetic; structured auth events only — no real telemetry):
  - TRUE   actor_users: a real burst — 12 FAILUREs inside ONE aligned 10-min bucket (true bruteforce).
  - DECOY  actor_users: 12 FAILUREs spread uniformly over 7 days — >=10 EVER but never >=10 in any
                        10-min window (normal accumulated typos/lockouts). The windowed rule must IGNORE
                        these; the windowless PPL WRONGLY flags them — the dropped-window false positives.
  - BENIGN actor_users: <10 FAILUREs total — neither rule flags.

Score: the windowless PPL's precision / over-fire rate (DECOY flagged) vs the windowed query, vs the
known ground truth. Tier B, single host, synthetic, one chain shape.
"""
import json, os, random, time, urllib.request

OS = os.environ.get("OS_HOST", "http://localhost:9200")
INDEX = "auth-synth"
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 0x51614   # fixed; deterministic corpus
N_TRUE, N_DECOY, N_BENIGN = 20, 50, 500
BURST_N = 12            # failures in a true burst (>=10)
DECOY_N = 12            # failures spread over 7 days (>=10 ever, never >=10 in 10m)
WINDOW_S = 600          # 10 minutes
BASE = (1_760_000_000 // WINDOW_S) * WINDOW_S  # epoch-ALIGNED to the 10-min span bucket so a planted
#                                                burst lands in ONE OpenSearch span(@timestamp,10m) bucket
#                                                (else a boundary-straddling burst splits — a tumbling
#                                                artifact, not a real finding); synthetic, not real telemetry


def _req(method, path, body=None, ctype="application/json"):
    data = body.encode() if isinstance(body, str) else body
    r = urllib.request.Request(f"{OS}{path}", data=data, method=method,
                               headers={"Content-Type": ctype} if data else {})
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.load(resp)


def gen_corpus():
    rng = random.Random(SEED)
    docs = []   # each: (ts_epoch_s, actor_user, outcome)
    truth = {"true": [], "decoy": [], "benign": []}

    def add(user, ts, outcome):
        docs.append((ts, user, outcome))

    # TRUE: 12 failures inside one aligned 10-min bucket
    for i in range(N_TRUE):
        u = f"true_{i:03d}"; truth["true"].append(u)
        bucket_start = BASE + (rng.randint(0, 6 * 24 * 6) * WINDOW_S)  # an aligned 10m bucket in a 6-day span
        for _ in range(BURST_N):
            add(u, bucket_start + rng.randint(10, WINDOW_S - 10), "FAILURE")
        # a couple successes for realism
        for _ in range(rng.randint(0, 2)):
            add(u, bucket_start + rng.randint(0, WINDOW_S), "SUCCESS")

    # DECOY: 12 failures spread uniformly across 7 days (>=10 ever, <10 in any 10m bucket)
    span = 7 * 24 * 3600
    for i in range(N_DECOY):
        u = f"decoy_{i:03d}"; truth["decoy"].append(u)
        # evenly spaced so no two land in the same 10-min bucket
        step = span // DECOY_N
        for k in range(DECOY_N):
            add(u, BASE + k * step + rng.randint(0, step - 1), "FAILURE")

    # BENIGN: <10 failures total, scattered
    for i in range(N_BENIGN):
        u = f"benign_{i:03d}"; truth["benign"].append(u)
        for _ in range(rng.randint(0, 5)):
            add(u, BASE + rng.randint(0, span), "FAILURE")
        for _ in range(rng.randint(0, 8)):
            add(u, BASE + rng.randint(0, span), "SUCCESS")

    rng.shuffle(docs)
    return docs, truth


def load(docs):
    # recreate index with an explicit date mapping so span() works
    try:
        _req("DELETE", f"/{INDEX}")
    except Exception:
        pass
    _req("PUT", f"/{INDEX}", json.dumps({
        "mappings": {"properties": {
            "@timestamp": {"type": "date", "format": "epoch_second"},
            "actor_user": {"type": "keyword"},
            "outcome": {"type": "keyword"},
        }}}))
    # bulk
    lines = []
    for ts, user, outcome in docs:
        lines.append(json.dumps({"index": {}}))
        lines.append(json.dumps({"@timestamp": ts, "actor_user": user, "outcome": outcome}))
    body = "\n".join(lines) + "\n"
    _req("POST", f"/{INDEX}/_bulk", body, ctype="application/x-ndjson")
    _req("POST", f"/{INDEX}/_refresh")
    cnt = _req("GET", f"/{INDEX}/_count")["count"]
    return cnt


def ppl(query):
    return _req("POST", "/_plugins/_ppl", json.dumps({"query": query}))


def users_from_ppl(resp, user_col="actor_user"):
    cols = [c["name"] for c in resp["schema"]]
    ui = cols.index(user_col)
    return {row[ui] for row in resp["datarows"]}


def main():
    docs, truth = gen_corpus()
    n = load(docs)
    print(f"  loaded {n} synthetic auth events ({N_TRUE} true-burst, {N_DECOY} decoy, {N_BENIGN} benign users)", flush=True)
    true_set, decoy_set, benign_set = set(truth["true"]), set(truth["decoy"]), set(truth["benign"])

    # 1) the emitted WINDOWLESS PPL (as pySigma-backend-opensearch produces it) — window dropped
    windowless_q = (f"source={INDEX} | where outcome='FAILURE' | "
                    f"stats count() as event_count by actor_user | where event_count >= 10")
    wl = users_from_ppl(ppl(windowless_q))

    # 2) a CORRECT WINDOWED PPL (tumbling 10-min span) — what a careful engineer writes
    windowed_q = (f"source={INDEX} | where outcome='FAILURE' | "
                  f"stats count() as c by actor_user, span(@timestamp, 10m) as win | where c >= 10")
    wd = users_from_ppl(ppl(windowed_q))

    def score(flagged):
        tp = len(flagged & true_set); fp_decoy = len(flagged & decoy_set); fp_benign = len(flagged & benign_set)
        fp = fp_decoy + fp_benign
        return {"flagged": len(flagged), "tp": tp, "fp_total": fp, "fp_decoy": fp_decoy,
                "fp_benign": fp_benign,
                "recall": round(tp / max(len(true_set), 1), 3),
                "precision": round(tp / max(len(flagged), 1), 3),
                "false_positive_rate_of_alerts": round(fp / max(len(flagged), 1), 3)}

    res = {
        "benchmark": "ocsf-sigma-detection / PPL execution (H-SIGMA-01 execution leg)",
        "evidence_tier": "B (single host; synthetic planted corpus; OpenSearch 3.7.0 PPL)",
        "rule": "brute_force: event_count >=10 failed logons per actor_user in 10m",
        "emitted_windowless_ppl": windowless_q,
        "correct_windowed_ppl": windowed_q,
        "ground_truth": {"true_burst": len(true_set), "decoy_spread": len(decoy_set), "benign": len(benign_set)},
        "windowless": score(wl),
        "windowed": score(wd),
        "events": n,
    }
    wl_s, wd_s = res["windowless"], res["windowed"]
    print(f"  WINDOWLESS (emitted PPL): flagged {wl_s['flagged']} | tp {wl_s['tp']}/{len(true_set)} "
          f"recall {wl_s['recall']} | precision {wl_s['precision']} | "
          f"FPs {wl_s['fp_total']} (decoy {wl_s['fp_decoy']})", flush=True)
    print(f"  WINDOWED  (correct PPL): flagged {wd_s['flagged']} | tp {wd_s['tp']}/{len(true_set)} "
          f"recall {wd_s['recall']} | precision {wd_s['precision']} | FPs {wd_s['fp_total']}", flush=True)

    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, "ppl_execution.json"), "w") as f:
        json.dump(res, f, indent=2, sort_keys=True)
    print("  wrote results/ppl_execution.json", flush=True)


if __name__ == "__main__":
    main()

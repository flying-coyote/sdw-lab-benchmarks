"""H-SIGMA-01 execution leg #3 — value_count (userspray): the 3rd windowless count rule, executed.

Completes the correlation-type execution matrix. The compile-time finding (sigma-portability) flagged
THREE PPL count rules that silently drop the timespan window (bruteforce/passwordspray event_count +
userspray value_count); the 2026-06-15 event_count leg executed one of them. This executes the value_count
one. The pySigma OpenSearchPPLBackend compiles `userspray` (>=10 DISTINCT actor_users per src_ip in 10m) to a
RUNNABLE but WINDOWLESS query (verified, compiled live):

    | search source=auth-* | where outcome="FAILURE" | stats dc(actor_user) as value_count by src_ip
                           | where value_count >= 10

i.e. ">=10 distinct users in 10 minutes" silently becomes ">=10 distinct users EVER". Executes the emitted
windowless PPL and a correct windowed (tumbling span 10m) PPL against a planted synthetic corpus on
OpenSearch 3.7.0 and measures the over-fire — confirming the dropped-window over-fire GENERALIZES from
event_count to value_count (the distinct-count path), as the compile finding predicted.

Boundary: structured synthetic auth events only — no real telemetry. Tier B, single host, one rule shape.
"""
import json, os, random, urllib.request

OS = os.environ.get("OS_HOST", "http://localhost:9200")
INDEX = "auth-vcspray"
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 0x5163C
N_TRUE, N_DECOY, N_BENIGN = 20, 50, 300
SPRAY_USERS = 12          # distinct users per spray (>=10)
DECOY_USERS = 12          # distinct users spread over 7 days (>=10 ever, never >=10 in 10m)
WINDOW_S = 600
BASE = (1_760_000_000 // WINDOW_S) * WINDOW_S


def _req(method, path, body=None, ctype="application/json"):
    data = body.encode() if isinstance(body, str) else body
    r = urllib.request.Request(f"{OS}{path}", data=data, method=method,
                               headers={"Content-Type": ctype} if data else {})
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.load(resp)


def emitted_ppl():
    from sigma.collection import SigmaCollection
    from sigma.backends.opensearch import OpenSearchPPLBackend
    col = SigmaCollection.from_yaml(open(os.path.join(HERE, "rules", "correlation", "userspray.yml")).read())
    q = OpenSearchPPLBackend().convert(col)[0]
    return q.replace("source=auth-*", f"source={INDEX}")


def gen_corpus():
    rng = random.Random(SEED)
    docs = []
    truth = {"true": [], "decoy": [], "benign": []}

    def add(ip, ts, user):
        docs.append((ts, ip, user, "FAILURE"))

    # TRUE: one src_ip sprays >=12 DISTINCT users inside one aligned 10-min bucket
    for i in range(N_TRUE):
        ip = f"10.0.1.{i}"; truth["true"].append(ip)
        bucket = BASE + rng.randint(0, 6 * 24 * 6) * WINDOW_S
        for u in range(SPRAY_USERS):
            add(ip, bucket + rng.randint(5, WINDOW_S - 5), f"user_{i}_{u:02d}")

    # DECOY: one src_ip hits >=12 distinct users spread over 7 days (>=10 distinct EVER, never >=10 in 10m)
    span = 7 * 24 * 3600
    for i in range(N_DECOY):
        ip = f"10.0.2.{i}"; truth["decoy"].append(ip)
        step = span // DECOY_USERS
        for u in range(DECOY_USERS):
            add(ip, BASE + u * step + rng.randint(0, step - 1), f"d_{i}_{u:02d}")

    # BENIGN: <10 distinct users total
    for i in range(N_BENIGN):
        ip = f"10.0.3.{i}"; truth["benign"].append(ip)
        for u in range(rng.randint(0, 5)):
            add(ip, BASE + rng.randint(0, span), f"b_{i}_{u:02d}")

    rng.shuffle(docs)
    return docs, truth


def load(docs):
    try: _req("DELETE", f"/{INDEX}")
    except Exception: pass
    _req("PUT", f"/{INDEX}", json.dumps({"mappings": {"properties": {
        "@timestamp": {"type": "date", "format": "epoch_second"},
        "src_ip": {"type": "keyword"}, "actor_user": {"type": "keyword"}, "outcome": {"type": "keyword"}}}}))
    lines = []
    for ts, ip, user, outcome in docs:
        lines.append(json.dumps({"index": {}}))
        lines.append(json.dumps({"@timestamp": ts, "src_ip": ip, "actor_user": user, "outcome": outcome}))
    _req("POST", f"/{INDEX}/_bulk", "\n".join(lines) + "\n", ctype="application/x-ndjson")
    _req("POST", f"/{INDEX}/_refresh")
    return _req("GET", f"/{INDEX}/_count")["count"]


def ppl(query):
    return _req("POST", "/_plugins/_ppl", json.dumps({"query": query}))


def ips_from(resp, col="src_ip"):
    cols = [c["name"] for c in resp["schema"]]
    ci = cols.index(col)
    return {row[ci] for row in resp["datarows"] if row[ci] is not None}


def main():
    q = emitted_ppl()
    print(f"  emitted PPL: {q}", flush=True)
    docs, truth = gen_corpus()
    n = load(docs)
    true_set, decoy_set, benign_set = set(truth["true"]), set(truth["decoy"]), set(truth["benign"])
    print(f"  loaded {n} synthetic auth events ({N_TRUE} spray IPs, {N_DECOY} decoy IPs, {N_BENIGN} benign)", flush=True)

    wl = ips_from(ppl(q))   # emitted WINDOWLESS
    windowed_q = (f"source={INDEX} | where outcome='FAILURE' | "
                  f"stats dc(actor_user) as c by src_ip, span(@timestamp, 10m) as win | where c >= 10")
    wd = ips_from(ppl(windowed_q))   # correct WINDOWED

    def score(flagged):
        tp = len(flagged & true_set); fp_d = len(flagged & decoy_set); fp_b = len(flagged & benign_set)
        return {"flagged": len(flagged), "tp": tp, "fp_total": fp_d + fp_b, "fp_decoy": fp_d, "fp_benign": fp_b,
                "recall": round(tp / max(len(true_set), 1), 3),
                "precision": round(tp / max(len(flagged), 1), 3) if flagged else 0.0}

    res = {
        "benchmark": "ocsf-sigma-detection / value_count (userspray) PPL execution (H-SIGMA-01 execution leg #3)",
        "evidence_tier": "B (single host; synthetic planted corpus; OpenSearch 3.7.0 PPL; OpenSearchPPLBackend)",
        "rule": "userspray: value_count dc(actor_user) >= 10 per src_ip in 10m",
        "emitted_windowless_ppl": q, "correct_windowed_ppl": windowed_q,
        "ground_truth": {"true_spray": len(true_set), "decoy_spread": len(decoy_set), "benign": len(benign_set)},
        "windowless": score(wl), "windowed": score(wd), "events": n,
    }
    wl_s, wd_s = res["windowless"], res["windowed"]
    res["dropped_window_overfire_decoys"] = wl_s["fp_decoy"]
    print(f"  WINDOWLESS (emitted): flagged {wl_s['flagged']} | recall {wl_s['recall']} precision {wl_s['precision']} | decoy FP {wl_s['fp_decoy']}", flush=True)
    print(f"  WINDOWED  (correct):  flagged {wd_s['flagged']} | recall {wd_s['recall']} precision {wd_s['precision']} | decoy FP {wd_s['fp_decoy']}", flush=True)

    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "value_count_execution.json"), "w"), indent=2, sort_keys=True)
    print("  wrote results/value_count_execution.json", flush=True)


if __name__ == "__main__":
    main()

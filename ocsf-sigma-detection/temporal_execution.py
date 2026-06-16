"""H-SIGMA-01 execution leg #2 — does PPL's temporal_ordered rule miss + over-fire at runtime?

Companion to ppl_execution.py (which executed the event_count rule and quantified the dropped-WINDOW
over-fire). This executes the OTHER correlation type the 2026-06-15 caveats left unexecuted: the
**temporal_ordered** exec->lateral sequence. See PRE-REG-temporal-execution-2026-06-16.md.

The pySigma OpenSearchPPLBackend compiles `exec_then_lateral.yml` (ps_exec THEN rdp_lat per host within 2h) to:

    | multisearch [search source=process_creation-* | where LIKE(cmd_line, "%-EncodedCommand%")]
                  [search source=network_connection-* | where dst_port=3389]
    | stats dc(EventID) as unique_rules by span(@timestamp, 2h), host | where unique_rules >= 2

Two defects become measurable at execution:
  1. ORDERING DROPPED  — counts co-occurrence, not exec-THEN-lateral -> fires on reversed sequences (over-fire).
  2. WINDOW TUMBLING   — span(2h) is a fixed bucket, not sliding -> a true sequence straddling a 2h bucket
                         boundary lands in two buckets, neither reaching dc>=2 -> silent MISS (the miss rate).
  (3. EventID referenced - a Windows-EventLog field generic data lacks; planted here as a per-rule-type
      constant so the charitable execution can run at all. The "no EventID in your data -> 100% silent miss"
      mode is noted in RESULTS, not the headline.)

We run the VERBATIM emitted PPL against OpenSearch 3.7.0 over a planted synthetic corpus and score flagged
hosts vs a correct sliding+ordered Python reference. Tier B, single host, synthetic, one chain shape.
Boundary: structured synthetic events only — no real telemetry.
"""
import json, os, random, urllib.request

OS = os.environ.get("OS_HOST", "http://localhost:9200")
PROC_INDEX = "process_creation-synth"
NET_INDEX = "network_connection-synth"
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 0x5163A
N = 40                       # hosts per population
WINDOW_S = 7200             # 2h, the rule's timespan
BASE = (1_760_000_000 // WINDOW_S) * WINDOW_S   # epoch-aligned to a 2h bucket (so an in-bucket plant is fair)
EVID_PS, EVID_RDP = 4104, 3  # per-rule-type EventID constants (so dc(EventID) counts distinct RULE types)


def _req(method, path, body=None, ctype="application/json"):
    data = body.encode() if isinstance(body, str) else body
    r = urllib.request.Request(f"{OS}{path}", data=data, method=method,
                               headers={"Content-Type": ctype} if data else {})
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.load(resp)


def emitted_ppl():
    """Compile the rule LIVE so the executed query is the verbatim backend output (version-traceable)."""
    from sigma.collection import SigmaCollection
    from sigma.backends.opensearch import OpenSearchPPLBackend
    col = SigmaCollection.from_yaml(open(os.path.join(HERE, "rules", "correlation", "exec_then_lateral.yml")).read())
    return OpenSearchPPLBackend().convert(col)[0]


def gen_corpus():
    rng = random.Random(SEED)
    proc, net = [], []   # (ts, host, EventID, cmd_line) ; (ts, host, EventID, dst_port)
    truth = {k: [] for k in ("inbucket", "straddle", "wrong_order", "benign_single", "benign_farapart")}

    def bucket_start():
        return BASE + rng.randint(0, 5 * 12) * WINDOW_S   # an aligned 2h bucket within ~5 days

    def ps(host, ts):  proc.append((ts, host, EVID_PS, "powershell.exe -EncodedCommand ZQBjAGgAbwA="))
    def rdp(host, ts): net.append((ts, host, EVID_RDP, 3389))

    # TRUE_INBUCKET: ps THEN rdp, in order, same 2h bucket -> emitted query SHOULD fire
    for i in range(N):
        h = f"inb_{i:03d}"; truth["inbucket"].append(h)
        bs = bucket_start(); t_ps = bs + rng.randint(60, 3000)
        ps(h, t_ps); rdp(h, t_ps + rng.randint(30, 1500))   # rdp after ps, still inside [bs, bs+7200)

    # TRUE_STRADDLE: ps late in bucket k, rdp early in bucket k+1, in order, gap < 2h -> tumbling MISSES it
    for i in range(N):
        h = f"str_{i:03d}"; truth["straddle"].append(h)
        bs = bucket_start(); t_ps = bs + WINDOW_S - rng.randint(120, 600)     # last ~2-10 min of bucket k
        t_rdp = bs + WINDOW_S + rng.randint(120, 600)                          # first ~2-10 min of bucket k+1
        ps(h, t_ps); rdp(h, t_rdp)   # gap < 20 min << 2h, in order -> a REAL attack the sliding rule catches

    # WRONG_ORDER: rdp THEN ps, same bucket -> ordered rule must reject; unordered emitted query OVER-FIRES
    for i in range(N):
        h = f"wro_{i:03d}"; truth["wrong_order"].append(h)
        bs = bucket_start(); t_rdp = bs + rng.randint(60, 3000)
        rdp(h, t_rdp); ps(h, t_rdp + rng.randint(30, 1500))   # ps AFTER rdp = not exec->lateral

    # BENIGN_SINGLE: only one rule type fires -> dc=1, never matches
    for i in range(N):
        h = f"bsg_{i:03d}"; truth["benign_single"].append(h)
        bs = bucket_start()
        (ps if i % 2 == 0 else rdp)(h, bs + rng.randint(60, 6000))

    # BENIGN_FARAPART: both rules but > 2h apart -> different buckets, correctly never matches
    for i in range(N):
        h = f"far_{i:03d}"; truth["benign_farapart"].append(h)
        bs = bucket_start(); t_ps = bs + rng.randint(60, 1200)
        ps(h, t_ps); rdp(h, t_ps + WINDOW_S + rng.randint(1800, 7200))   # > 2h after ps

    return proc, net, truth


def load(proc, net):
    mapping_proc = {"mappings": {"properties": {
        "@timestamp": {"type": "date", "format": "epoch_second"}, "host": {"type": "keyword"},
        "EventID": {"type": "integer"}, "cmd_line": {"type": "keyword"}}}}
    mapping_net = {"mappings": {"properties": {
        "@timestamp": {"type": "date", "format": "epoch_second"}, "host": {"type": "keyword"},
        "EventID": {"type": "integer"}, "dst_port": {"type": "integer"}}}}
    for idx, mp in ((PROC_INDEX, mapping_proc), (NET_INDEX, mapping_net)):
        try: _req("DELETE", f"/{idx}")
        except Exception: pass
        _req("PUT", f"/{idx}", json.dumps(mp))
    def bulk(idx, rows, cols):
        lines = []
        for r in rows:
            lines.append(json.dumps({"index": {}}))
            lines.append(json.dumps(dict(zip(cols, r))))
        _req("POST", f"/{idx}/_bulk", "\n".join(lines) + "\n", ctype="application/x-ndjson")
        _req("POST", f"/{idx}/_refresh")
    bulk(PROC_INDEX, proc, ("@timestamp", "host", "EventID", "cmd_line"))
    bulk(NET_INDEX, net, ("@timestamp", "host", "EventID", "dst_port"))
    return _req("GET", f"/{PROC_INDEX}/_count")["count"], _req("GET", f"/{NET_INDEX}/_count")["count"]


def ppl(query):
    return _req("POST", "/_plugins/_ppl", json.dumps({"query": query}))


def hosts_from(resp, col="host"):
    cols = [c["name"] for c in resp["schema"]]
    hi = cols.index(col)
    return {row[hi] for row in resp["datarows"] if row[hi] is not None}


def reference(proc, net):
    """Correct detector: sliding 2h window AND order enforced (ps.ts < rdp.ts <= ps.ts + 2h)."""
    ps_by = {}; rdp_by = {}
    for ts, h, *_ in proc: ps_by.setdefault(h, []).append(ts)
    for ts, h, *_ in net: rdp_by.setdefault(h, []).append(ts)
    flagged = set()
    for h, pts in ps_by.items():
        for rt in rdp_by.get(h, []):
            if any(pt < rt <= pt + WINDOW_S for pt in pts):
                flagged.add(h); break
    return flagged


def main():
    q = emitted_ppl()
    print(f"  emitted PPL: {q}", flush=True)
    proc, net, truth = gen_corpus()
    cp, cn = load(proc, net)
    print(f"  loaded {cp} process + {cn} network synthetic events across {5*N} hosts", flush=True)

    true_pos = set(truth["inbucket"]) | set(truth["straddle"])   # real exec->lateral within 2h, in order
    negatives = set(truth["wrong_order"]) | set(truth["benign_single"]) | set(truth["benign_farapart"])

    emitted = hosts_from(ppl(q))
    ref = reference(proc, net)

    def score(flagged, label):
        tp = len(flagged & true_pos); fp = len(flagged & negatives)
        rec = round(tp / max(len(true_pos), 1), 3)
        prec = round(tp / max(len(flagged), 1), 3) if flagged else 0.0
        by_pop = {k: len(flagged & set(v)) for k, v in truth.items()}
        return {"label": label, "flagged": len(flagged), "tp": tp, "fp": fp, "recall": rec,
                "precision": prec, "caught_by_population": by_pop}

    res = {
        "benchmark": "ocsf-sigma-detection / temporal_ordered PPL execution (H-SIGMA-01 execution leg #2)",
        "evidence_tier": "B (single host; synthetic planted corpus; OpenSearch 3.7.0 PPL; OpenSearchPPLBackend)",
        "rule": "exec_then_lateral: temporal_ordered ps_exec THEN rdp_lat per host within 2h",
        "emitted_ppl": q,
        "window_seconds": WINDOW_S,
        "ground_truth": {"true_inbucket": N, "true_straddle": N, "wrong_order": N,
                         "benign_single": N, "benign_farapart": N, "true_positives_total": len(true_pos)},
        "emitted_query": score(emitted, "emitted PPL (tumbling span, unordered dc>=2)"),
        "correct_reference": score(ref, "correct sliding+ordered Python reference"),
        "events": {"process": cp, "network": cn},
    }
    # derived headline metrics
    e = res["emitted_query"]
    straddle_caught = e["caught_by_population"]["straddle"]
    res["dropped_window_miss_rate"] = round(1 - straddle_caught / max(N, 1), 3)   # fraction of straddlers missed
    res["dropped_order_overfire"] = e["caught_by_population"]["wrong_order"]       # reversed seqs wrongly flagged

    for s in (res["emitted_query"], res["correct_reference"]):
        print(f"  {s['label']}: flagged {s['flagged']} | recall {s['recall']} | precision {s['precision']} | "
              f"by-pop {s['caught_by_population']}", flush=True)
    print(f"  >> dropped-window MISS RATE (straddlers missed): {res['dropped_window_miss_rate']}", flush=True)
    print(f"  >> dropped-order OVER-FIRE (wrong-order wrongly flagged): {res['dropped_order_overfire']}/{N}", flush=True)

    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, "temporal_execution.json"), "w") as f:
        json.dump(res, f, indent=2, sort_keys=True)
    print("  wrote results/temporal_execution.json", flush=True)


if __name__ == "__main__":
    main()

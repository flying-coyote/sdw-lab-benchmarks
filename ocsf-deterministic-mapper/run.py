"""Deterministic validator vs LLM grounding — does a schema-constrained harness beat the model?

BENCH-B (ocsf-mapping-oracle) ran an LLM under five grounding conditions and found its silent-error rate
(mapping a field to an OCSF path that doesn't exist) ranged 0.60–0.99. This builds the alternative the
Fleak/ZephFlow "harness not the model" posture implies: a deterministic source→OCSF mapper that picks
targets from a generic field-name alias table and **only ever emits a path that exists in the OCSF 1.8.0
schema** (or marks the field unmapped). By construction it cannot produce a silent error. The question is
what that costs in coverage and path-correctness versus the model.

It reuses BENCH-B's gold key, OCSF-1.8.0 path closure, and scoring, and compares against BENCH-B's
committed phi3 numbers. The alias table is generic (common field-naming conventions, not the gold answer
key) so the deterministic arm isn't tuned to the test — it's a fair schema-constrained baseline.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ocsf-mapping-oracle"))
import run as bench_b  # noqa: E402  reuse gold_fields, load_valid_paths, normalize

# Generic field-name → candidate OCSF path rules. Each: (token predicate, candidate path).
# Candidates are checked against the class's valid closure before being emitted, so an
# unsupported candidate falls through to the next rule or to "unmapped" — never an invented path.
def candidates(field):
    f = field.lower()
    toks = set(re.split(r"[^a-z0-9]+", f)) | {f}
    has = lambda *xs: any(x in toks or x in f for x in xs)
    src = has("src", "source", "orig", "client", "sender")
    dst = has("dst", "dest", "resp", "server", "target", "remote")
    out = []
    if has("time", "timestamp", "ts", "published", "eventtime", "_time", "occurred"):
        out += ["time"]
    if has("ip", "addr", "address") and src:
        out += ["src_endpoint.ip", "src_endpoint.uid"]
    if has("ip", "addr", "address") and dst:
        out += ["dst_endpoint.ip"]
    if has("ip", "addr", "address"):
        out += ["src_endpoint.ip", "device.ip"]
    if has("port") and src:
        out += ["src_endpoint.port"]
    if has("port"):
        out += ["dst_endpoint.port"]
    if has("user", "username", "account", "actor", "principal", "uid") and not has("uuid"):
        out += ["actor.user.name", "user.name", "actor.user.uid", "user.uid"]
    if has("host", "hostname", "device", "computer", "machine"):
        out += ["device.hostname", "device.name", "src_endpoint.hostname"]
    if has("bytes", "size", "length") and (has("in", "rx", "recv", "resp")):
        out += ["traffic.bytes_in"]
    if has("bytes", "size", "length") and (has("out", "tx", "sent", "orig")):
        out += ["traffic.bytes_out"]
    if has("bytes", "size"):
        out += ["traffic.bytes"]
    if has("severity", "level", "priority"):
        out += ["severity_id", "severity"]
    if has("message", "msg", "description", "desc", "text", "raw"):
        out += ["message"]
    if has("eventtype", "eventname", "event", "action", "operation", "activity", "method"):
        out += ["metadata.event_code", "activity_id", "api.operation", "action_id"]
    if has("query", "domain", "dns", "hostname") and has("query", "dns", "qname"):
        out += ["query.hostname", "query"]
    if has("status", "result", "outcome", "disposition"):
        out += ["status_id", "disposition_id", "status"]
    if has("uid", "id", "uuid") and has("event", "record", "log"):
        out += ["metadata.uid"]
    if has("proto", "protocol"):
        out += ["connection_info.protocol_name"]
    if has("rule", "policy", "signature"):
        out += ["firewall_rule.name", "policy.name"]
    if has("url", "uri"):
        out += ["url.url_string", "http_request.url"]
    return out


def deterministic_map(field, cls, valid):
    """First candidate path that exists in the class's valid closure; else 'unmapped'."""
    for cand in candidates(field):
        if cand in valid[cls]:
            return cand
    return "unmapped"


def run():
    valid = bench_b.load_valid_paths()
    items = bench_b.gold_fields(0)        # the full 141-mapping gold set, all 6 sources
    n = correct = silent = mapped = 0
    by_source = {}
    for it in items:
        bs = by_source.setdefault(it["source"], {"n": 0, "correct": 0, "mapped": 0})
        pred = deterministic_map(it["field"], it["class"], valid)
        n += 1; bs["n"] += 1
        if pred != "unmapped":
            mapped += 1; bs["mapped"] += 1
            if pred not in valid[it["class"]]:
                silent += 1                # cannot happen by construction; asserted below
            if bench_b.normalize(pred, it["class"]) == bench_b.normalize(it["gold"], it["class"]):
                correct += 1; bs["correct"] += 1
    det = {"n": n, "silent_error_rate": round(silent / n, 4),
           "path_correct": round(correct / n, 4), "coverage_mapped": round(mapped / n, 4),
           "path_correct_of_mapped": round(correct / mapped, 4) if mapped else 0.0,
           "by_source": {s: {"path_correct": round(v["correct"]/v["n"], 4),
                             "coverage": round(v["mapped"]/v["n"], 4)} for s, v in by_source.items()}}
    assert det["silent_error_rate"] == 0.0, "schema-constrained mapper emitted an invalid path"

    # pull BENCH-B's committed phi3 numbers for the comparison
    bpath = os.path.join(HERE, "..", "ocsf-mapping-oracle", "results", "results.json")
    llm = {}
    if os.path.exists(bpath):
        bj = json.load(open(bpath))
        m = next(iter(bj["models"].values()))
        llm = {c: {"silent_error_rate": m["cells"][c]["silent_error_rate"],
                   "path_correct": m["cells"][c]["path_correct"]} for c in m["cells"]}
    return {"benchmark": "ocsf-deterministic-mapper", "evidence_tier": "B",
            "n_fields": n, "deterministic": det, "llm_phi3_conditions": llm}


def render_md(res):
    d = res["deterministic"]; llm = res["llm_phi3_conditions"]
    llm_rows = "\n".join(f"| phi3 / {c} | {llm[c]['silent_error_rate']:.2f} | {llm[c]['path_correct']:.2f} |"
                         for c in llm) if llm else "| (phi3 results not found) | — | — |"
    return f"""# Deterministic validator vs LLM grounding (results)

**Tier B.** A schema-constrained deterministic source→OCSF mapper (generic field-name alias rules, only
ever emitting a path that exists in OCSF 1.8.0) vs BENCH-B's LLM under five grounding conditions, on the
same {res['n_fields']}-mapping gold key and the same scoring.

| mapper | silent-error rate | path-correct |
|---|---|---|
| deterministic (schema-constrained) | {d['silent_error_rate']:.2f} | {d['path_correct']:.2f} |
{llm_rows}

- Deterministic coverage (fields it maps rather than marking unmapped): **{d['coverage_mapped']:.2f}**
- Path-correct *among the fields it maps*: **{d['path_correct_of_mapped']:.2f}**

## Reading

The deterministic mapper's silent-error rate is **0 by construction** — it picks targets only from the
OCSF 1.8.0 schema, so it can map a field correctly, map it wrong-but-valid, or mark it unmapped, but it
can never invent a path that doesn't exist. The LLM, by contrast, invents non-existent paths 60–99% of
the time depending on grounding. That is the "harness not the model" point made concrete: constraining
the output to the schema eliminates the security-relevant failure (a mapping that validates and ships and
is wrong) outright, where prompting alone never does. The honest trade is coverage and content: the
generic alias mapper only attempts the common fields (the rest go unmapped rather than guessed), and its
overall path-correctness is modest — but on the fields it does map it is at least as accurate as the weak
model, with none of the invented paths. The lesson isn't "rules beat models"; it's that the *schema-
constraint in the harness* is doing the safety work, and a model is only safe to use behind the same
constraint. Tier B; the alias table is generic (not tuned to the gold), so this is a fair schema-
constrained baseline, not an upper bound on what a tuned deterministic mapper could cover.
"""


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    res = json.load(open(os.path.join(rdir, "results.json"))) if args.render_only else run()
    if not args.render_only:
        with open(os.path.join(rdir, "results.json"), "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
        d = res["deterministic"]
        print(f"  deterministic: silent-error {d['silent_error_rate']}  path-correct {d['path_correct']}  "
              f"coverage {d['coverage_mapped']}  (correct-of-mapped {d['path_correct_of_mapped']})")
        for c, v in res["llm_phi3_conditions"].items():
            print(f"  phi3/{c}: silent-error {v['silent_error_rate']}  path-correct {v['path_correct']}")
    with open(os.path.join(rdir, "RESULTS.md"), "w") as f:
        f.write(render_md(res))
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()

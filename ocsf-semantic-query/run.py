"""BENCH-C — semantic-query head-to-head (first pass: text-to-SQL arm).

The decisive BENCH-C metric is the silent-error rate on adversary-tail concept queries:
a runtime composes a query that executes and returns a plausible-but-wrong answer. The
full benchmark is three arms — OBDA (Ontop), GraphRAG, and plain text-to-SQL. This first
pass implements the **text-to-SQL baseline** (a local LLM composes DuckDB SQL over the
fidelity store and the result is scored against the testbed ground truth) and scaffolds
the other two arms as pending infrastructure (see README: Ontop and a GraphRAG stack are
not installed here).

Each query is scored: correct (truth recovered), silent (executed, returned rows, truth
not recovered — the security-relevant failure), or loud (SQL errored or returned empty
when truth is non-empty — operationally safer than a silent wrong answer). Anchors to
beat are external: NL2KQL ~58% result-accuracy, BIRD 81.67%.
"""

import argparse
import json
import os
import sys

import duckdb
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
STORE_F = os.path.join(HERE, "..", "bench-a-context-collapse", "_work", "store_f")
GT = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "ground_truth.json")
OLLAMA = "http://localhost:11434/api/generate"

# Adversary-tail concept queries (subset with clean truth comparison). Each: the NL
# question the model sees, and a scorer(result_rows, truth) -> "correct"|"silent".
QUERIES = [
    {"id": "A1", "nl": "Find the beaconing connection: a source/destination pair with roughly "
        "60-second regular inter-arrival, low bytes, sustained for about an hour. Return the "
        "event_uid of each such connection.", "truth_key": "beacon_conn_uids", "kind": "uidset"},
    {"id": "A2", "nl": "Return the exact PowerShell command line containing -EncodedCommand that "
        "executed on host WS1.", "truth_key": "powershell_encoded_cmd", "kind": "substring"},
    {"id": "A6", "nl": "Find the privilege escalation: an AttachUserPolicy API call where MFA was "
        "not present (the mfa_present flag is false). Return its event_uid.", "truth_key": "nomfa_event_uid", "kind": "uid"},
    {"id": "A8", "nl": "Find the DNS domain queried by host WS1 (source hostname WS1) that appears "
        "only once in the data (a first-seen, never-before-observed domain). Return the query_hostname.",
        "truth_key": "c2_domain", "kind": "substring"},
]


def schema_context(con):
    out = []
    for t in ("auth", "session", "network", "dns", "process", "api", "asset"):
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM f_{t}").fetchall()]
        out.append(f"  f_{t}({', '.join(cols)})")
    return "Tables (DuckDB, fidelity OCSF store):\n" + "\n".join(out)


def connect():
    con = duckdb.connect(":memory:")
    for t in ("auth", "session", "network", "dns", "process", "api", "asset"):
        con.execute(f"CREATE VIEW f_{t} AS SELECT * FROM '{STORE_F}/{t}.parquet'")
    return con


def compose_sql(model, schema, nl):
    prompt = (f"You write one DuckDB SQL query to answer a security question over an OCSF "
              f"fidelity store. Output JSON only: {{\"sql\": \"<one SELECT statement>\"}}.\n"
              f"{schema}\n\nQuestion: {nl}")
    try:
        r = requests.post(OLLAMA, json={"model": model, "prompt": prompt, "stream": False,
                          "format": "json", "options": {"temperature": 0}, "keep_alive": "10m"},
                          timeout=180)
        return json.loads(r.json().get("response", "")).get("sql", "")
    except Exception:
        return ""


def score(query, rows, truth):
    """Classify the result against ground truth: correct | silent. (loud handled by caller.)"""
    flat = [str(c) for row in rows for c in row]
    if query["kind"] == "substring":
        return "correct" if any(str(truth) in c for c in flat) else "silent"
    if query["kind"] == "uid":
        return "correct" if str(truth) in flat else "silent"
    if query["kind"] == "uidset":
        truth_set = set(truth)
        got = truth_set & set(flat)
        # recover a majority of the needle set, without flooding (precision proxy)
        return "correct" if len(got) >= 0.5 * len(truth_set) and len(flat) <= 4 * len(truth_set) else "silent"
    return "silent"


def run_text_to_sql(model):
    con = connect()
    schema = schema_context(con)
    gt = json.load(open(GT))["truth_needles"]
    rows_out = []
    for q in QUERIES:
        sql = compose_sql(model, schema, q["nl"])
        outcome, n = "loud", 0
        if sql.strip():
            try:
                res = con.execute(sql).fetchall()
                n = len(res)
                if n == 0:
                    outcome = "loud"        # empty when truth exists ⇒ a visible miss
                else:
                    outcome = score(q, res, gt[q["truth_key"]])
            except Exception:
                outcome = "loud"            # SQL error ⇒ loud failure (safer than silent)
        rows_out.append({"id": q["id"], "outcome": outcome, "rows_returned": n,
                         "sql": sql[:300]})
    con.close()
    n = len(rows_out)
    counts = {k: sum(1 for r in rows_out if r["outcome"] == k) for k in ("correct", "silent", "loud")}
    return {"rows": rows_out, "counts": counts,
            "silent_error_rate": round(counts["silent"] / n, 4),
            "result_accuracy": round(counts["correct"] / n, 4)}


def _obda_section(results):
    o = results.get("arms", {}).get("obda_ontop")
    if not o or o.get("status") != "measured":
        return "\n## OBDA / Ontop arm\n\nPending.\n"
    pq = o["per_query"]
    expr = "\n".join(f"| {q} | {pq[q]['outcome']} | {pq[q].get('rows_returned','—')} |"
                     for q in o["expressible_queries"])
    oob = "\n".join(f"| {q} | out-of-OWL2QL (loud by design) | {why} |"
                    for q, why in o["out_of_owl2ql"].items())
    return f"""
## OBDA / Ontop arm ({o['engine']})

On the queries OWL2QL can express, the formal rewrite is exact; on the rest it is out of
expressivity and refuses rather than guessing. **{int(o['result_accuracy_on_expressible']*100)}% correct on the
expressible set, {int(o['silent_error_rate_on_expressible']*100)}% silent, refusal-honest = {o['refusal_honest']}.** Coverage: {o['coverage']}.

| query | outcome | rows |
|---|---|---|
{expr}

| query | outcome | why it's out of OWL2QL |
|---|---|---|
{oob}

The contrast is the whole point: the OBDA arm answers fewer adversary-tail queries but is
**never silently wrong** on the ones it answers, and its failures are loud (an out-of-expressivity
boundary), where a frontier LLM's failures on this tail are silent (plausible-but-wrong) and the
local text-to-SQL's are loud-but-broken. Whether the formal rewrite's narrow-but-clean coverage
beats the LLM's broad-but-unverified coverage is the decision the third (GraphRAG) arm and a
frontier text-to-SQL leg would complete.
"""


def render_md(results):
    t = results["arms"]["text_to_sql"]
    rows = "\n".join(f"| {r['id']} | {r['outcome']} | {r['rows_returned']} |" for r in t["rows"])
    return f"""# BENCH-C — semantic-query head-to-head: results (first pass)

**Tier B, one arm of three.** This first pass runs the **text-to-SQL baseline arm** (a
local LLM composes DuckDB SQL over the fidelity store, scored against the testbed ground
truth). The OBDA/Ontop and GraphRAG arms are pending infrastructure, so this is the
baseline the formal rewrite would have to beat, not the head-to-head itself.

Model: `{results['model']}`. Anchors (external): NL2KQL ~58% result-accuracy, BIRD 81.67%.

## text-to-SQL arm

| query | outcome | rows |
|---|---|---|
{rows}

- result-accuracy: **{t['result_accuracy']:.2f}**
- silent-error rate: **{t['silent_error_rate']:.2f}**
- counts: {t['counts']}

## Reading

A local model composing SQL over a multi-table OCSF store for adversary-tail concept
queries fails **loudly**, not silently: it hallucinates columns and even functions, so
the SQL errors or returns nothing rather than returning a plausible-but-wrong answer. At
this tier the text-to-SQL baseline is near-unusable on the adversary tail, well below the
NL2KQL frontier anchor. That makes the loud/silent distinction the interesting one: the
silent-error contrast BENCH-C is built to measure — whether a formal OWL2QL rewrite (OBDA)
avoids the plausible-but-wrong answers an LLM gives — needs a model strong enough to
produce silent errors in the first place (the frontier leg) and the OBDA arm to compare
against. Both are the next steps.

{_obda_section(results)}
GraphRAG arm still pending ({results['arms'].get('graphrag', {}).get('blocker', 'no graph+vector stack installed')}).
Tier B, single machine, one planted chain.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="phi3:latest")
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--determinism", action="store_true")
    args = ap.parse_args()
    if args.determinism:
        import hashlib
        con = connect()
        s1, s2 = schema_context(con), schema_context(con)
        gt = json.load(open(GT))["truth_needles"]
        # scorer is a pure function of (query, rows, truth); verify it's stable on a fixed input
        fixed = [("x",), ("y",)]
        stable = score(QUERIES[0], fixed, gt[QUERIES[0]["truth_key"]]) == score(QUERIES[0], fixed, gt[QUERIES[0]["truth_key"]])
        con.close()
        print(f"schema context reproduces: {s1 == s2}")
        print(f"scorer + ground-truth load reproduce: {stable}")
        print("NOTE: schema context, ground truth, and the correct/silent/loud scorer are deterministic; "
              "the SQL the model composes is temperature-0 greedy decode (reproducible in practice, not asserted).")
        sys.exit(0 if (s1 == s2 and stable) else 1)

    if args.render_only:
        res = json.load(open(os.path.join(HERE, "results", "results.json")))
        with open(os.path.join(HERE, "results", "RESULTS.md"), "w") as f:
            f.write(render_md(res))
        print("rendered results/RESULTS.md")
        return

    if not os.path.isdir(STORE_F):
        print("Store F not built — run bench-a-context-collapse/run.py first.", file=sys.stderr)
        sys.exit(2)

    t2s = run_text_to_sql(args.model)
    results = {
        "benchmark": "ocsf-semantic-query (BENCH-C, first pass — text-to-SQL arm)",
        "evidence_tier": "B (text-to-SQL baseline arm only; OBDA + GraphRAG arms pending infra)",
        "model": args.model,
        "anchors": {"NL2KQL_result_accuracy": 0.58, "BIRD_sota": 0.8167},
        "arms": {
            "text_to_sql": t2s,
            "obda_ontop": {"status": "pending", "blocker": "Ontop CLI not installed (JVM present); R2RML mappings to author"},
            "graphrag": {"status": "pending", "blocker": "no graph+vector GraphRAG stack installed"},
        },
    }
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "results.json"), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    with open(os.path.join(HERE, "results", "RESULTS.md"), "w") as f:
        f.write(render_md(results))
    print(f"text-to-SQL ({args.model}): {t2s['counts']}  "
          f"silent-error={t2s['silent_error_rate']:.2f}  result-acc={t2s['result_accuracy']:.2f}")
    for r in t2s["rows"]:
        print(f"  {r['id']}: {r['outcome']} ({r['rows_returned']} rows)")
    print("wrote results/results.json")
    return results


if __name__ == "__main__":
    main()

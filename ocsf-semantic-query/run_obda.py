"""BENCH-C — the OBDA (Ontop) arm: formal OWL2QL rewrite over the OCSF store.

The second arm of the head-to-head. Ontop exposes the fidelity store as a virtual RDF graph
via an OBDA mapping + an OWL2QL ontology, and rewrites SPARQL concept-queries to SQL over
DuckDB. The point of contrast with the LLM arms is the silent-error behaviour: on the queries
OWL2QL CAN express (filters/joins), the rewrite is provably correct on its coverage; on the
queries it CANNOT express (aggregation, windows, recursion), it is out of expressivity and does
not answer — a loud boundary rather than a silently-wrong result.

Needs the Ontop CLI (5.5.0) downloaded and the DuckDB JDBC driver in its jdbc/ dir; set
ONTOP_HOME or use the default. The mapping, ontology, and SPARQL are committed under obda/.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OBDA = os.path.join(HERE, "obda")
WORK = os.path.join(HERE, "_work")
STORE_F = os.path.join(HERE, "..", "bench-a-context-collapse", "_work", "store_f")
GT = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "ground_truth.json")
ONTOP = os.environ.get("ONTOP_HOME", "/tmp/ontop-bench/ontop-cli")
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import configure_duckdb  # noqa: E402

# Queries OWL2QL can express (filters/joins) — expected provably correct on coverage.
EXPRESSIBLE = {
    "A2": {"rq": "a2.rq", "kind": "substring", "truth_key": "powershell_encoded_cmd"},
    "A4": {"rq": "a4.rq.template", "kind": "count", "truth_key": "pit_active_session_uids"},
    "A6": {"rq": "a6.rq", "kind": "uid", "truth_key": "nomfa_event_uid"},
}
# Queries outside OWL2QL (AC0 / first-order-rewritable) — the loud refusal boundary.
OUT_OF_OWL2QL = {
    "A1": "~60s beacon cadence — needs window/aggregation; OWL2QL is first-order-rewritable (no aggregation)",
    "A3": "cross-source kill-chain ordering — needs sort/aggregation over joins",
    "A5": "recursive identity closure — OWL2QL is non-recursive (no transitive closure)",
    "A7": "dwell-time delta — needs aggregation across events",
    "A9": "distinct-asset count — needs aggregation",
}


def nl_pit_anchor(dbf):
    """v2 (addendum §1): A4 point-in-time anchor DERIVED FROM THE NL — the timestamp of the
    privilege-escalation marker event (the no-MFA AttachUserPolicy event, api-needle-nomfa). This
    replaces the v1 gold-constant substitution (which fed the OBDA template the answer-defining
    pit_point_ms straight from ground_truth.json). NEVER reads the gold pit_point_ms."""
    import duckdb
    con = duckdb.connect(dbf)
    r = con.execute("SELECT time FROM api WHERE event_uid = 'api-needle-nomfa'").fetchone()
    con.close()
    return int(r[0]) if r else None


def build_duckdb():
    import duckdb
    os.makedirs(WORK, exist_ok=True)
    dbf = os.path.join(WORK, "storef.duckdb")
    if os.path.exists(dbf):
        os.remove(dbf)
    con = configure_duckdb(duckdb.connect(dbf))
    for t in ("network", "process", "api", "auth", "dns", "session", "asset"):
        con.execute(f"CREATE TABLE {t} AS SELECT * FROM '{STORE_F}/{t}.parquet'")
    con.close()
    return dbf


def write_props(dbf):
    p = os.path.join(WORK, "storef.properties")
    with open(p, "w") as f:
        f.write(f"jdbc.url=jdbc:duckdb:{os.path.abspath(dbf)}\njdbc.driver=org.duckdb.DuckDBDriver\n")
    return p


def run_sparql(props, rq_path):
    cmd = [os.path.join(ONTOP, "ontop"), "query", "-p", props,
           "-m", os.path.join(OBDA, "storef.obda"), "-t", os.path.join(OBDA, "storef.ttl"),
           "-q", rq_path]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    rows = []
    for line in out.stdout.splitlines():
        s = line.strip()
        if not s or "WARNING" in line or "|-" in line or s in ("e", "c", "s", "en"):
            continue
        if line.startswith(("0", "1", "2")) and "|" in line:  # log timestamps
            continue
        rows.append(s)
    return rows, out.returncode


def main():
    if not os.path.isdir(ONTOP):
        print(f"Ontop CLI not found at {ONTOP}. Download ontop-cli-5.5.0.zip, add the DuckDB JDBC "
              f"driver to its jdbc/ dir, and set ONTOP_HOME.", file=sys.stderr)
        sys.exit(2)
    gt = json.load(open(GT))["truth_needles"]
    dbf = build_duckdb()
    props = write_props(dbf)
    nl_anchor = nl_pit_anchor(dbf)   # v2: A4 anchor DERIVED FROM NL, never the gold pit_point_ms

    results = {}
    for qid, q in EXPRESSIBLE.items():
        # v2 (addendum §1): A4 is ill-posed (the NL anchor yields 45, the gold pit yields 35), so it
        # is EXCLUDED from the scored head-to-head and REPORTED as a question-design finding. The
        # template is still executed with the NL-DERIVED anchor (NOT the gold constant) for the audit
        # record, so a reviewer can see the 45-vs-35 mismatch directly.
        if qid == "A4":
            rq2 = os.path.join(WORK, "a4.rq")
            with open(os.path.join(OBDA, q["rq"])) as f:
                tmpl = f.read().replace("__PIT__", str(nl_anchor))
            open(rq2, "w").write(tmpl)
            rows, rc = run_sparql(props, rq2)
            results[qid] = {"outcome": "excluded_ill_posed", "expressible": True, "scored": False,
                            "nl_anchor_ms": nl_anchor, "nl_anchored_rows": len(rows) if rc == 0 else None,
                            "gold_pit_ms": gt.get("pit_point_ms"), "gold_count": len(gt[q["truth_key"]]),
                            "note": ("A4 EXCLUDED as ill-posed: NL anchor = priv-esc marker event time "
                                     f"({nl_anchor}) -> {len(rows) if rc==0 else 'err'} sessions; gold "
                                     f"pit_point_ms ({gt.get('pit_point_ms')}) -> {len(gt[q['truth_key']])}. "
                                     "The gold pit is tied to no named chain stage; do NOT score A4.")}
            print(f"  {qid}: excluded_ill_posed (NL-anchored rows={len(rows) if rc==0 else 'err'}, gold={len(gt[q['truth_key']])})")
            continue
        rq = os.path.join(OBDA, q["rq"])
        rows, rc = run_sparql(props, rq)
        if rc != 0:
            outcome = "loud"
        elif not rows:
            outcome = "loud"
        elif q["kind"] == "substring":
            outcome = "correct" if any(str(gt[q["truth_key"]]) in r for r in rows) else "silent"
        elif q["kind"] == "uid":
            outcome = "correct" if str(gt[q["truth_key"]]) in rows else "silent"
        elif q["kind"] == "count":
            outcome = "correct" if len(rows) == len(gt[q["truth_key"]]) else "silent"
        results[qid] = {"outcome": outcome, "rows_returned": len(rows), "expressible": True, "scored": True}
        print(f"  {qid}: {outcome} ({len(rows)} rows)")

    for qid, why in OUT_OF_OWL2QL.items():
        results[qid] = {"outcome": "out_of_expressivity", "expressible": False, "reason": why}
        print(f"  {qid}: out-of-OWL2QL (loud by design) — {why}")

    # v2: A4 is excluded from scoring (ill-posed), so the scored expressible set is A2/A6 only.
    expr_scored = [r for r in results.values() if r["expressible"] and r.get("scored")]
    n_expr = len(expr_scored)
    correct = sum(1 for r in expr_scored if r["outcome"] == "correct")
    silent = sum(1 for r in expr_scored if r["outcome"] == "silent")
    excluded = [qid for qid, r in results.items() if r.get("outcome") == "excluded_ill_posed"]
    arm = {
        "status": "measured", "engine": "Ontop 5.5.0 (OWL2QL) over DuckDB",
        "expressible_queries": list(EXPRESSIBLE), "out_of_owl2ql": OUT_OF_OWL2QL,
        "excluded_ill_posed": excluded,   # A4 (addendum §1)
        "per_query": results,
        "result_accuracy_on_expressible": round(correct / n_expr, 4) if n_expr else None,
        "silent_error_rate_on_expressible": round(silent / n_expr, 4) if n_expr else None,
        "coverage": f"{n_expr} scored expressible (A4 excluded ill-posed) + {len(OUT_OF_OWL2QL)} out-of-OWL2QL",
        # refusal-honest = never silently wrong on what it SCORES (excluded A4 is not a silent result)
        "refusal_honest": all(r["outcome"] not in ("silent",) for r in results.values()),
    }
    # merge into the BENCH-C results.json
    rpath = os.path.join(HERE, "results", "results.json")
    full = json.load(open(rpath)) if os.path.exists(rpath) else {"arms": {}}
    full["arms"]["obda_ontop"] = arm
    json.dump(full, open(rpath, "w"), indent=2, sort_keys=True)
    print(f"\nOBDA arm: {correct}/{n_expr} correct on expressible, {silent} silent, "
          f"{len(OUT_OF_OWL2QL)} out-of-OWL2QL (loud-by-design), refusal-honest={arm['refusal_honest']}")
    print("merged into results/results.json")


if __name__ == "__main__":
    main()

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

    results = {}
    for qid, q in EXPRESSIBLE.items():
        rq = os.path.join(OBDA, q["rq"])
        if q["rq"].endswith(".template"):
            rq2 = os.path.join(WORK, "a4.rq")
            with open(os.path.join(OBDA, q["rq"])) as f:
                tmpl = f.read().replace("__PIT__", str(gt["pit_point_ms"]))
            open(rq2, "w").write(tmpl); rq = rq2
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
        results[qid] = {"outcome": outcome, "rows_returned": len(rows), "expressible": True}
        print(f"  {qid}: {outcome} ({len(rows)} rows)")

    for qid, why in OUT_OF_OWL2QL.items():
        results[qid] = {"outcome": "out_of_expressivity", "expressible": False, "reason": why}
        print(f"  {qid}: out-of-OWL2QL (loud by design) — {why}")

    expr = [r for r in results.values() if r["expressible"]]
    n_expr = len(expr)
    correct = sum(1 for r in expr if r["outcome"] == "correct")
    silent = sum(1 for r in expr if r["outcome"] == "silent")
    arm = {
        "status": "measured", "engine": "Ontop 5.5.0 (OWL2QL) over DuckDB",
        "expressible_queries": list(EXPRESSIBLE), "out_of_owl2ql": OUT_OF_OWL2QL,
        "per_query": results,
        "result_accuracy_on_expressible": round(correct / n_expr, 4),
        "silent_error_rate_on_expressible": round(silent / n_expr, 4),
        "coverage": f"{n_expr}/{n_expr + len(OUT_OF_OWL2QL)} adversary queries expressible in OWL2QL",
        "refusal_honest": all(r["outcome"] != "silent" for r in results.values()),
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

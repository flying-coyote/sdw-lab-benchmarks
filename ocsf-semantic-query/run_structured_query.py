#!/usr/bin/env python3
"""BENCH-C v2 — the STRUCTURED-GRAPH-QUERY arm (addendum §2).

The tail (A3/A4/A7/A9) is compute-over-a-population, not a fact to retrieve, so the honest contrast
is compute-over-graph vs probabilistic compute. v1 never gave GraphRAG a structured-query channel —
it measured retrieve-from-graph where it should have measured compute-over-graph. This arm closes
that gap:

  - the LLM AUTHORS a SPARQL query over the existing OCSF ontology (probabilistic GENERATION step,
    8 trials/query for variance, addendum §6), then
  - the query is EXECUTED DETERMINISTICALLY via the existing Ontop/OBDA mapping path (reuse
    run_obda.py: build_duckdb / write_props / run_sparql) — no new graph DB.

This is DISTINCT from:
  - OBDA-deterministic (curated/templated SPARQL -> deterministic rewrite), and
  - LLM-text-to-SQL (LLM SQL over the RAW tables).
The differentiator under test is the TARGET SCHEMA (curated ontology view vs raw tables) and whether
the query is curated or LLM-authored; execution is deterministic in both structured arms.

A4 (addendum §1): EXCLUDED as ill-posed — the NL anchor (the priv-esc marker event timestamp) yields
45 active sessions; the gold pit_point_ms (2.7h later, tied to no named stage) yields 35. So the NL
does not determine the gold. This arm never reads the gold pit_point_ms; A4 is reported, not scored.

Ontop dependency: the canonical execution path is Ontop (set ONTOP_HOME; run_obda.py documents the
fetch). If Ontop is ABSENT, --exec-fallback runs the SPARQL through a documented, restricted
SPARQL->DuckDB executor (rdflib parse + a basic-graph-pattern evaluator over the SAME OBDA mappings)
so the deterministic EXECUTION path is exercisable for the smoke test. The fallback is labeled in the
output and is NOT the path of record for a published result — flag it if it is ever scored.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import bench_c_v2_config as CFG  # noqa: E402
import run_obda as OBDA  # noqa: E402  (reuse build_duckdb / write_props / run_sparql)

# The tail queries this arm authors SPARQL for. A4 is present so it can be REPORTED-as-excluded.
TAIL = {
    "A3": {"truth_key": "truth_event_order", "kind": "order",
           "nl": "Reconstruct the kill chain: list the attack stages in the order they occurred."},
    "A4": {"truth_key": "pit_active_session_uids", "kind": "count",
           "nl": "How many sessions were active at the point in time of the privilege escalation?",
           "excluded": True},
    "A7": {"truth_key": "dwell_seconds", "kind": "scalar",
           "nl": "Dwell time in seconds: elapsed time between the first and last event of the chain."},
    "A9": {"truth_key": "distinct_asset_count", "kind": "exact_scalar",
           "nl": "How many DISTINCT physical assets are there once hostname/ip/instance-id aliases "
                 "are collapsed across the asset population?"},
}


def execute_sparql_ontop(sparql_text, props):
    """Canonical execution: write the SPARQL to a temp .rq and run it through Ontop over the OBDA
    mappings (run_obda.run_sparql). Returns (cells|None, returncode). None/empty/non-zero = loud."""
    rqf = os.path.join(OBDA.WORK, "_structured_query.rq")
    os.makedirs(OBDA.WORK, exist_ok=True)
    open(rqf, "w").write(sparql_text)
    rows, rc = OBDA.run_sparql(props, rqf)
    if rc != 0:
        return None, rc
    return rows, rc


def execute_sparql_fallback(sparql_text):
    """Ontop-absent EXECUTION fallback for the smoke test only. Parses the SPARQL with rdflib and
    evaluates a restricted basic-graph-pattern (the OWL2QL-expressible subset: type + datatype-
    property filters/joins) against an in-memory rdflib graph materialized from the SAME OBDA
    mappings. NOT the path of record — labeled in the result. Raises if rdflib is unavailable so the
    caller can mark the arm loud-by-infrastructure rather than silently passing."""
    import rdflib  # noqa
    g = _materialize_rdf_from_mappings()
    try:
        res = g.query(sparql_text)
    except Exception:
        return None  # parse/exec failure -> loud
    cells = []
    for row in res:
        for v in row:
            cells.append(str(v))
    return cells


_RDF_CACHE = {}


def _materialize_rdf_from_mappings():
    """Build an rdflib Graph from the OBDA mappings over Store F — the same virtual RDF view Ontop
    would expose, materialized for the fallback executor. Covers the mapped classes (Process /
    ApiEvent / Session) exactly as storef.obda declares. Cached per process."""
    if "g" in _RDF_CACHE:
        return _RDF_CACHE["g"]
    import duckdb
    import rdflib
    from rdflib import Literal, URIRef
    NS = "http://sdw.example/ocsf#"
    g = rdflib.Graph()
    g.bind("", rdflib.Namespace(NS))
    con = duckdb.connect()
    SF = CFG.STORE_F
    # m-process
    for uid, cmd, host in con.execute(
            f"SELECT event_uid, cmd_line, device_hostname FROM '{SF}/process.parquet'").fetchall():
        s = URIRef(f"{NS}proc/{uid}")
        g.add((s, URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), URIRef(f"{NS}Process")))
        g.add((s, URIRef(f"{NS}eventUid"), Literal(uid)))
        if cmd is not None:
            g.add((s, URIRef(f"{NS}cmdLine"), Literal(cmd)))
        if host is not None:
            g.add((s, URIRef(f"{NS}host"), Literal(host)))
    # m-api
    for uid, op, mfa, actor in con.execute(
            f"SELECT event_uid, api_operation, mfa_present, actor_user_uid FROM '{SF}/api.parquet'").fetchall():
        s = URIRef(f"{NS}api/{uid}")
        g.add((s, URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), URIRef(f"{NS}ApiEvent")))
        g.add((s, URIRef(f"{NS}eventUid"), Literal(uid)))
        if op is not None:
            g.add((s, URIRef(f"{NS}operation"), Literal(op)))
        g.add((s, URIRef(f"{NS}mfaPresent"), Literal(bool(mfa))))
        if actor is not None:
            g.add((s, URIRef(f"{NS}actor"), Literal(actor)))
    # m-session
    for uid, st, en, host in con.execute(
            f"SELECT event_uid, start_time, end_time, host FROM '{SF}/session.parquet'").fetchall():
        s = URIRef(f"{NS}sess/{uid}")
        g.add((s, URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), URIRef(f"{NS}Session")))
        g.add((s, URIRef(f"{NS}eventUid"), Literal(uid)))
        if st is not None:
            g.add((s, URIRef(f"{NS}startTime"), Literal(int(st))))
        if en is not None:
            g.add((s, URIRef(f"{NS}endTime"), Literal(int(en))))
        if host is not None:
            g.add((s, URIRef(f"{NS}host"), Literal(host)))
    con.close()
    _RDF_CACHE["g"] = g
    return g


def execute(sparql_text, props=None, use_fallback=False):
    """Single entry point. Ontop if available + props given; else the labeled fallback."""
    if not use_fallback:
        return execute_sparql_ontop(sparql_text, props)[0]
    return execute_sparql_fallback(sparql_text)


def load_predictions(path):
    """Generation-workflow output for this arm: {"sparql": [{qid, trial, sparql}], "trials": N}.
    The LLM-authoring step is run by the harness/workflow (frontier proxy); this module only
    EXECUTES + scores, exactly as bench_c_headtohead_score.py executes the text-to-SQL predictions."""
    return json.load(open(path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", help="LLM-authored SPARQL predictions JSON")
    ap.add_argument("--exec-fallback", action="store_true",
                    help="use the labeled rdflib SPARQL->DuckDB executor (Ontop absent); smoke-test only")
    ap.add_argument("--smoke", action="store_true",
                    help="execute one HAND-WRITTEN SPARQL (no LLM) to prove the execution path runs")
    args = ap.parse_args()

    ontop_present = os.path.isdir(OBDA.ONTOP)
    use_fallback = args.exec_fallback or not ontop_present
    props = None
    if not use_fallback:
        dbf = OBDA.build_duckdb()
        props = OBDA.write_props(dbf)

    if args.smoke:
        # A hand-written, OWL2QL-expressible SPARQL (NO LLM, NO gold constant) over the ontology:
        # "every Session's eventUid" — proves the deterministic EXECUTION path runs end-to-end and
        # returns cell strings the shared scorer can accept.
        hand = ('PREFIX : <http://sdw.example/ocsf#>\n'
                'SELECT ?e WHERE { ?x a :Session ; :eventUid ?e . } LIMIT 5')
        cells = execute(hand, props=props, use_fallback=use_fallback)
        path = "rdflib-fallback (Ontop absent)" if use_fallback else "Ontop"
        print(f"structured-query EXECUTION smoke ({path}): "
              f"{'LOUD/none' if not cells else f'{len(cells)} cells'} -> {cells[:5] if cells else cells}")
        return 0 if cells else 3

    if not args.predictions:
        print("no --predictions given and not --smoke; nothing to execute.", file=sys.stderr)
        return 2
    # full execution+score path (run by the harness; deterministic given the LLM-authored SPARQL)
    print("structured-query arm: execution+scoring is driven by bench_c_headtohead_score.py "
          "(register_structured_query). This module exposes execute()/the smoke path.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

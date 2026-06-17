#!/usr/bin/env python3
"""BENCH-C v2 — dump the per-query GENERATION tasks for the frontier arms (NO LLM here).

Mirrors v1's dump_benchc_frontier.py but for the v2 arm set, so the generation step (frontier
Claude-Code subagents — the claude-opus-class proxy, the SAME mechanism v1 used via workflow
wpr33e44g; NOT a direct Anthropic-SDK call) can answer each task in an isolated call and the
answers are collected into a v2 predictions JSON for bench_c_v2_headtohead.py.

Per arm it writes isolated task files into _frontier/v2/:
  - graphrag (lookup A2/A6/A8): HYBRID-retrieved context (vector UNION BM25 over entity docs) →
    structured + flat serializations. Tail (A3/A7/A9): vector-only context (unchanged from v1).
  - text2sql (lookup + tail, A4 excluded): the raw schema + NL (LLM writes DuckDB SQL over RAW tables).
  - structured-graph-query (tail A3/A7/A9): the OCSF ontology + mappings + NL (LLM writes SPARQL).

A4 is OMITTED from every generation task (excluded as ill-posed, addendum §1). The deterministic
arms (OBDA / metrics-layer) need no generation tasks — they run in-process in the harness.

Model-tiering: each task file is answered by ONE subagent; the runner picks the model per arm
(see RUN-v2.md). Tier the model by arm by routing each arm's task files to a different subagent model.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench_c_v2_config as CFG  # noqa: E402
import run_graphrag as R  # noqa: E402

OUT = os.path.join(HERE, "_frontier", "v2")
EXCLUDE = {"A4"} if CFG.A4_EXCLUDED_ILL_POSED else set()


def schema_text():
    import duckdb
    con = duckdb.connect()
    lines = []
    for t in ("auth", "session", "network", "dns", "process", "api"):
        cols = [r[0] for r in con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{CFG.STORE_F}/{t}.parquet')").fetchall()]
        lines.append(f"  f_{t}({', '.join(cols)})")
    # A9 reads the v2 enlarged asset overlay
    cols = [r[0] for r in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{CFG.STORE_F_V2_ASSET}')").fetchall()]
    lines.append(f"  f_asset({', '.join(cols)})  -- v2 12-asset population")
    con.close()
    return "Tables (DuckDB, OCSF fidelity store):\n" + "\n".join(lines)


def ontology_text():
    obda = os.path.join(HERE, "obda")
    ttl = open(os.path.join(obda, "storef.ttl")).read()
    mapping = open(os.path.join(obda, "storef.obda")).read()
    return ("OCSF ontology (OWL2QL classes + datatype properties):\n" + ttl +
            "\n\nOBDA mapping (table -> RDF):\n" + mapping)


def main():
    os.makedirs(OUT, exist_ok=True)
    con = R.connect()
    g = R.build_graph(con)
    con.close()
    fp = R.graph_fingerprint(g)
    mat, ids = R.build_or_load_embeddings(g, "nomic-embed-text", fp)
    sameadj = R.sameas_index(g)
    bm25, bm25_path = R.build_bm25_index(g)
    schema, ontology = schema_text(), ontology_text()

    manifest = {"trials_llm": CFG.TRIALS_LLM, "bm25_channel": bm25_path,
                "lookup_class": sorted(CFG.LOOKUP_CLASS), "tail_class": sorted(CFG.TAIL_CLASS),
                "a4_excluded": sorted(EXCLUDE), "tasks": []}

    for q in R.QUERIES:
        qid = q["id"]
        if qid in EXCLUDE:
            continue
        qvec = R.embed([q["nl"]], "nomic-embed-text")[0]
        # graphrag arm: hybrid seeds for the lookup class, vector-only for the tail (unchanged)
        if qid in CFG.LOOKUP_CLASS:
            seeds, _ = R.hybrid_seeds(qvec, mat, ids, bm25, q["nl"], R.K_SEED)
            retrieval = "hybrid (vector UNION bm25 over entity docs)"
        else:
            seeds = R.vector_topk(qvec, mat, ids, R.K_SEED)
            retrieval = "vector-only (tail unchanged from v1)"
        seed_rank = {n: i for i, n in enumerate(seeds)}
        keep = R.retrieve(g, seeds, sameadj)
        ctx_struct = R.serialize_subgraph(g, keep, seed_rank)
        ctx_flat = R.serialize_flat(g, keep, seed_rank)

        # graphrag tasks (structured + flat), isolated
        for mode, ctx in (("structured", ctx_struct), ("flat", ctx_flat)):
            tf = os.path.join(OUT, f"graphrag_{qid}_{mode}.json")
            json.dump({"arm": "graphrag", "qid": qid, "mode": mode, "kind": q["kind"],
                       "nl": q["nl"], "retrieval": retrieval, "context": ctx}, open(tf, "w"))
        # text2sql task (raw tables)
        json.dump({"arm": "text2sql", "qid": qid, "kind": q["kind"], "nl": q["nl"],
                   "schema": schema}, open(os.path.join(OUT, f"text2sql_{qid}.json"), "w"))
        # structured-graph-query task (LLM authors SPARQL) — tail only (the compute-over-graph contrast)
        if qid in CFG.TAIL_CLASS:
            json.dump({"arm": "structured", "qid": qid, "kind": q["kind"], "nl": q["nl"],
                       "ontology": ontology}, open(os.path.join(OUT, f"structured_{qid}.json"), "w"))
        manifest["tasks"].append({"qid": qid, "kind": q["kind"], "retrieval": retrieval,
                                  "keep_nodes": len(keep)})

    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w"), indent=2)
    print(f"dumped v2 generation tasks -> {OUT}")
    print(f"  BM25 channel: {bm25_path}")
    print(f"  lookup (hybrid): {sorted(CFG.LOOKUP_CLASS)}   tail (vector + SPARQL): {sorted(CFG.TAIL_CLASS)}")
    print(f"  A4 excluded (ill-posed): {sorted(EXCLUDE)}")
    for t in manifest["tasks"]:
        print(f"    {t['qid']} {t['kind']:11s} keep={t['keep_nodes']:4d}  {t['retrieval']}")


if __name__ == "__main__":
    main()

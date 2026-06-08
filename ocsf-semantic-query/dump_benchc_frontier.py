#!/usr/bin/env python3
"""Dump the BENCH-C per-query contexts for the frontier GraphRAG-vs-flat_retrieval comparison
(run via claude-opus-4-8 subagents). For each of the 9 A-queries: build the graph, retrieve the
SAME entity-seeded subgraph, and serialize it TWO ways — structured (facts + relationships) and
flat (same facts, no relationships). The frontier model then answers each context in a SEPARATE
call (no cross-context leakage), and score_benchc_frontier.py scores both with the shared scorer.
This isolates graph-structure-value from retrieval-value at a tier that can actually answer
(phi3 floored at all-loud)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_graphrag as R  # noqa: E402

con = R.connect()
g = R.build_graph(con)
con.close()
fp = R.graph_fingerprint(g)
mat, ids = R.build_or_load_embeddings(g, "nomic-embed-text", fp)  # cached -> instant
sameadj = R.sameas_index(g)

out = []
for q in R.QUERIES:
    qvec = R.embed([q["nl"]], "nomic-embed-text")[0]
    seeds = R.vector_topk(qvec, mat, ids, R.K_SEED)
    seed_rank = {n: i for i, n in enumerate(seeds)}
    keep = R.retrieve(g, seeds, sameadj)
    out.append({
        "qid": q["id"], "kind": q["kind"], "truth_key": q["truth_key"], "nl": q["nl"],
        "ctx_structured": R.serialize_subgraph(g, keep, seed_rank),
        "ctx_flat": R.serialize_flat(g, keep, seed_rank),
        "keep_nodes": len(keep),
    })

os.makedirs(os.path.join(HERE, "_frontier"), exist_ok=True)
path = os.path.join(HERE, "_frontier", "benchc_contexts.json")
json.dump(out, open(path, "w"))
# per-(qid,mode) task files so each frontier agent sees ONLY its own context (no structured/flat leak)
for e in out:
    for mode, key in (("structured", "ctx_structured"), ("flat", "ctx_flat")):
        tf = os.path.join(HERE, "_frontier", f"task_{e['qid']}_{mode}.json")
        json.dump({"qid": e["qid"], "mode": mode, "kind": e["kind"],
                   "truth_key": e["truth_key"], "nl": e["nl"], "context": e[key]}, open(tf, "w"))
print(f"dumped {len(out)} queries x 2 contexts -> {path}  (+ {2*len(out)} isolated task files)")
for e in out:
    print(f"  {e['qid']} {e['kind']:9s} keep={e['keep_nodes']:4d} "
          f"struct_len={len(e['ctx_structured'])} flat_len={len(e['ctx_flat'])}")

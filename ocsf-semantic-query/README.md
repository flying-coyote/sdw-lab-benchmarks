# BENCH-C — semantic-query head-to-head

For concept-level query over an OCSF lakehouse, does a formal virtual rewrite (OBDA /
Ontop) beat an LLM-mediated runtime (GraphRAG, or plain text-to-SQL) on the queries that
matter — which for security is the adversary tail? The decisive axis is not average
accuracy but the **silent-error rate on adversary-tail queries**: a runtime that composes
a query that executes and returns a plausible-but-wrong answer. That is the failure mode
NL2KQL quantified at ~42% confidently-wrong in security telemetry.

Three arms over the [shared testbed](../ocsf-semantic-testbed/)'s Store F, scored against
the planted ground truth:

- **text-to-SQL** — an LLM composes DuckDB SQL from the schema in context. *(RAN — frontier
  multi-trial; correct+stable on lookups, silently wrong on the adversary tail)*
- **OBDA / Ontop** — OWL2QL virtual rewrite (SPARQL→SQL). *(RAN — `run_obda.py`; correct or
  refusal-honest on its 3/8 OWL2QL-expressible coverage)*
- **GraphRAG (structured) + a flat_retrieval control** — retrieve a concept subgraph, LLM
  composes the query. *(RAN — `run_graphrag.py`; structure did not beat the flat control above
  run-to-run noise; retrieval was the binding constraint)*

## State — head-to-head RAN (2026-06-17 update)

All three arms plus a flat_retrieval control ran at the frontier with run-to-run variance
(8 trials/query), pre-registered (`BENCH-C-PREREGISTRATION.md`), adversarially verified. The
canonical result is **[RESULTS-headtohead-2026-06-16.md](RESULTS-headtohead-2026-06-16.md)**;
the earlier single-pass `results/results.json` is superseded for the variance claim. It
**resolves toward the problem, not either proposed solution**: frontier text-to-SQL with full
data access is correct+stable on simple lookups but silently wrong on the
aggregate/sequence/identity adversary tail (silent 0.49 overall / 0.84 on the tail, 0 correct);
the graph-structure pre-registered null was not refuted (retrieval recall ~0.10 was the binding
constraint, the one apparent win an A9 sameAs-index artifact); OBDA's defensible property is
refusal-honesty on its 3/8 OWL2QL coverage, not same-question safety (the A4 "safer" reading was
a confound — the template was fed the gold constant). Moves H-CONCEPT-GRAPH-03 to 3.5/5;
H-CONCEPT-GRAPH-02 holds 2.5/5. A clean re-run is pre-registered
(`BENCH-C-PREREGISTRATION-v2-rerun.md`): the adversary tail is compute-over-graph, not
needle-retrieval, so the GraphRAG arm needs a structured-query channel to fairly adjudicate.

Each query is scored **correct** (truth recovered), **silent** (executed, returned rows,
truth not recovered — the security-relevant failure), or **loud** (SQL errored or came
back empty — operationally safer than a silent wrong answer, reported separately).

## Run it

```bash
# build Store F first (depends on the shared testbed corpus)
.venv/bin/python ocsf-semantic-testbed/generate.py
cd bench-a-context-collapse && python run.py && cd ..
# then the text-to-SQL arm
.venv/bin/python ocsf-semantic-query/run.py --model phi3:latest
```

## Evidence tier

Tier B — all three arms ran at the frontier (claude-opus-class proxy) with run-to-run
variance, single machine, one planted chain, directional pilot (n=9). The OWL2QL recursion
ceiling and the documented text-to-SQL silent-error literature (NL2KQL ~42% confidently-wrong,
BIRD 81.67% vs 92.96% human) are the external anchors. Tier-A needs a second host (independent
reproduction), the v2 re-run's confound removals (`BENCH-C-PREREGISTRATION-v2-rerun.md`), a
published labeled query set, a named reviewer, and a non-toy scale.

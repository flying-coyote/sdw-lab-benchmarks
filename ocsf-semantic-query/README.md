# BENCH-C — semantic-query head-to-head

For concept-level query over an OCSF lakehouse, does a formal virtual rewrite (OBDA /
Ontop) beat an LLM-mediated runtime (GraphRAG, or plain text-to-SQL) on the queries that
matter — which for security is the adversary tail? The decisive axis is not average
accuracy but the **silent-error rate on adversary-tail queries**: a runtime that composes
a query that executes and returns a plausible-but-wrong answer. That is the failure mode
NL2KQL quantified at ~42% confidently-wrong in security telemetry.

Three arms over the [shared testbed](../ocsf-semantic-testbed/)'s Store F, scored against
the planted ground truth:

- **text-to-SQL** — a local LLM composes DuckDB SQL from the schema in context. *(first
  pass: implemented)*
- **OBDA / Ontop** — OWL2QL virtual rewrite over R2RML mappings. *(pending: Ontop CLI not
  installed here; the JVM is present, the mappings are to author)*
- **GraphRAG** — retrieve a concept subgraph, LLM composes the query. *(pending: no
  graph+vector GraphRAG stack installed here)*

## State — first pass (text-to-SQL baseline only)

This first pass runs the text-to-SQL arm and records the OBDA and GraphRAG arms as
pending with their blockers, so the comparison is honestly partial rather than implied.
The text-to-SQL baseline is the arm the formal rewrite has to beat; measuring its
silent-error rate on the adversary tail is the starting point for the head-to-head.
Results in [results/RESULTS.md](results/RESULTS.md) (when rendered) and
[results/results.json](results/results.json).

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

Tier B, and only one of three arms. A local weak model composing SQL is the baseline, not
the headline; the headline is the OBDA-vs-LLM silent-error contrast on the adversary tail,
which needs all three arms. Single machine, one planted chain, one model. The OWL2QL
recursion ceiling and the documented text-to-SQL silent-error literature are the external
anchors the full result would sit against. Tier-A needs all three arms, a published
labeled query set, a named reviewer, and a non-toy scale.

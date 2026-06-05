# BENCH-C — semantic-query head-to-head: results (first pass)

**Tier B, one arm of three.** This first pass runs the **text-to-SQL baseline arm** (a
local LLM composes DuckDB SQL over the fidelity store, scored against the testbed ground
truth). The OBDA/Ontop and GraphRAG arms are pending infrastructure, so this is the
baseline the formal rewrite would have to beat, not the head-to-head itself.

Model: `phi4:latest`. Anchors (external): NL2KQL ~58% result-accuracy, BIRD 81.67%.

## text-to-SQL arm

| query | outcome | rows |
|---|---|---|
| A1 | loud | 0 |
| A2 | correct | 1 |
| A6 | correct | 1 |
| A8 | loud | 0 |

- result-accuracy: **0.50**
- silent-error rate: **0.00**
- counts: {'correct': 2, 'loud': 2, 'silent': 0}

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

Pending arms: OBDA/Ontop (Ontop CLI not installed (JVM present); R2RML mappings to author); GraphRAG
(no graph+vector GraphRAG stack installed). Tier B, single machine, one planted chain.

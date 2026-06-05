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


## OBDA / Ontop arm (Ontop 5.5.0 (OWL2QL) over DuckDB)

On the queries OWL2QL can express, the formal rewrite is exact; on the rest it is out of
expressivity and refuses rather than guessing. **100% correct on the
expressible set, 0% silent, refusal-honest = True.** Coverage: 3/8 adversary queries expressible in OWL2QL.

| query | outcome | rows |
|---|---|---|
| A2 | correct | 1 |
| A4 | correct | 35 |
| A6 | correct | 1 |

| query | outcome | why it's out of OWL2QL |
|---|---|---|
| A1 | out-of-OWL2QL (loud by design) | ~60s beacon cadence — needs window/aggregation; OWL2QL is first-order-rewritable (no aggregation) |
| A3 | out-of-OWL2QL (loud by design) | cross-source kill-chain ordering — needs sort/aggregation over joins |
| A5 | out-of-OWL2QL (loud by design) | recursive identity closure — OWL2QL is non-recursive (no transitive closure) |
| A7 | out-of-OWL2QL (loud by design) | dwell-time delta — needs aggregation across events |
| A9 | out-of-OWL2QL (loud by design) | distinct-asset count — needs aggregation |

The contrast is the whole point: the OBDA arm answers fewer adversary-tail queries but is
**never silently wrong** on the ones it answers, and its failures are loud (an out-of-expressivity
boundary), where a frontier LLM's failures on this tail are silent (plausible-but-wrong) and the
local text-to-SQL's are loud-but-broken. Whether the formal rewrite's narrow-but-clean coverage
beats the LLM's broad-but-unverified coverage is the decision the third (GraphRAG) arm and a
frontier text-to-SQL leg would complete.

GraphRAG arm still pending (no graph+vector GraphRAG stack installed).
Tier B, single machine, one planted chain.

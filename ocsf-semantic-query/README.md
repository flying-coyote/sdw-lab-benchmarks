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

*(corrected 2026-11-17: the State section above names `RESULTS-headtohead-2026-06-16.md` as canonical.
Two later runs supersede it for the head-to-head. `RESULTS-v2-2026-06-17.md` re-ran it after removing the
v1 confounds, under `BENCH-C-PREREGISTRATION-v2-rerun.md` and its implementation addendum, with the
LLM arms at three Claude tiers: on the three compute-over-population tail queries no LLM arm was
reliably correct (Opus text-to-SQL was correct on 3 of 24 tail query-trials, 0.125), text-to-SQL was
silently wrong on 13, 15 and 12 of 24 tail query-trials at Haiku, Sonnet and Opus (0.54 / 0.625 / 0.50),
GraphRAG on all 24 at every tier, and LLM-authored SPARQL went from loud at Haiku and Sonnet to silent
at Opus (23 of 24, 0.96). Each tail rate is over three queries at 8 trials each
(`results/v2_headtohead_haiku.json`, `v2_headtohead.json`, `v2_headtohead_opus.json`,
`arms.<arm>.tail.trial_rates`). `RESULTS-v2.1-2026-06-17.md`, under the v2.1 arm extension, added an agentic
self-correct arm, whose tail silent rate rose rather than fell, and a self-consistency vote, which
missed the unanimous GraphRAG errors. Those two files are the current read.)*

## What would have made it fail

The planted answers come from the shared testbed's generator, and the models compose queries against it,
so every LLM cell could have come out correct; none of the LLM outcomes is fixed by construction. The
baselines are deterministic and were fixed before the run: an OWL2QL rewrite (OBDA, correct or refuses on
what it can express) and a hand-curated SQL metrics layer (v2 addendum, item 3, which forbids gold
constants). The metrics layer was curated by the author of the planted corpus, though, so its lookup
correctness is a lower bar than an independent curator's would be. The weak point is
size. The tail is three queries, each at 8 trials per cell, so a tail rate such as 0.96 is 23 of 24
trials over three questions, and the 1.0 GraphRAG figure is three unanimous wrong answers repeated, not
24 independent ones. All LLM arms are one model family.

## Pre-registration

Four files: `BENCH-C-PREREGISTRATION.md` (v1), `BENCH-C-PREREGISTRATION-v2-rerun.md`,
`BENCH-C-PREREGISTRATION-v2-ADDENDUM-impl-decisions.md` and `BENCH-C-PREREGISTRATION-v2.1-arm-extension.md`.
None carries a hash file or a frozen-at stamp, so freeze-before-run can be checked only against the git
history. The verdicts in the v2 and v2.1 results match the falsifiers as written in those files (the
graph-structure null confirmed; OBDA determinism-safety supported on its expressible set, which is two of
eight queries; the v2.1 agentic falsifier did not fire because the silent rate rose). The v2 lookup class
is recorded as confounded and its prediction as inconclusive, which is a declared deviation.

## Reproduce

```bash
# build Store F first (depends on the shared testbed corpus)
.venv/bin/python ocsf-semantic-testbed/generate.py
cd bench-a-context-collapse && python run.py && cd ..
# then the text-to-SQL arm
.venv/bin/python ocsf-semantic-query/run.py --model phi3:latest
```

## Results

- `RESULTS-v2-2026-06-17.md` and `RESULTS-v2.1-2026-06-17.md`: current.
- `RESULTS-headtohead-2026-06-16.md`: the v1 head-to-head, superseded for the comparison by v2.
- `results/RESULTS.md` and `results/results.json`: the first single-pass phi4 and OBDA arms (2026-06-05).
- `results/v2_*.json`, `results/v2_1_*.json`, `results/headtohead_frontier.json`: machine-readable outputs.
- `GRAPHRAG-READINESS.md`, `RUN-v2.md`: design and run notes.

## Versions and pins

Ontop CLI 5.5.0 with the DuckDB JDBC jar, fetched by `RUN-v2.md` at run time; DuckDB from the root
`requirements.txt`. The v2 LLM arms are Claude Haiku, Sonnet and Opus through Claude Code at harness
defaults, with no temperature or seed control; the first pass used Ollama `phi4:latest`. The folder has no
requirements file of its own.

## Evidence tier

Tier B — all three arms ran at the frontier (claude-opus-class proxy) with run-to-run
variance, single machine, one planted chain, directional pilot (n=9). The OWL2QL recursion
ceiling and the documented text-to-SQL silent-error literature (NL2KQL ~42% confidently-wrong,
BIRD 81.67% vs 92.96% human) are the external anchors. Tier-A needs a second host (independent
reproduction), the v2 re-run's confound removals (`BENCH-C-PREREGISTRATION-v2-rerun.md`), a
published labeled query set, a named reviewer, and a non-toy scale.

## Corrections

- 2026-11-17: the current results named; construction, sample size and pre-registration notes added; one
  first-person phrase recast in `RESULTS-headtohead-2026-06-16.md`.

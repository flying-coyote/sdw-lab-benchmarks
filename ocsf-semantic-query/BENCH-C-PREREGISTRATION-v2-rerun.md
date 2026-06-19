---
type: benchmark-spec
title: "BENCH-C v2 Pre-Registration: Clean Re-Run with Structural Reframe (OBDA vs Probabilistic over OCSF)"
created: 2026-06-17
tags: [bench-c, pre-registration, ocsf-semantic-query, graphrag, obda, falsification]
---

# BENCH-C re-run pre-registration v2 — clean adjudication of OBDA vs probabilistic over OCSF

**Pre-registered before the re-run** (loop iter 13, 2026-06-17). The v1 head-to-head
(`RESULTS-headtohead-2026-06-16.md`) resolved *toward the problem, not either solution*: retrieval was the
binding constraint (literal-needle recall ~0.10, 0/6 lookup queries cleared the 70% gate), the graph-structure
NULL was not refuted (the one apparent win was an A9 sameAs-index materialization artifact; ex-A9 the delta
inverted), and the "OBDA safer on A4" reading was refuted (the OBDA template was fed the literal gold
`pit_point_ms` constant). This v2 fixes those so the re-run can actually adjudicate graph-value and
determinism-safety rather than re-confirming the problem. It does **not** tune budgets to hit planted needles
(v1's locked-params fairness contract holds); every change below is a defensible *strategy* change, committed
in advance.

## The structural reframe (the load-bearing change)

v1 applied one retrieval-recall gate (70% needle recall) to all nine queries. That conflates two query
classes that need different machinery, and is why the tail looked like a pure retrieval failure:

- **Lookup queries (A2 PowerShell cmd, A6 no-MFA uid, A8 C2 domain)** — a specific fact has to be *retrieved*.
  Needle-recall is the right gate here, and v1's ~0.10 recall is a real retrieval failure with a principled
  fix (below).
- **Aggregate / sequence / identity tail (A4 count, A7 dwell, A9 distinct-assets, A3 cross-day sequence)** —
  the answer is a *computation over a population* (COUNT / DISTINCT / time-ordering / alias-closure), not a
  fact to retrieve. **No vector-retrieval budget can answer these** — retrieving "more needles" does not
  produce a COUNT. So the 70% needle-recall gate is the wrong instrument for the tail; entity-seeded
  needle-retrieval is structurally incapable here, which is the same wall the text-to-SQL arm hit by writing a
  wrong SQL aggregate (full data access, no retrieval limit, still silently wrong). The honest comparison on
  the tail is therefore *compute-over-graph* (a structured graph query — SPARQL/Cypher/SQL over the graph)
  vs *probabilistic compute* (LLM text-to-SQL), which is exactly where OBDA's deterministic SPARQL→SQL
  rewrite is supposed to earn its place. v1 never gave the GraphRAG arm a structured-query channel, so it
  measured retrieve-from-graph where it should have measured compute-over-graph.

**Consequence for the arms:** the v2 GraphRAG/structured arm gets a structured-query channel for the tail
(it emits a graph query, not a needle bag), so the tail comparison is OBDA-deterministic-rewrite vs
LLM-probabilistic-compute vs structured-graph-query — the comparison the two hypotheses were created to run.

## Fixes (committed in advance)

1. **Principled retrieval fix for the lookup class (no needle-tuning):** add a **BM25 / keyword channel**
   alongside vector retrieval (hybrid retrieval, standard practice) so an exact substring (a PowerShell
   command, a C2 domain, a specific uid) is findable by literal match, not only by vector similarity at
   ~7 events/seed. This is a retrieval-*strategy* change, not budget-tuning to the planted needles; K_SEED /
   NODE_BUDGET / HOPS stay at the v1 locked values. Pre-registered prediction: lookup-class recall clears
   70%; the tail is unaffected (it was never a retrieval problem).
2. **A4 confound removed:** the OBDA template must **derive the point-in-time anchor from the NL question**
   like every other arm — it must NOT be handed the literal gold `pit_point_ms` constant from
   `ground_truth.json`. If the NL-as-worded does not determine a single gold (v1 found the real
   privilege-escalation needle is 2.7h before the gold PIT and yields 45, not 35), then **A4 is excluded from
   the scored head-to-head as ill-posed** and reported as a question-design finding, not a determinism result.
3. **A9 confound removed:** do not hand the structured context two precomputed `--sameAs-->` collapse edges
   over a 2-asset corpus. **Enlarge the asset population** so the alias closure is non-trivial (≥ tens of
   assets, multi-hop alias chains), so the arm must *compute* the closure rather than read a materialized
   freebie. Pre-registered: if structured still beats flat after this, the graph-structure value is real;
   if the delta vanishes, the v1 null holds.
4. **Add a metrics/semantic-layer baseline (4th comparison point):** a dbt/SQL semantic-layer answer (a
   curated view) as the "what a mature data team ships today" baseline, so the result is read against the
   realistic alternative, not only against raw text-to-SQL.

## Primary metric + reporting order (unchanged discipline)

Report retrieval recall FIRST for the lookup class only; report the tail as compute-correctness (correct /
silent-wrong / loud-wrong) across the four compute paths (OBDA-deterministic / LLM-text-to-SQL /
structured-graph-query / metrics-layer). Shared scorer, byte-identical kinds, 8 trials/query for variance.

## Falsification criteria (committed in advance, M6)

- **Graph-structure value is NULL if** the structured-graph-query arm does not beat the metrics-layer + flat
  controls on the tail after the A9 population fix (report as the finding — the v1 null would then be
  confirmed, not just un-refuted).
- **OBDA determinism-safety is supported only if** OBDA is correct-or-refuses (never silent-wrong) on its
  OWL2QL-expressible coverage *with the A4 anchor derived from the NL*, beating the probabilistic arms'
  silent-error rate on the same fairly-posed questions.
- **Predicted confidence deltas:** H-CONCEPT-GRAPH-03 holds 3.5/5 (the silent-error problem is already
  measured; a clean re-run sharpens, doesn't inflate, absent a second host). H-CONCEPT-GRAPH-02 moves off
  2.5/5 **only if** the structured-graph-query arm demonstrates graph-value OR OBDA demonstrates
  same-question safety on fairly-posed questions; otherwise it holds.
- **The number that would falsify the reframe:** if the structured-graph-query arm is *also* silently wrong
  on the tail at the same rate as text-to-SQL, then "compute-over-graph beats probabilistic compute" fails
  and the durable claim narrows to "verify every compute path, structured or not" (which strengthens the
  verification-is-the-product line and weakens the graph-determinism line).

## Scope / honest limits (carried forward)

Synthetic Store F corpus (security-telemetry injection boundary honored — schema/entity-facts only, never raw
production rows); single host; directional pilot; frontier = claude-opus-class proxy, not a productized
runtime; magnitudes parameter/host-dependent, the *order* of arms is the transferable claim. This is a design
note, not a result — no benchmark numbers, no vendor comparisons.

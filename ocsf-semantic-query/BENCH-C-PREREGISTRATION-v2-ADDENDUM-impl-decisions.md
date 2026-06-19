---
type: benchmark-spec
title: "BENCH-C v2 Implementation-Decision Addendum: Six Pre-Run Ambiguity Resolutions"
created: 2026-06-17
tags: [bench-c, pre-registration, implementation-decisions, ocsf-semantic-query, hybrid-retrieval, asset-population]
---

# BENCH-C v2 — implementation-decision addendum (pre-run, committed BEFORE the re-run)

Resolves the six implementation ambiguities under [`BENCH-C-PREREGISTRATION-v2-rerun.md`](BENCH-C-PREREGISTRATION-v2-rerun.md) **before any scored run**, to preserve the no-post-hoc-tuning contract. Each is an implementation choice under the already-committed v2 strategy, not a new strategy. Committed 2026-06-17.

1. **A4 PIT anchor (derive-from-NL).** The anchor is derived by locating the privilege-escalation event from the NL semantics via the same data path every arm uses (the no-MFA / priv-esc marker event's timestamp), NOT the gold `pit_point_ms` constant. If the NL-as-worded does not yield a single unambiguous gold (v1 found the real needle is ~2.7h off the gold PIT and yields 45, not 35), **A4 is EXCLUDED from the scored head-to-head as ill-posed** and reported as a question-design finding. (Already committed in the v2 doc; restated here as the operational rule.)

2. **Structured-graph-query arm = LLM-generated SPARQL executed via the existing Ontop/OBDA mappings.** On the tail, the GraphRAG arm emits a SPARQL query (probabilistic generation) executed deterministically through the existing OBDA mapping layer — no new graph DB. This makes the three-way tail contrast clean: OBDA-deterministic (curated/templated SPARQL → deterministic rewrite) vs structured-graph-query (LLM-authored SPARQL over the same ontology) vs LLM-text-to-SQL (LLM SQL over raw tables). The differentiator under test is target schema (curated ontology view vs raw tables) and whether the query is curated or LLM-authored, with execution deterministic in both structured arms.

3. **Metrics/semantic-layer baseline = hand-curated plain SQL views**, fixed before the run — "what a mature data team ships today": standard SQL aggregations only, no ML, no dynamic thresholds, and NO access to gold constants (A4 uses the same NL-derived anchor as every other arm). Deterministic.

4. **Hybrid retrieval = real BM25 (`rank_bm25`) over entity docs, unioned with the existing vector top-k seeds, before the locked ego traversal.** If `rank_bm25` is unavailable offline, fall back to a documented tokenized Okapi-BM25-lite scoring, NOT a bare substring hack. K_SEED / NODE_BUDGET / HOPS / EDGE_BUDGET stay at the v1 locked values (this is a retrieval-strategy change, not budget-tuning). Applies to the lookup class (A2 / A6 / A8); the tail is unaffected.

5. **A9 asset population = 12 assets**, each with hostname + IP + instance_id (3 alias nodes), and ≥3 of them carrying a multi-hop alias chain (e.g., a reassigned IP linking two hostnames) so the alias closure is ≥2 hops and must be *computed*, not read from a 2-edge freebie. The exact enlarged corpus is committed before the run; `sameas_index()` speed is re-checked after enlargement.

6. **Trials.** Arms with an LLM-generation step (text-to-SQL; structured-graph-query SPARQL generation) run **8 trials/query** for variance. Fully-deterministic arms (OBDA with a fixed template; metrics-layer curated SQL; structured-query *execution*) run **1 trial** (variance is zero by construction; reported as such, not padded to 8).

Scope / limits unchanged from the v2 pre-registration: synthetic Store F corpus (security-telemetry injection boundary honored — schema/entity-facts only, never raw production rows), single host, directional pilot, frontier = claude-opus-class proxy for the LLM arms; the *order* of arms is the transferable claim, not the magnitudes. This is a design note, not a result — no benchmark numbers, no vendor comparisons.

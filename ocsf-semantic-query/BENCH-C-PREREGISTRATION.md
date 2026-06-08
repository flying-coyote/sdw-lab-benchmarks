# BENCH-C pre-registration — concept-graph query arms, with the flat_retrieval control

**Pre-registered before the scored run** (per the Security Context Graph program plan's Phase-B gate).
The point of pre-registering is that a *null* is a valid, publishable finding here — the honest answer
to "does the graph help?" may be "no," and this doc commits to reporting that if it happens.

## The question

Does a concept graph improve LLM-mediated querying of an OCSF lakehouse over the adversary tail, and
if so, is the value in the *retrieval* (which facts get pulled) or in the *graph structure* (how they
connect)? This is the H-CONCEPT-GRAPH-02 (provable OBDA) vs H-CONCEPT-GRAPH-03 (probabilistic GraphRAG)
load-bearing question, decided on the adversary-tail queries where the two diverge.

## Arms (same corpus, same questions, same scorer)

1. **text-to-SQL** — the model writes DuckDB SQL over Store F directly (implemented, `run.py`).
2. **OBDA / Ontop** — formal SPARQL→SQL rewrite over an OWL2QL mapping (implemented, `run_obda.py`).
3. **GraphRAG (structured)** — entity-layer retrieval + 2-hop traversal, facts **with** relationships
   (`run_graphrag.py`, the rebuilt arm).
4. **flat_retrieval (CONTROL)** — the **same retrieved facts** as arm 3, serialized as a flat list with
   **no relationships / graph structure** (`run_graphrag.py --flat`). This is the control that isolates
   retrieval-value from graph-structure-value.

## Primary metric and reporting order

- The shared **correct / silent / loud** scorer (`scoring.py`); the headline is the **silent-error rate**
  (a query that runs and returns a plausible wrong answer — the analyst-trust failure).
- **Report retrieval precision/recall FIRST.** If the GraphRAG/flat retrieval does not surface the gold
  needle into context at reasonable k, the arm cannot answer regardless of structure — that is a retrieval
  problem, not a graph-value finding, and must be fixed (or reported as the limiter) before any
  graph-structure claim is made. Threshold: if retrieval recall < 70% on the answerable queries, the
  finding is "retrieval is the bottleneck," not "graph adds/doesn't add value."

## Falsification criteria (committed in advance)

- **Graph-structure value is NULL if** the structured GraphRAG arm does not beat the flat_retrieval
  control by more than run-to-run noise on the silent-error rate. (Same facts, structure removed — if the
  scores match, the relationships did no work.) **This null will be reported as the finding.**
- **OBDA-over-GraphRAG** is decided on the adversary tail (A3/A5/A7/A9 — ordering, identity-closure,
  dwell, distinct-asset — the recursive/aggregate queries OWL2QL excludes but a graph traversal can reach).
- A positive GraphRAG result that does **not** survive removing the structure (arm 4) only demonstrates
  retrieval value, not graph value — and will be labeled as such.

## Fixed design (no tuning to the planted answers — fairness §6)

- Hyper-params locked: `K_SEED=20`, `HOPS=1` (entity→events, the structured-design semantics),
  `NODE_BUDGET=150`, `EDGE_BUDGET=300`. Bounded per-seed expansion + precomputed sameAs index (so a
  super-hub host-entity doesn't blow up retrieval). These are set before scoring and not adjusted to hit
  needles.
- Questions: the A1–A9 union (9 queries), per-query reported so either implemented arm's subset can be
  sliced without re-running. A10 omitted for parity (it is a BENCH-A store-degradation needle).
- Models: the local ladder (phi3) for the capability floor, plus the **claude-opus-4-8 frontier proxy**
  (now available — same substitution validated on the mapping-oracle) for the frontier ceiling.

## Honest limits (stated up front)

- n = 9 queries on one synthetic adversary-chain corpus, single host. This is **directional/pilot**, not a
  statistically powered comparison; magnitudes are host- and parameter-dependent and the *order* of arms is
  the transferable claim, not the absolute numbers.
- CPU LLM latency is ~minutes/query; runs are temperature-0 greedy (reproducible in practice, the graph +
  cached embeddings are deterministic and asserted, the decode is not byte-asserted).
- Tier B at best. A passing result is a first OCSF datapoint for the concept-graph thread, not a settled
  finding; a null tempers the grounding-as-differentiator thesis (consistent with the mapping-oracle, where
  the grounding-note content was inert across the capability spectrum).

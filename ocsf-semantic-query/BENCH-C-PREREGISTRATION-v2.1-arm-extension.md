# BENCH-C v2.1 — arm extension (pre-registered BEFORE the run)

Two new arms added to the v2 head-to-head, **pre-registered before generation** to hold the no-post-hoc-tuning contract. Same corpus (Store F + the A9 12-asset overlay), same shared scorer (`scoring.classify`, byte-identical), same A4 exclusion, same three model tiers (Haiku / Sonnet / Opus) so the tier-invariance read extends to the new arms. Both arms target the question the v2 result raised: the failure on the compute tail is *silent*, and the only guard that worked was refuse / fail-loud / pre-verified — so v2.1 tests whether adding a **verification mechanism** to the probabilistic path converts silent → caught. Committed 2026-06-17, before the v2.1 generation runs.

## Arm #1 — Agentic execute-and-self-correct text-to-SQL

**Method.** A subagent is given the same NL question + raw-table schema as the one-shot `text_to_sql` arm, plus a **SQL-execution tool** (DuckDB over Store F). It iterates up to **K = 5** rounds: write SQL → execute → inspect returned rows / errors → revise; it returns its FINAL SQL when confident or at the round cap. The final SQL is then executed and scored by the same deterministic scorer as every other arm (no special-casing). 8 trials per (qid, tier); model held constant across arms within a tier.

**What it isolates.** The one-shot `text_to_sql` arm is the control (identical prompt/schema, no execution feedback). The only difference is the self-correction loop, so any delta is attributable to execution feedback, not prompt or model.

**Locked params (committed):** K = 5 rounds; execution tool = read-only DuckDB over the same `f_*` tables the one-shot arm sees; no access to `ground_truth.json` or gold constants (the agent sees only the data + its own query results); A4 excluded as elsewhere; temperature = the subagent default (same as the one-shot arms).

**Pre-registered hypothesis.** Execution feedback reduces *loud* failures (the agent fixes its own syntax/empty-result errors) but does NOT substantially reduce *silent* failures on the compute tail (a wrong-but-runnable aggregate returns plausible rows, so the agent has no error signal to correct against).

**Falsifier.** If the agentic arm's **tail silent rate drops materially below the one-shot text_to_sql tail silent rate** (Sonnet baseline 0.625), then execution-feedback self-correction *does* fix compute-over-population silent error, and the durable claim weakens to "agentic verification closes the gap." If the tail silent rate is ≈ the one-shot rate, the claim strengthens: self-correction can't catch what it can't see, so a wrong aggregate survives the loop.

## Arm #2 — Self-consistency (N-of-8 majority-vote-or-abstain)

**Method.** Derived from the trials ALREADY collected — **no new generation** for the existing arms. For each (arm, qid, tier) with 8 trials: cluster the 8 answers by the scorer's equality, take the **majority answer** as the arm's answer, and **ABSTAIN (flag)** when no answer reaches a **≥ 5/8** majority. Score two things: (a) does majority-vote raise the *correct* rate vs the per-trial mean? (b) does abstain-on-disagreement *catch the silent errors* — i.e., are the silent-wrong cells the ones that fail to reach majority? Applied to `text_to_sql`, `graphrag` (both modes), and `structured_graph_query`.

**Locked params (committed):** majority threshold = 5/8; equality = the shared scorer's `classify` kind-equality (not string identity); abstention counts as a *caught* error (loud-equivalent), never as correct.

**Pre-registered hypothesis (and the visible early signal).** Self-consistency catches silent errors ONLY where the model is *inconsistently* wrong. The v2 result already shows the graphRAG tail silent rate is **1.0 with zero variance across all 8 trials** — i.e., unanimous — so self-consistency is predicted to **NOT** catch those: the 8 trials agree on the wrong answer, clear the 5/8 majority, and emit a confident silent error.

**Falsifier.** If the silent-wrong cells are predominantly *low-agreement* (< 5/8), abstention catches them and self-consistency is a cheap silent-error detector. If the silent-wrong cells are predominantly *high-agreement / unanimous*, self-consistency does NOT catch them — disagreement ≠ wrongness — and the durable claim is "the model is confidently, consistently wrong; ensembling its own samples won't save you; you need an external check (execution, a curated layer, a refusing engine)."

## Reporting

Both arms reported alongside the v2 arms in the three-tier table, with the same lookup-recall-first / tail-as-compute-correctness ordering. v2.1 runs AFTER the v2 Haiku/Sonnet/Opus sweep completes (avoids API contention with the in-flight reruns). Scope/limits carried from v2 + the v2 addendum: synthetic Store F, single host, directional pilot, order-of-arms is the transferable claim. Design note, not a result — no numbers here.

# BENCH-C v2.1 results — does adding a verification mechanism to the probabilistic path convert silent → caught?

**2026-06-17. Tier B, single host, synthetic Store F + the A9 12-asset overlay. Directional pilot — the order/mode of failure is the transferable claim, not the magnitudes.** Pre-registered in [`BENCH-C-PREREGISTRATION-v2.1-arm-extension.md`](BENCH-C-PREREGISTRATION-v2.1-arm-extension.md) BEFORE generation. Two arms extend the [v2 head-to-head](RESULTS-v2-2026-06-17.md): both target the question v2 raised — the compute-tail failures are *silent*, and the only guards that worked were refuse / fail-loud / pre-verified, so v2.1 asks whether bolting a verification mechanism onto the probabilistic path turns silent into caught. Same corpus, same shared byte-identical scorer (`scoring.classify`), same A4 exclusion, same three model tiers (Haiku / Sonnet / Opus). The answer for both arms is **no** — and each fails in an instructive way.

## Headline

Neither a self-correction loop nor self-consistency makes the probabilistic path safe on the compute tail (A3 cross-source ordering, A7 dwell-time, A9 distinct-asset count). **Arm #1 (agentic execute-and-self-correct) cuts loud failures to ~0 but converts them into silent ones — tail silent goes UP, not down.** **Arm #2 (self-consistency) does not catch the unanimous-silent graphRAG errors, and where it does "catch" it is abstaining on disagreement, which is orthogonal to correctness — it never produces a correct tail answer and sometimes discards a correct one.** Both reinforce the v2 conclusion: safety comes from an *external semantic check* (a deterministic rewrite that refuses, a curated metric, a refusing engine), not from making the model try harder — more rounds, or more samples, optimize for *executable / agreed-upon*, which on the compute tail is exactly *silently wrong*.

## Arm #1 — Agentic execute-and-self-correct text-to-SQL

A subagent gets the same NL question + raw-table schema as the one-shot `text_to_sql` control, plus a read-only DuckDB execution tool, and iterates up to K=5 rounds (write SQL → execute → inspect rows/errors → revise) before returning its final SQL, which is then scored deterministically by the same scorer. 8 trials per (qid, tier); model held constant across arms within a tier. Mean rounds used: Haiku 3.17, Sonnet 2.79, Opus 3.62.

### Tail (A3 / A7 / A9) — mean trial rates (correct / silent / loud)

| Tier | Agentic (K=5) | One-shot control |
| :-- | :-- | :-- |
| Haiku | 0.00 / **0.958** / 0.042 | 0.00 / 0.542 / 0.458 |
| Sonnet | 0.125 / **0.875** / 0.00 | 0.00 / 0.625 / 0.375 |
| Opus | 0.125 / **0.875** / 0.00 | 0.125 / 0.500 / 0.375 |

Lookup (A2/A6/A8) is preserved: agentic correct 1.0 at Haiku and Sonnet, 0.958 at Opus (one trial's final query errored). The self-correction loop confirms the right needle on the easy class and does not regress it.

### What it shows

The pre-registered falsifier was: if the agentic tail silent rate drops materially below the one-shot rate (Sonnet baseline 0.625), execution-feedback self-correction fixes compute-over-population silent error. **It did not fire — the silent rate ROSE** (Haiku 0.542 → 0.958, Sonnet 0.625 → 0.875, Opus 0.500 → 0.875) while loud fell to ~0 and correct barely moved. The loop's stopping condition is "the query runs and returns plausible rows," and on the compute tail a wrong aggregate runs fine and returns plausible rows, so the agent has no error signal to correct against: it iterates away the loud failures (empty results, syntax errors) and lands on a confident wrong answer. A7 and A9 converge to a *stable* silent answer (unanimous across all 8 trials at every tier); A3 carries a little more variance. Spot-checked end to end — Opus's A9 query, after 5 rounds, builds an elaborate actor-to-asset closure and returns `1` distinct asset against a gold of `9`: executable, confident, wrong.

So execution feedback is verification of *executability*, not of *correctness*. It removes the accidental loud safety net (the weaker model's broken query that errored out) without adding a semantic check — the same mechanism as the v2 capability-inversion, where Opus removed the loud net by writing clean executable SPARQL. Anything that makes a query more likely to execute moves its failures from loud to silent unless something checks the answer.

## Arm #2 — Self-consistency (5/8 majority-vote-or-abstain)

Derived from the trials already collected in v2 — no new generation. For each (arm, qid, tier) the 8 answers are clustered by a per-kind canonical key that mirrors the shared scorer's salient extraction (so two trials cluster iff `scoring.classify` would treat them equivalently, not by raw string identity); the majority answer (≥ 5/8) is the arm's answer and is scored normally, and the arm ABSTAINS (a caught / loud-equivalent outcome, never correct) when no answer reaches 5/8.

### Tail (A3 / A7 / A9) — per-trial mean (c/s/l) vs self-consistency (correct / silent / caught), 3 queries

| Arm | Tier | per-trial mean (c/s/l) | self-consistency (correct/silent/caught) |
| :-- | :-- | :-- | :-- |
| graphRAG (structured) | Haiku | 0 / 1.0 / 0 | 0 / 2 / 1 |
| graphRAG (structured) | Sonnet | 0 / 1.0 / 0 | 0 / **3** / 0 |
| graphRAG (structured) | Opus | 0 / 1.0 / 0 | 0 / **3** / 0 |
| graphRAG (flat) | Haiku | 0 / 1.0 / 0 | 0 / 1 / 2 |
| graphRAG (flat) | Sonnet | 0 / 1.0 / 0 | 0 / 2 / 1 |
| graphRAG (flat) | Opus | 0 / 1.0 / 0 | 0 / 2 / 1 |
| text-to-SQL | Haiku | 0 / 0.542 / 0.458 | 0 / 1 / 2 |
| text-to-SQL | Sonnet | 0 / 0.625 / 0.375 | 0 / 1 / 2 |
| text-to-SQL | Opus | 0.125 / 0.500 / 0.375 | 0 / 0 / 3 |
| LLM-authored SPARQL | Haiku | 0 / 0 / 1.0 | 0 / 0 / 3 |
| LLM-authored SPARQL | Sonnet | 0 / 0.042 / 0.958 | 0 / 0 / 3 |
| LLM-authored SPARQL | Opus | 0 / 0.958 / 0.042 | 0 / 1 / 2 |

### What it shows

The pre-registered prediction holds: self-consistency catches silent errors only where the model is *inconsistently* wrong. The graphRAG tail is silent 1.0 with zero variance — the 8 trials agree on the wrong answer, clear the 5/8 majority, and emit a confident silent error. At the frontier (Sonnet, Opus) self-consistency catches **none** of the three graphRAG-structured tail queries (3/3 silent); it only catches a couple at Haiku, and the catch-rate *decreases with capability* — the better model is more confidently, consistently wrong, so ensembling its own samples is least useful exactly where it is most dangerous.

Where self-consistency does catch (text-to-SQL: 2-3 of 3 caught), it is abstaining because the trials disagree — different SQL each round produces different wrong answers, none reaching 5/8. That catch is a property of answer-variance, not error-detection: it is orthogonal to correctness, and it cuts the other way too — at Opus, text-to-SQL had a 0.125 per-trial correct rate, but self-consistency abstained on it (correct 0), discarding the occasional right answer along with the wrong ones. Self-consistency never produced a single correct tail answer for any arm at any tier. (The LLM-authored-SPARQL "caught" counts are mostly the v2 loud-by-Ontop-refusal at Haiku/Sonnet, not detection; at Opus, where that arm goes silent, self-consistency emits one of the three. The lookup-class graphRAG numbers inherit the v2 lookup retrieval confound and are not a clean test — the tail is the clean signal.)

## Combined conclusion

Two independent mechanisms that a practitioner would reach for to make an LLM query path trustworthy — let it check its own work by running it, or sample it several times and take the consensus — both fail on the compute tail, and fail in the same direction. The self-correction loop optimizes for *executable*; self-consistency optimizes for *agreed-upon*; on compute-over-population questions a wrong answer is usually both executable and agreed-upon, so both methods preserve or amplify the silent error rather than catch it. The agentic loop is actively worse than one-shot because it trades visible (loud) failures for invisible (silent) ones. The durable claim is unchanged from v2 and now triangulated from three angles (capability tier, execution loop, self-ensemble): the catch has to come from outside the probabilistic path — a deterministic rewrite that refuses what it cannot express, a curated metric, a typed engine that rejects the wrong shape — not from more model effort.

## Hypothesis implications (no magnitude move)

These reinforce H-CONCEPT-GRAPH-03's null (LLM-composed joins fail silently on the adversary tail at a rate that disqualifies them where correctness is load-bearing) and the cross-leg invariant that safety lives in the verification/execution layer, not in model capability — now extended to "not in execution-retry and not in self-ensembling either." No confidence magnitude moves on this pilot evidence (single host, synthetic, directional). The result also answers the open re-check question filed in `01-knowledge-base/contradictions/llm-capability-makes-failures-visible-vs-silent.md`: an execution-feedback loop does NOT convert silent into caught — it converts loud into silent.

## Scope / limits

Synthetic Store F (security-telemetry injection boundary honored — schema/entity facts only, never raw production rows); single host; directional pilot; LLM arms = Claude Haiku/Sonnet/Opus held constant across arms within a tier. Arm #1: K=5, read-only DuckDB, the agent sees only the schema + its own query results (no gold). Arm #2: derived from the existing 8 trials, 5/8 threshold, clustering via a per-kind canonical key mirroring the shared scorer. Magnitudes are parameter- and host-dependent; the transferable claims are the order and mode of failure. Files: `_frontier/v2_1/agentic_{haiku,sonnet,opus}.json`, `results/v2_1_agentic.json`, `results/v2_1_self_consistency.json`. Reproduce: `bench_c_v2_1_agentic_score.py` (Arm #1, after the agentic generation), `run_self_consistency.py` (Arm #2, derived).

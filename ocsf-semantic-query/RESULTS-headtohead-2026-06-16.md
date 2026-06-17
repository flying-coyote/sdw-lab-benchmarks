# BENCH-C-GRAPHRAG head-to-head — RESULTS: the probabilistic silent-error problem is real on OCSF; graph structure and OBDA-same-question-safety are not the demonstrated solution (2026-06-16)

The first first-party OCSF datapoint that runs the load-bearing H-CONCEPT-GRAPH-02 (deterministic OBDA)
vs H-CONCEPT-GRAPH-03 (probabilistic GraphRAG / text-to-SQL) head-to-head **at the frontier with
run-to-run variance** (8 trials/query) — the variance discipline the single-pass `*_opus` arms lacked.
Pre-registration: `BENCH-C-PREREGISTRATION.md` (locked params; a null is a valid, publishable finding).
Shared scorer: `scoring.py` (correct / silent / loud, byte-identical kinds across arms). Corpus: Store F,
~177k synthetic OCSF events, one planted APT29-style chain, A1–A9 adversary-tail concept queries. Tier B,
single host, **directional pilot (n=9, one chain)**. Every load-bearing claim was put through an
adversarial-verification panel (workflow `wpr33e44g`) that re-executed the SQL against Store F; two of the
three first-draft claims were caught as over-claims and are corrected below.

## Finding 1 (reported first, per the pre-registration gate): retrieval is the bottleneck for GraphRAG on OCSF

The pre-registration commits to reporting retrieval recall first: *"if retrieval recall < 70% on the
answerable queries, the finding is 'retrieval is the bottleneck,' not a graph-value finding."* Measured
literal-needle recall into the retrieved context, at the **locked, untuned** config (K_SEED=20,
NODE_BUDGET=150, HOPS=1):

| query | needle | recall (structured) |
|---|---|---|
| A1 beacon UIDs | 60 conn uids | 0/60 |
| A2 PowerShell cmd | 1 substring | 0/1 |
| A4 sessions | 35 session uids | 0/35 |
| A6 no-MFA uid | 1 uid | 0/1 |
| A8 C2 domain | 1 substring | 0/1 |
| A5 identity | 12 id strings | 8/12 (0.67) |

Mean ~0.10; **0 of 6 literal-needle queries clear the 70% gate.** The needle nodes *exist* in the
234,212-node graph (e.g. `proc:proc-needle-1` carries the encoded command), but entity-seeded vector
retrieval at ~7 events/seed cannot surface one specific event among 40k–60k. I did **not** tune budgets to
hit the planted needles (that violates the locked-params fairness contract). So per the pre-registration,
the GraphRAG arm is retrieval-bottlenecked and the graph-structure-value question is downstream of a
retrieval failure — which is itself the finding: naive entity-GraphRAG over OCSF event telemetry fails at
retrieval before structure matters.

## Finding 2 (SURVIVES adversarial verification): frontier text-to-SQL silently fails on the aggregate / sequence / identity adversary tail

The clean OBDA-counterpart probabilistic arm is **text-to-SQL with full data access** — it writes its own
DuckDB SQL over Store F, so it has no retrieval bottleneck. Frontier model (claude-opus-class subagents),
8 independent trials/query, executed deterministically and scored:

| arm (all 9 queries) | silent | correct | loud |
|---|---|---|---|
| **text-to-SQL (full data access)** | **0.49** [0.44–0.56] | 0.39 | 0.12 |
| GraphRAG structured (retrieved) | 0.25 [0.22–0.33] | 0.11 | 0.64 |
| flat control (retrieved) | 0.31 [0.22–0.33] | 0.03 | 0.67 |

| adversary tail only (A3/A5/A7/A9) | silent | correct | loud |
|---|---|---|---|
| **text-to-SQL** | **0.84** [0.75–1.00] | 0.00 | 0.16 |
| GraphRAG structured | 0.56 | 0.25 | 0.19 |
| flat control | 0.69 | 0.06 | 0.25 |

text-to-SQL is **correct and perfectly stable (8/8) on the simple-lookup queries A2/A6/A8** and produces
**stable-across-8-trials confident-wrong answers on the aggregate/sequence/identity tail** — independently
reproduced against Store F: A4 returns count `0` (gold 35), A7 returns ~1.21M seconds (gold 3905), A9
returns `0` distinct assets (gold 2), and A3 fabricates a wrong cross-day kill-chain (stitching day-0
decoy rows to the day-7 lateral needle, with `lateral` last and no OAuth stage). The gold is recoverable
with correct SQL and the scorer credits the correct values when fed them, so these are genuine model
errors. **This is the strongest result: at the frontier, a default text-to-SQL path is right on lookups
and silently wrong on exactly the correctness-critical adversary tail** — Tier-B first-party support for
the H-CONCEPT-GRAPH-03 null, now measured on OCSF at the frontier with variance.

Two mandatory caveats (adversarial-verified):

- **The scalar/count tail is partly *structurally* silent.** A COUNT/scalar query always returns one row
  even over an empty match, so a `0`-over-empty-join is scored silent where a row-returning SELECT with no
  rows would be loud. That is precisely the analyst-facing pathology the bench exists to expose — an empty
  answer dressed as a confident zero — but it is named here rather than left to read as a pure model
  property.
- **It is conditioned on a single default one-line prompt; no prompt ablation was run.** The honest claim
  is "a default text-to-SQL prompt produces stable silent errors on the tail," not "no prompt could fix
  it." A3-silent is additionally overdetermined by the order-scorer's keyword strictness, though the
  timeline is genuinely wrong regardless — so A3 is not a clean single-mechanism example.

## Finding 3 (TEMPERED — pre-registered NULL not refuted): graph structure did not beat the flat control above noise

Structured GraphRAG (facts + relationships) vs the flat control (same facts, no relationships): silent
0.25 vs 0.31, delta **+0.056**, run-to-run noise stdev **0.048** — barely one stdev, with **fully
overlapping bands** ([0.22–0.33] both). The advantage is carried **entirely by A9**: per-query majority
outcomes are identical on 8 of 9 queries, and removing A9 **inverts** the delta to **−0.031** (structured
slightly worse). And A9 is a **materialized sameAs-index effect, not graph-traversal reasoning**: the A9
structured context literally hands the model two precomputed `--sameAs-->` collapse edges over a 2-asset
corpus (`f_asset` = 2 rows), so the model counts two pre-collapsed pairs rather than computing an alias
closure. Combined with the ~0.10 retrieval recall (Finding 1), the pre-registered graph-structure **null
is not refuted** — per the pre-registration's own line, a null here *tempers the grounding-as-
differentiator thesis at the query layer*. (text-to-SQL does genuinely get A9 wrong — returns 0 vs 2 — so
"the probabilistic arm fails the identity-collapse query" survives independently of the graph framing.)

## Finding 4 (CORRECTED — the OBDA "safer on A4" claim FAILS; only refusal-honesty stands)

A first draft read the A4 result as "OBDA's deterministic rewrite returns 35 while text-to-SQL is 8/8
silent → determinism buys safety on its coverage." **Adversarial verification refuted this**: the A4
comparison is not apples-to-apples. `run_obda.py` substitutes the **literal gold constant**
`pit_point_ms = 1767880980000` (read straight from `ground_truth.json`) into the OBDA SPARQL template — the
OBDA arm is *handed the answer-defining anchor* — while text-to-SQL got the NL question ("sessions active
at the point in time of the privilege escalation") and had to infer it. Decisively, **even a perfect
reading of the question-as-worded fails the gold**: the real privilege-escalation needle is 2.7 hours
before the gold PIT and yields 45, not 35; `pit_point_ms` corresponds to no named chain stage and exists
only in the truth file. So OBDA's A4 correctness reflects the unequal input, not determinism. **Dropped:
"OBDA strictly safer / determinism buys safety on its coverage."**

What stands for OBDA (from the prior gated leg, unchanged): on its OWL2QL-expressible coverage (3/8: A2,
A4, A6) it is correct and **refusal-honest** — it refuses the 5/8 it cannot express *loud, by design*,
never silently wrong. That **refusal honesty is a structural OWL2QL property** and the durable OBDA claim;
it is a different and weaker claim than "safer on the same question," and it is the one the writeup leads
with.

## What this resolves for H-CONCEPT-GRAPH-02 vs -03

The head-to-head the two hypotheses were created to run has now run on OCSF at the frontier with variance,
and it resolves **toward the problem, not toward either proposed solution**:

- **The probabilistic null (-03) gains a real first-party OCSF datapoint:** default frontier text-to-SQL
  with full data access silently and stably fails the aggregate/sequence/identity adversary tail (0.49
  silent overall, 0.84 on the tail with 0 correct). The silent-error tax falls on exactly the
  correctness-critical region. This supports the *problem statement* (probabilistic query is unsafe on the
  tail where correctness is load-bearing), with the structural-silent and prompt-conditioned caveats.
- **The graph-structure solution (-02's GraphRAG sibling) is not demonstrated:** the pre-registered null is
  not refuted, the one apparent win is a sameAs-index artifact, and retrieval is the binding constraint at
  the locked config.
- **The OBDA-determinism solution is not demonstrated as same-question safety** (the A4 datapoint was
  confounded); its defensible property is refusal-honesty, already established and unchanged.

So BENCH-C is evidence that retrieval/config is the binding constraint at this pilot scale and that the
probabilistic-query *problem* is real on OCSF — it does not, on this run, raise confidence in graph
structure or OBDA as the *answer*.

## Caveats (consolidated)

- n=9, one synthetic planted chain, single host, locked K_SEED=20/NODE_BUDGET=150/HOPS=1; Tier B,
  directional only; magnitudes parameter/host-dependent, the *order* of arms is the transferable claim.
- Frontier = claude-opus-class subagents answering (a frontier *proxy*, not a productized GraphRAG/SaaS
  text-to-SQL runtime), temperature-sampled (the run-to-run variance reported is real, not temp-0).
- Scalar/count tail is structurally silent (named, not a defect); silent-error finding is conditioned on a
  default one-line prompt (no ablation); A3-silent is overdetermined.
- A4 head-to-head confounded (OBDA fed the gold constant; NL gold not derivable) — not a determinism-vs-LLM
  result; A4 figures are re-derived, not in the scored stability block.
- Graph-structure advantage is A9-only and a sameAs-index materialization effect; ex-A9 the delta inverts.
- Retrieval recall ~0.10 ≪ the 70% gate → retrieval is the bottleneck; graph-structure null not refuted.
- Synthetic corpus (security-telemetry injection-surface boundary honored — agents saw synthetic schema /
  retrieved entity facts, never raw production rows).

## Gate

Route through karen-evaluator → hypothesis-validator → contradiction-detector. Recommended (conservative,
per the adversarial synthesis): **H-CONCEPT-GRAPH-03 attaches the frontier-variance silent-error leg as
strengthening its null on OCSF** (the problem is now measured at the frontier with variance) with the
caveats; **H-CONCEPT-GRAPH-02 HOLDS** — the head-to-head ran but does not validate graph-structure or
OBDA-same-question-safety; if anything it tempers grounding-as-differentiator at the query layer, and the
retrieval bottleneck + A4/A9 confounds must be removed in a re-run before any graph-value or
determinism-safety claim. The single-pass `graphrag_opus`/`flat_retrieval_opus` arms in `results.json` are
superseded for the variance claim by this multi-trial run.

## Artifacts

- `bench_c_headtohead_score.py` + `results/headtohead_frontier.json` (scored, variance, ex-A9 sensitivity)
- `_frontier/headtohead_predictions.json` (every raw SQL + answer, 8 trials/query)
- `dump_benchc_frontier.py` (context builder) + `_frontier/benchc_contexts.json` + task files
- adversarial verification: workflow `wpr33e44g` (3 refuters + synthesis)
- prior arms: `run_obda.py` (OBDA 3/8, refusal-honest), `run.py` (text-to-SQL baseline), `run_graphrag.py`
  (local arm), `BENCH-C-PREREGISTRATION.md`

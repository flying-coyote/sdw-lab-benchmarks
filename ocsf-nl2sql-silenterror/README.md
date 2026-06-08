# OCSF NL2SQL silent-error benchmark

When an analyst asks a question in English and a local LLM composes the DuckDB SQL
over an OCSF lakehouse, how often does the SQL **run and return the wrong answer**
with no error — and where on the difficulty curve does that happen? The wrong-but-
clean answer is the analyst-trust danger, because nothing flags it; an erroring or
empty query is safer because the failure is visible. This benchmark measures the
**silent-error rate** by difficulty, over a deterministic OCSF corpus with a
hand-authored gold answer key.

Three outcomes per question, the same definitions the rest of the concept-graph
thread uses (`../ocsf-semantic-query/run.py:score`):

- **correct** — the SQL ran and the gold answer is recovered in the result.
- **silent** — the SQL ran and returned a non-empty result, but the gold answer is
  NOT in it. A plausible wrong answer with no error. **The headline metric is the
  silent-error rate.**
- **loud** — the SQL errored, came back empty when the gold is non-empty, or the
  model emitted no SQL / refused. Operationally safer than silent.

## What is new here vs. the BENCH-C text-to-SQL arm

`../ocsf-semantic-query/run.py` (BENCH-C, first pass) runs only the **4 hardest
adversary-tail concept queries** (A1, A2, A6, A8). It found that a weak local model
fails *loudly* on that tail — it hallucinates columns and functions, so the SQL
errors or returns nothing rather than a confident wrong answer — and so it posts a
0.00 silent rate. That is a real finding but it leaves the interesting question open:
the tail is where the model fails loud; **the mid-difficulty band is where a model is
most likely to produce SQL that plausibly runs and quietly returns the wrong number.**

This benchmark supplies the breadth that exercises that band: **33 labeled questions
across seven difficulty tiers**, from a one-table filter up to the adversary tail.
Same corpus, same Store F, same scorer semantics, so the tail slice here is directly
comparable to BENCH-C; the new contribution is the by-difficulty silent-error curve.

### Question set (33 questions, 7 tiers)

| tier | n | shape |
|---|---|---|
| `simple_filter` | 5 | one table, a WHERE predicate, project a column |
| `aggregation` | 5 | one table, a single COUNT / SUM / AVG / COUNT(DISTINCT) scalar |
| `group_by` | 5 | one table, GROUP BY + an ordered or keyed result set |
| `time_window` | 4 | one table, a BETWEEN / range predicate on a time column |
| `multi_condition` | 5 | one table, several ANDed predicates (the realistic-analyst band) |
| `join` | 4 | two+ tables joined — OCSF's hard cross-source case |
| `adversary_tail` | 5 | the sparse planted needles (cadence / first-seen / absence / closure / point-in-time) — the BENCH-C concept queries |

The adversary-tail questions (A01, A02, A06, A08, A04) are the BENCH-C needles with
the **same NL, truth_key, and scorer kind** as `ocsf-semantic-query/run.py` and the
`GRAPHRAG-READINESS.md` table, so the tail slice lines up query-for-query with the
other arms.

## Corpus and gold answer key

The corpus is **not** re-authored here. It is the shared testbed's fidelity store
(Store F) built by BENCH-A:
`../bench-a-context-collapse/_work/store_f/{auth,session,network,dns,process,api,asset}.parquet`
(~177k events, the planted six-stage APT29-style chain on the middle day), with ground
truth in `../ocsf-semantic-testbed/_work/ground_truth.json`. Reusing it is what keeps
this benchmark comparable to BENCH-A/B/C and re-runnable from one seed
(`MASTER_SEED=20260601`).

Each question's gold answer comes from one of three deterministic sources, never an LLM:

- **`truth`** — a planted ground-truth needle read live from `ground_truth.json`
  (the adversary tail + the asset-collapse join).
- **`literal`** — a pinned corpus invariant from the generator manifest
  (`ocsf-semantic-testbed/_work/manifest.json`), e.g. the network-table row count.
- **`sql`** — a human-authored reference query (the answer-key oracle, the same logic
  `bench-a-context-collapse/bench.py` uses for the needles) executed **once** on Store F
  at run time to materialize the gold. This is answer-key computation, not the model's
  SQL; the model's SQL is scored against the executed *result*, not against this text.

The `gold_sql` text lives in `questions.py` next to each NL question so the answer key
is auditable.

## Design (per model, per question)

```
for model in {phi3:latest, gemma4:26b}, temperature 0:
  for question in the 33:
    gold  = resolve_gold(question)            # truth | literal | sql-oracle (deterministic)
    sql   = LLM(schema_of_store_F, question)  # Ollama /api/generate, temp 0, JSON-only
    rows  = duckdb.execute(sql)               # over Store F
    if   sql empty / error          -> loud
    elif rows empty (gold non-empty)-> loud
    else outcome = score(kind, rows, gold)    # correct | silent
```

Report per model: overall silent-error rate + result-accuracy, and the
**by-difficulty breakdown** (the load-bearing output — where do silent errors
concentrate?).

## Run it

This is a **readiness build**; the heavy eval has NOT been run (another benchmark
holds the box). See [READINESS.md](READINESS.md) for the exact run-when-free commands,
expected runtime, and which models must be present.

```bash
# light, anytime — no DuckDB, no LLM:
.venv/bin/python ocsf-nl2sql-silenterror/run.py --determinism
.venv/bin/python ocsf-nl2sql-silenterror/questions.py     # question-set self-check

# the heavy eval (DO NOT run while another benchmark holds the box):
.venv/bin/python ocsf-nl2sql-silenterror/run.py --models phi3:latest gemma4:26b
.venv/bin/python ocsf-nl2sql-silenterror/run.py --render-only   # re-render RESULTS.md
```

## Relationship to BENCH-B and BENCH-C

This is a third silent-error measurement in the same thread, deliberately
non-overlapping:

- **BENCH-B** (`../ocsf-mapping-oracle`) measures silent error at **mapping time**:
  a source log field mapped to an OCSF 1.8.0 path that does not exist — a wrong
  mapping that validates and ships. Different task (field→OCSF mapping), different
  failure (invented path), same headline metric.
- **BENCH-C** (`../ocsf-semantic-query`) is the **OBDA-vs-GraphRAG-vs-text-to-SQL
  head-to-head** on the adversary tail: whether a formal OWL2QL rewrite avoids the
  plausible-but-wrong answers an LLM gives. Its text-to-SQL arm runs 4 tail queries;
  its question is *which mechanism* is safest on the tail.
- **This benchmark** measures silent error at **query time** for the plain text-to-SQL
  mechanism, across the **whole difficulty curve**, to find *where* on that curve
  silent errors live. It shares the tail queries and the scorer with BENCH-C's
  text-to-SQL arm, so it is the breadth that arm's 4-query tail slice lacks, not a
  re-run of it. The mid-difficulty silent concentration it is built to surface is the
  affirmative evidence for both H-CONCEPT-GRAPH-03's null (LLM-composed SQL carries a
  silent-error tax) and, by contrast, H-CONCEPT-GRAPH-02's case (a deterministic
  rewrite is provably correct on what it covers).

## Evidence tier

Tier B. Local models, single machine, one synthetic planted chain, a hand-authored
gold set of 33 questions, exact-result scoring that can undercount a defensible
alternative phrasing of the same answer. The silent-vs-loud contrast and the
by-difficulty shape are the readable signals at this tier; the magnitudes are
model-and-question-specific. Determinism covers the corpus, the gold, and the scorer;
the SQL each model composes is temperature-0 greedy decode — reproducible in practice,
not asserted. Tier-A would need a published larger labeled set, a named reviewer on the
ambiguous gold adjudications, an independent (non-same-family) frontier model leg
(blocked here on no API key), and a non-toy corpus scale.

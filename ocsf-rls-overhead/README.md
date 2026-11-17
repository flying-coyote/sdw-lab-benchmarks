# OCSF RLS overhead — engine-side predicate cost of row-level security

Row-level security (RLS) is how a multi-tenant security data platform limits what each analyst
or automated query sees: a SOC tier-1 analyst reads their assigned tenants, a threat-hunt
engineer with cross-tenant privilege reads the full corpus, a compliance reviewer reads a
regulatory-scoped slice. Whatever the catalog or policy engine decides, the filter has to run
somewhere — and the cheapest enforcement layer is the query engine itself (a WHERE predicate or
a secured VIEW). This benchmark measures exactly that cost: the engine-side overhead of
appending a tenant-visibility predicate to OCSF-shaped event data, across three selectivity
tiers and four SOC query shapes.

## Design

**Corpus.** A seeded, 1M-row (default) OCSF Network Activity table with a `tenant_id`
column drawn uniformly from 100 tenant IDs. Every run regenerates the exact same rows because
the corpus is derived from a fixed seed (`lib.common.MASTER_SEED + 9901`); the corpus
fingerprint is logged so it can be re-verified across runs.

**Selectivity tiers.** Three role-visibility widths, chosen to cover the realistic range of
security-platform multi-tenancy:

| tier | visible tenants | approx % of rows |
|---|---|---|
| `tier_1pct` | 1 of 100 | ~1% |
| `tier_10pct` | 10 of 100 | ~10% |
| `tier_50pct` | 50 of 100 | ~50% |

**RLS enforcement approaches.** Two mechanisms compared against an unfiltered baseline:

| approach | mechanism |
|---|---|
| `baseline` | No filter — full table scan, the upper-bound throughput |
| `predicate` | WHERE clause appended to the query: `WHERE tenant_id < N` |
| `view` | Query hits a secured VIEW that encapsulates the predicate |

Both `predicate` and `view` perform the same logical work; any gap between them is the cost of
view-wrapper indirection (DuckDB should inline the view predicate into the plan, so the gap
should be within CV — a systematic view-is-slower result would indicate the wrapper is blocking
predicate-pushdown for a specific query shape).

**Query shapes.** Four representative SOC queries run under every (tier × approach) combination:

| query | what it measures |
|---|---|
| `count_all` | Full-scan count — maximum I/O, minimum result payload |
| `top_talkers` | Top-20 src_ip by event count — aggregation over a filtered table |
| `group_by_act` | Group-by activity_id — medium-cardinality aggregation |
| `needle` | Single event_id lookup — the rare-event / alert-triage query shape |

**Metrics.**
- Median latency (ms) per (query, approach, tier), with coefficient of variation
- Overhead % = (enforced median − baseline median) / baseline median × 100
- Correctness gate: `predicate` and `view` must return identical answers (sorted multiset
  comparison); a mismatch is a hard error

**Determinism.** Corpus generation and query answers are reproducible. Latencies are
wall-clock and legitimately non-deterministic; run under the Windows High-Performance power
plan per `BENCHMARKING-METHODOLOGY.md` for consistent CV.

## Result (Tier B)

Run `python ocsf-rls-overhead/run.py` to produce `results/results.json` and
`results/RESULTS.md`. Pre-run: `READINESS.md`.

## What this is — and is not

This is the **engine-side predicate-overhead lower bound**. DuckDB evaluates RLS predicates
as ordinary WHERE clauses after query parsing. Real multi-tenant catalog systems (Apache
Polaris, Unity Catalog, AWS Lake Formation) enforce RLS at the catalog protocol layer —
validating principal tokens, evaluating row-filter policies, and injecting predicates before
the engine ever sees the query plan. That catalog-layer enforcement adds its own cost on top of
what we measure here, so the numbers from this bench are the minimum overhead you'd expect in a
production system that uses catalog-mediated RLS.

Cross-reference `~/q3-catalog-benchmark` for the catalog-enforcement component. The two
benchmarks together bound the full RLS overhead range: this bench measures the floor (engine),
q3 measures the catalog layer on top.

Advances **H-SECURITY-02** (federated catalog RBAC enables centralized security governance).
The latency cost of RLS enforcement is a prerequisite measurement for any governance
architecture claim: a policy that is correct but slow enough to push analysts toward bypassing
it is not a real governance control.

---

## Layout and audit notes (added 2026-11-17)

### Result, and whether it is measured

Measured, with the predicate and secured-view answers identical in every cell (`results/results.json`, `all_answers_identical: true`), on DuckDB 1.5.3 over 1,000,000 rows. Two readings need to travel with the numbers in `results/RESULTS.md`, which `run.py` regenerates and whose Reading section describes what to look for without stating what was found:

- The positive overheads on `count_all` (+54% to +96%) are 0.4 to 0.7 ms on a 0.7 ms baseline whose CV runs from 13% to 36%. They clear the CV gate, but they sit near the client's timing floor and say little about a large table.
- The baseline is the unfiltered query, which does more work than the filtered one, so "overhead %" mixes the cost of enforcement with the saving from reading fewer rows. That is why `top_talkers` comes out 32% to 86% faster under the predicate. A baseline that isolates enforcement cost would run the same filtered row set without a security predicate.

Predicate and view land within each other's CV in 9 of 12 cells; the other three differ in both directions (the view is faster on `needle` at the 10% tier and on `group_by_act` at the 1% tier, and slower on `count_all` at the 50% tier), all on sub-3 ms medians, so the run shows no systematic view penalty that would point to blocked predicate pushdown.

### What would have made it fail

The predicate-versus-view equality gate is a real control and would have failed loudly on a mismatch. A view that blocked pushdown would have shown as a systematic view-is-slower gap.

### Pre-registration

None. `READINESS.md` is a pre-run checklist, not a pre-registration.

### Results

`results/RESULTS.md` (regenerated by `run.py`) and `results/results.json`.

### Versions and pins

DuckDB 1.5.3, recorded in the results and pinned in the root `requirements.txt`.

### Evidence tier and limits

Tier B, one host, engine-side only; catalog-layer enforcement would add its own cost on top.

### Corrections

- 2026-11-17: the two readings in the Result section are stated here because `results/RESULTS.md` is regenerated by `run.py` and does not state them.

# OCSF semantic testbed (BENCH-A foundation)

A deterministic, multi-source security-telemetry corpus with a planted, fully
ground-truthed attack chain. It is the *build-once* substrate behind three Lab
benchmarks, so it lives on its own rather than inside any one of them:

- **BENCH-A** (OCSF context-collapse) — build two OCSF stores from this one corpus,
  a fidelity-preserving store and a realistically-coarse normalized store, and
  measure whether coarse normalization degrades *adversary-relevant* queries more
  than routine ones. The headline is `Δ(adversary-tail) − Δ(routine)`.
- **BENCH-B** (mapping oracle) — the source→OCSF mappings used to build the stores
  are the mapping test set, and the rare needle events are the adversary tail on
  which a formally-grounded answer-key is hypothesized to beat schema-self-reference.
- **BENCH-C** (semantic-query head-to-head) — the A1–A10 questions, re-expressed as
  concept queries, are the head-to-head set for OBDA vs GraphRAG vs text-to-SQL,
  scored against this corpus's ground truth.

The pre-registration that governs all of this (the two-store design, the frozen
16-query battery, the metric definitions, and the planted-chain ground truth) is
in the (private) benchmark repo at
`splunk-db-connect-benchmark/workloads/ocsf-context-collapse/`, frozen 2026-05-31.
This directory is the *implementation* of the data-generation half of that spec;
it does not get to change the queries or the ground truth.

## Why a synthetic corpus

The whole premise of the Lab is that a skeptic can re-run the measurement, and a
synthetic corpus is what makes that possible here: no customer data, no NDA, every
value a pure function of one seed. It is also the only honest way to have *ground
truth*, because I know the true event order, the true identity links, and exactly
which events are the needles, since I planted them. The cost is external validity: one
synthetic APT29-style chain is not the population of real adversary behavior, which
is why BENCH-A's result is Tier B and its promotion to Tier A is gated on an
independent practitioner confirming the coarse store resembles what shops actually
build (see the fairness checklist in the query battery).

## State (phased build)

| Phase | What | State |
|---|---|---|
| **1** | the corpus + ground truth (this generator) | **done, verified, 14/14 integrity checks** |
| 2 | Store F (fidelity-preserving) + Store N (normalized/coarse), built blind to the queries | next |
| 3 | the frozen 16-query battery against both stores + the Δ headline + RESULTS.md | after 2 |

BENCH-C (OBDA / GraphRAG / text-to-SQL) layers on the same corpus once Phases 2–3
land; it is tracked separately.

## Run it

```bash
# from the repo root, using the shared venv (duckdb 1.5.3)
.venv/bin/python ocsf-semantic-testbed/generate.py            # full scale (~177k events)
.venv/bin/python ocsf-semantic-testbed/generate.py --scale smoke   # fast, for iteration
.venv/bin/python ocsf-semantic-testbed/validate.py            # ground-truth integrity check
```

`generate.py` builds the corpus twice and refuses to write unless the two builds
fingerprint identically; that is the reproducibility guarantee, the same
determinism discipline as the rest of the Lab (`lib/common.py`: one `MASTER_SEED`,
a fixed epoch, no wall-clock). The raw corpus and ground truth land under `_work/`
(git-ignored, regenerated from the seed). The canonical raw is the per-source
JSONL; the Parquet materialization is a query convenience for the later phases.

## What's in the corpus

Six native-shaped source streams (Okta auth + sign-in sessions, Zeek conn + dns,
Sysmon process-creation, and CloudTrail-shaped cloud audit), about 177k events over
a 14-day window, with the six-stage chain planted on the middle day inside the
background. `GENERATION-PLAN.md` documents the source shapes, the volumes, the
identity model, the planted-chain timing, and how each needle maps to the query it
serves. The ground truth (`_work/ground_truth.json`) carries the true event order,
the true host↔user↔principal↔role identity links, and the flagged needle sets.

## Public-language constraint

Per the benchmark publication strategy, the public methodology genericizes the
incumbent to a *schema-on-read SIEM* rather than naming a product in comparative
claims. Nothing here names a customer or carries customer data; the corpus is
entirely synthetic.

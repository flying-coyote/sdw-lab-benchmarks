# OCSF semantic testbed (BENCH-A foundation)

## What it measures

It measures nothing on its own, because it is a deterministic, multi-source security-telemetry corpus with a planted, fully
ground-truthed attack chain. It is the *build-once* corpus behind several Lab
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

Benches that read this corpus or its stores: `bench-a-context-collapse`, `ocsf-sigma-detection`,
`ocsf-attack-coverage`, `ocsf-marimo-hunt`, `ocsf-semantic-query` and `ocsf-nl2sql-silenterror` (the last
two read Store F and `_work/ground_truth.json`, `ocsf-semantic-query/run.py:26-27` and
`ocsf-nl2sql-silenterror/run.py:49-50`; their planted-value exposure is assessed with their own READMEs,
outside this unit). Any rule or query in the first four benches that names a planted
value (the C2 domain `cdn-telemetry-sync.net` and address `203.0.113.66`, host `WS1`, the absent
`mfaAuthenticated` key, lateral port 3389; `generate.py:104-113`, `:400-408`) cannot miss on this corpus,
and their READMEs now say so.

## Result, and what would have made it fail

The folder produces a corpus, not a scored number. Its checkable claims are determinism (two builds must
fingerprint identically before anything is written) and `validate.py`'s 14 ground-truth integrity
checks, both of which could fail. Both are asserted by the code on every build.

## Pre-registration

The design is governed by a pre-registration frozen 2026-05-31 in a private benchmark repo
([GENERATION-PLAN.md](GENERATION-PLAN.md) cites it), so it cannot be read or hash-checked from this
public repo.

## Why a synthetic corpus

The whole premise of the Lab is that a skeptic can re-run the measurement, and a
synthetic corpus is what makes that possible here: no customer data, no NDA, every
value a pure function of one seed. It is also the only honest way to have *ground
truth*, because the generator fixes the true event order, the true identity links, and exactly
which events are the needles, since it planted them. The cost is external validity: one
synthetic APT29-style chain is not the population of real adversary behavior, which
is why BENCH-A's result is Tier B and its promotion to Tier A is gated on an
independent practitioner confirming the coarse store resembles what shops actually
build (see the fairness checklist in the query battery).

## State (phased build)

| Phase | What | State |
|---|---|---|
| **1** | the corpus + ground truth (this generator) | **done, verified, 14/14 integrity checks** |
| 2 | Store F (fidelity-preserving) + Store N (normalized/coarse) | done, in `../bench-a-context-collapse/stores.py` |
| 3 | the frozen 16-query battery against both stores + the Δ headline + RESULTS.md | done, `../bench-a-context-collapse/results/RESULTS.md` |

*(corrected 2026-11-17: phases 2 and 3 were listed as "next" and "after 2" after both had run; Store N
was also described as "built blind to the queries", which `../bench-a-context-collapse/stores.py:146`
contradicts for the routine query R4.)*

BENCH-C (OBDA / GraphRAG / text-to-SQL) layers on the same corpus now that Phases 2–3
have run; it is tracked separately in `../ocsf-semantic-query/`, and `../ocsf-nl2sql-silenterror/` extends its text-to-SQL arm.

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

## Results

None of its own; the corpus and `_work/ground_truth.json` are regenerated from the seed.

## Versions and pins

No `requirements.txt`; the generator needs `duckdb` from the root `requirements.txt` (`duckdb==1.5.3`).

## Evidence tier and limits

The corpus carries no tier of its own; the six benches that read it record Tier B in their `bench.yaml`
files, or B/C for `ocsf-marimo-hunt`. Its limits
travel to every dependant: one synthetic APT29-style chain on one seed, so external validity is the open
question (see "Why a synthetic corpus"), and every planted value is known to the author of each rule or
query that reads it. The governing pre-registration sits in a private repo and cannot be checked here.

## Corrections

- *(corrected 2026-11-17: the phase table, the blind-build wording and the first-person narration of
  the generator were updated.)*

# t8c-trifecta-detection (T8c)

## What it measures

Can the lethal trifecta be detected as a sequence inside one agent session, over OCSF 1.9.0 `api_activity` events
carrying the `ai_operation` profile? Chains shaped like ATLAS AML.CS0066 (ZombieAgent, the T1698 → T1700 shape
through connectors) and AML.CS0067 (Claude Code GitHub Action, the same shape through a CI agent) are planted at
their defender-visible steps among benign agent sessions, and three tiers of rule are scored DETECTED / NOISY /
MISSED at precision floor T = 0.9 on DuckDB 1.5.3 and stdlib SQLite: single-step Sigma rules per leg, session rules
(pySigma `temporal` correlation and hand SQL), and session rules after a delegation walk to the root session.

## Result

At 2,000 benign sessions per seed over three seeds, the only rule that reached DETECTED on both chain shapes and all
four plant strata was `c2_walk_sql_qualified`, the session rule that walks delegation to the root and qualifies the
outbound leg by content, at precision 1.0 and recall 1.0; the plain session rule `b3_session_sql` was NOISY at a
median precision of 0.2083 with recall 0.5, because it missed every delegated chain and fired on 37 to 42 benign
sessions per seed (`RESULTS.md`, Headline, citing `results/coverage.json`). This is a demonstration of a mechanism
and not a detection rate. c2's recall follows from construction, because its content qualifier matches the fixture
string `api03-` or a burst of 20 or more calls and every planted chain carries one of the two, and the precisions
follow from lookalike rates the same agent chose (`PREREGISTRATION.md`, Known biases; `RESULTS.md`, Limits). What the
run does show is the shape of the result: which rules collapse on delegated chains and which lookalike classes
produce the false positives. Two post-hoc probes found that on DuckDB c2 and b4 miss an upper-cased `api03-` prefix,
so on the bench's corpus regenerated with the planted `api03-` prefix upper-cased, c2's DuckDB recall falls to 0.5
(CS0067 strata 0.0) while precision stays 1.0; SQLite is unaffected (`RESULTS-CORPUS-CASE-CHECK-2026-11-16.md`).

## What would have made it fail

Six hypotheses in `PREREGISTRATION.md` carry falsifiers, and three were falsified (H1 on the a6 clause, H2, H6). The
benign sessions include seven pre-committed lookalike classes as the false-positive control, the allowlist was fixed
before any row existed, and no rule matches on the `.invalid` attacker hostnames. All positives are planted, so recall
figures are counts of planted chains flagged.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before the run and not owner-reviewed. Its sha256 in `results/PREREG.sha256`
(`7703a4bb…a106d9`) still matches, and `.frozen` records 2026-11-10T00:54:01Z. The rules are named in the
pre-registration with their literals (`/proc/self/environ`, `api03-`, the 20-call burst) but the rule files were
written after the freeze, at 00:56Z by the run's own account, and `rules/` has no hash file, so "rules frozen before
the corpus existed" rests on the pre-registration text, not on a hash (`RESULTS.md`, Deviation 1). An unregistered one-seed probe ran at 01:01Z,
before run 1, and `run.py` was edited afterwards to add the post-hoc `supplementary` block; both are declared
(`RESULTS.md`, Deviation 2). `LEDGER-ROW.md` is index text for the lab's pre-registration ledger, kept
outside this repo.

## Reproduce

Local CPU only, zero spend, about 3 minutes per seed, most of it corpus writing:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
taskset -c 0-3 nice -n 10 .venv/bin/python -I run.py                      # three seeds -> results/coverage.json
taskset -c 0-3 nice -n 10 .venv/bin/python -I run.py --scale 20000 --seeds 20261109 --sql-only --out results/coverage-scale20k.json
```

The corpus is regenerated deterministically per seed and is gitignored. Rules are `rules/*.yml` (Sigma, compiled
through pySigma 2.0.3 and pySigma-backend-sqlite 2.1.1), with hand SQL in `run.py`. The post-hoc probes run as
`mixed_case_probe_2026_11_16.py` and `corpus_case_check_2026_11_16.py`, which import `run.py` and `gen_corpus.py`
read-only. Column paths are validated against the OCSF 1.9.0 schema JSON in
`../atlas-ocsf-observables/sources/ocsf-1.9.0/` (read-only). That schema tree is gitignored and not committed, so
`run.py` stops at `validate_columns()` until the directory is rebuilt from schema.ocsf.io/api/1.9.0, and
`corpus_case_check_2026_11_16.py` skips that check for the same reason (noted 2026-11-22).

Everything in the corpus is synthetic test fixture: reserved hostnames (`.invalid`, `.example`), a labelled fixture
marker where the injected content would be, and a fixture string where the de-prefixed key would be. No real
credentials, no real data, no exploit content, no model in the loop.

## Results

- `RESULTS.md` is the entry point: headline, results by rule, scale check at 20,000 sessions, hypotheses, deviations,
  post-hoc views, limits.
- `results/coverage.json` (sha256 `55666d53…402e0`, identical over three runs) and `results/coverage-scale20k.json`
  hold every number; `results/chain_steps.md` is the per-step observability table for the two case studies;
  `results/probe-coverage.json` and `results/probe-timings.json` are the unregistered pre-run probe.
- `RESULTS-MIXED-CASE-PROBE-2026-11-16.md` (post-hoc, not pre-registered, not independently verified) tests every
  `LIKE` predicate in four letter cases on both engines.
- `RESULTS-CORPUS-CASE-CHECK-2026-11-16.md` (post-hoc, not pre-registered) repeats the case test at corpus level with
  a mixed-case key body.
- `VERIFICATION.md` is the independent check (VERIFIED-WITH-FIXES). `verify/` holds the verifier's own runs and its
  cross-provider prompt and response, and `verify/pre-fix/chain_steps.md` is a superseded copy from before the
  verifier's fixes; none of them is the current result.

## Versions and pins

`requirements.txt` is a full freeze with every line pinned (duckdb 1.5.3, pySigma 2.0.3, pySigma-backend-sqlite
2.1.1). `coverage.json` records the DuckDB, SQLite and Python versions but not the pySigma versions (Deviation 4).

## Evidence tier and limits

Tier B for the mechanism and Tier D for every judgment about what a benign session looks like
(`PREREGISTRATION.md` line 46); `RESULTS.md` describes the run as agent-run and not owner-reviewed. The corpus is synthetic,
the lookalike rates were chosen, the session uid and delegation object are cleaner than shipping telemetry, and c2's
clean score rests on a fixture string and a fixed burst threshold that a slow-drip attacker without a recognisable
credential shape would not trip. See Limits in `RESULTS.md`.

## Corrections

- 2026-11-10 UTC (2026-11-09 local): verifier fixes are marked `[fixed in verify]` in `RESULTS.md`.
- 2026-11-17: `RESULTS.md` now carries a dated note in its headline saying that c2's recall of 1.0 follows from the
  plants and the rule, and pointing to the two 2026-11-16 case probes, which the file did not previously cite.
  First-person narration of the second run agent's steps was recast in neutral voice. This README was restructured
  to the lab layout.

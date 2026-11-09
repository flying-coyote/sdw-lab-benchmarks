---
type: benchmark-verification
title: "R1 atlas-ocsf-observables: independent verification"
created: 2026-11-09
verifier: independent agent run (not the original author), not owner-reviewed
---

# Verification of R1 atlas-ocsf-observables

**Verdict: VERIFIED-WITH-FIXES.** Every number reproduces exactly. The fixes are to wording and framing in
`RESULTS.md` (one hypothesis verdict was scored against the wrong engine, one count move was unexplained, and
three deviations were undeclared). No result file, script or the pre-registration was changed.

## What I re-ran

Copied the scripts, CSVs, rules and `sources/` to a scratch directory
(`/tmp/claude-1000/-home-jerem-project1/af12c3ec-6e7f-4f5c-a239-70fb7dfd0d6e/scratch/r1v/`) (ephemeral session scratch; every hash it produced is in the table below) and ran the full
pipeline with the R1 `.venv` (Python 3.12.3, duckdb 1.5.3, pySigma 2.0.3, pySigma-backend-sqlite 2.1.1, PyYAML
6.0.3, matching `requirements.txt` and RESULTS). Beelink, WSL2 6.6.87.2. Nothing was timed. Commands:

```
.venv/bin/python -I ocsf_reach.py
.venv/bin/python -I join.py
.venv/bin/python -I split_attack.py
.venv/bin/python -I run_planted.py   # x3
```

| File | Original sha256 | Re-run sha256 |
|---|---|---|
| results/ocsf_reach.json | 0de548fa…f14d | identical |
| results/observables.json | 95c56312…931e | identical |
| results/technique_artifact_ocsf.csv | 207547d9…55a6 | identical |
| results/attack_split.json | bbe0d4be…5a5a | identical |
| results/coverage.json | a7b10d1d…949a | identical on all three runs |

Hand-checked arithmetic against `observables.json` and `attack_split.json`: 235/290 = 81.0%, 155/182 = 85.2%,
161/290 = 55.5%, 112/182 = 61.5%, 91/107 = 85.0%, 55/107 = 51.4%; ATT&CK-referenced 104/122 = 85.2% and 119/122
= 97.5%; ATLAS-native 57/168 = 33.9% and 116/168 = 69.0%; sensitivity 123/290 = 42.4% and 202/290 = 69.7%;
no-field block 54 of 55 steps from the 15 no-row techniques (sum 9+8+8+6+6+3+2+2+2+2+2+1+1+1+1 = 54). Planted
states, precision min/median/max and FP per seed all match the RESULTS table. The engine claim checks out
directly: `'Ignore previous instructions' LIKE '%ignore previous instructions%'` is false in DuckDB 1.5.3 and true
in stdlib SQLite, and `ocsf-attack-coverage/run.py` does compile with `sqliteBackend` and execute in DuckDB. The
1.8.0 clone has no `ai_agent` or `delegation` object, as claimed.

## Pre-registration timing

`sha256sum` of PREREGISTRATION.md = `0e93ad54…5283`, matching `results/PREREG.sha256` and the RESULTS header.
File times (local -0500): PREREGISTRATION.md 18:06:10, PREREG.sha256 18:06:16 (= 23:06:16Z), join.py 18:06:56,
artifact_ocsf_map.csv 18:07:09 (deviation 1 edit), rules 18:08:52, corpus 18:11, result files 18:22 to 18:27.
That chain is consistent with freeze before the join and the planted runs. One exception: `ocsf_reach.json` was
written at 18:02:48, before the freeze (fix 4 below). `technique_direct_ocsf.csv` (18:05:23) predates the freeze
and its hash `d914f59b…` matches the one the pre-registration records, as intended.

## Fixes made to RESULTS.md

1. **H5 scored against the pre-registered engine.** The pre-registration names the pipeline as pySigma sqlite
   backend to DuckDB 1.5.3; SQLite was added after the freeze. Under DuckDB the profile-arm T0051.000 rule is
   MISSED on all three seeds, so H5 is refuted as written. Before: "holds on SQLite and fails on DuckDB". After:
   "refuted on the pre-registered engine", with the SQLite NOISY result kept as the supplementary reading. The
   mapped-vs-fires table now leads with DuckDB (pre-registered) and puts SQLite in the supplementary column; the
   only row where they differ is T0051.000 in the profile arm. The run summary's "H5 holds on SQLite and fails on
   DuckDB" should be read the same way.
2. **Unexplained 161 to 163 specific move.** RESULTS said only T0093 gains a field in the profile arm. T0093 goes
   none to generic (the 235 to 236 move); the +2 specific steps come from T0008 Acquire Infrastructure (2 steps,
   off defender ground) going generic to direct. Sentence added.
3. **T0024 needle size undeclared** (added as deviation 5). The pre-registration says one planted needle per
   technique; T0024's is a 600-call burst, which is why its single-event rule shows precision 0.23 rather than
   about 0.0005.
4. **Reachability ran before the freeze** (deviation 6). The pre-registration's claim that no coverage figure was
   computed is literally true, but the instrument output existed while the map grades were written. It
   reproduces byte for byte, so I judge the impact low.
5. **Stop rule (b) not followed as written** (deviation 7). The map was fixed and recorded but not re-frozen;
   leaving the original hash is the more honest record. The original map `d565ab33…` was not kept, so the claim
   that only the ConfigurationFile row changed is unverifiable.
6. **H3 note.** The pre-registration did not restrict the "at least 3 observable" clause to the core arm, so the
   profile reading (6, or 3 counting only fields that record the act) is the literal one. Note added; verdict
   wording otherwise unchanged.

A pre-edit copy of RESULTS.md is at `scratch/RESULTS.md.pre-verify` in this directory.

## Claims versus evidence

Nothing else overreaches. The tier-D status of the artifact-to-OCSF grades, the schema-can-hold versus
product-emits distinction, the synthetic corpus written by the same author as the rules, the ATLAS-only (27
incident) weights, and the single crosswalk are all declared. The ATT&CK split and the File/UserAccount
sensitivity are labelled post-freeze. The `ocsf-attack-coverage` exposure is stated as a risk that was not
tested, which is the right strength. I did not re-fetch the OCSF schema from schema.ocsf.io; the verification
uses the fetched copies in `sources/`.

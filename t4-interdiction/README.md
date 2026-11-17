# t4-interdiction (T4)

## What it measures

The ATLAS control burn-down ranks MITRE ATLAS v2026.10 mitigations by how many of 290 incident steps each is mapped
to, which is relevance and not interdiction. This bench takes the eight controls near the top of that order whose
text names a telemetry or enforcement artefact, implements each as the check its mitigation sentence describes,
plants the mapped incident steps as OCSF 1.9.0 event sequences among synthetic background, and scores each step slot
CAUGHT, NOISY, MISSED or MISSED-by-construction on SQLite (pre-registered for H1) and DuckDB, over three seeds.

## Result

Of the 22 rule-selected step slots the burn-down credits to these eight controls, the check the mitigation text
describes caught one cleanly on SQLite, caught seven only alongside legitimate background, missed eight, and could
not see six because the step leaves no event on the control holder's side; DuckDB gave 2, 5, 9 and 6, and a
hand-picked mechanism set of eight slots gave 3 CAUGHT on both engines (`RESULTS.md`, Headline;
`results/interdiction.json` summary block from line 4503). These states could have come out otherwise, since the
hypothesis was a ceiling of seven CAUGHT and the rules were not tuned to the plants, but the corpus, the lookalike
background, the control-to-check mapping and the rules were all written by one agent, so the precision figures show
the mechanism rather than field false-positive rates. The single rule-set CAUGHT depends on where that agent placed
the holder of M0043; another reader could move it to MISSED-by-construction (`RESULTS.md`, Limits). E3's precision of
1.0 is partly by construction, because its pre-committed lookalike is approved identities on the same paths, so the
background holds no non-approved reader that could produce a false positive (`RESULTS.md`, What the table says).

## What would have made it fail

H1 to H7 in `PREREGISTRATION.md` each carry a numeric falsifier (for example H1 fails if more than 7 of 22 rule slots
are CAUGHT on SQLite). Every check runs over a synthetic background with pre-committed lookalike rates, which is the
false-positive control, and the precision floor T is fixed before the run. All planted positives are injected, so the
recall figures are counts of planted cases flagged.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before the run and not owner-reviewed. Its sha256 in `results/PREREG.sha256`
(`55d3fe5a…57338`) still matches, and `results/PREREG.frozen_at` records 2026-11-10T01:00:30Z. The verifier's file
mtimes put the rules, corpus generator and checks after the freeze and the corpora at 01:24Z to 01:30Z
(`VERIFICATION.md`, pre-registration row), which supports freeze before run on self-reported mtimes only.
`extract_mappings.py` and `select_steps.py` ran before the freeze and are declared as orientation. Seven deviations
are listed in `RESULTS.md`, and each matches a stated cause there. The pre-registration's input list names private
working paths outside this repo; the file is frozen and is left as it is.

## Reproduce

Zero spend, no model calls, no containers:

```bash
python3 -m venv .venv && .venv/bin/pip install duckdb==1.5.3 pySigma==2.0.3 pySigma-backend-sqlite==2.1.1 PyYAML==6.0.3
.venv/bin/python -I ocsf_fields.py
taskset -c 0-3 nice -n 10 .venv/bin/python -I run.py      # x3 for the determinism check
sha256sum -c results/PREREG.sha256
```

The inputs are the ATLAS v2026.10 YAML (sha256 `ac41ee9f…e142d`), `control_burndown_2026.10.json` and the OCSF 1.9.0
dump under `../atlas-ocsf-observables/sources/ocsf-1.9.0`. The first two are not in this repo, and
`extract_mappings.py` and `select_steps.py` read the ATLAS YAML from a hard-coded path outside it, so the orientation
step needs that path edited; `run.py` itself works from `results/selected_steps.json` and `results/mappings_top12.json`,
which are committed. The generated corpora (`corpus/<seed>/`) are not committed and regenerate deterministically.

## Results

- `RESULTS.md` is the entry point: headline, per-control table, hypotheses, variance, deviations, limits.
- `results/interdiction.json` (sha256 `d35b4928…a7c5d`, identical over three runs and two verifier runs) holds every
  per-slot state; `results/timings.json` holds wall times taken under contention.
- `VERIFICATION.md` is the independent check (VERIFIED-WITH-FIXES). `verification/RESULTS.pre-verification.md` is a
  superseded copy of the results file from before the verifier's fixes, and `verification/rerun/` holds the
  verifier's copies of the scripts; neither is the current result.

## Versions and pins

`requirements.txt` is a full `pip freeze` with every line pinned (duckdb 1.5.3, pySigma 2.0.3,
pySigma-backend-sqlite 2.1.1, PyYAML 6.0.3 among them), and the verifier matched it against the venv that ran. Python
3.12.3 and SQLite 3.45.1 (stdlib).

## Evidence tier and limits

Tier B for the planted runs and the scoring, Tier D for the control-to-check mapping, the fixtures and the
holder-of-control judgments (`RESULTS.md` frontmatter). One author for mapping, fixtures, lookalikes and rules,
invented background volumes, tool calls carried on `api_activity` because OCSF 1.9.0 has no tool-call class, and
checks that follow the mitigation text literally without tuning. See Limits in `RESULTS.md`.

## Corrections

- 2026-11-09: five verifier edits in `RESULTS.md`, marked there, including that 14 of the 22 rule slots are marginal
  steps and 8 are reach-only.
- 2026-11-17: the per-control table row for E3 now carries the partly-by-construction note next to its precision of
  1.0; this README was added.

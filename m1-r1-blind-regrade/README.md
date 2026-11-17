# M1: blind re-grade of R1's artifact-to-OCSF grades

`../atlas-ocsf-observables/` (R1) graded, in one pass by one agent, how well each D3FEND artifact lands on
an OCSF 1.9.0 field (direct, event, generic, proxy or none), and its headline that 55.5% of ATLAS incident
steps reach a specific field rests on those grades. This bench gives the same rows, rubric and schema
excerpt to a second grader from another model provider, blind to R1's grades, three times, and asks how
far the headline moves.

## What it measures

Agreement between R1's grades (Grader A) and the second grader's modal grade over three passes (Grader B,
Gemini 3.8 Flash) on 79 artifact rows and 15 technique rows; Grader B's stability across its own passes;
how often it names an OCSF object or class that does not exist; and R1's headline recomputed under
Grader B's grades. A third, adjudicating model was planned for the disagreements.

## Result

Measured: five-category kappa 0.452 on the 79 artifact rows (62.0% agreement against 30.8% expected,
re-derived from the confusion matrix in `results/agreement.json` on 2026-11-17), Grader B flip rate 3.2%,
no invented objects in 282 row-grades. Under Grader B the specific-field share moves from 161 to 168 of
290 steps (55.5% to 57.9%), and the any-field share moves from 235 to 204 (81.0% to 70.3%), because
Grader B puts 13 artifact rows at none where R1 had one. The adjudication leg did not run (quota floor),
so there is no consensus grade and H4 is untested.

## What would have made it fail

Each of H1 to H6 has a frozen falsifier, and one fired (H3, which predicted that most disagreements would
be direct against generic; 12 of 30 were). H1 clears its 0.40 bar narrowly. Agreement between two graders
is not accuracy, and without the adjudicator there is no third reading on the 36 disputed rows.

## Pre-registration

`PREREGISTRATION.md`, frozen at 2026-11-10T00:51:49Z (`results/PREREG.frozen_at`); its sha256
`a2eed4ad…a6b240cf` verifies against `results/PREREG.sha256` (checked 2026-11-17). On in-file evidence the
freeze precedes the first grading call, which `RESULTS.md` places at about 03:00 UTC on 2026-11-10. Each
verdict in `RESULTS.md` matches its frozen threshold (H1 0.4516 against at least 0.40; H2 57.9% inside
45.5% to 65.5%; H3 40% against at least half, so wrong; H5 3.19% against at most 15%; H6 0% against at
most 5%). The deviations, including the change of executing agent and the operational patches to
`run_pass.sh`, are listed in `RESULTS.md`.

## Reproduce

The grading calls need the Antigravity CLI (`agy`) behind a local usage-ledger wrapper that is not part of
this repository, and `build_prompts.py`, `run_pass.sh` and `run_adj.sh` name local paths that a clone must
change first. `analyze.py` needs only checked-in files (the responses and R1's map and reachability files); `recompute.py` imports R1's `join.py`, so
it needs the same ATLAS YAML, edge list and crosswalk clone that R1's README describes:

```bash
cd m1-r1-blind-regrade
python3 -I analyze.py      # results/agreement.json, grader_b.json, disagreements.csv
python3 -I recompute.py    # results/headline.json (imports ../atlas-ocsf-observables/join.py)
```

## Results

- `RESULTS.md`: the entry point.
- `VERIFICATION.md`: independent verification.
- `results/`: `agreement.json`, `headline.json`, `grader_b.json`, `disagreements.csv`, and the freeze record.
- `responses/` and `prompts/`: raw Grader B answers and the built (unsent) adjudication prompts.

## Versions and pins

`requirements.txt` pins PyYAML. The grader is `gemini-3.8-flash-high` through agy 1.5.3; model versions
behind a hosted alias can change without notice, which limits exact re-runs.

## Evidence tier and limits

No tier is stated in the folder; R1's grades it re-checks are Tier D. One second grader from one provider,
an excerpt that shows one-sentence descriptions without nesting, and no adjudication.

## Corrections

- 2026-11-16: provider-attribution note added to `RESULTS.md` Limits.
- 2026-11-17: a local wrapper path in `RESULTS.md` replaced by a description; this README added.

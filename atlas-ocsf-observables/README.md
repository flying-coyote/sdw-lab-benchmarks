# ATLAS realized techniques to OCSF fields (R1)

Which techniques that MITRE ATLAS records as actually used in its 27 incident case studies leave a field
in OCSF 1.9.0, going technique to D3FEND artifact (through the ATLAS-to-D3FEND crosswalk) to OCSF object
and class, and, for eight of them, does a Sigma rule on that field fire on a planted corpus? Two arms
share the folder: a mechanical join with graded artifact-to-field calls, and a small planted bench.

## What it measures

- **Join arm.** For 290 procedure steps over 107 techniques, whether a step reaches a specific OCSF field
  (direct or event grade), any field (adding generic and proxy carriers), or nothing, in a core arm
  (native class fields) and a profile arm (with `ai_operation`).
- **Planted arm.** For eight pre-registered techniques, a synthetic OCSF-shaped corpus with one needle per
  technique and authored lookalike background, three seeds, each rule scored DETECTED, NOISY or MISSED at
  a precision threshold of 0.9, on DuckDB (pre-registered) and SQLite (added).

## Result

- Join arm: 161 of 290 steps (55.5%) reach a specific field and 235 (81.0%) reach some field in the core
  arm; ATT&CK-referenced steps reach a specific field at 85.2% against 33.9% for ATLAS-native steps (a
  supplementary split). These rest on one grader's calls; a blind second grader moved the specific share
  to 57.9% and the any-field share to 70.3% (`../m1-r1-blind-regrade/RESULTS.md`).
- Planted arm: 2 DETECTED, 5 NOISY, 1 MISSED in the core arm, identical on all three seeds. The two
  DETECTED states follow from construction, because the same agent wrote the needles, the lookalikes and
  the rules, and the T0049 rule's one filter (`--`) is the feature that separates the planted query from
  the authored UNION lookalikes; `RESULTS.md` (corrections of 2026-11-17) and its Limits say the precision
  figures show a mechanism and are not false-positive rates. The NOISY states rest on the same agent's
  lookalikes, so they show that a kind-level rule collides with authored lookalikes, which is also a
  mechanism and not a false-positive rate.

## What would have made it fail

Each of H1 to H5 has a frozen falsifier, and two were refuted (H1 and H5). In the planted arm the
rule-writing constraint (signal plus at most one filter named by the technique's definition, no
allowlist) was set by the bench agent when it wrote the rules, after the freeze (`RESULTS.md` deviation
3), and is not in `PREREGISTRATION.md`; no file records whether the corpus generator or the rules came
first. The same agent wrote the needles, the lookalikes and the rules, so neither the DETECTED nor the
NOISY states are independent of construction, and a DETECTED rule could not easily have missed the
needle it was written beside. A case probe after the run
(`RESULTS-PROBE-DETECTED-CASE-2026-11-16.md`) shows the T0049 rule misses a lower-case `union select` on
DuckDB.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent at 2026-11-09T23:06:16Z and not owner-reviewed. Its sha256
`0e93ad54…5283` verifies against `results/PREREG.sha256` (checked 2026-11-17). Deviation 6 records that
`ocsf_reach.py` ran four minutes before the freeze, and deviation 1 that the frozen artifact map was
changed by one row after it, with the original map not kept. Each H verdict in `RESULTS.md` matches its
frozen threshold on the numbers given (H1 refuted at 55.5% against "fewer than half"; H2 holds at 85.2%
against 70%; H4 holds at 2 / 5 / 1 against "at most 5 DETECTED, at least 1 NOISY, at least 1 MISSED";
H5 refuted on DuckDB). The rest of the freeze-before-run order needs the git history to confirm.

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -r atlas-ocsf-observables/requirements.txt
cd atlas-ocsf-observables
../.venv/bin/python -I ocsf_reach.py
../.venv/bin/python -I join.py
../.venv/bin/python -I split_attack.py
../.venv/bin/python -I run_planted.py      # three seeds; writes corpus/<seed>/ and results/coverage.json
```

The join needs the ATLAS v2026.10 YAML, an incident-to-technique edge list and a clone of the
`atlas-d3fend-crosswalk` dataset at commit `66b7726`, all hashed in `results/observables.json`. Their
locations are absolute paths on the lab host set at `join.py` l.10-12, so a fresh clone has to point
those three constants at its own copies before the join will run. The 2026-11-16
supplement's 48-incident re-weight reads a researcher-mapped CSV that is not in this repository, so that
part of the supplement cannot be reproduced from a clone.

## Results

- `RESULTS.md`: the entry point, with verification notes and the 2026-11-16 and 2026-11-17 corrections.
- `RESULTS-SUPPLEMENT-2026-11-16.md`: post-hoc split and sensitivity under the second grader, and the
  48-incident re-weight. Not pre-registered and not independently verified.
- `RESULTS-PROBE-DETECTED-CASE-2026-11-16.md`: post-hoc case probe of the two DETECTED rules.
- `VERIFICATION.md`: independent verification of the original run.
- `results/`: `technique_artifact_ocsf.csv` (194 rows), `observables.json`, `coverage.json` and the
  supplement and probe JSON.

## Versions and pins

`requirements.txt` pins every package (duckdb 1.5.3, pySigma 2.0.3, pySigma-backend-sqlite 2.1.1,
PyYAML 6.0.3 and their dependencies). OCSF 1.9.0 objects and classes were fetched from schema.ocsf.io on
2026-11-09 and are checked in under `sources/`. The supplement ran under PyYAML 6.0.1 because the
original `.venv` was gone; its gate reproduces the original numbers exactly.

## Evidence tier and limits

Tier B for the mechanical join and the planted runs, Tier D for the artifact-to-field grades (single
grader, with one blind re-grade that agreed at kappa 0.45). "Has a field" means the schema can hold the
fact, not that a product emits it. ATLAS-only weights.

## Corrections

- 2026-11-09 and 2026-11-16: verification and post-hoc corrections in `RESULTS.md`.
- 2026-11-17: the construction of the two DETECTED states stated in `RESULTS.md`; first-person narration
  recast; this README added.

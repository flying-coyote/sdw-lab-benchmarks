---
type: benchmark-results
title: "R1 post-hoc supplement: split and sensitivity under the M1 second grader, and a 48-incident re-weight"
created: 2026-11-16
status: post-hoc, not pre-registered, not independently verified
evidence_tier: "B for the mechanical recomputation; D for every grade it consumes (R1 single-author grades, M1 Grader B unadjudicated modal grades, three new single-author cells)"
---

# R1 supplement (2026-11-16): second-grader split and the 48-incident re-weight

**Post-hoc.** Neither reading below was pre-registered, by R1 (`PREREGISTRATION.md`, sha256 `0e93ad54…5283`) or by
M1 (`../m1-r1-blind-regrade/PREREGISTRATION.md`, sha256 `a2eed4ad…a6b240cf`). Written for draft 05's build pass so the
essay can quote R1's supplementary split and the 48-incident figure honestly. Not independently verified; the main
session should treat it as a single-agent run until a verifier re-runs it.

**Script and output:** `supplement_2026_11_16.py` writes `results/supplement-2026-11-16.json`. It imports `join.py`
and `../m1-r1-blind-regrade/recompute.py` and never calls `join.main()`, so no tracked file is rewritten. Two runs
gave the same sha256, `5358bc2ad8b31778006ac66ffcb6b25b7588cff394e5992ac6f61185929a3899`. Environment: system
Python 3.12.3, PyYAML 6.0.1 (the bench's `.venv`, PyYAML 6.0.3, is no longer on disk; the gate below passing is
the check that the version change did not matter). Zero spend, no model calls.

**Gate:** Grader A (R1's own grades) reproduces R1 exactly, 161 and 235 of 290 steps and 112 and 155 of 182
defender-ground steps, or the script exits 2. It passed.

## 1. R1's supplementary split and sensitivity under both graders (27 ATLAS incidents, core arm)

| Reading | Grader A (R1) | Grader B (M1 modal) |
| --- | --- | --- |
| ATT&CK-referenced, 36 techniques / 122 steps, specific | 104 (85.2%) | 112 (91.8%) |
| ATT&CK-referenced, any field | 119 (97.5%) | 118 (96.7%) |
| ATLAS-native, 71 techniques / 168 steps, specific | 57 (33.9%) | 56 (33.3%) |
| ATLAS-native, any field | 116 (69.0%) | 86 (51.2%) |
| Without `d3f:File` and `d3f:UserAccount`, specific of 290 | 123 (42.4%) | 130 (44.8%) |
| Without `d3f:File` and `d3f:UserAccount`, any field of 290 | 202 (69.7%) | 169 (58.3%) |

Grader A reproduces R1's `results/attack_split.json` figures. The specific-field gap between ATT&CK-referenced and
ATLAS-native steps survives the second grader (about 85 to 92% against about 33 to 34%). What moves is the
ATLAS-native any-field share: under Grader B, 82 of 168 native steps (48.8%) land on no field, against 52 (31.0%)
under R1, which is the same any-field drop M1 reported for the whole set, concentrated on the native side. The
sensitivity reading (specific share under 50% once the two broad artifacts are set aside) holds under both.

## 2. 48-incident re-weight (27 ATLAS incidents plus 21 researched prior incidents)

**Unit warning.** The 21 prior incidents come from `project1/02-projects/atlas-mitigations/research-returns/atlas-candidate-mappings.csv`,
filtered exactly as `ai-flows-2026-11-09/analysis/critical_controls.py` l.53-67 filters them (Incident; confidence
high or medium; not superseded by CS0068 to CS0075; not "alternate framing"; retired IDs remapped; technique present
in v2026.10). That leaves 130 rows over 21 incidents (dropped: 51 not Incident, 45 superseded, 4 low confidence),
with no duplicate incident-technique pairs and a tactic on every row (111 on defender ground). These rows are
researcher-mapped technique uses, not ATLAS-published procedure steps, and they average about 6 per incident
against ATLAS's 10.7, so the 48-incident "steps" (290 + 130 = 420) mix two units. Read the 48 figure as a
robustness check on the 27, not as a replacement for it.

**New cells.** The 21 incidents add 13 techniques not in R1's 107 (`AML.T0004`, `T0034`, `T0034.000`, `T0053`, `T0066`,
`T0078`, `T0081`, `T0083`, `T0100`, `T0110`, `T0111`, `T0112.000`, `T0112.001`; 120 techniques in all). Three cells
had no grade from either grader: `d3f:InboundInternetWebTraffic` and `d3f:ApplicationConfigurationFile` (absent from
`artifact_ocsf_map.csv`) and `AML.T0110 AI Agent Tool Poisoning` (no crosswalk row). Point grades are single-author
analogies (Tier D): InboundInternetWebTraffic direct via `http_request`, after `d3f:OutboundInternetWebTraffic`;
ApplicationConfigurationFile generic via `file`, after `d3f:ConfigurationFile`; T0110 none, after T0011.002 (no tool
object in OCSF 1.9.0). Under Grader B the point run uses B's modal grade for each analogue row instead. The low bound
sets all three to none; the high bound sets all three to direct with a reachable class.

| Core arm, 420 steps (293 on defender ground) | Grader A point | Grader A low to high | Grader B point | Grader B low to high |
| --- | --- | --- | --- | --- |
| Specific, all steps | 235 (56.0%) | 234 to 239 (55.7% to 56.9%) | 234 (55.7%) | 234 to 239 (55.7% to 56.9%) |
| Any field, all steps | 332 (79.0%) | 331 to 332 | 288 (68.6%) | 283 to 288 (67.4% to 68.6%) |
| Specific, defender ground | 170 (58.0%) | 169 to 174 | 159 (54.3%) | 159 to 164 |
| Any field, defender ground | 233 (79.5%) | 232 to 233 | 204 (69.6%) | 199 to 204 |
| The 21 prior incidents alone, specific of 130 | 74 (56.9%) | | 66 (50.8%) | |
| The 21 prior incidents alone, any field of 130 | 97 (74.6%) | | 84 (64.6%) | |
| ATT&CK-referenced, 37 techniques / 172 steps, specific | 153 (89.0%) | | 156 (90.7%) | |
| ATLAS-native, 83 techniques / 248 steps, specific | 82 (33.1%) | | 78 (31.5%) | |
| ATLAS-native, any field | 164 (66.1%) | | 121 (48.8%) | |

So adding the 21 researched incidents leaves the specific-field share where it was on the 27 (about 56% under
either grader, with the new cells moving it by at most 1.2 points), keeps the ATT&CK-referenced vs ATLAS-native
split, and leaves the any-field share depending on which grader you believe (79% vs 69%).

## Limits

- Post-hoc, single agent, not independently re-run. Every grade it consumes is Tier D; M1's adjudication leg never
  ran, so there is no consensus grade set.
- The 48 figure mixes ATLAS procedure steps with researcher-mapped technique rows; the prior rows' tactic (and so
  defender ground) is the researcher's assignment.
- Grader B never saw the three new cells; the point run substitutes its grade for an analogue row.

## Command

```bash
python3 -I supplement_2026_11_16.py   # results/supplement-2026-11-16.json
```

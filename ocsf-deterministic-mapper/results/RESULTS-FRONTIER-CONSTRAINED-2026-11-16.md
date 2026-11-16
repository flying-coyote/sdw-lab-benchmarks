---
type: evidence
title: "Frontier model behind the schema constraint: post-hoc re-score of the June 2026 frontier predictions (2026-11-16)"
created: 2026-11-16
tags: [ocsf-mapping, deterministic-mapper, schema-constraint, frontier-model, post-hoc, tier-b]
---

# Frontier behind the constraint (post-hoc re-score, 2026-11-16)

**What this is.** A post-hoc re-score, with no new model calls, of the cached June 2026 frontier-proxy
predictions (claude-opus-4-8 via Claude Code subagents, three blind runs, 705 prompts each; method and
declared deviations in `../ocsf-mapping-oracle/_frontier/REPLICATION-2026-06-14.md`) through the same
reject / snap wall `llm_behind_constraint.py` put phi3 behind. No frozen pre-registration covers it.
The headline condition was fixed as `schema` before looking, because that is the condition the phi3 arm
used; all 705 prompts are reported as well. Script: `frontier_behind_constraint_2026_11_16.py`; raw output:
`results/results-frontier-constrained-2026-11-16.json`, `results/frontier-constrained-2026-11-16.stdout.txt`.
Nothing tracked was rewritten.

A current-model leg and a second-provider leg are still open. These are June predictions from one model.

## Full OCSF 1.8.0 validator

`fetch_ocsf_1_8_0_full_2026_11_16.py` pulled the five class definitions and all 178 object definitions
from `https://schema.ocsf.io/1.8.0/api/` on 2026-11-16 (the `/export/schema` endpoint refused with a
legacy-format error, so it fetches per object). The API's default response includes every profile's
attributes, so the full validator is profile-inclusive. A path is valid if it walks attribute by attribute
through the class and its object types (array markers stripped; catch-alls valid, as in the June scorer).
Sanity: every path in the transcribed subset closure walks in the full schema (0 exceptions).
Invented-path audit (2026-11-16): the 35 / 64 / 64 paths the
walker calls invented are 22 / 22 / 26 distinct paths, none under a free-form catch-all and none touching an
extension object; each was spot-checked against the fetched JSON (e.g. `network_endpoint` has `owner`
but no `user`, `network_activity` has no `http_request`, `url` has no `text`, `evidences` has no
`observables`, `detection_finding` has no top-level `process`), so they are real non-paths.
The alias mapper re-run with the full-1.8.0 closure as its valid set is unchanged (0.163 / 0.667), so the
alias-versus-frontier comparison is not an artifact of the two validators.

## Two scorer findings that change the June numbers

1. **24 of the 141 gold paths are not in the transcribed-subset closure** the June scorer validated
   against (the `evidences.*` process paths on CrowdStrike, `src_endpoint.autonomous_system.*` on Okta,
   `*.hw_info.*` and `src_endpoint.owner.groups.name` on PAN-OS, and three on Zscaler). A prediction that
   matched the gold exactly on one of those fields was counted as a silent error and as correct at the same
   time: 28, 81 and 85 such predictions across the three frontier runs' 705 prompts. The alias mapper,
   which can only emit subset paths, could never get those 24 fields right.
2. **Two gold paths do not exist in OCSF 1.8.0**: `src_endpoint.hw_info.model` and
   `dst_endpoint.hw_info.model` (PAN-OS `src_model`, `dst_model`); `device_hw_info` has no `model`
   attribute in 1.8.0. A gold-key error, recorded here, not fixed in the tracked key.

The raw frontier bands reproduce exactly under the June subset scorer (all 705 prompts: path-correct
57.6 / 67.2 / 68.5%, silent-error 17.0 / 26.7 / 26.1%).

## Invented versus real-but-off-subset

Silent errors under the June scorer, split by whether the path exists in full OCSF 1.8.0 (share of prompts):

| Frontier run | Prompts | Subset "silent" | Invented (not in full 1.8.0) | Real 1.8.0, outside subset |
|---|--:|--:|--:|--:|
| run 1 | all 705 | 0.170 | 0.050 | 0.121 |
| run 2 | all 705 | 0.267 | 0.091 | 0.176 |
| run 3 | all 705 | 0.261 | 0.091 | 0.170 |
| run 1 | schema 141 | 0.128 | 0.007 | 0.121 |
| run 2 | schema 141 | 0.284 | 0.099 | 0.184 |
| run 3 | schema 141 | 0.199 | 0.057 | 0.142 |

So the frontier proxy truly invented a path on roughly 5 to 9% of all prompts, and the rest of the June
"silent" figure was real 1.8.0 paths the subset did not carry. The local models barely move under the full
validator: phi3 (schema, cached run) 0.688 → 0.681; gemma4:26b, re-scored from its 705 cached predictions,
is unchanged at every condition (none 0.83, schema 0.18, formal 0.19, skill 0.30, wrong_grounding 0.18).

## The wall

Path-correct / coverage / silent-error, schema condition (141 prompts per run):

| Arm | run 1 | run 2 | run 3 |
|---|---|---|---|
| Raw | 0.574 / 0.87 / 0.007 | 0.660 / 1.00 / 0.099 | 0.894 / 1.00 / 0.057 |
| Reject, full-1.8.0 wall | 0.574 / 0.86 / 0 | 0.645 / 0.90 / 0 | 0.879 / 0.94 / 0 |
| Snap, full-1.8.0 wall | 0.574 / 0.87 / 0 | 0.652 / 1.00 / 0 | 0.901 / 1.00 / 0 |
| Reject, subset wall (the June closure) | 0.518 / 0.74 / 0 | 0.553 / 0.72 / 0 | 0.752 / 0.80 / 0 |
| Snap, subset wall | 0.539 / 0.87 / 0 | 0.574 / 1.00 / 0 | 0.759 / 1.00 / 0 |

All 705 prompts, full-1.8.0 wall: reject 0.572 / 0.658 / 0.671 path-correct at coverage 0.85 / 0.91 / 0.91;
snap 0.576 / 0.671 / 0.687 at coverage 0.90 / 1.00 / 1.00; silent-error 0 throughout. The alias mapper, for
comparison: 0.163 path-correct at coverage 0.667, silent 0. Run 3's schema batch (0.894 raw) is an outlier
against run 3's other four conditions (0.610 to 0.674), so the all-705 figures are the steadier read.

Reading:

- Behind a wall built from the full schema, the frontier proxy keeps nearly all its path-correctness
  (a drop of at most 1.5 points) with silent-error at zero. The whole drop is the two gold paths that do
  not exist in 1.8.0: the frontier reproduced `*.hw_info.model` on 3 / 10 / 10 of all 705 prompts
  (0 / 2 / 2 on schema), the full wall rejected them, and those are exactly the 0.4 / 1.4 / 1.4-point
  drops, so the wall caught an error the gold key and the model shared. Reject cannot lower path-correct where the gold is valid, so
  that part is by construction; the measured part is coverage (0.85 to 0.94) and the gap to the alias
  mapper (0.57 to 0.69 against 0.16).
- Behind the June subset wall, reject cost 4 to 14 points of path-correctness, because the incomplete
  closure rejected right answers. The validator is only as good as the schema it was built from.
- Snap rarely lands on the gold: with the full wall it moved 35, 64 and 64 invented paths (all 705) and
  landed 3, 9 and 11 of them on the gold, so most snapped paths become valid-but-wrong mappings, which is
  the failure a validator cannot see.
- phi3 behind the snap wall gets 3 paths right; 2 of those (Cisco Umbrella `query_type`, Zscaler
  `contenttype`) are fields the alias table missed. Full-wall phi3 numbers are unchanged from
  `results-constrained.json` (reject 0.007 / 0.32, snap 0.021 / 0.68).
- The frontier proxy's own valid-but-non-gold share (full validator, all 705 prompts, raw) is 0.275,
  0.250 and 0.238 across the three runs. Those are not adjudicated; some are defensible alternatives
  that exact match penalizes.

## Wrong-but-valid adjudication of the alias mapper (Tier D, single author)

The alias mapper attempted 94 of 141 fields, got 23 exactly right and sent 71 to a valid path other than
the gold. Rubric: **defensible** if a reviewer reading OCSF 1.8.0 would accept the
path as a home for that source field's meaning; **lossy or ambiguous** if it is the right object or role but
drops part of the value or collides with another field; **wrong** if it names a different attribute, entity,
role or direction. Result (`results/alias-wrong-but-valid-adjudicated-2026-11-16.csv`, with a reason per row):

| Class | Fields | Share of 141 |
|---|--:|--:|
| Defensible alternative | 7 | 0.05 |
| Lossy or ambiguous | 4 | 0.03 |
| Wrong | 60 | 0.43 |

Examples of wrong-but-valid: PAN-OS `sport` → `dst_endpoint.port` (direction inverted), CrowdStrike
`event.MACAddress` → `device.ip`, PAN-OS `src_host` → `device.hostname` (the reporting firewall, not the
source host), and 18 CrowdStrike fields sent to `metadata.event_code`. Single-author judgement, Tier D; a
second reader is the next step.

Tier B for the re-score; Tier D for the adjudication.

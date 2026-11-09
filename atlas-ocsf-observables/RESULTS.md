---
type: benchmark-results
title: "R1 ATLAS realized techniques -> D3FEND artifact -> OCSF 1.9.0 field: observable vs fires"
created: 2026-11-09
evidence_tier: "B for the mechanical join and the planted runs; D for the artifact->OCSF grades (one author, not reviewed)"
---

# R1 results: which realized ATLAS techniques leave an OCSF field, and which rules fire

**Pre-registration:** `PREREGISTRATION.md` sha256 `0e93ad5483aa29ecb792a1c7a95a4720bd0552eb173114bc6f153bfba1f75283`,
frozen 2026-11-09T23:06:16Z. Frozen by agent before run; not owner-reviewed. `sha256sum -c` against
`results/PREREG.sha256` passes after the run, so the file was not edited afterwards. The deviations are listed below.

**Environment:** Beelink (Ryzen 7 5800H), WSL2 6.6.87.2, 14 vCPU, chrony offset 0.00005 s. Python 3.12.3,
duckdb 1.5.3, pySigma 2.0.3, pySigma-backend-sqlite 2.1.1, PyYAML 6.0.3, stdlib sqlite3. No timings are reported,
so no rig stamp applies. Zero spend, and no model calls.

**Inputs:** ATLAS v2026.10 YAML `ac41ee9f…e142d`; crosswalk @ `66b7726` (core `9160e460…`, rebaseline `53b4d52c…`,
annex-10 `accceac6…`); OCSF 1.9.0 fetched from `schema.ocsf.io/api/1.9.0` at 2026-11-09T23:02Z (server default
1.9.0; 1.10.0-dev is also listed and was not used). Every hash is recorded again in `results/observables.json`.

## Scope

There are 27 Incident case studies, 290 steps and 107 distinct techniques. The YAML `employs` block and the hub's
`employs_edges.csv` agree, which `join.py` asserts. 182 of the steps are on defender ground, meaning they are not
in Reconnaissance, Resource Development or AI Attack Adaptation. 92 of the 107 techniques have at least one
crosswalk row. The review's 48-incident set (27 ATLAS incidents plus 21 researched ones) is out of scope here, so
these weights are ATLAS-only.

## Headline (core arm: native class fields, no profiles)

| | Techniques | All steps (290) | Defender-ground steps (182) |
|---|---|---|---|
| Some OCSF field (direct/event/generic/proxy) | 91 (85.0%) | 235 (81.0%) | 155 (85.2%) |
| Specific field (direct/event) | 55 (51.4%) | 161 (55.5%) | 112 (61.5%) |
| No field | 16 | 55 | 27 |

When the ai_operation profile is applied (the profile arm), the totals barely move: 236 of 290 steps are
observable and 163 have a specific field. Only T0093 Prompt Infiltration gains a field (through
`message_context.prompt_text`, graded generic), which is the 235 to 236 move. The 161 to 163 move in specific
steps comes from T0008 Acquire Infrastructure (2 steps, none on defender ground) going from generic to direct
once profiles are applied (added at verification, 2026-11-09). T0051.000 stays generic in both arms, because DigitalMessage already reaches
`email` in core, and an email object standing in for a prompt is a generic carrier.

The split that matters most here is supplementary, so it was not pre-registered (`split_attack.py`,
`results/attack_split.json`):

| | Techniques | Steps | Specific | Any field |
|---|---|---|---|---|
| Carries an ATT&CK reference | 36 | 122 | 85.2% | 97.5% |
| ATLAS-native | 71 | 168 | 33.9% | 69.0% |

The steps that are ordinary tradecraft land on OCSF fields that already exist. The AI-native steps mostly land
on generic carriers, and almost a third of them land on nothing at all. Those generic carriers are an API call
with no model or tool semantics, an email object standing in for a prompt, and an application object standing
in for an adversary's tool.

**Sensitivity (not pre-registered).** The crosswalk often lists a broad parent artifact (`d3f:File`,
`d3f:UserAccount`) next to a narrower one, and a "best grade" rule lets that broad parent carry the technique.
With those two dropped, the specific share falls to 123 of 290 steps (42.4%) and any-field falls to 202 (69.7%).
So the 55.5% headline rests partly on two artifacts that OCSF records nearly everywhere and that say little
about the AI part of the attack.

## Realized techniques with no observable via the crosswalk route (core arm)

| ATLAS | Steps | Ground | Why there is no field | OCSF 1.9.0 directly (bypassing D3FEND) |
|---|---|---|---|---|
| T0116 Autonomous Reconnaissance | 9 | 0 | crosswalk honest no-fit (agent planning loop) | `ai_agent` identity only, profile |
| T0025 Exfiltration via Cyber Means | 8 | 8 | no crosswalk record (a tactic pointer to ATT&CK Exfiltration) | `network_traffic.bytes_out`, core |
| T0117 Autonomous Attack-Path Adaptation | 8 | 0 | honest no-fit (control loop) | `ai_agent` identity only, profile |
| T0017.001 Autonomous Exploit Development | 6 | 0 | pending (the rebaseline note recommends may-create Software; no row emitted) | none |
| T0048.000 Financial Harm | 6 | 6 | no record (an impact outcome) | none |
| T0054 LLM Jailbreak | 3 | 3 | class gap (no LLM class in D3FEND; proposal killed) | `message_context.prompt_text`, profile |
| T0016.002 Generative AI | 2 | 0 | class gap (proposal upheld; no row in the current CSVs) | none |
| T0016.003 Exploits | 2 | 0 | honest no-fit (exploit is a role) | none |
| T0031 Erode AI Model Integrity | 2 | 2 | class gap (proposed model artifact) | `ai_model` identity only, profile |
| T0048.002 Societal Harm | 2 | 2 | no record (outcome) | none |
| T0048.003 User Harm | 2 | 2 | no record (outcome) | none |
| T0000.003 Scan Databases | 1 | 0 | honest no-fit | none |
| T0011.001 Malicious Package | 1 | 1 | killed (over-generic; SoftwarePackage not adopted) | `package.purl`, core |
| T0011.002 Poisoned AI Agent Tool | 1 | 1 | class gap | none (no tool object in 1.9.0) |
| T0048 External Harms | 1 | 1 | no record (outcome) | none |
| T0093 Prompt Infiltration via Public-Facing App | 1 | 1 | artifact `d3f:DigitalText` has no core field | `message_context.prompt_text`, profile |

54 of the 55 no-field steps come from the 15 techniques that have no crosswalk row, and only one comes from a
mapped artifact that lacks a field. Read directly against OCSF, 2 of those 15 are observable in core (T0025 and
T0011.001). With the ai_operation profile, 4 more become observable (T0054, T0031, T0116, T0117), but only T0054
has a field that records the act itself rather than which agent or model was involved. The Windows registry
objects and `ai_agent` are named differently, or missing, in the local 1.8.0 clone. `ai_agent` and `delegation`
arrive in 1.9.0.

The full per-row table is `results/technique_artifact_ocsf.csv`, with 194 rows of technique, verb, artifact,
grade, OCSF field, core classes, profile classes and rationale. Where nothing exists, the field column says
"no field".

## Mapped vs fires (8 pre-registered techniques, 3 seeds, T = 0.9)

DuckDB 1.5.3 is the pre-registered engine; SQLite was added after the freeze (deviation 4). The states and
precision below are identical on both engines except the last row (column order corrected at verification).

| ATLAS | Artifact (grade) | Core arm, DuckDB (pre-registered) | Precision min/med/max | FP per seed | SQLite (supplementary) |
|---|---|---|---|---|---|
| T0049 Exploit Public-Facing App | DatabaseQuery (direct) | DETECTED ×3 | 1.0 / 1.0 / 1.0 | 0,0,0 | same |
| T0050 Command and Scripting Interpreter | ShellCommand (direct) | DETECTED ×3 | 1.0 / 1.0 / 1.0 | 0,0,0 | same |
| T0012 Valid Accounts | DefaultUserAccount (generic) | NOISY ×3 | 0.14 / 0.25 / 0.33 | 6,3,2 | same |
| T0024 Exfil via AI Inference API | WebAPIResource (generic) | NOISY ×3 | 0.23 / 0.23 / 0.23 | 2001 each (all benign calls plus the T0051 needle) | same |
| T0025 Exfil via Cyber Means | none via crosswalk; network_traffic | NOISY ×3 | 0.024 / 0.029 / 0.036 | 40,33,27 | same |
| T0055 Unsecured Credentials | CloudInstanceMetadata (proxy) | NOISY ×3 | 0.056 / 0.083 / 0.083 | 11,11,17 | same |
| T0089 Enterprise Environment Discovery | CreateProcess (event) | NOISY ×3 | 0.011 / 0.011 / 0.012 | 89,88,85 | same |
| T0051.000 Direct prompt injection | DigitalMessage (profile only) | MISSED ×3 (no such column) | 0 | n/a | same |
| T0051.000, profile arm | message_context.prompt_text | **MISSED ×3** (case-sensitive `LIKE`) | 0 | n/a | NOISY ×3, precision 0.048, 20 FP each |

In the core arm, 2 of the 8 are DETECTED, 5 are NOISY and 1 is MISSED, and every state holds across all three
seeds. The two that fire cleanly are the ones whose OCSF field carries the attack's own content (the injected SQL
and the decoded-exec command line). Every rule that matches on an artifact *kind* rather than on content is
caught in the background its lookalike produces: a built-in account name, an inference call, a large outbound
transfer, a metadata-service URL, a `tasklist`. So a mapped field is necessary but nowhere near sufficient, and
the mapping table alone would have scored all eight as covered.

**Supplementary, not pre-registered as a state.** A pySigma `event_count` correlation for T0024 (≥300 calls from
one source in 1 h) went DETECTED on all three seeds, catching 600 of 600 burst events with 0 FP. It runs in SQLite
only, because the backend emits SQLite-specific SQL (`julianday`, `json_each`, `rowid`). It also returned 301
alert rows for one burst, one per anchor event, so alert deduplication would be needed downstream.

**An engine finding I did not expect.** In the profile arm, the prompt-injection rule is NOISY in SQLite but
MISSED in DuckDB. The sqlite backend compiles `|contains` to `LIKE '%…%'`, which SQLite matches
case-insensitively (as Sigma's semantics require) and DuckDB matches case-sensitively. So the planted
"Ignore previous instructions…" was missed, while the 20 lower-case benign quotes still matched. The
`ocsf-attack-coverage` pattern runs sqlite-backend SQL in DuckDB, so any of its rules that match mixed-case text
are exposed to the same silent recall loss. Its four rules (for example `-EncodedCommand` on `WS1`) use values whose
case matches the planted data, so the issue would not show up there. I have not checked them against mixed-case
variants.

## Hypotheses

- **H1 (fewer than half of steps specific in core): refuted.** 161 of 290 is 55.5%. It does hold, at 42.4%, if
  the broad File and UserAccount artifacts are set aside, but that sensitivity was not pre-registered.
- **H2 (≥70% of defender-ground steps have some field): holds.** 155 of 182 is 85.2%.
- **H3 (the no-row block is the largest no-field block, and ≥3 are directly observable in OCSF 1.9.0):** the
  first half holds (54 of 55 steps). The second half holds only with the ai_operation profile (6 found). In the
  core arm only 2 are found, which falls short of 3. The pre-registration did not restrict this clause to the
  core arm, so the profile reading is the literal one; three of the six profile finds (T0031, T0116, T0117) only
  identify the model or agent, and counting only fields that record the act gives exactly 3 (T0025, T0011.001,
  T0054). Note added at verification.
- **H4 (≤5 DETECTED, ≥1 NOISY, ≥1 MISSED of 8, core): holds.** The result is 2 / 5 / 1.
- **H5 (prompt rule MISSED in core, fires in profile): refuted on the pre-registered engine.** DuckDB was the
  pre-registered pipeline, and there the profile-arm rule is MISSED on all three seeds because the compiled
  `LIKE` is case-sensitive. On SQLite, which was added after the freeze, it fires (NOISY), so the profile field
  is usable but the pre-registered pipeline loses it (corrected at verification; the original line read "holds on
  SQLite and fails on DuckDB").

## Variance

The join and the rule scoring are deterministic. Three full runs of `run_planted.py` gave an identical
`results/coverage.json` (sha256 `a7b10d1d4250c548babdbe8ba9ef638f82ee4c06f665cb41ef95a35bdeff949a` each time).
Two runs of `join.py` gave identical `observables.json` (`95c56312…931e`) and `technique_artifact_ocsf.csv`
(`207547d9…55a6`). Across the three corpus seeds, every state held. Precision moved only where the
lookalike count moved: T0012 ranged 0.14–0.33 and T0055 ranged 0.056–0.083.

## Deviations from the pre-registration

1. `d3f:ConfigurationFile` was missing from the frozen `artifact_ocsf_map.csv`, and `join.py`'s completeness
   assert stopped the run. I added one row (generic, `file.path`), which changed the map sha from `d565ab33…` to
   `0622cb6c…`. No other row changed.
2. The authentication background puts 10% of all logons on external IPs, independent of the account, so about
   0.3% are built-in accounts logging on from outside. The pre-registered lookalike column named only internal
   built-in logons. This is the source of T0012's false positives.
3. Rules were written after the freeze, as planned, under a rule I set myself at that point: each rule expresses
   the artifact signal plus at most one discriminating filter that the technique's definition names, and no
   allowlist derived from the background. Under that rule, two NOISY results (T0055, T0089) would become
   DETECTED with a parent-process allowlist, which is the real-world fix but would have been tuning to my own
   corpus.
4. SQLite was added as a second engine next to DuckDB, because the backend targets SQLite. The correlation
   variant and `split_attack.py` (the ATT&CK split and the File/UserAccount sensitivity) are supplementary and
   were not pre-registered. The correlation SQL needed `timestamp` renamed to `time`.
5. (Added at verification.) The T0024 needle is a 600-call burst from one source, not the single planted event
   per technique the pre-registration describes. It exists to feed the correlation rule, and it is why the
   single-event T0024 rule shows precision 0.23 (600 of 2,601 matches) rather than roughly 0.0005.
6. (Added at verification.) `ocsf_reach.py` ran and wrote `results/ocsf_reach.json` at 23:02:48Z, before the
   23:06:16Z freeze. The pre-registration lists the schema fetch but not this run. It computes object-to-class
   reachability, not a coverage figure, and it reproduces byte for byte, but the map grades were written with
   that output available.
7. (Added at verification.) Stop rule (b) says to re-freeze after fixing the map. The pre-registration hash was
   left at the original, which keeps the before-run record intact; the map change is recorded in deviation 1.
   The original map (`d565ab33…`) was not kept, so "no other row changed" cannot be checked independently.

## Commands

```
python3 -m venv .venv && .venv/bin/pip install duckdb==1.5.3 pysigma pysigma-backend-sqlite pyyaml   # pinned in requirements.txt
# OCSF 1.9.0: GET schema.ocsf.io/api/1.9.0/{objects,classes}/<name> with and without ?profiles= (win/ prefix for Windows items) -> sources/
.venv/bin/python -I ocsf_reach.py          # results/ocsf_reach.json
.venv/bin/python -I join.py                # results/observables.json, results/technique_artifact_ocsf.csv
.venv/bin/python -I split_attack.py        # results/attack_split.json (supplementary)
.venv/bin/python -I run_planted.py         # corpus/<seed>/, results/coverage.json  (x3 for determinism)
```

## Limits

- The artifact→OCSF grades are my judgment, one pass with the ontology-thinking checklist, and nobody else has
  reviewed them. The reachability is mechanical, but "direct" vs "generic" is not. Treat the specific share as
  tier D until someone else grades the 80 rows.
- "Has a field" means the schema can hold the fact. It says nothing about whether any product emits it. The core
  arm also counts deep paths such as `actor.process.environment_variables`, which few sources populate.
- The crosswalk is one dataset, mostly unmerged upstream. A different artifact choice per technique moves the
  grade, and the best-grade rule rewards rows that list a broad parent.
- The planted bench is synthetic, I wrote both the rules and the background, and there is one needle per
  technique. The precision figures show the mechanism, mapped-but-noisy; they are not field false-positive rates.
- ATLAS-only weights. The review's 48-incident set would change the step counts, and the counts here should not
  be quoted as the 48-incident figure.

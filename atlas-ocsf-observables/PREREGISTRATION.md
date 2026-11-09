---
type: benchmark-preregistration
title: "R1 ATLAS realized techniques -> D3FEND artifact -> OCSF field: observable vs fires"
created: 2026-11-09
status: frozen-by-agent-before-run (not owner-reviewed)
review_ref: project1/02-projects/securitydataworks/SITE-REVIEW-2026-11-09.md section 5, row R1
---

# Pre-registration: R1 atlas-ocsf-observables

Written before any join result or rule firing was computed. Orientation done before writing it
(listed so a reader can see what I knew): counted the ATLAS v2026.10 Incident steps (290 steps,
27 Incidents, 107 techniques), counted which techniques have a crosswalk row (15 do not, 54 steps),
listed the 79 distinct D3FEND artifacts those rows name, and fetched the OCSF 1.9.0 schema. I did not
compute any OCSF coverage figure or run any Sigma rule before freezing this file.

## Question

For every ATLAS v2026.10 technique used in an Incident case study, does any OCSF 1.9.0 field record the
D3FEND artifact the technique acts on (per the ATLAS->D3FEND crosswalk), and, for a small named subset,
does a Sigma rule over that field actually fire on a planted event at a usable precision?

## Scope and denominators

- **Incident set:** the 27 `type: Incident` case studies in `ATLAS-2026.10.yaml`
  (sha256 `ac41ee9f…e142d`). The review's "48-incident" set adds 21 researched incidents from the hub's
  Wall corpus; those are out of scope here and would change the step weights.
- **Steps:** one `employs` relationship = one step. The 290 count is re-derived from the YAML
  `relationships[*].employs` block and asserted equal to the hub's `employs_edges.csv`
  (sha256 `cc47feca…d8d6`) filtered to Incidents before use.
- **Defender-ground steps:** steps whose tactic is not Reconnaissance (TA0002), Resource Development
  (TA0003) or AI Attack Adaptation (TA0001), since those happen on adversary or third-party
  infrastructure where no victim log exists. Reported alongside the all-steps figure.

## Instrument

1. **Technique -> D3FEND artifact** (`~/atlas-d3fend-crosswalk` @ `66b7726`):
   `crosswalk-rebaseline-2026-11.csv` rows with verdict keep/revise (retire dropped; rows with
   `removed_in_latest=True` move to their `successor` ID, the "(inferred)" suffix stripped and the row
   flagged); plus `crosswalk.csv` rows for the merged T0021 and T0037 (absent from the queue because
   merged); plus `crosswalk-annex-v2026.10.csv` rows with verdict keep/revise (kill dropped).
   Hashes: core `9160e460…13a2`, rebaseline `53b4d52c…819a`, annex-10 `accceac6…175e`.
2. **Artifact -> OCSF** (`artifact_ocsf_map.csv`, sha256 `d565ab33…2947`, authored by me before the
   run, using the ontology-thinking checklist). Grades:
   - `direct`: an OCSF object or dedicated field denotes the same kind as the artifact.
   - `event`: the artifact is an occurrent (a D3FEND system-call class); OCSF records it as a class
     plus `activity_id`, not an object.
   - `generic`: OCSF has the parent kind only; what makes it this artifact is not a field.
   - `proxy`: no object for the artifact; only a carrier field could hold a reference (path, URL).
   - `none`: nothing.
3. **OCSF 1.9.0 reachability** (`ocsf_reach.py`, mechanical, not by eye): class and object definitions
   fetched from `schema.ocsf.io/api/1.9.0` on 2026-11-09T23:02Z (server default = 1.9.0, a tagged
   release; 11 Windows items from the `win/` extension namespace). Two arms:
   - **core**: fetched with `?profiles=` (no profiles), paths through generic wrappers (enrichments,
     observables, metadata, unmapped, osint, evidences, malware, finding/vulnerability wrappers)
     excluded, depth <= 4.
   - **profile**: all profiles applied (server default), wrappers allowed.
   An artifact counts as having a field in an arm only if its OCSF object (or named class) is reachable
   from at least one event class in that arm. An object that exists but no class carries is `no field`.
   Every `ocsf_field` in the map is validated against the fetched object/class attributes; an invented
   path fails the run.
4. **No-crosswalk-row techniques** (`technique_direct_ocsf.csv`, sha256 `d914f59b…9c74`): each of the
   15 carries the crosswalk's reason (honest no-fit, class gap, killed/pending, no record), and a
   secondary judgment of whether an OCSF 1.9.0 object observes the technique directly, bypassing
   D3FEND. This is a separate arm and never merged into the crosswalk-route count.

## Metrics

- Per technique: best grade over its artifacts, per arm. Observable = grade in {direct, event,
  generic, proxy} with a reachable class; specific = {direct, event} with a reachable class.
- Counts of techniques and of steps (incident-step-weighted) at each grade, all steps and
  defender-ground steps, core and profile arms.
- The list of realized techniques with no observable via the crosswalk route, with reason.
- The 1.8.0 -> 1.9.0 delta for the objects used (from the local 1.8.0 clone at
  `~/d3fend-atlas-worktree/data/ocsf-schema`).

## Hypotheses and what would prove each wrong

- **H1.** Fewer than half of the 290 steps reach a *specific* (direct/event) native field in the core
  arm. Wrong if >= 50% do.
- **H2.** Counting generic and proxy, at least 70% of defender-ground steps have some core field.
  Wrong if < 70%.
- **H3.** The no-crosswalk-row techniques are the largest single block of steps with no observable, and
  the direct-OCSF arm finds at least 3 of them observable through OCSF 1.9.0 objects (so the crosswalk
  route undercounts what OCSF can see). Wrong if another block is larger or fewer than 3 are found.
- **H4 (mapped vs fires).** Of the 8 planted techniques below, at most 5 are DETECTED at precision
  T = 0.9 in the core arm, with at least one NOISY and at least one MISSED. Wrong if 6 or more are
  DETECTED or if none is NOISY.
- **H5.** The prompt-injection rule (T0051.000) is MISSED in the core arm (no column to match) and
  fires (DETECTED or NOISY) in the profile arm. Wrong if it misses in the profile arm.

## Planted subset (named before any rule is written)

Selection rule: the highest step-weighted defender-ground techniques with at least one mapped artifact,
one per artifact family, plus T0025 (no crosswalk row, observable directly) and T0051.000 (artifact
observable only in the ai_operation profile), so that every grade is represented.

| ATLAS | Steps | Artifact family (grade) | OCSF table | Benign lookalike pre-committed in background |
|---|---|---|---|---|
| AML.T0012 Valid Accounts | 15 | DefaultUserAccount (generic) | authentication 3002 | internal logons by built-in admin accounts |
| AML.T0055 Unsecured Credentials | 14 | CloudInstanceMetadata (proxy) | process 1007 | cloud agent polling the metadata endpoint |
| AML.T0049 Exploit Public-Facing App | 10 | DatabaseQuery (direct) | datastore 6005 | reporting queries that use UNION |
| AML.T0050 Command and Scripting Interpreter | 6 | ShellCommand/ExecutableScript (direct) | process 1007 | admins running python/powershell scripts |
| AML.T0089 Enterprise Environment Discovery | 4 | CreateProcess/GetRunningProcesses (event/proxy) | process 1007 | admins and monitoring running ps/tasklist |
| AML.T0024 Exfiltration via AI Inference API | 3 | WebAPIResource (generic) | api 6003 | ordinary LLM API completion calls |
| AML.T0025 Exfiltration via Cyber Means | 8 | none via crosswalk; network_traffic directly | network 4001 | nightly backup uploads to an external backup host |
| AML.T0051.000 Direct prompt injection | 4 | DigitalMessage (generic; profile only) | api 6003 + message_context | prompts that quote or discuss injection text |

Corpus: synthetic, generated by `gen_corpus.py` in this directory, 2,000 benign rows per table drawn from
fixed templates that include the lookalikes above at a rate between 1% and 5%, plus one planted needle
per technique. Rules: one Sigma rule per technique, authored by me after this file is frozen, modeled
on public SigmaHQ logic where one exists. States as in `ocsf-attack-coverage`: DETECTED (needle matched,
precision >= 0.9), NOISY (needle matched, precision < 0.9), MISSED (needle not matched, or the rule cannot
execute because the column does not exist). Pipeline: pySigma 2.0.3 + pySigma-backend-sqlite 2.1.1 ->
SQL -> DuckDB 1.5.3 in memory, as in `ocsf-attack-coverage/run.py`. Two corpus arms: core (no
message_context columns) and profile (ai_operation columns present).

## Variance

The join and rule evaluation are deterministic, so "variance" means two things: (a) three identical
runs must produce the same sha256 of `results/coverage.json` (sort_keys); (b) the planted bench is re-run
on three corpus seeds (20261109, 20261110, 20261111), and per-rule precision is reported as min/median/
max across seeds. No timing claims are made, so no rig stamp is needed beyond the environment record.

## Environment

Beelink (Ryzen 7 5800H), WSL2 kernel 6.6.87.2-microsoft-standard-WSL2, 14 vCPU; chrony offset
0.00005 s at freeze; Python 3.12.3; duckdb 1.5.3, pySigma 2.0.3, pySigma-backend-sqlite 2.1.1, PyYAML
6.0.3 (`requirements.txt`). Monotonic timers only if anything is timed.

## Stop rule and cost

Zero spend: local CPU, no model calls, no paid API. Stop and report short if (a) the YAML step count does
not reconcile with `employs_edges.csv`, (b) any `ocsf_field` in the map fails validation against the
fetched 1.9.0 schema (fix the map, record the change as a deviation, re-freeze), or (c) a rule fails to
compile for a reason other than a missing column. Deviations from this file are listed in RESULTS.md.

## Known biases, declared in advance

- The artifact -> OCSF map and the Sigma rules are both mine. The grades are judgment (evidence tier D
  until someone else reviews them); the reachability is mechanical.
- The planted bench's background is synthetic and I chose the lookalikes, from operational experience
  rather than from the rules, but a reader should treat precision figures as illustrative of the
  mechanism, not as field rates.
- The crosswalk is one dataset (Jeremy's, mostly unmerged upstream); a different artifact choice moves
  the grade.

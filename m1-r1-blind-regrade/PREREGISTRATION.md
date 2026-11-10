---
type: benchmark-preregistration
title: "M1 blind re-grade of R1's artifact-to-OCSF grades: second grader, kappa, headline sensitivity"
created: 2026-11-10
status: frozen-by-agent-before-run (not owner-reviewed)
parent_bench: atlas-ocsf-observables (R1)
review_ref: project1/02-projects/securitydataworks/SITE-REVIEW-2026-11-09.md, draft 12 method fix
---

# Pre-registration: M1 r1-blind-regrade

Written before any grading call was made. Orientation done before writing it, listed so a reader can see
what I knew: I read R1's `PREREGISTRATION.md`, `RESULTS.md`, `VERIFICATION.md`, `join.py`, both grade
CSVs (`artifact_ocsf_map.csv`, 79 rows, sha256 `0622cb6c…`; `technique_direct_ocsf.csv`, 15 rows, sha256
`d914f59b…`), the fetched OCSF 1.9.0 schema under R1's `sources/`, and the `ontology-thinking` skill R1
says it used as its checklist. I confirmed that D3FEND 1.4.0 definitions exist locally for 78 of the 79
artifacts (`d3f:GetRunningProcesses` has a label and parent but no definition). I ran one smoke test of
the `agy` headless path with an unrelated prompt (`{"ok": true}`, gemini-3.8-flash-low, 2 s) to confirm the
instrument answers without tools. No artifact or technique row was shown to any model before this freeze.

## Question

Do R1's artifact-to-OCSF grades, which R1 itself labels evidence tier D because one author produced them,
survive an independent blind grader, and how far does R1's headline (161 of 290 incident steps, 55.5%,
reach a specific OCSF 1.9.0 field in the core arm) move when the grades come from the second grader, and
when they come from an adjudicated consensus?

## Design

**Grader A** is R1's frozen grade set, read from the two CSVs above and not changed.

**Grader B** is Gemini 3.8 Flash (`gemini-3.8-flash-high`) called headless through
`~/project1/automation/agy-tracked.sh` (prompt as the last argument; usage logged to the agy ledger). It is
blind: every R1 column that carries judgment (`grade`, `ocsf_object`, `ocsf_class_uid`, `ocsf_field`,
`rationale`, and for the technique file `crosswalk_reason`) is stripped. Each row is presented as the D3FEND
IRI, its `rdfs:label`, `d3f:definition` and parent class from the D3FEND 1.4.0 JSON-LD held at
`~/project1/02-projects/d3fend-wall/cache/d3fend_ontology.json`, or for the 15 technique rows the ATLAS
v2026.10 id, name and description (first 600 characters) from `ATLAS-2026.10.yaml`. The grader receives the
same five-grade rubric R1 pre-registered, word for word:

- `direct`: an OCSF object or dedicated field denotes the same kind as the artifact.
- `event`: the artifact is an occurrent (a D3FEND system-call class); OCSF records it as a class plus
  `activity_id`, not an object.
- `generic`: OCSF has the parent kind only; what makes it this artifact is not a field.
- `proxy`: no object for the artifact; only a carrier field could hold a reference (path, URL).
- `none`: nothing.

plus the four-clause prompt-form from `ontology-thinking/references/prompt-form.md` (map by meaning, actor
vs object, most specific existing path, preserve distinctions), and an OCSF 1.9.0 excerpt built from R1's
fetched `sources/`: all 194 objects (name, first sentence of description, attribute names) and all 87 event
classes (uid, name, category, first sentence, deprecated flag). The excerpt includes profile-only objects
(`message_context`, `ai_agent`, `ai_model`, …) because reachability per arm is computed mechanically
afterwards, as in R1. The grader returns one JSON object per row: `grade`, `ocsf_object` or null,
`ocsf_class_uid` or null, `ocsf_field` or null, `rationale` (at most 40 words). The prompt tells it to use
no tools and to answer from the excerpt only.

**Batching and repeats.** Rows are shuffled with a fixed seed per pass and sent in batches of 10 (artifact
file: 8 batches; technique file: 2 batches). Three independent passes (seeds 1, 2, 3; a new agy conversation
per call) give 30 bulk calls. Grader B's grade for a row is the modal grade over its three passes; a
three-way tie takes the pass-1 grade and the row is marked `tie`. Prompt bytes must stay under 120,000
(Linux single-argument limit is 131,072), asserted before any call.

**Validation of Grader B's targets.** `ocsf_object` must name one of the 194 fetched objects, or
`ocsf_class_uid` one of the 87 classes; otherwise the target is `invented` and the row's grade is scored
`none` for the headline recomputation (the rubric grants a grade only to something that exists in OCSF),
and the invention is counted. An `ocsf_field` attribute that does not exist on a real object is counted as
an invented attribute but leaves the grade standing, because the headline depends on the object's
reachability, not the attribute.

**Reachability.** Same as R1: a grade counts only if the named object (or class) is reachable from at least
one event class in the arm, per R1's frozen `results/ocsf_reach.json` (sha256 `0de548fa…f14d`); otherwise
the row scores `none`. Core arm is the headline arm; the profile arm is reported beside it.

**Adjudicator.** Gemini 4 Argon (`gemini-4-argon-high`) sees every row where Grader A and Grader B
disagree on `grade` (or Grader B tied), up to 30 rows; if there are more than 30, a random sample of 30 with
seed 20261109 is adjudicated and the rest keep Grader A's grade in the consensus and are listed as
un-adjudicated. The adjudicator sees the same definition, rubric and excerpt, and both gradings labelled
Grader 1 and Grader 2 with the assignment randomised per row (seed 20261109), so it cannot tell which is
R1. It may pick either or a third grade. One pass, batches of at most 10. The wrapper refuses Argon below
25% weekly quota (currently 59.8%); if it refuses, consensus is reported as unavailable.

**Consensus** grade = Grader A where A and B agree; adjudicator's grade where adjudicated; Grader A where
disagreed but un-adjudicated. Consensus target (object/field) = the adjudicator's where it ruled, else A's.

## Metrics

- Percent agreement and Cohen's kappa (unweighted, five categories) between Grader A and Grader B modal,
  on the 79 artifact rows and, separately, the 15 technique rows (strata never pooled). Kappa also on the
  two binary collapses the headline uses: specific (`direct`/`event`) vs not, and observable (anything but
  `none`) vs not.
- Same-object agreement: share of rows where B names the same `ocsf_object` (or class uid) as A.
- Grader B stability: pairwise kappa between passes, and flip rate = share of (row, pass) grades that
  differ from the row's modal grade (methodology §10).
- Invention rate: share of row-grades (across all passes) naming a nonexistent object or class, and
  separately a nonexistent attribute.
- Disagreement matrix: 5×5 confusion of A against B modal.
- Headline recomputation (core arm, `recompute.py`, which reuses `join.py`'s crosswalk and step logic):
  specific share of 290 steps, any-field share of 290, specific and any-field shares of the 182
  defender-ground steps, and technique counts, under (1) Grader A, (2) Grader B modal, (3) each Grader B
  pass (reported as a range), (4) consensus. Movement reported in percentage points against 55.5%.
  Gate: under Grader A the recomputation must reproduce 161/290, 235/290, 112/182, 155/182 exactly, or the
  run stops.
- Direct-arm count (how many of the 15 no-crosswalk-row techniques are directly observable in core and in
  profile) under A, B and consensus, since R1's H3 rested on it.

## Hypotheses and what would prove each wrong

- **H1.** Cohen's kappa (five categories, 79 artifact rows) between Grader A and Grader B modal is at
  least 0.40. Wrong if below 0.40.
- **H2.** The core-arm specific share under Grader B modal is within 10 percentage points of 55.5% (between
  45.5% and 65.5%). Wrong if outside that band.
- **H3.** At least half of the A-vs-B disagreements on artifact rows are `direct` against `generic` in
  either direction. Wrong if fewer than half.
- **H4.** The consensus specific share stays at or above 50.0%, so R1's own refutation of "fewer than half
  of steps reach a specific field" survives adjudication. Wrong if consensus falls below 50.0%.
- **H5.** Grader B's flip rate across three passes is at most 15% of (row, pass) grades. Wrong if above 15%.
- **H6.** Grader B names a nonexistent OCSF object or class in at most 5% of row-grades. Wrong if above 5%.

## Variance

Grading is stochastic, so the three passes are the variance instrument: flip rate, pairwise kappa and the
headline range across passes. The adjudicator runs once; its single-pass nature is a declared limit. The
recomputation and kappa are deterministic and are run twice to confirm identical `results/*.json` hashes.

## Environment

Beelink (Ryzen 7 5800H), WSL2 6.6.87.2, 14 vCPU, 47 GB. Other benches run concurrently, so every process
here runs under `nice -n 10 taskset -c 0-3`, and any call duration quoted from the agy ledger is a
contention-era number used only to describe cost, never as a timing claim. Clock: chrony, `System time`
0.59 s slow of NTP at freeze (larger than the §7a check wants; irrelevant here because nothing is timed).
Python 3.12.3 in a local venv, `PyYAML==6.0.3` pinned in `requirements.txt`; everything else stdlib. agy
1.5.x (`agy --version` recorded in RESULTS), models `gemini-3.8-flash-high` and `gemini-4-argon-high`.
Monotonic timers if anything is timed.

## Stop rule and cost

Spend is zero dollars: agy runs on the existing Antigravity plan quota (gemini weekly 88.9%, Argon weekly
59.8% at freeze), no paid API key. Cap: at most 36 Flash calls (30 planned plus 6 retries) and 4 Argon
calls. Stop and report short if (a) a batch returns non-SUCCESS or unparseable JSON after two retries,
(b) the `gemini-5h` bucket drops below 10%, (c) the Grader A gate above does not reproduce R1's counts, or
(d) the recomputation finds an R1 object that `ocsf_reach.json` does not know (which would mean I misread
`join.py`). Deviations from this file are listed in RESULTS.md.

## Known biases, declared in advance

- Grader B is one model, not a domain expert, and agreement between two graders is reported as agreement,
  never as accuracy (methodology §10). A high kappa would mean the grades are reproducible by a second
  reader following the same rubric, not that they are right.
- The rubric and the excerpt are R1's framing; a grader given the same five categories is pushed toward the
  same cuts. Disagreements on the rubric itself are out of scope.
- D3FEND definitions come from the 1.4.0 release held in the hub cache; the crosswalk may have used other
  releases, and `GetRunningProcesses` is presented without a definition.
- The excerpt truncates descriptions to one sentence and omits attribute types and nesting, so a grader
  cannot see that, say, `file.path` is also reachable under `actor.process.file`. Reachability is applied
  mechanically afterwards, so this affects target choice, not the arm filter.
- The adjudicator runs once and is from the same model family as Grader B, so the consensus is a
  within-provider consensus; a cross-provider leg (an Anthropic or OpenAI grader) is not run here.
- Ties and the tie rule (pass-1 grade) bias nothing in a known direction, but they are a judgment call.

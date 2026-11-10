---
type: benchmark-results
bench: M1-r1-blind-regrade
parent_bench: atlas-ocsf-observables (R1)
run_date: 2026-11-09 (EST; first call started about 22:00:55 local, ledger completion timestamps 22:07:01 to 22:38:20 local, 03:07 to 03:38 UTC 2026-11-10) [fixed in verify]
status: partial (Grader B complete; adjudication and consensus unavailable, quota floor refusal)
prereg_sha256: a2eed4adbab81c3980220e3c7e4ec3f9bff304f6a60736116fac4327b6a240cf
---

# Results: M1 blind re-grade of R1's artifact-to-OCSF grades

## Headline

A blind second grader (Gemini 3.8 Flash, three passes) moves R1's core-arm headline from 161 of 290 incident steps
(55.5%) reaching a specific OCSF 1.9.0 field to 168 of 290 (57.9%), a move of +2.4 percentage points, with the three
passes spanning 167 to 173 (57.6% to 59.7%, +2.1 to +4.2 pp) (`results/headline.json` lines 1533, 1554, 1556, 1565,
1576, 1578, 1587, 1589). So the specific-field headline survives a second reader, and it survives on the high side.
The any-field share moves more and in the other direction, from 235 of 290 (81.0%) to 204 of 290 (70.3%), about
-10.7 pp, identical in every pass (`results/headline.json` lines 1531, 1552, 1563, 1574, 1585), because the second
grader puts 13 artifact rows at `none` where R1 had one, mostly rows R1 graded `proxy` or `generic`. That any-field
move was not hypothesised, so it is reported as an observation, not a test.

Five-category agreement on the 79 artifact rows is 62.0% with Cohen's kappa 0.452 (`results/agreement.json` lines 63,
65), which clears the pre-registered 0.40 bar by a small margin. The second grader is very stable against itself
(flip rate 3.2%, pairwise kappa 0.90 to 0.93) and named no nonexistent OCSF object, class or attribute in any of 282
row-grades. The adjudication leg did not run: Gemini 4 Argon's weekly bucket had fallen to 18.7% by the time the
disagreements were ready, below the wrapper's 25% floor, so the consensus grade set and H4 are unavailable, as the
pre-registration says they should be in that case.

## Hypotheses

| ID | Pre-registered test | Result | Source |
| --- | --- | --- | --- |
| H1 | 5-category kappa, A vs B modal, 79 artifact rows, at least 0.40 | Holds: 0.4516 (62.0% agreement, 30.8% expected) | `results/agreement.json` lines 61 to 65 |
| H2 | Core specific share under B modal within 45.5% to 65.5% | Holds: 57.9% (168/290) | `results/headline.json` line 1554 |
| H3 | At least half of artifact disagreements are direct vs generic | Wrong: 12 of 30 (40%) | `results/agreement.json` lines 3 to 7, 109 |
| H4 | Consensus specific share at or above 50.0% | Not tested: adjudicator refused at quota floor | `responses/adjudication/run.log` |
| H5 | Grader B flip rate at most 15% | Holds: 3.19% (9 of 282 row-grades differ from the modal grade; 9 of 94 rows flip, each in one pass) [fixed in verify] | `results/agreement.json` lines 82, 103 |
| H6 | Invented object or class in at most 5% of row-grades | Holds: 0.0% (0 of 282); invented attributes also 0.0% | `results/agreement.json` lines 106, 107 |

On H3, the disagreements split five ways rather than clustering on the direct/generic cut: direct vs generic 12,
generic vs none 6, none vs proxy 6, generic vs proxy 5, event vs proxy 1 (`results/agreement.json` lines 3 to 7). So
more of the disagreements (17 of 30) involve the `proxy` or `none` grades than the specificity cut, and the 12 that
end at `none` on one side are the ones that move the any-field share.

## Other metrics

Artifact rows (n=79), from `results/agreement.json`:

- Specific-vs-not binary: 83.5% agreement, kappa 0.6695 (lines 74 to 78).
- Observable-vs-not binary: 84.8% agreement, kappa 0.1222 (lines 67 to 71). The low kappa reflects that R1 called 78
  of 79 rows observable, so chance agreement is already 82.7%, and every disagreement is B saying `none`.
- Same-target share: 58.2% of rows name the same OCSF object or class uid as R1 (line 73).
- Distributions: R1 direct 35, generic 29, proxy 11, event 3, none 1; Grader B modal direct 31, generic 26, none 13,
  proxy 5, event 4.

Confusion, R1 rows against Grader B modal columns (direct, event, generic, proxy, none), from the `analyze.py` output
written to `results/agreement.json` under `artifact_rows.confusion_A_rows_B_cols`:

| R1 \ B | direct | event | generic | proxy | none |
| --- | --- | --- | --- | --- | --- |
| direct | 27 | 0 | 8 | 0 | 0 |
| event | 0 | 3 | 0 | 0 | 0 |
| generic | 4 | 0 | 16 | 3 | 6 |
| proxy | 0 | 1 | 2 | 2 | 6 |
| none | 0 | 0 | 0 | 0 | 1 |

Technique rows (n=15, never pooled with the artifact stratum): Grader B graded all 15 `none` in every pass, against
R1's 9 none, 3 direct, 3 generic, so agreement is 60% on the five-category and observable collapses and 80% on the specific collapse, and kappa is 0.0 on all three because B's labels are
constant [fixed in verify] (`results/agreement.json` lines 165 to 182). The B rationales mostly argue the technique happens on
adversary infrastructure or outside the system boundary, which is a framing disagreement with R1's direct arm rather
than a schema-reading one. The consequence is that R1's direct-arm list (AML.T0011.001 and AML.T0025 observable in
core; six techniques in profile) goes to empty under Grader B in every pass (`results/headline.json`, `summary.*.
direct_arm_observable_core` and `_profile`, lines 1529 to 1595).

Grader B stability (`results/agreement.json` lines 81 to 103): pairwise kappa 1v2 0.9267, 1v3 0.9112, 2v3 0.8964.

Defender-ground steps (n=182): R1 112 specific (61.5%), 155 any (85.2%); Grader B modal 109 (59.9%) and 136 (74.7%);
passes 109 to 112 specific (`results/headline.json` lines 1530, 1532, 1551, 1553, 1564, 1575, 1586). Techniques
specific: R1 55/107, B modal 58/107, passes 57 to 60. Profile arm under Grader B equals the core arm in every pass
(168, 173, 167): Grader B named two profile-only objects (`metadata`, `whois`) across its row-grades, but neither
changed any technique's best grade; under R1 the profile arm is 163/290 (line 1548).

Thirty of 107 techniques change grade between R1 and Grader B modal in the core arm (listed under
`technique_grade_moves_core.B_modal` in `results/headline.json`): 9 go up from generic to direct, 6 go down from
direct to generic, and 15 go from generic or proxy to none.

## Method as run

1. Pre-registration integrity checked before any call: `sha256sum PREREGISTRATION.md` =
   `a2eed4ad…a6b240cf`, identical to `results/PREREG.sha256`, frozen at `2026-11-10T00:51:49Z` per
   `results/PREREG.frozen_at`. R1 inputs re-hashed: `artifact_ocsf_map.csv` `0622cb6c…`, `technique_direct_ocsf.csv`
   `d914f59b…`, `results/ocsf_reach.json` `0de548fa…f14d`, all matching the pre-registered prefixes.
2. Reused the prior agent's venv (Python 3.12.3, PyYAML 6.0.3), the 30 built prompts in `prompts/pass{1,2,3}` with
   `prompts/manifest.json` (excerpt sha256 `85138738…`, 62,340 bytes; largest prompt 70,777 bytes, under 120,000),
   and the unrun scripts. Nothing had been called before; `responses/pass1/run.log` and `responses/pass1.out` were
   empty and the agy ledger had no `m1-` row, so this was a fresh start of the grading, with the prompt build resumed
   rather than redone.
3. Grader B: 30 calls to `gemini-3.8-flash-high` through `~/project1/automation/agy-tracked.sh` (prompt as the last
   argument, `-p` last inside the wrapper), one new agy conversation per call, under `nice -n 10 taskset -c 0-3`. One
   smoke call (pass 1, artifact batch 1) ran alone first to confirm the model id and parse; it counts toward the 30.
   Then passes 1 and 2 ran concurrently (4 parallel each) and pass 3 after. 30 of 30 succeeded on the first try; no
   retries were used. Every call is in the agy usage ledger under ids `m1-p{1,2,3}-{batch}-t1`.
4. `analyze.py` parsed all 30 responses with no problems (no missing rows, no bad grades, no ties), computed modal
   grades, kappa, stability and inventions.
5. `adjudicate.py build` found 36 disagreements (30 artifact, 6 technique), more than the 30 cap, so it sampled 30
   with seed 20261109 into 3 batches; the 6 left out are AML.T0054, d3f:ArtifactServer, d3f:CloudUserAccount,
   d3f:GetRunningProcesses, d3f:GroupPolicy, d3f:ProcessSegment (`prompts/adjudication/assignment.json`).
6. Adjudication: `run_adj.sh` sent each batch to `agy-tracked.sh` with `gemini-4-argon-high`; the wrapper checked
   the Argon weekly bucket (0.1866), refused each batch below the 0.25 floor before calling agy, and logged
   `SKIPPED`. No Argon model call was made; only the wrapper's `agy -p /usage` quota query ran, and it refused. `adjudicate.py parse` and the consensus grade set were therefore not run,
   and `recompute.py` evaluated A, B modal and each B pass only.
7. `recompute.py` passed the Grader A gate (161/290, 235/290, 112/182, 155/182, 55/107, 91/107 reproduced exactly).
   `analyze.py` and `recompute.py` were each run twice; the sha256 of every file in `results/*.json` and
   `results/*.csv` was identical across the two runs.

Cost: zero dollars, on the Antigravity plan quota. 30 Flash calls of the 36 cap, 0 Argon calls of the 4 cap,
1,889,180 total tokens and 132 call-minutes summed across parallel calls (contention-era figures, cost description
only, not timing claims). Quota at run start: gemini-weekly 0.8526, gemini-5h 0.8732, Argon weekly 0.5728; after the
last Flash call: 0.8064, 0.7114, 0.1866. The `gemini-5h` stop rule (below 0.10) never triggered. agy version 1.5.3.

## Deviations from the pre-registration

- The freeze-era agent built the prompts and scripts and then died before making any grading call; a second agent
  (this run) executed the bench. No hypothesis, metric, threshold or prompt was changed, and the pre-registration
  was not edited (its hash still matches the freeze record).
- `run_pass.sh` was patched before any call, for operations only: a global 36-call cap counted under `flock` across
  all passes (the original allowed up to 90), a `gemini-5h` below 0.10 check before each call (stop rule b), a
  stricter retry trigger (the response must parse as a JSON array containing every manifest row id for the batch,
  where the original only grepped for the string `"row_id"`), a halt marker so a batch that fails after two retries
  stops further calls (stop rule a), and a skip for batches whose response already validates. None of these fired
  except the skip of the smoke-run batch.
- `run_adj.sh` was added because no adjudication runner existed; it enforces the 4-call Argon cap. Its summary line
  prints "argon calls: 3", which counts attempts; all three were refused by the wrapper before reaching agy.
- Adjudication and consensus did not run (quota floor), so H4 and the consensus rows of the headline and direct-arm
  metrics are missing. The Argon bucket was 0.598 at freeze (19:51 local) and 0.5728 at a quota check about thirty
  minutes before the first Flash call (about 22:00 local), and it read 0.1866 by 22:38. The tracked agy ledger has
  no Argon-model row in that window; its `quota_after` trail puts the whole drop between 22:16:52 (0.5728) and
  22:25:30 (0.1866), while only this bench's Flash calls were logged, and the bucket then stayed flat through the
  remaining Flash calls. That points to use the ledger does not see (untracked agy use or another client on the same
  account) or to quota accounting the ledger cannot attribute; its source is unknown. [fixed in verify]
- The pre-registration's own smoke test of agy used `agy` directly and does not appear in the tracked ledger, which
  is consistent with its description.

## Limits

- Agreement is agreement, never accuracy. A kappa of 0.45 says a second reader with the same rubric reproduces R1's
  grades moderately well, not that either is right. With no adjudication, there is no third reading to say which
  grader is closer on the 36 disputed rows.
- H1 clears its bar narrowly (0.452 against 0.40); a handful of different modal grades would put it under. The
  three-pass stability makes it unlikely that Grader B's side moves much, but R1's side is a single reading.
- Grader B is one model and one provider family; with the adjudicator missing there is no within-family check either,
  and no cross-provider leg (Anthropic or OpenAI) was run.
- The technique stratum's kappa of 0.0 is driven by a constant rater, which is a known degenerate case of Cohen's
  kappa; the 60% raw agreement and the framing difference described above are the informative numbers there.
- The excerpt gives one-sentence descriptions and no nesting, so Grader B's tendency toward `none` over `proxy` may
  partly reflect that it could not see carrier fields like `file.path` in their nested positions. Reachability was
  applied mechanically, so this affects grade choice, not the arm filter.
- `d3f:GetRunningProcesses` was presented without a definition and is among the un-adjudicated rows.

## What would change the conclusion

- An adjudicated consensus that sides with Grader B on the generic/proxy-to-none rows would confirm a real drop in
  the any-field headline (81.0% toward 70%), which R1's text leans on less than the specific share but does quote.
  A consensus that sides with R1 there would make the any-field move a Grader B framing artefact.
- A consensus specific share below 50.0% (H4 wrong) would undo R1's refutation of "fewer than half of steps reach a
  specific field"; on these numbers that looks unlikely, since both graders sit at 55.5% to 59.7%, but it is untested.
- A cross-provider grader whose kappa with R1 falls below 0.40, or whose specific share leaves the 45.5% to 65.5%
  band, would weaken the reading that R1's specific-field grades are reproducible.
- Re-running adjudication once the Argon bucket is back above 25% needs only `./run_adj.sh`, then
  `.venv/bin/python -I adjudicate.py parse` and `recompute.py`; the prompts and assignment are already built and
  seeded, so no other step has to repeat.

## Files

- `results/agreement.json`, `results/grader_b.json`, `results/disagreements.csv`, `results/headline.json`
- `responses/pass{1,2,3}/*.md` (raw Grader B answers, sanitised by the wrapper), `responses/pass*/run.log`,
  `responses/calls.count` (30), `responses/adjudication/run.log` (three SKIPPED and three FAILED lines)
- `prompts/adjudication/adj-b{1,2,3}.txt` and `assignment.json`, built and unsent
- No `LEDGER-ROW.md`: the pre-registration does not ask for one. The agy ledger convention it names is the usage
  ledger that `agy-tracked.sh` writes (ids, model, status, tokens, quota snapshot, never prompt text), and all 30
  calls are recorded there.

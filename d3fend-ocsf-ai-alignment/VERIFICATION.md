# R8 verification: D3FEND AI artifacts vs OCSF ai_* objects

Verifier: independent agent, 2026-11-09. Machine: Beelink, WSL2 (6.6.87.2-microsoft-standard-WSL2),
Python 3.12.3, gh 2.83.2. Read-only `gh api` calls only; no git commands, nothing posted.

**Verdict: VERIFIED-WITH-FIXES**

## What was checked

- Pre-registration. The frozen document is `METHOD.md`, not `PREREGISTRATION.md`. That is a naming
  deviation from BENCHMARKING-METHODOLOGY.md, and METHOD.md explains it: R8 compares documents and
  times nothing. Its sha256 is `4b756f629b8332081f4f043c019f9185cee09297900b3d4df347637ccf6ee2e0`,
  which matches the value at the top of RESULTS.md and was unchanged after verification. The file's
  mtime is 22:56:46Z, and the freeze is stamped 22:56:49Z. `build_table.py` (23:00:54Z), the table
  outputs and RESULTS.md (23:00:55Z) all come later. Sources were fetched at 22:52–22:54Z, before
  the freeze, which is correct because the pins had to exist first. File times cannot prove that
  grading started only after the freeze, so that point rests on the agent's own record.
- Analysis matches the pre-registration. METHOD.md fixes the row set (14 D3FEND-side terms after
  merging shared nouns, and 11 OCSF-side terms) along with a four-value rubric and three
  OCSF-version columns. The table has exactly those 25 rows and uses that rubric. I found no
  deviation.
- Reproduction. I ran `python3 -I build_table.py` in a scratch copy, and the CSV and MD came out
  byte-identical to the shipped files. The grade counts are D3FEND→OCSF 0/9/2/3 and OCSF→D3FEND
  0/4/3/4 (exact/partial/wrong-kind/none), with 25 rows in total. The run is deterministic, so
  there is no variance to report.
- Versions, re-checked against live tag trees with `gh api git/trees/<ref>`:
  - `ai_model`, `message_context` and `profiles/ai_operation` are absent in v1.7.0 and present in
    v1.8.0.
  - `ai_agent`, `delegation` and `attestation` first appear in v1.9.0.
  - `ai_capability` and `ai_status` exist only at main `d1cbd619`.
  - API Activity is uid 3 in Application, which gives 6003.
  - `ai_role_id` Retriever is present in v1.9.0 `message_context`.
- #1754. The head is still `08d6f530`, the PR is still a draft, and updatedAt is
  2026-11-09T14:40:38Z. Re-fetching all nine info objects at that head gives attribute counts of 0
  for seven of them, 2 for stop_info and 4 for tool_use_info. So the claim that 7 of 9 are empty
  holds. The tool_use_info attributes are `name`, `ai_tool_input`, `ai_tool_response` and
  `is_pre_occurrence`, and `is_pre_occurrence` is documented as "true indicates that the tool has
  not yet been invoked".
- D3FEND TTL. The sha256 matches `d3b44c77…2d15`. The following classes exist in develop:
  `Agent`, `Database`, `DatabaseRecord`, `AccessToken`, `PermissionGrantingEvent`, `Session`,
  `AuthorizationEvent`, `Metadata`, `DigitalMessage`, `Command`, `ConfigurationResource`,
  `ConfigurationFile`, `DocumentFile`, `DigitalInformation`, `DigitalEvent` and `Software`. The
  seeAlso claims also hold:
  - `Agent` links to `objects/actor`.
  - `Metadata` links to `objects/metadata`.
  - `FileEvent` links to `file_activity`.
  - `ProcessEvent` links to `process_activity`.
  - `AuthorizationEvent` links to `authorize_session`.
  - No class links to an OCSF profile (0 hits for `ocsf.io/profiles`).
  - No ML-model artifact class exists. The `*Model` classes are analytic techniques, and
    `MachineLearningModel`, `AIModel` and `MachineLearningEvent` are all absent.
- #601 diff. It contains four classes with the parents the table claims, and `AIAgentToolCall`
  sits under `Command`.
- MVP image. `sources/img/mvp.png` was transcribed correctly: four classes with parents
  DigitalInformation, DigitalMessage, Command and Metadata.
- OCSF `ai_model` has exactly `ai_provider`, `name`, `version` and `uid`. `attestation`'s
  description says it attests that "an event has not been altered". `delegation` in 1.9.0 has
  `uid`, `parent_uid`, `issuer_uid` and `created_time`, and main adds `scopes`, `audience` and
  `expiration_time`.
- The RESIDUAL.md inconsistency the agent flagged is real. The summary line at line 19 says
  "4×MachineLearningModel", but the table at lines 13–15 lists three techniques.

## Fixes made in place (grades and counts unchanged)

1. **"Proposed or issued" misattributed (RESULTS.md, build_table.py row D5).** RESULTS said that
   the `is_pre_occurrence` flag is the "proposed or issued" distinction the MVP draws and that
   #601's `AIAgentToolCall` does not. That is wrong. #601's definition reads "A command proposed or
   issued by an AI agent…", which uses the same wording as the MVP ("A Command proposed or issued
   by an AI model…"). Each class covers both states, and neither has a property that tells them
   apart. The corrected text says that `is_pre_occurrence` is the discriminator that both D3FEND
   proposals lack. The recommendation to raise this on #1754 still stands, and it now applies to
   #606 as well. I regenerated the table, and the D5 gap text changed while every grade stayed the
   same.
2. **"3 none rows" attributed to training and fine-tuning (RESULTS.md).** Only D12 and D13 are
   training and fine-tuning. The third `none` row on the D3FEND side is agent memory (D8). The
   text now says so.

Pre-fix copies are kept in the verifier's scratchpad and are not part of the deliverable.

## Remaining limits (not errors)

- The grades are expert judgement against definitions with no reasoner run, so they count as
  Tier D-to-B analysis, as the run itself states. A second grader might move some partial or
  wrong-kind boundaries, for example O7 delegation versus AccessToken and O3 the naming row,
  which is a hazard note more than a counterpart pair. No inter-rater check was done.
- The RUN SUMMARY repeats the same "#601 does not have it" error. Anyone quoting it should use
  the corrected RESULTS.md.
- OCSF main, #1754 and #601 are moving targets, so re-pin them before posting. Any post to #606
  or #1754 stays with the owner.

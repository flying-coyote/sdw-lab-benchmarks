# OCSF 1.9.0 re-score verification (ocsf-1.9-rescore)

**Verdict: VERIFIED-WITH-FIXES.** Every number in `RESULTS.md` that I could reach without Docker or the network reproduces. All eight runnable scripts in `scripts/` were re-run from a copy of the bench against the committed schemas and saved inputs (`ocsf_full.py` is the shared resolver they import). Eleven of the fourteen regenerated result files are byte-identical to the committed ones, and the other three differ only in a recorded relative path string. An independent script that imports nothing from the bench reproduces the 1.9.0 deprecation counts, the six-source strict-validation result on 1.8.0 and 1.9.0, and the IAM arm's class, enum and path facts. Two more re-derive, from the emitted JSONL, the Tenzir facts behind H6, H7 and H9, H1's field and activity figures, and H7's field figure. No hypothesis verdict changes. What needs fixing is wording and disclosure. One sentence in the H8b row is literally false. The headline's "falsified on one clause" framing is softer than the frozen falsifiers. Gate G1 was run with the imported June scorer rather than a re-implementation, which is an undisclosed deviation. And the reproduce block and one stdout capture are incomplete. Fixes are proposed below, and `RESULTS.md` is left untouched.

Independent verifier agent, 2026-11-15, about 21:20Z to 21:40Z, after `RESULTS.md` landed (20:25:41Z) and against lab commit `aa918db`. The working tree for `ocsf-1.9-rescore/` and `pipeline-normalization-fidelity/` was clean against that commit when I started, so what I checked is what was committed. Spend was $0 on the bench, using local CPU only. The cross-provider leg used one Gemini call on the agy subscription quota (39,344 tokens, ledger id `ocsf19-verify-gemini`), with no metered spend. I ran no git command that changes state, and this file is the only one written in the lab tree. All re-runs went to a scratch mirror outside the repo, and after the last script ran I checked that no file in `lib/`, `pipeline-normalization-fidelity/`, `ocsf-mapping-fidelity/` or this folder, other than this one, had a newer mtime than the mirror.

## Pre-registration hash and timing

- `sha256(PREREGISTRATION.md)` = `938eb121a7d41986dc01ef1d109c7aa8899aa8f0238d9d1132642a57589a5844`, recomputed now. It equals `results/PREREG.sha256`, the `RESULTS.md` frontmatter and `LEDGER-ROW.md`.
- `sha256(alternates-gold-zeek_conn.json)` = `8eda25148935f143b6a684e21ec5d34c933711aa38133c602d90cd23af2390e5`. It equals the value in the pre-registration's pinned-inputs table and the second line of `results/PREREG.sha256`.
- Every other pinned input hashes to its recorded value:
  - the six schema exports;
  - both ocsf-schema tag tarballs (`052f6ce9…dd221`, `0ed367ea…abfc7`);
  - `mapping.py` (`360f9e73…a265e`) and the Okta inventory (`cf5a7405…c6d`);
  - the zeek corpus, gold and saved Tenzir 6.0.0 output;
  - the library tarball at `9949f753` (`d61a463b…f386c`);
  - the Okta event-type page (`ac8cdce0…d59d96`), which contains `user.lifecycle.create`, `user.lifecycle.activate` and `user.lifecycle.action.failed`.

  Both emitted JSONL files are still on disk (gitignored) and hash to the values in `RESULTS.md`: zeek `5077a09e…c08e08` and sysmon `5e42e0de…cd2a57`. The three hash prefixes in `LEDGER-ROW.md` also match (`six-source-strict.json` `a69df495…d9bae41`, `zeek-alternates-tenzir-6.0.0-671e049.json` `ff225798…177f64a`, `iam-arm.json` `bfe3bd29…13c0`).
- **Timing (mtimes, UTC):**
  - schema exports 19:54:48 to 19:55:03;
  - `erratum_derive.py` 19:58:18, `results/erratum-derivation.json` 19:58:34, and the erratum text in both `pipeline-normalization-fidelity` files 19:59:32;
  - alternates gold 20:01:08, `PREREGISTRATION.md` 20:02:36, and `.frozen` plus `results/PREREG.sha256` 20:02:50 (`.frozen` reads `2026-11-15T20:02:50Z`, consistent);
  - the first scored output, `count_deprecations.py`, 20:03:17 and `deprecations.json` 20:03:23. Every other result file and every scoring script comes later, ending with `iam-enum-compare.json` at 20:25:16.

  So the freeze predates every score. Only the erratum derivation and the schema fetches predate it, and the pre-registration discloses both ("the erratum ... was written first, from a read-only derivation script, and is a mechanism statement, not a score"). The caveat from the T8c pass applies here too. mtimes are the only timestamp evidence, because I read no git history beyond `git show aa918db` for the erratum diff, so this shows ordering on disk and is not tamper-proof.

## Scoring scripts re-run (no Docker, no network)

Every runnable script in `scripts/` was run in a scratch mirror of the lab. That mirror held a copy of this folder, with the two emitted JSONL files and the sibling `ocsf-mapping-fidelity`, `pipeline-normalization-fidelity`, `lib` and `.venv` linked read-only. I used the bench's own interpreter split: lab `.venv` for the two scripts that import `score.py`, and system Python 3.12 with `-I` for the rest. `count_deprecations.py` was given `--tags-dir` over a fresh extraction of the two hash-matched tag tarballs.

| Output | Result |
|---|---|
| `erratum-derivation.json`, `six-source-strict.json`, `proposed-mapping-changes.md`, `zeek-alternates-tenzir-6.0.0-671e049.json`, `zeek-alternates-tenzir-v6.22.0-lib9949f753.json`, `original-scorer-sysmon-tenzir-v6.22.0-lib9949f753.json`, `iam-arm.json`, `iam-enum-compare.json`, `iam/okta_account_change_1.8.0.json`, `iam/okta_user_management_1.9.0.json` | byte-identical |
| `deprecations.json` | byte-identical when run with `--tags-dir`. Without it, the `tag_events_with_class_deprecation` key is absent, which is the script's documented behaviour |
| the three `emitted-paths-*.json` | identical except the recorded `emitted` path string. The committed files say `results/…` and `../pipeline-normalization-fidelity/…`, so the bench ran these from inside `ocsf-1.9-rescore/`, while the Reproduce block runs from lab root and records `ocsf-1.9-rescore/results/…` |
| stdout captures for count_deprecations, both zeek alternates runs, sysmon original scorer, iam_arm, compare_iam_enums | identical |
| `validate_six_source.stdout.txt` | the committed capture lacks the two `valid only with profiles: [...]` lines that line 135 of the committed script prints (one per version). Every other line is identical, and the JSON is identical, so no number is affected |

The gates reproduce inside the identical `zeek-alternates-tenzir-6.0.0-671e049.json`. G1 gives field 0.8, value 0.9166 and activity 0.167, and G2 gives 1.0 on every metric. G1 does not match its frozen wording, though. The pre-registration defines it as "Re-implementing the original gold's scoring on the saved 6.0.0 output must reproduce field 0.80, value 0.9166 and activity 0.167". But `score_zeek_alternates.py` computes G1 by calling the imported June `score.py` (`S.score_source`, line 195), so G1 checks that the June scorer still returns its own June numbers and does not exercise the new scorer. G2 does exercise the new scorer, and my independent field and activity derivations below agree with it, so no number is at risk. But `RESULTS.md` should list this as a deviation (discrepancy 6).

**Tenzir arms: what I could and could not re-run.** I did not run Docker, so I did not re-execute either Tenzir pipeline, and four things rest on the bench's own logs:
- the `--network none` and read-only flags as executed (they are in `tenzir/run_arm.sh` as committed);
- the walk-back itself (`results/tenzir-v6.22.0-walkback.txt` shows 6 plus 10 voided attempts, which matches "16");
- the control run with library `671e049`;
- the claim that `v7.0.0-rc.1` lacks `--package-dirs`.

What I did check:
- **Image digests.** A read-only `docker image inspect` shows the local `tenzir/tenzir:v6.22.0` at `sha256:bf8067a1…9e20` and `v7.0.0-rc.1` at `sha256:4a55363b…fb86a040`, both as pinned.
- **Library claims.** In a fresh extraction of the `9949f753` tarball, no file mentions CloudTrail, and `amazon/operators/` holds only `route53`, `vpc_flow` and `security_lake`. There is no `sysmon` package. `microsoft/` exists with `examples/windows-event-log-nxlog-to-ocsf.tql`, and `im_msvistalog` routing sits in `microsoft/operators/windows/canonicalize.tql`. `zeek/operators/ocsf/logs/conn.tql` carries `S0: 1` with the SYN-only comment at lines 21 and 22, and `README.md` line 6 reads "Packages require Tenzir 7 or later."
- **Emitted outputs.** Both emitted files were re-scored by the bench's scorers (identical, above) and spot-checked by my own script (next section).
- **stderr.** The stderr files hold Tenzir field-missing warnings only (`missed_bytes`, `ParentUser` and similar), with no errors.

## Independent re-implementation

Three short scripts written for this pass. None imports a bench script, and all read only the committed exports, the extracted tag trees, `mapping.py` (as data), the two IAM files, the frozen alternates gold, the zeek corpus and the emitted JSONL. They are `indep_check.py` (sha256 `dee7372937a5aa2775dd29764f2e7f930fe4b9e099c198adfb393e831ce875b1`), `indep_tenzir.py` (sha256 `efd5078e5bbdd0a147c45fee88465fa326dc8b93c9d133380880240e3f90440a`) and `indep_fields.py` (sha256 `e3eab7c27384b9dc9332d62795ae162cd2355893ca64a479d0fa364d858e9afc`), kept in the verifier's scratchpad and not part of the deliverable.

**Deprecation counts (H4).** My script walks every `@deprecated` under `classes` and `objects` attributes, plus class-level ones, with its own loop. 1.9.0 gives 2 classes (`account_change`, `user_access`), with 33 slots / 26 names without profiles and 35 / 28 with profiles. 1.8.0 gives 0 classes and 1 slot / 1 name either way. As context, for any `since`, 1.9.0 has 25 classes and 99 / 116 slots and 1.8.0 has 23 classes and 66 / 81 slots. These match `RESULTS.md` section (c). My own glob over `events/` in the tag trees finds exactly `account_change` and `user_access` with `since` 1.9.0, and 22 class deprecations of any `since`. The export's 25 are those 22 plus `win/prefetch_query`, `win/registry_key_query` and `win/registry_value_query`, which confirms the "22 core plus 3 Windows extension" split. One thing I checked because the bench's count does not walk it: the export's `dictionary_attributes` carries 9 names deprecated since 1.9.0 (`app`, `cpu_cores`, `cpu_speed`, `cpu_type`, `entity_result`, `is_src_dst_assignment_known`, `resources_result`, `user_result`, `web_resources_result`), and `base_event` carries none. The pre-registered definition is (class or object, attribute) slots, so excluding the dictionary is correct. I note it only so nobody reads "26 names" as a dictionary count.

**Six-source strict validation (H2, H3).** My script has its own resolver. It walks each dotted path from the class's attributes through `object_type`, fails on a missing attribute, a non-object intermediate or a missing object, and collects `@deprecated` on every attribute and object segment. It ran on all 251 records with the source classes as named in `mapping.py`'s section headers (Authentication 3002, Detection Finding 2004, Network Activity 4001 twice, DNS Activity 4003, HTTP Activity 4002).
- **1.8.0, profiles applied:** 146 typed, 33 coerced, 72 unmapped. Coverage is 58.17% and lossy is 41.83%.
  - Exactly 2 invalid: PAN-OS `src_model` and `dst_model`, because `model` is not an attribute of `device_hw_info`.
  - Exactly 1 deprecated typed or coerced path: Zscaler `respcode` → `http_status`, since 1.1.0.
- **1.9.0, profiles applied:** the same counts, plus Okta `client.id` → `actor.app_uid` deprecated since 1.9.0 on the `actor` object. Per-source coverage and lossy are identical between versions and equal the `RESULTS.md` table to four places.
- **No-profile sensitivity:** 22 invalid, 133 typed and 52.99% coverage on both versions, which matches "20 paths resolve only through profiles".
- **Tag source:** `objects/device_hw_info.json` has no `model` in either tag. `dictionary.json` carries `http_status` `@deprecated` `since` 1.1.0 in both. `objects/actor.json` carries `app_uid` `@deprecated` `since` 1.9.0 in 1.9.0 only.

**IAM arm (H8a to H8c).** I resolved every non-unmapped path in both IAM files with the same resolver:
- 0 invalid paths in `account_change` 1.8.0 and 0 in `user_management` 1.9.0, with status 31 typed / 5 coerced / 14 unmapped in both;
- class_uid 3001 and 3007;
- the only changed path is `client.id`, `actor.app_uid` → `actor.application.uid`.

I resolved each 1.8.0 path in `user_management` 1.9.0 and found zero invalid, so count (i) is 0 and H8b is falsified as stated. One path, `actor.app_uid`, does resolve as deprecated, and that is why the H8b row needs a wording fix (below).

The activity enums confirm Enable 2 → 4 and that only Create (1) and Disable (5) keep their integer. `account_change`'s enum is identical in the 1.8.0 and 1.9.0 exports. Taking the set difference of attribute names in 1.9.0, `user_management` drops `user_result` and adds `iam_roles`, `privileges`, `resources` and `updated_user`, all as stated. That gives H8a = 1 class_uid + 1 activity_id + 2 type_uid + 1 shared deprecation = 5.

**Tenzir outputs (H6, H7, H9, and H1's tool clauses).** My script joins each emitted record to the corpus on `_id`, with 0 unjoined out of 100,000 in both files.
- **v6.22.0 / `9949f753`:** `metadata.version` is 1.9.0 on 100,000 records, `time` is a JSON string on 100,000, and top-level `duration` is present on 0. `traffic.end_time − traffic.start_time` is within 1 ms of the corpus `duration` on every record.
- **6.0.0 / `671e049`:** 1.8.0 on 100,000, `time` a string on 100,000, and `duration` present on 100,000.
- **Activity by `conn_state`,** the same in both: S0 → 1 (16,697), SF → 2 (16,579), RSTO → 3 (16,629), RSTR → 3 (16,716), REJ → 5 (16,677), OTH → 6 (16,702), with `type_uid` following. So the accept-set figure is 100,000 − 16,697 = 83,303.
- **Sysmon emitted:** class 1007, activity 1 and version 1.9.0 on 100,000 of 100,000.
- **Field landing under the frozen alternates gold.** A third script (`indep_fields.py`, sha256 below) checks, for each of the 15 gold fields, whether the primary path or any accepted alternate is present and non-null, and it skips `service` on `-` records per the `dash_rule`. For 6.0.0 it gives 1,479,834 / 1,479,834 = 100%. For v6.22.0 it gives 1,379,834 / 1,479,834 = 93.24%, and the only missed field is `duration`, on 100,000 records. That is H1's field clause and H7's field clause re-derived.
- **Activity under the frozen rule.** Applying the gold's `activity_rule` accept and primary sets to the counts above: S0's emitted 1 is outside S0's accept set [4, 6], and every other emitted value is inside its state's set and equal to its primary. So accept-set and derived-primary are both 83,303 = 83.30% for both Tenzir versions. The original gold's flat 6 is in every accept set (100%) and equals the primary only for OTH (16,702 = 16.70%).
- **Not independently re-derived:** strict and information-preserving value fidelity (93.24% / 92.75% strict, 100% info-preserving). These rest on the bench scorer's byte-identical re-run plus the fact that `time` is a string on every record.
- **Sysmon landing prose (section d), first record only.** `LogonId` is at `process.session.uid_alt`, `User` `CORP\u570` is split into `process.user.name` `u570` and `process.user.domain` `CORP`, and `actor.user.name` and `session.uid` are absent. `Hashes` is emitted as `process.file.hashes`, a fingerprint array with `algorithm_id` 3 (SHA-256), and `time` is the RFC 3339 string `2026-01-03T14:09:18Z`. That matches the prose for that record. I did not check the other 99,999.
- **Denominators:** the corpus has 20,166 `service = "-"` records, so the denominator is 15 × 100,000 − 20,166 = 1,479,834. From that I re-derived 1,200,000 / 1,479,834 = 81.09%, 1,379,834 / 1,479,834 = 93.24%, and 1,279,834 / 1,379,834 = 92.75%.

## Discrepancies

| # | File | Claimed | Found | Moves a verdict? |
|---|---|---|---|---|
| 1 | `RESULTS.md`, H8b row | "Every 1.8.0 `account_change` path resolves, not deprecated, in `user_management` 1.9.0" | Every path resolves, but `actor.app_uid` (Okta `client.id`) is deprecated in `user_management` 1.9.0. It is deprecated on the `actor` object in every class, so the frozen count (ii) excludes it from count (i) | No. Count (i) is 0 either way |
| 2 | `RESULTS.md` headline and `LEDGER-ROW.md` | H1 and H7 "falsified on one clause each", set apart from H8b "falsified" | The frozen falsifiers are "Falsified if any of these numbers differs" (H1) and "Falsified if either is lower" (H7), so both hypotheses are falsified, full stop. The table rows already show which clause failed, and the frame is accurate as description, but the 8 / 2 / 1 split reads softer than the frozen rules | No. The count of falsified hypotheses is 3 |
| 3 | `results/validate_six_source.stdout.txt` | stdout of the committed script | Lacks the two `valid only with profiles` lines that the committed script prints. The JSON is identical | No |
| 4 | `RESULTS.md` Reproduce block | the command list reproduces the results | Running from lab root changes the `emitted` string in the three `emitted-paths-*.json` files, because the bench ran from inside the folder. Four commands are missing: `score_original.py --source sysmon`, `validate_emitted.py` for the 6.0.0 and sysmon files, `compare_iam_enums.py`, and the sysmon Tenzir run (`SRC=sysmon TQL=map_sysmon_nxlog_probe.tql tenzir/run_arm.sh …`) | No |
| 5 | `RESULTS.md` frontmatter and `LEDGER-ROW.md` | "no independent verification pass" | This pass now exists | No |
| 6 | `RESULTS.md` Gates and Deviations; `scripts/score_zeek_alternates.py` | G1 "passed", the pre-registration's "re-implementing the original gold's scoring" | G1 calls the imported June `score.py` and does not re-implement it, so it confirms the June scorer reproduces itself and does not test the new scorer. It is not listed among the deviations | No. G2 tests the new scorer, and the independent derivations here agree with it |

## Proposed fixes (not applied; `RESULTS.md` was out of scope for edits)

1. H8b row, Result cell: "0. Every 1.8.0 `account_change` path resolves in `user_management` 1.9.0; the only one deprecated there is `actor.app_uid`, deprecated on the `actor` object in every class (count (ii)), so count (i) is 0."
2. Headline and ledger row: "8 held and 3 were falsified (H1, H7, H8b). H1 failed only on its reference-mapper percentage and H7 only on its field clause; every tool clause of H1 and H7's activity clause held." The same wording would suit the commit-message summary in future rows.
3. Re-capture `results/validate_six_source.stdout.txt` from the committed script, or add a one-line note that the capture predates the `valid only with profiles` print.
4. Reproduce block: say to run from inside `ocsf-1.9-rescore/` (or accept the path-string difference), and add the four missing commands listed in discrepancy 4.
5. Confidence consequence, draft 15 line: keep the frozen wording ("a class and enum remap only"), but add "plus the one `actor.app_uid` deprecation that the six sources share", so the IAM line does not read as zero attribute changes. The headline bullet already lists it, but the consequence line does not.
6. Optional, under H5: name the two shipped packages that do map to Authentication 3002 at `9949f753`, `okta` (Okta System Log) and `openssh` (sshd syslog), and say why neither applies. The `auth` corpus is a synthetic generic shape (`auth_protocol` SAML/NTLM, SID `user_id`, `logon_type`) and is neither Okta LogEvent nor sshd text. Without this, a reader who browses the library may think the "auth: none" call missed them.
7. Optional, section (a): "Current Tenzir targets 1.9.0, with one regression" sits awkwardly next to the later sentence that the `duration` move "is a choice about where to put the time span, not a schema violation". "with one field the frozen gold no longer credits" says the same thing without the judgement.
8. Frontmatter and ledger row: replace "no independent verification pass" with a pointer to this file and its verdict.
9. Deviations: add "G1 was run with the imported June scorer, not a re-implementation as the pre-registration says, so it checks that the June scorer reproduces its own numbers. The new scorer is covered by G2 and by the verification's independent re-derivation."

## Erratum on `pipeline-normalization-fidelity/FINDINGS-2026-06-14.md`

`git show aa918db` shows the erratum as a pure append, 18 lines to `FINDINGS-2026-06-14.md` and 15 to `results/RESULTS.md`, with no change to the text above it. The cited lines `gen_corpus.py` l.180-181 read `# Network Activity activity_id: 6 = Traffic (the conn.log grain). type_uid convention pinned.` and `activity_id = 6`, which is exactly the pin the erratum describes. All 100,000 gold rows carry 6 (`erratum-derivation.json`, reproduced byte-identical). Points 1 to 5 trace to that JSON: the cross-tab, the `unmapped` keyset of `_id` only, the three landings at 100,000 / 100,000 each, `time` as a string with max parse-back error 240 ns and 99,963 / 37 at millisecond truncation, and 53 `duration` differences all at +1 ms.

I checked three statements against primary text outside that JSON:
- **Point 3, schema text.** In the 1.8.0 export, `metadata.uid` is described as "distinct from the original event identifier in the source system (see original_event_uid)", `connection_info.tcp_flags` is `integer_t`, and `flag_history`'s description gives "ShAD" as its example. The C1 1.8.0 subset carries no type names (no `*_t` string anywhere), so "the validator could not catch the second one" holds.
- **Point 4, `timestamp_t`.** The export's `timestamp_t` is "the number of milliseconds since the Epoch".
- **Point 5, the duration tie.** The gold value comes from `int(round(raw["duration"] * 1000))` at `gen_corpus.py` l.165. Of the 104 corpus durations whose sixth-decimal value ends in `500`, 103 multiply to an exact .5 in float. Python's half-to-even rounding sends about half of those down. 53 differ from Tenzir and 51 agree, and there are no differences outside the ties. That is consistent with "gold rounds half to even, Tenzir rounds half up". The erratum could add that the other 51 ties agree, but nothing in it is wrong.

The erratum is accurate as written.

## Cross-provider leg (Gemini)

One call through the project's tracked agy wrapper. The model was `gemini-4-hydrogen-high`, and the reply self-identifies as "Gemini 4 Hydrogen (High)". The prompt was bench text only: the pre-registration's arms-and-hypotheses section, plus the `RESULTS.md` headline, gates, verdict table, confidence consequence and deviations, with no sections (a) to (e) detail. Prompt sha256 is `cbc22887…e11cfa` and response sha256 is `1ca0deb9…7aad36`. Its output is treated as data.

Gemini judged ten of eleven verdicts to follow ("yes") and H1 "partly". Summarised close to verbatim:
- **H1:** "the frozen falsifier ('Falsified if any of these numbers differs') makes H1 falsified outright rather than 'Falsified on one clause'". The same point applies to how the headline groups H7 with H1. **I agree.** This is discrepancy 2.
- **H8b:** follows, "even though the table prose inaccurately omits the count-(ii) `actor.app_uid` deprecation". **I agree.** This is discrepancy 1, found independently by my resolver.
- **Reinterpretation after seeing data:** it named the sysmon `_id` re-run and the three NXLog constants, the switch to `docker cp` volumes with the walk-back budget reset twice, the tag cross-check reading, and the single-process IAM phases. All four are disclosed deviations. On one detail it is wrong. It says the author "switched from the frozen 'read-only mounts'", but `run_arm.sh` still mounts the volume `:ro`, so only the population method changed. None of the four decides a verdict: H5 holds on CloudTrail and auth alone, whatever is decided about sysmon.
- **Claims beyond the verdicts:**
  - "regression" for the `duration` move. **Partly agree**, see proposed fix 7.
  - "not an attribute re-map" understating the shared deprecation. **Agree**, see proposed fix 5.
  - The sysmon availability claim "lacks reported evidence in (B)". **I disagree.** That evidence is in `RESULTS.md` section (d), which I did not send, and I confirmed class 1007 on 100,000 of 100,000 from the emitted file. The claim is correctly marked as an owner call that rests on a shaping judgement.

No disagreement is left to resolve against the data.

## Context observed in passing (post-hoc, unscored)

Tenzir's shipped `okta` package at `9949f753` declares `version: "1.9.0"` in `okta/operators/ocsf/map.tql`. Even so, `okta/operators/ocsf/event/account_change.tql` still sets `class_uid = 3001` for `user.lifecycle.*` and maps `user.lifecycle.activate` to activity 2. So a shipping 1.9.0 mapper has not made the `account_change` → `user_management` move this bench costs. That is legal, because the class is deprecated, not removed, but it shows the IAM migration is still pending in the shipped mapper, and it shows the `activity_id` 2 that a naive class swap would turn into Update. I read this from code only and ran nothing. It could inform draft 15, and it changes no verdict here.

## Residual limits

- The six-source mappings, the alternates gold and the IAM procedure were all written by the bench's agents. Reproduction shows the numbers are computed correctly from this design. It does not show that the design is the right one.
- The alternates gold was written with knowledge of Tenzir 6.0.0's output, as the pre-registration says, so H1 is confirmatory by design.
- The pre-registration is agent-frozen and not owner-reviewed.
- I did not re-execute Tenzir.
- The sysmon usability call depends on the three-constant shaping judgement, which `RESULTS.md` correctly leaves to the owner.

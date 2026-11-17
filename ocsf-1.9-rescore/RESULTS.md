---
type: benchmark-results
title: "OCSF 1.9.0 re-score: results"
created: 2026-11-15
status: complete (agent-run, not owner-reviewed; independently verified 2026-11-15, VERIFIED-WITH-FIXES, see VERIFICATION.md)
prereg: PREREGISTRATION.md (sha256 938eb121a7d41986dc01ef1d109c7aa8899aa8f0238d9d1132642a57589a5844, frozen 2026-11-15T20:02:50Z; alternates gold sha256 8eda25148935f143b6a684e21ec5d34c933711aa38133c602d90cd23af2390e5)
---

# OCSF 1.9.0 re-score: results

## Headline

Of the 11 pre-registered hypotheses and sub-hypotheses (H1 to H9, with H8 split into a, b and c), 8 held outright: H2, H3, H4, H5, H6, H8a, H8c and H9, and 3 were falsified (H1, H7, H8b). H1 failed only on its reference-mapper percentage and H7 only on its field clause; every tool clause of H1 and H7's activity clause held.

- **H1 (one clause).** This was an arithmetic slip in the pre-registered prediction.
- **H7 (field clause).** Tenzir's current Zeek mapping stopped emitting a top-level `duration`.
- **H8b.** The Okta identity-lifecycle arm needed no attribute-path change for the class move.

The five headline results:

- **Corrected Tenzir 6.0.0 Zeek numbers.** Under the pre-registered alternates-accepting gold, Tenzir 6.0.0 / library `671e049` on zeek_conn scores field fidelity 100%, strict value fidelity 93.24% (only `ts` fails, on every record, because `time` is an RFC 3339 string rather than epoch-ms), information-preserving value fidelity 100%, and accept-set activity 83.30%. The June figures were 80% field and 17% activity. The one activity disagreement left is S0, which Tenzir maps to Open and the frozen rule maps to Fail or Traffic. The 83.30% rests entirely on rejecting Open for S0. Accepting Open there would make it 100%. That alternative is post-hoc and not scored, and it is noted here so that 83% doesn't travel the way 17% did.
- **Current Tenzir targets 1.9.0, with one regression.** Tenzir's current release, v6.22.0 with library HEAD `9949f753`, emits OCSF 1.9.0 on every record and still derives activity from `conn_state`. Its field fidelity falls to 93.24% because `duration` moved off the top level: it is now carried only as `traffic.start_time`/`traffic.end_time`, which reproduce the source duration within 1 ms on every record (a post-hoc check).
- **Six-source drift is one path.** The C1 corpus on a strict full-schema validator has two latent defects on 1.8.0 (the PAN-OS `*_model` paths are invalid) and one pre-existing deprecated target (Zscaler `respcode` → `http_status`, deprecated since 1.1.0). The move to 1.9.0 adds exactly one deprecated target (Okta `client.id` → `actor.app_uid`), so 1 of 181 typed and coerced paths drifts and no coverage figure moves. Strict 1.8.0 coverage is 146 typed / 58.17%, against the published 148 / 59%.
- **IAM cost is a class-and-enum remap.** On the Okta `user.lifecycle.create`/`activate` arm the 1.9.0 cost is not an attribute cost. These decisions change:
  - `class_uid`, 3001 → 3007;
  - one activity renumber, Enable 2 → 4;
  - two `type_uid` values derived from those;
  - the same `client.id` → `actor.app_uid` deprecation that is the six sources' single drift.

  Zero paths moved because of the class consolidation, and zero fields were lost. The scope is narrow. It covers two event types. It never touches `user_result`, the one `account_change` attribute that `user_management` drops. It does not test `user_access`, the other class deprecated in 1.9.0.
- **Deprecation counts confirmed by a lab script.** Against pinned, hashed exports: 2 classes, 33 slots / 26 names without profiles, and 35 / 28 with profiles.

Spend $0. Local CPU and Docker only, no paid API.

## Gates

- **G1, sanity: passed.** The original frozen scorer, imported from `pipeline-normalization-fidelity/score.py`, reproduces field 0.8, value 0.9166 and activity 0.167 on the saved 6.0.0 output (`results/zeek-alternates-tenzir-6.0.0-671e049.json`, key `G1`).
- **G2, self-check: passed.** A reference event built from the new gold's primary paths and derived-primary activity scores 1.0 on field, both value metrics, both activity metrics, both `type_uid` metrics and class (same file, key `G2`).

## Hypotheses, scored against the frozen text

| H | What it predicted | Result | Verdict |
|---|---|---|---|
| H1 | Tenzir 6.0.0 under alternates gold: field 100%, strict value fails on `ts` only, info-preserving 100%, accept-set and derived-primary activity 83.30%; original gold as mapper lands 12 of 15 fields (80%), accept-set 100%, derived-primary 16.70% | Tool: field 1,479,834 / 1,479,834 = 100%; strict value 1,379,834 / 1,479,834 = 93.24%, with `ts` failing 100,000 of 100,000 and no other field failing; info-preserving 100%; accept-set 83,303 = 83.30%; derived-primary 83,303 = 83.30%. Original gold as mapper: 12 of 15 fields on every record (1,200,000 landed), but **81.09%**, not 80%, because the frozen `dash_rule` drops the 20,166 `service = "-"` records from the denominator; accept-set 100%; derived-primary 16,702 = 16.70% | **Falsified on one clause** (the 80% figure; an arithmetic slip in the prediction). Every clause about the tool held |
| H2 | 1.8.0 strict: exactly 2 invalid (PAN-OS `src_model`, `dst_model`), exactly 1 deprecated (Zscaler `respcode` → `http_status` since 1.1.0); 148 → 146 typed, 59% → 58% coverage, 41% → 42% lossy | Exactly those three. 146 typed, 33 coerced, 72 unmapped; coverage 58.17%, lossy 41.83% | **Held** |
| H3 | ≤ 2 of 181 typed and coerced paths drift to 1.9.0 (expected exactly Okta `client.id`); coverage moves ≤ 1 point per source and in total | 1 of 181 (Okta `client.id` → `actor.app_uid`, deprecated since 1.9.0, "Use `application.uid`"). Coverage and lossy identical per source and in total | **Held** |
| H4 | 1.9.0: 2 classes, 33/26 without profiles, 35/28 with profiles; tag cross-check finds the same 2 | 2 classes (`account_change`, `user_access`), 33 slots / 26 names without profiles, 35 / 28 with. In the 1.9.0 tag's `events/` tree, exactly those two classes carry `@deprecated` with `since` 1.9.0 | **Held** |
| H5 | Current Tenzir has no usable mapping for ≥ 2 of cloudtrail, sysmon-JSON, auth | CloudTrail: no package or operator in the library at `9949f753` names CloudTrail. Generic auth: none. Sysmon: usable under a disclosed shaping judgement (below). 2 of 3 unusable | **Held** |
| H6 | Current Zeek mapping declares `metadata.version` 1.9.0 on every record | 1.9.0 on 100,000 of 100,000 | **Held** (partly blind, given the commit titles) |
| H7 | Current Zeek mapping: field ≥ 99% and accept-set activity ≥ 80% under the alternates gold | Field 1,379,834 / 1,479,834 = **93.24%** (`duration` absent on every record); accept-set activity 83.30% | **Falsified** on the field clause; the activity clause held |
| H8a | IAM decisions changed ≥ 3 × six-source drift (≥ 3) | 5 changed (class_uid 1, activity_id 1, type_uid 2, shared deprecation 1) against a six-source drift of 1 | **Held**, and near-guaranteed by construction, as the pre-registration said (see the 2026-11-17 note under Corrections) |
| H8b | ≥ 1 Okta attribute path changes because of the class move | 0. Every 1.8.0 `account_change` path resolves in `user_management` 1.9.0; the only one deprecated there is `actor.app_uid`, deprecated on the `actor` object in every class (count (ii)), so count (i) is 0 | **Falsified** |
| H8c | No field lost in the move | None lost: 31 typed / 5 coerced / 14 unmapped before and after | **Held** |
| H9 | Current mapping still writes `time` as a string | String on 100,000 of 100,000; strict value fails on `ts` for all of them | **Held** |

Confidence consequence, per the pre-registration:
- **Draft 12.** H1 lets it state corrected Tenzir 6.0.0 numbers under a pre-registered gold.
- **Draft 15.** H3 held and H8b was falsified, so draft 15 should say that on this source (Okta lifecycle create and activate) the 1.9.0 IAM cost is a class and activity-enum remap plus the one `actor.app_uid` deprecation that the six sources share, not an attribute re-map. Other identity sources, `user_access` mappings and anything that wrote `user_result` are untested.
- **Not triggered by any frozen consequence, but an owner call for draft 12.** H5 held, yet JSON-shaped Sysmon now maps through the shipped `microsoft` package on the current release once three NXLog metadata constants are added (section d). If that shaping is accepted, draft 12's availability table (Tenzir 1 of 4) and its JSON-versus-EVTX "input-shape trap" paragraph are stale for the current version. They still describe 6.0.0 / `671e049` correctly.
- **Hub hypotheses.** None moves on this bench. That goes through the evidence gate and the owner.

## (a) Zeek alternates re-score

Rows are from `results/zeek-alternates-*.json` (key `alternates`, and key `original_scorer` for the June scorer's view of the same file). Denominators: field 1,479,834 = 15 fields × 100,000 records − 20,166 `service = "-"` records; activity 100,000.

| Arm | Field | Value strict | Value info-preserving | Activity accept-set | Activity derived-primary | Original scorer (field / value / activity) |
|---|--:|--:|--:|--:|--:|---|
| Tenzir 6.0.0 / `671e049` (saved June output, sha256 `561ce680…661929c`) | 100% | 93.24% | 100% | 83.30% | 83.30% | 80% / 91.66% / 16.7% |
| Tenzir v6.22.0 / `9949f753` (sha256 `5077a09e…c08e08`) | 93.24% | 92.75% (1,279,834 / 1,379,834) | 100% | 83.30% | 83.30% | 73.33% / 90.91% / 16.7% |
| Original gold's own paths as a mapper (reference) | 81.09% | n/a | n/a | 100% | 16.70% | 100% / 100% / 100% by construction |

Per `conn_state`, both Tenzir versions emit the same activity values: S0 → 1 (16,697, not accepted), SF → 2 (16,579), RSTO → 3 (16,629), RSTR → 3 (16,716), REJ → 5 (16,677), OTH → 6 (16,702), all accepted (`activity_by_conn_state`). The current library's own comment in `zeek/operators/ocsf/logs/conn.tql` maps "S0: 1" with the note that S0 means only a SYN was seen. So the S0 disagreement is a documented choice on Tenzir's side, and Open versus Fail for a SYN with no reply is the one place where the frozen rule and Tenzir read the OCSF enum text differently.

What changed between the two Tenzir versions on this corpus: `metadata.version` moved from 1.8.0 to 1.9.0, and top-level `duration` and `start_time`/`end_time` were removed, with the times now under `traffic.start_time` and `traffic.end_time`. Everything else the scorer checks is unchanged. Every emitted leaf path in both outputs is valid and not deprecated in its declared version's export (`results/emitted-paths-*.json`: 37 paths each, 0 invalid, 0 deprecated). So the current mapping's `duration` change is a choice about where to put the time span, not a schema violation. The frozen gold accepts only top-level `duration`, and under that rule it is a field miss.

## (b) Six-source mapping corpus, strict validator

From `results/six-source-strict.json`, profiles-applied export:

| Source | Published coverage | 1.8.0 strict coverage / lossy | 1.9.0 strict coverage / lossy | Findings |
|---|--:|--:|--:|---|
| Okta | 58.00% | 58.00% / 42.00% | 58.00% / 42.00% | 1.9.0: `client.id` → `actor.app_uid` deprecated since 1.9.0 |
| CrowdStrike | 69.77% | 69.77% / 30.23% | 69.77% / 30.23% | none |
| Palo Alto | 55.42% | 53.01% / 46.99% | 53.01% / 46.99% | `src_model`, `dst_model` → `*_endpoint.hw_info.model` invalid in both (`device_hw_info` has no `model`) |
| Cisco ASA | 61.54% | 61.54% / 38.46% | 61.54% / 38.46% | none |
| Cisco Umbrella | 46.15% | 46.15% / 53.85% | 46.15% / 53.85% | none |
| Zscaler | 58.33% | 58.33% / 41.67% | 58.33% / 41.67% | `respcode` → `http_status` deprecated since 1.1.0 in both |
| Total (251) | 148 typed, 58.96% | 146 typed, 58.17% / 41.83% | 146 typed, 58.17% / 41.83% | |

- **Changes needed.** Reaching zero invalid and zero deprecated targets needs 3 `mapping.py` records changed on 1.8.0 and 4 on 1.9.0. They are listed, with the replacement named by the schema, in `results/proposed-mapping-changes.md`. Nothing is applied.
- **Detection affected.** One named detection depends on a record that has to change: Zscaler "HTTP error-rate / response monitoring", through `respcode`.
- **Profiles matter.** With the no-profile export, 22 paths fail instead of 2, because 20 paths (`device.*`, `action_id`, `firewall_rule.*`, `attacks.*`, `disposition*`, `malware.name`, `risk_score`, `policy.name`) resolve only through profiles (`valid_only_with_profiles`). A validator that ignores profiles would report 20 false defects on this corpus.
- **Catch-alls.** `unmapped` and `raw_data` exist on every class used.

## (c) Deprecation counts

From `results/deprecations.json`, by `scripts/count_deprecations.py`:

- **1.9.0, `since` 1.9.0:** 2 classes; 33 attribute slots / 26 names without profiles; 35 / 28 with profiles.
- **1.8.0, `since` 1.8.0:** 0 classes; 1 slot / 1 name with or without profiles.
- **Any `since`, as context.** 1.9.0 carries 25 deprecated classes, 22 in core `events/` and 3 from the Windows extension, and 99 deprecated attribute slots without profiles, or 116 with. 1.8.0 carries 23 classes and 66 or 81 slots.
- **Tag cross-check.** At tag 1.9.0, the `events/` classes with class-level `@deprecated` and `since` 1.9.0 are exactly `account_change` and `user_access`. All 22 core-event class deprecations, of any `since`, match the export's set; the 3 `win/` classes come from `extensions/`, which the cross-check does not walk.

## (d) Tenzir on its current release

**Versions.**
- **Image.** `tenzir/tenzir:v6.22.0`, pulled and verified at `sha256:bf8067a122f4b7144fbdb6d2f73fecf9cd98b2d4e35e9e47c67a23ce9b789e20`.
- **Library.** `tenzir/library` at HEAD `9949f753aa44614a914b83eb81d8276bdcb91886` (2026-11-15), codeload tarball sha256 `d61a463bb70458c965fc90cb7d6dd596a57c5e54873e99d28b5c90782dff386c`.
- **Load result.** HEAD loaded on the first valid attempt, even though the library README at that SHA says "Packages require Tenzir 7 or later" (`results/tenzir-v6.22.0-walkback.txt`).

**Zeek invocation.** Entry point `zeek::ocsf::normalize`, as in the package's `examples/map.tql`. The input shaping is the June recipe: `read_json` plus `unflatten(".")`, `_path = "conn"`, and lift `_id` (`tenzir/map_zeek_conn.tql`). The run used `--network none`, read-only mounts, and the corpus from `pipeline-normalization-fidelity/_work` (sha256 matches the manifest). It took 22 s wall time. Results are in section (a).

**Availability of the other sources at `9949f753`:**
- **cloudtrail.** No package names CloudTrail; the `amazon` package ships `route53`, `vpc_flow` and `security_lake`. Not usable, same as June.
- **auth.** No mapping for a generic auth shape exists by design. Not usable.
- **sysmon.** June's `sysmon::ocsf::map` package is gone. The `microsoft` package's `microsoft::windows::ocsf::normalize` adapts Windows events from NXLog, Winlogbeat, Fluent Bit or XML. The corpus is flat, pre-parsed Sysmon EID 1 JSON, which is NXLog's flat shape minus NXLog's own metadata. The run added three collector-metadata constants a real NXLog record carries (`SourceModuleType = "im_msvistalog"`, which routes to the NXLog adapter; `SourceName`; `Channel`). That is analogous to June's `_path = "conn"`, but it is three constants, not one, so it is a judgement the owner may not accept. Under it the shipped mapping emits Process Activity 1007 on 100,000 of 100,000 records with `metadata.version` 1.9.0, so it passes the frozen usability rule (gold `class_uid` on ≥ 50%). Every emitted path is valid and not deprecated in 1.9.0 (`results/emitted-paths-tenzir-sysmon-v6.22.0-lib9949f753.json`, 84 paths).
  - **Original scorer.** Class 100%, activity 100%, field 84.62%, value 81.82% (`results/original-scorer-sysmon-tenzir-v6.22.0-lib9949f753.json`; emitted sha256 `5e42e0de…cd2a57`).
  - **Gold-key caveat.** The same caveat as Zeek applies, and here it is unscored and post-hoc. The two "dropped" fields landed elsewhere: `LogonId` at `process.session.uid_alt` (gold: `session.uid`) and `User` split into `process.user.name` and `domain` (gold: `actor.user.name` with the `DOMAIN\user` string). The two "mangled" fields are `Hashes`, emitted as an OCSF fingerprint array where the gold carries the raw `SHA256=…` string, and `UtcTime`, an RFC 3339 string where the gold carries epoch-ms. No alternates gold was frozen for sysmon, so these numbers stay on the original gold and should not be quoted as fidelity.

**Release-candidate arm, not run.** `v7.0.0-rc.1` (`sha256:4a55363b…fb86a040`, pulled and verified) has a new CLI with no `--package-dirs` flag. Packages are added to a workspace and downloaded with `tenzir package fetch`, which needs the network, and the frozen protocol runs with `--network none`.

## (e) IAM source arm

It was built from public documentation without inventing fields. The source fields are the 50 documented Okta LogEvent fields in `../ocsf-mapping-fidelity/schemas/okta/inventory.json`. The event types are `user.lifecycle.create` and `user.lifecycle.activate`, both present on Okta's event-type catalog page fetched 2026-11-15. The two mapping files, `iam/okta_account_change_1.8.0.json` and `iam/okta_user_management_1.9.0.json`, are produced by `scripts/iam_arm.py`, which implements the frozen procedure as a rule. Each field's `note` says which rule step placed it.

| | 1.8.0 `account_change` | 1.9.0 `user_management` |
|---|---|---|
| class_uid | 3001 | 3007 |
| `user.lifecycle.create` | activity 1 Create, type_uid 300101 | activity 1 Create, type_uid 300701 |
| `user.lifecycle.activate` | activity 2 Enable, type_uid 300102 | activity 4 Enable, type_uid 300704 |
| typed / coerced / unmapped | 31 / 5 / 14 (coverage 62%) | 31 / 5 / 14 (coverage 62%) |
| paths changed | | 0 from the class move; 1 shared deprecation (`client.id`: `actor.app_uid` → `actor.application.uid`) |

Exploratory observation, post-hoc and not pre-registered: the activity enum is renumbered between the two classes (`scripts/compare_iam_enums.py` → `results/iam-enum-compare.json`, against the pinned 1.9.0 export, where `account_change`'s enum equals its 1.8.0 enum). In 1.9.0, `account_change` 2 = Enable while `user_management` 2 = Update. The script matches captions after singularising and sorting the words, which handles "Attach Policy" / "Attach Policies" and "MFA Factor Enable" / "Enable MFA Factors". It matches all twelve non-Unknown/Other captions, and only Create (1) and Disable (5) keep their integer. So a migration that swaps `class_uid` and keeps `activity_id` would silently turn every Enable into Update, every Password Change (3) into Delete (3), and so on. That silent-wrong-answer risk is probably the part of the IAM cost that matters, more than the attribute count. `user_management` also drops `account_change`'s `user_result` and adds `updated_user`, `privileges`, `iam_roles` and `resources`. This Okta mapping uses none of them, so none counts here.

## Deviations

1. **Tenzir walk-back attempts voided twice before a valid attempt.** The first 6 attempts bind-mounted the library from the session scratchpad under `/tmp`, which Docker Desktop's WSL integration does not share, so `/library` was empty in the container. A control run of June's own library `671e049` failed the same way. The next 10 attempts copied the library into Docker volumes through `tar`, which the Tenzir image lacks, so the volumes stayed empty. Both batches are marked VOID in `results/tenzir-v6.22.0-walkback.txt`, and the 10-attempt budget restarted each time. The valid procedure populates a named volume with `docker cp`, checks that `/library/zeek/package.yaml` exists, and passes a control run with June's library. On it, HEAD loaded on the first attempt. All failures were invocation failures, never library failures, and none was scored.
2. **Validator bug found and fixed before results were recorded.** The first run of `validate_six_source.py` filtered out deprecations on class-level attributes because of a string-prefix check meant to drop only the class's own deprecation, so Zscaler `respcode` did not show. The label was fixed (`class-itself:`) and the script re-run. The recorded outputs are from the fixed run. No hypothesis was evaluated on the buggy output.
3. **H1 prediction arithmetic.** The 80% clause ignored the pre-registered `dash_rule`, so it is recorded as falsified rather than reinterpreted.
4. **Tag cross-check wording.** The pre-registration compares "classes carrying a class-level `@deprecated`" with "the classes H4 counts", which are the `since` 1.9.0 classes. Both readings are reported: the `since` 1.9.0 sets match, and the all-`since` core-event sets match. The extension classes are outside the `events/` walk.
5. **Sysmon shaping judgement** (section d). The first sysmon run did not lift `_id` out of `unmapped.EventData`; it was re-run with the lift. Only the second output (sha256 `5e42e0de…`) is scored.
6. **Python environment.** `pipeline-normalization-fidelity/score.py` imports `../lib/common.py`, which imports `duckdb`, so the two scripts that import `score.py` ran under the lab `.venv`. The others ran under system Python 3.12 with `-I`.
7. **IAM phases in one process.** `iam_arm.py` writes the 1.8.0 file from the 1.8.0 export before it loads the 1.9.0 export, but both phases run in one invocation. Before the run the bench agent had not looked at `user_management`.
8. **What was seen before freezing** is listed in the pre-registration. H1 to H4 are confirmatory; H5, H7, H8b, H8c and H9 were blind.

## Files

- **Pre-registration.** `PREREGISTRATION.md`, `alternates-gold-zeek_conn.json`, `.frozen`, `results/PREREG.sha256`.
- **Schemas.** `schemas/{1.8.0,1.9.0}/{export-profiles,export-noprofile,profiles}.json`, hashed in the pre-registration (about 12.8 MB together).
- **Scripts.** `scripts/` holds `ocsf_full.py` (strict resolver), `erratum_derive.py`, `count_deprecations.py`, `validate_six_source.py`, `score_zeek_alternates.py`, `score_original.py`, `validate_emitted.py`, `iam_arm.py` and `compare_iam_enums.py` (post-hoc).
- **Tenzir.** `tenzir/` holds `run_arm.sh`, `map_zeek_conn.tql`, `map_sysmon_nxlog_probe.tql` and `probe3.tql` (the three-row walk-back probe).
- **IAM.** `iam/` holds the two Okta mapping files.
- **Results.** `results/` holds the JSON outputs and stdout captures listed above, the walk-back record `tenzir-v6.22.0-walkback.txt`, the post-hoc `iam-enum-compare.json`, plus two Tenzir emitted JSONL files (gitignored by `*.emitted.jsonl`, 94 MB and 241 MB, regenerable with `tenzir/run_arm.sh`; sha256 above) and their stderr warnings.

Reproduce (lab root):
```bash
python3 -I ocsf-1.9-rescore/scripts/erratum_derive.py
python3 -I ocsf-1.9-rescore/scripts/count_deprecations.py --tags-dir <dir with extracted ocsf-schema tag tarballs>
python3 -I ocsf-1.9-rescore/scripts/validate_six_source.py
.venv/bin/python -I ocsf-1.9-rescore/scripts/score_zeek_alternates.py --label tenzir-6.0.0-671e049 --emitted pipeline-normalization-fidelity/results/tenzir_zeek_conn.emitted.jsonl --gates
ocsf-1.9-rescore/tenzir/run_arm.sh tenzir/tenzir:v6.22.0 9949f753aa44614a914b83eb81d8276bdcb91886 <extracted library dir> v6.22.0-lib9949f753
.venv/bin/python -I ocsf-1.9-rescore/scripts/score_zeek_alternates.py --label tenzir-v6.22.0-lib9949f753 --emitted ocsf-1.9-rescore/results/tenzir_zeek_conn.v6.22.0-lib9949f753.emitted.jsonl
python3 -I ocsf-1.9-rescore/scripts/validate_emitted.py --emitted <emitted file> --label <label>
python3 -I ocsf-1.9-rescore/scripts/iam_arm.py
```

Single host (Beelink 5800H, WSL2, load average 10 to 18 from other work during the run). No timing claims are made.

## Corrections after independent verification (2026-11-15)

`VERIFICATION.md` reproduced every reachable number and changed no verdict. Applied in place: the status line, the headline count (H1 and H7 are plainly falsified under their frozen falsifiers), the H8b result cell (`actor.app_uid` is deprecated in `user_management`, count (i) still 0) and the draft 15 consequence line. Recorded here rather than rewritten:

- **Deviation not listed at run time.** Gate G1 ran with the imported June `score.py`, not a re-implementation as the pre-registration says, so it checks that the June scorer reproduces its own numbers. The new scorer is covered by G2 and by the verification's independent re-derivation.
- **H5 scope.** At library `9949f753` two shipped packages do map to Authentication 3002, `okta` (Okta System Log) and `openssh` (sshd syslog). Neither applies, because the `auth` corpus is a synthetic generic shape (`auth_protocol` SAML/NTLM, SID `user_id`, `logon_type`) that is neither Okta LogEvent nor sshd text.
- **Wording in section (a).** "with one regression" should read "with one field the frozen gold no longer credits"; the `duration` move is a choice about where to put the time span, not a schema violation.
- **Reproduce block.** Run from inside `ocsf-1.9-rescore/`, or path strings in `emitted-paths-*.json` differ. Missing commands: the sysmon scorer, the two `validate_emitted` runs, `compare_iam_enums` and the sysmon Tenzir run.
- **Stdout capture.** `results/validate_six_source.stdout.txt` predates the "valid only with profiles" print in the committed script; the JSON output is identical.
- **Unscored, post-hoc.** Tenzir's shipped Okta mapping at `9949f753` declares OCSF 1.9.0 but still emits the deprecated `account_change` (3001) class for `user.lifecycle.*`.

## Corrections (2026-11-17, quality pass)

- **H8a cannot fail in practice.** Its frozen threshold is at least 3 times the six-source drift count
  (1 here), so at least 3, and that is met by the class move alone, because moving `account_change` to
  `user_management` changes `class_uid` and the two `type_uid` values derived from it before any
  attribute is looked at, which is already 3. The pre-registration says so ("close to guaranteed by
  construction ... I give it no weight beyond its numeric form", `PREREGISTRATION.md` l.150) and so does
  `LEDGER-ROW.md`. Of the 8 holds, H8a is near-guaranteed by construction, and H1 to H4 are
  confirmatory (deviation 8), so H2, H3 and H4 held on outcomes seen before the freeze; H8b is the real
  test of the IAM claim, and it was falsified.
- 2026-11-17: wording only in the headline, sections (a), (d) and (e) and the deviations; no number,
  state or verdict changed.

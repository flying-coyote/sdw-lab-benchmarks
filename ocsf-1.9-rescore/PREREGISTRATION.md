---
type: benchmark-preregistration
title: "OCSF 1.9.0 re-score: alternates-accepting zeek_conn gold, six-source mapping corpus on a strict full-schema validator (1.8.0 then 1.9.0), lab deprecation counts, Tenzir on its current release, Okta identity-lifecycle arm"
created: 2026-11-15
status: frozen-by-agent-before-scoring (not owner-reviewed)
review_ref: project1/02-projects/securitydataworks/content/drafts-2026-11/12-what-ocsf-native-delivers.md and 15-ocsf-version-drift-cost.md, sections "What's missing before this can publish"
---

# Pre-registration: OCSF 1.9.0 re-score

Written before any score in this directory was computed. The erratum to `pipeline-normalization-fidelity` (draft 12 item 1) was written first, from a read-only derivation script, and is a mechanism statement, not a score.

## What I knew before freezing

So a reader can tell confirmatory hypotheses from blind ones, this is what I had seen:

- The `conn_state` × `activity_id` cross-tab of Tenzir 6.0.0 / library `671e049` against the gold (draft 12, re-derived today in `results/erratum-derivation.json`), where Tenzir put `uid`, `service` and `history`, that `unmapped` holds only `_id`, that `time` is an RFC 3339 string preserved to the microsecond, and that the 53 `duration` differences are half-millisecond ties. So everything about scoring the saved 6.0.0 output under a new gold is known in advance, and H1 below is confirmatory.
- Draft 15's desk check (unregistered, agent-run 2026-11-09, script lost) and its gate re-check: Okta `client.id` → `actor.app_uid` deprecated since 1.9.0; Zscaler `respcode` → `http_status` deprecated since 1.1.0; PAN-OS `src_model` / `dst_model` → `*_endpoint.hw_info.model` resolving nowhere in 1.8.0 or 1.9.0, masked by the "deep" acceptance in `map_fidelity.py` l.71-73. So H2 and H3 are confirmatory.
- The 1.9.0 deprecation counts from the 2026-11-15 currency pass (2 classes, 33 slots / 26 names without profiles, 35 / 28 with profiles). H4 is confirmatory.
- The schema exports below, fetched before writing this file. I hashed them and read only the Network Activity `activity_id` enum, the `time` / `duration` / `app_name` / `app_protocol_name` / `status_code` attribute text and the `metadata` and `network_connection_info` attribute text needed for the alternates gold. I did not run any mapping path against them.
- Tenzir: the latest GitHub release is v6.22.0 (2026-11-12); Docker Hub `tenzir/tenzir:latest` = `v6.22.0` = `sha256:bf8067a122f4b7144fbdb6d2f73fecf9cd98b2d4e35e9e47c67a23ce9b789e20`; `v7.0.0-rc.1` = `sha256:4a55363bb7d0cd7bac10d32c656ea623fb00cf1a2a05d77ea49d0f95fb86a040`. Library `main` HEAD is `9949f753aa44614a914b83eb81d8276bdcb91886` (2026-11-15). The library's `zeek` path history titles include "Map residual source fields to OCSF 1.9 (#191)" (2026-10-02), "Replace deprecated OCSF operators with functions (#231)" and "Port library packages to Tenzir 7 deployments (#233)" (both 2026-11-13). I have not read the mapping code or run anything. The commit titles hint that the mapping targets 1.9.0, so H6 is only partly blind.
- Okta: `developer.okta.com/docs/reference/api/event-types/` (fetched 2026-11-15, sha256 `ac8cdce0…d59d96`, JS-rendered, so only part of the catalog is in the HTML) contains `user.lifecycle.create`, `user.lifecycle.activate` and `user.lifecycle.action.failed`. I have not looked at the `account_change` or `user_management` class attributes in either export. The IAM arm (H8) is blind.

## Pinned inputs

| Input | Source | sha256 |
|---|---|---|
| OCSF 1.8.0 export, profiles applied | `https://schema.ocsf.io/1.8.0/export/schema?profiles=ai_operation,cloud,container,data_classification,datetime,host,incident,load_balancer,network_proxy,osint,security_control,trace` (fetched 2026-11-15T19:55Z) → `schemas/1.8.0/export-profiles.json` | `53b9ead66b269b1323378a4f059e511dc8d318d16a3872bf9053f83ce35755db` |
| OCSF 1.8.0 export, no profiles | `…/1.8.0/export/schema?profiles=` → `schemas/1.8.0/export-noprofile.json` | `8b3cfc80faee06a0162efef121621f2d5c2bc721dd43328be749a8d6458d8c1a` |
| OCSF 1.8.0 profiles | `https://schema.ocsf.io/api/1.8.0/profiles` → `schemas/1.8.0/profiles.json` | `a6b7e0b8276c609a0e2caf8bfd56304b4f86942d37a77e6f0a3ab3251a490198` |
| OCSF 1.9.0 export, profiles applied | same profile list plus `record_integrity` → `schemas/1.9.0/export-profiles.json` | `a25650f12f3a7c7f606022969bb20a506b7b111867918640f04b44aa6a97bf9a` |
| OCSF 1.9.0 export, no profiles | → `schemas/1.9.0/export-noprofile.json` | `7745b8ce09ad9a6eb33a86bd5e7f3f6d371c50fc860dbf713f67e19d1ff87b94` |
| OCSF 1.9.0 profiles | → `schemas/1.9.0/profiles.json` | `c2d64b77dc82d61b1bcd6f81138d53c3b38a24832407d3668bfc4b205e49a5a4` |
| ocsf-schema tag `1.8.0` source tarball | `github.com/ocsf/ocsf-schema/archive/refs/tags/1.8.0.tar.gz` (tag commit `6fa6499a0f8c9f449d342816e90e5f687c224b0a`), kept outside the repo | `052f6ce9f0873f64b806776f517907d6c99beba3f28ecef60922a6d8f31dd221` |
| ocsf-schema tag `1.9.0` source tarball | `…/1.9.0.tar.gz` (tag commit `856d462bd20dc46cc1ffed2dfffe3b91ef0fbeba`) | `0ed367ea97dd283d69401099974cec256c862621b6ef53243f76999ace2abfc7` |
| Alternates gold + activity rule | `alternates-gold-zeek_conn.json` (this folder) | `8eda25148935f143b6a684e21ec5d34c933711aa38133c602d90cd23af2390e5` |
| Six-source mapping (read-only import) | `../ocsf-mapping-fidelity/mapping.py` | `360f9e73b60cd45b95c900dc10a07733f7ec9d264c80333c375d239897ca265e` |
| Okta field inventory | `../ocsf-mapping-fidelity/schemas/okta/inventory.json` | `cf5a74058c4f5f15ab58292dc5a869f550783b524ad473c7d6466db3ed374c6d` |
| zeek corpus / gold / Tenzir 6.0.0 output | `../pipeline-normalization-fidelity/_work/zeek_conn.{corpus,gold}.jsonl`, `results/tenzir_zeek_conn.emitted.jsonl` | `30f624f1…aa1bd` / `f6e54d5c…742c1` / `561ce680…661929c` |

The export is the schema server's compiled form of the tag (inheritance, profiles and includes resolved), so it is the validation target. The source tarballs are pinned as provenance and used for one cross-check: the classes carrying a class-level `@deprecated` in the 1.9.0 tag's `events/` tree must equal the classes H4 counts from the export.

**Profiles.** The validation target is the profiles-applied export, with every profile the server lists except `linux/linux_users` and `macos/macos_users`. In 1.9.0 the server refuses to combine those two, because both add `euid` to `process`. They only touch process and user identity attributes, and I expect no mapping path here to depend on them; if one does, it is reported. The no-profile export is run as a sensitivity check, and any path that resolves only with profiles is listed.

## Arms, hypotheses and what falsifies each

### (a) Alternates-accepting re-score of zeek_conn (draft 12 item 2)

Instrument: `scripts/score_zeek_alternates.py`, written after this freeze. It joins emitted records to the corpus and gold on `_id`. **Field fidelity**: a source field counts as landed if its primary path or any accepted alternate is present and non-null. **Value, strict**: some landed accepted path carries the value under the field's `value_rule`, and for `time`/`start_time` that means a JSON integer of epoch milliseconds. **Value, information-preserving** (secondary): the same, but an RFC 3339 string is accepted under the `epoch_ms_long` rule's second clause. **Activity** is scored three ways. The original gold counts only 6. The accept-set rule counts the per-state accepted set and is the headline. The derived-primary rule counts the single derived value per state. `type_uid` follows activity. Denominators are given for each metric. The '-' service records are excluded from the service field per the gold file's `dash_rule`.

Gates, which stop the arm if they fail:
- G1, sanity. Re-implementing the original gold's scoring on the saved 6.0.0 output must reproduce field 0.80, value 0.9166 and activity 0.167 (rounded as in `results.json`).
- G2, self-check. A reference event built from the new gold's primary paths, canonical values and derived-primary activity must score 100% on every metric.

**H1 (confirmatory).** Tenzir 6.0.0 / `671e049` on zeek_conn, under the alternates gold:
- field fidelity 100%;
- strict value fidelity fails on `ts` only, and on every record;
- information-preserving value fidelity 100%;
- accept-set activity 83.30% (every state except S0, whose emitted 1 Open is not accepted) and derived-primary activity also 83.30%.

The original gold's own paths, scored as a mapper under the new gold, land on 12 of 15 fields (80% field fidelity) and score 100% accept-set activity but 16.70% derived-primary activity. Falsified if any of these numbers differs.

### (b) Six-source mapping corpus on a strict full-schema validator, 1.8.0 then 1.9.0 (draft 15 item 1)

Instrument: `scripts/validate_six_source.py`, written after this freeze. It imports `mapping.py` read-only and resolves every `ocsf` path, for all 251 records, against the class's attributes in the full export. It follows `object_type` through objects at every segment. Validator changes from `map_fidelity.py`:
- It fails a path that descends into an object missing from the export, or names an attribute the object does not have. There is no "deep" acceptance.
- It reports every segment whose attribute, object or class carries `@deprecated`, with the `since` value and the message.
- It collects every failure rather than stopping at the first.

Catch-alls (`unmapped`, `raw_data`, `enrichments`) must exist as attributes of the class.

Coverage arithmetic under the strict validator:
- an invalid path counts as unmapped;
- a deprecated-but-valid path keeps its status and is reported;
- coverage = typed / 251;
- lossy = (coerced + unmapped) / 251.

Per source, the output reports paths resolved, paths invalid, paths deprecated by since-version, coverage and lossy before and after, the records that would have to change to reach zero invalid and zero deprecated targets (with the replacement the `@deprecated` message names, or "untyped" when there is none), and the named detections that depend on a changed record. The changes go into `results/proposed-mapping-changes.md` as a proposed diff. `mapping.py` is not edited, because remap versus untyped moves published figures and is the owner's call.

**H2 (confirmatory).** On 1.8.0 strict, the 181 typed and coerced paths split as follows:
- exactly 2 invalid: PAN-OS `src_model` and `dst_model`;
- exactly 1 deprecated: Zscaler `respcode` → `http_status`, since 1.1.0;
- every other path valid and not deprecated.

Coverage moves from the published 148 typed / 59% to 146 / 58%, and lossy from 41% to 42%. Falsified if any other path is invalid or deprecated on 1.8.0, or if any of these three is not.

**H3 (draft 15's expectation, six-source half; confirmatory).** From 1.8.0 strict to 1.9.0 strict:
- at most 2 of the 181 typed and coerced paths drift (become invalid, or newly deprecated with `since` 1.9.0), and the expected count is exactly 1, Okta `client.id` → `actor.app_uid`;
- coverage and lossy move by at most 1 percentage point per source and in total.

Falsified if 3 or more paths drift, or if any source's coverage moves more than 1 point.

### (c) Deprecation counts by lab script against the pinned schema (draft 15 item 4)

Instrument: `scripts/count_deprecations.py`. For each export, it counts classes whose class-level `@deprecated.since` equals the version, plus attribute slots (class or object, attribute) and distinct attribute names whose `@deprecated.since` equals the version, on both the profiles-applied and the no-profile export. It also counts, as context, everything carrying any `@deprecated` regardless of `since`. The tarball cross-check is the one described under Pinned inputs.

**H4 (confirmatory).** 1.9.0:
- 2 classes (`account_change`, `user_access`);
- 33 slots / 26 names without profiles;
- 35 slots / 28 names with profiles.

The tag cross-check finds the same 2 classes. Falsified if any count differs. The 1.8.0 (`since` 1.8.0) counts are reported with no prediction.

### (d) Tenzir on its current release (draft 12 item 3, draft 15 item 3)

**Pinning.** The image is `tenzir/tenzir:v6.22.0`, pulled and checked against digest `sha256:bf8067a1…9e20`. The library is fetched as a tarball at an exact SHA from `codeload.github.com/tenzir/library/tar.gz/<sha>` into a scratch directory outside the repo (no clone, no checkout).

**Fallback.** The first try is HEAD `9949f753`. If the zeek package fails to load or parse under 6.22.0, I walk back the library's `main` commits newest-first and stop at the newest one that loads, at most 10 attempts, logging each attempt and error. If none loads, the arm is reported as not run on 6.22.0.

**Release candidate.** `v7.0.0-rc.1` with HEAD is run as a labelled release-candidate arm if it loads. It is reported but does not decide any hypothesis.

**Execution.** `docker run --rm --network none` with read-only mounts for the library and the corpus. Input shaping is the June recipe: `read_ndjson unflatten_separator="."`, `this._path = "conn"`, lift `_id` from `unmapped`. Where #231 replaced the operator with a function, I use the invocation the library's own package docs or examples give, without editing any mapping logic, and record the exact TQL. The emitted JSONL goes to `results/` (gitignored by `*.emitted.jsonl`) and its sha256 is recorded in RESULTS.md. If the permission system blocks running third-party library code, as it did in June, the arm is recorded as not run, with no workaround.

**Other sources.** For cloudtrail, sysmon and auth, the library at the pinned SHA is searched for a package whose operators or docs name the source (CloudTrail management events, Sysmon, a generic auth shape). A source counts as having a usable shipped mapping if that operator runs unedited on the corpus JSONL with only Tenzir-native input shaping and emits the gold `class_uid` on at least 50% of records. Any source with a usable mapping is scored with the original scorer.

**Scoring.**
- The zeek output is scored three ways: by the original scorer logic (imported, run with `--no-write`-equivalent into this folder), by the alternates scorer, and by the strict validator against the export of the OCSF version the output declares in `metadata.version` (every emitted leaf path checked for validity and deprecation).
- That version is read from `metadata.version` on the emitted records, not from commit messages.

**H5 (blind).** The current release still has no usable shipped mapping for at least 2 of cloudtrail (management events), sysmon (pre-parsed JSON) and auth on this corpus. Falsified if 2 or more of the three are usable.

**H6 (partly blind).** The current shipped Zeek mapping declares `metadata.version` = `1.9.0` on every record. Falsified by any other value.

**H7 (blind).** Under the alternates gold, the current Zeek mapping scores field fidelity ≥ 99% and accept-set activity ≥ 80%, which would mean it still derives activity from `conn_state`. Falsified if either is lower.

**H9 (blind, exploratory).** The current mapping still writes `time` as a string, so strict value fails on `ts` for ≥ 99% of records. Falsified if it emits an integer.

### (e) IAM source arm (draft 15 item 2)

**Source.** The Okta System Log LogEvent, with its 50-field documented inventory taken from the checked-in public-docs transcription. The event types in scope are `user.lifecycle.create` and `user.lifecycle.activate`, both confirmed on Okta's event-type catalog page. No field is invented. Every mapped source field is an inventory field.

**Procedure, before any 1.9.0 look.** I read the `account_change` (3001) class in the 1.8.0 export and write `iam/okta_account_change_1.8.0.json`, one record per inventory field with `{ocsf, status, note}`, in this order:
1. Start from `OKTA_MAPPING`, the Authentication mapping.
2. Apply the lifecycle role rule. Okta `actor` is the principal making the change, so actor fields that the Authentication mapping puts on `user.*` move to `actor.user.*` with the same leaf. Okta `target` is the user acted on, so `target.id` / `alternateId` / `displayName` / `type` go to `user.uid` / `user.email_addr` / `user.full_name` / `user.type`, the same leaves the Authentication mapping uses for the authenticating user.
3. Keep every other target path if it resolves strictly in `account_change` 1.8.0.
4. Otherwise re-home it to a same-named attribute of the class if one exists, or set it unmapped.

Each activity is set by enum caption from the export: create → the "Create" activity, activate → the "Enable" activity, or the closest caption if those are absent, which I would record as a judgement.

**Procedure, then 1.9.0.** I write `iam/okta_user_management_1.9.0.json` starting from the 1.8.0 file. I keep each path that resolves strictly in `user_management` 1.9.0 and is not deprecated. Otherwise I re-home it to the replacement the `@deprecated` message names or a same-named attribute, or set it unmapped. Activities are set by the same caption rule.

**Cost metric.** These are the mapping decisions that change from 1.8.0/`account_change` to 1.9.0/`user_management`:
- `class_uid` (1 if it changes);
- `activity_id` per event type (0 to 2);
- `type_uid` per event type (0 to 2);
- attribute paths changed. These are split into (i) paths valid in `account_change` 1.8.0 but invalid in `user_management` 1.9.0, which are caused by the class move, and (ii) paths that change because the attribute itself is deprecated in 1.9.0 in every class (for example `actor.app_uid`).

Also reported: typed / coerced / unmapped before and after, and the fields lost (typed or coerced in 1.8.0, unmapped in 1.9.0). The arm is scored as a pure function of the two mapping files and the exports, by `scripts/iam_arm.py`.

**H8a (draft 15's "IAM is where the cost sits", numeric).** The IAM arm's total changed decisions are at least 3 times the six-source drift count from H3, and at least 3 if that count is 0. Falsified otherwise. This is close to guaranteed by construction, because the class move alone changes `class_uid`, so I give it no weight beyond its numeric form. H8b is the real test.

**H8b (blind).** At least one Okta attribute path changes because of the class move, under count (i), not counting shared deprecations. Probability about 50%. Falsified if count (i) is 0.

**H8c (blind, exploratory).** No field is lost (typed or coerced to unmapped) in the move. Falsified if any is.

If the arm cannot be built from public documentation without inventing fields, H8a-c are reported as **not tested**, never as held or falsified.

## Confidence consequence

No hub hypothesis moves on this bench. Any move goes through the hub's evidence gate and the owner. What the results can do for the drafts:
- If H1 holds, draft 12 can state corrected Tenzir 6.0.0 numbers under a pre-registered gold.
- If H3 holds and H8b holds, draft 15's "IAM is where the cost sits" is supported on this corpus. If H8b is falsified, draft 15 should say the 1.9.0 IAM cost is a class and enum remap only.
- If H5 is falsified, draft 12's availability table needs a new current-version row.

## Stop rules

- G1 or G2 fails: the zeek alternates arm stops and the failure is reported.
- The strict validator cannot load a pinned export, or a hash mismatches: stop.
- The Tenzir image digest differs from the pin: stop that arm.
- Tenzir execution is blocked by the permission system: that arm is not run.
- Spend: $0, local CPU only, no paid API. Single host (Beelink 5800H, WSL2), no timing claims, so methodology §7b rig stamps do not apply.

## Not done here

No edits to `mapping.py`, `score.py`, `gen_corpus.py`, either bench's README, the hub tracker, the PRE-REGISTRATION-LEDGER or any Matrix page. No independent verification pass is part of this run. `LEDGER-ROW.md` is the handoff text for the main session.

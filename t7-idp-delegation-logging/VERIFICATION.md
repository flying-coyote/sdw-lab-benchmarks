---
type: benchmark-verification
title: "T7 independent verification"
created: 2026-11-10
verdict: VERIFIED-WITH-FIXES
---

# T7 verification: IdP delegation logging (Keycloak 26.8.1)

**Verdict: VERIFIED-WITH-FIXES.** Every scored number in RESULTS reproduces, both from the shipped raw data and from a
full independent re-run of both arms. The pre-registration predates the run by hash. Four wording fixes went into
RESULTS.md: one denominator correction and three hedges where a claim reached past what was measured. No number changed.

Verifier: a separate agent session, 2026-11-10 01:15–01:31 UTC. Cross-provider leg: Gemini (`gemini-3.8-flash` through
`automation/agy-tracked.sh`). No git.

## 1. Pre-registration predates the run

- `results/freeze.txt` records `PREREGISTRATION.md` sha256 `f95931e86b33294284ac58c989f62bb6dd4e9cced4f70a85122cb7177d6e8ef6` at `freeze_time_utc 2026-11-10T01:05:35Z`.
  If you truncate the current file just after `(none at freeze)` plus one newline, it hashes to exactly
  `f95931e86b33294284ac58c989f62bb6dd4e9cced4f70a85122cb7177d6e8ef6`. So the frozen body was left untouched, and
  amendment 1 is a pure append. The full current file hashes to `10814580b7f2255c5c4533f0a85078e51ef08900bd5c1e70f9fb5524ade1409e`, which matches the `final_hashes`
  entry.
- The harness hashes at freeze (`kc.py`, `harness.py`, `run_all.sh`, `requirements.txt`) match the files on disk.
  Their mtimes (01:01–01:04Z) fall before the freeze. `score.py` (01:10Z) and `map_ocsf.py` (01:15Z) come after the run,
  as the pre-registration says they would, and their hashes match the `post_freeze_analysis_hashes` entry.
- Caveat: the freeze time and the start of `run_all.sh` fall in the same second (01:05:35Z). So the evidence for
  "before" is the hash chain and the fact that the harness was not edited, not a time margin. The freeze is
  agent-frozen and not owner-reviewed, as RESULTS says.

## 2. Analysis matches the pre-registration

I read `score.py` against the rubric:
- H3 uses exactly the pre-registered rule: nearest earlier agent-a `TOKEN_EXCHANGE` in the same `sessionId`. Ground
  truth is the agent's own `subject_token_jti`, and events were mapped to hops by `token_id` in every rep (no order
  fallback).
- H4 root-only uses `{data:read, data:write}`, and chain-aware uses "hop-N ⊄ hop-(N-1)".
- Arm D linkage is the amended rule (`userId` + `subject_token_client_id` + nearest earlier `CODE_TO_TOKEN`), and it
  is disclosed in amendment 1.

The four deviations in amendment 1 are real and correctly disclosed:
- the H8 list read from OCSF main
- arm D linkage
- realm filter for H7
- `dst_endpoint` from config

The H5/H6 smoke-test pre-exposure is declared in the pre-registration and labelled in the table. One small point is
not labelled as a deviation. H3's 1-of-3-per-rep result is guaranteed by the harness design, because all three hop-1
exchanges are issued before any hop 2. The pre-registration says this ("the shuffled order makes the nearest
predecessor the last agent-a hop"), so it is a prediction that could only fail if the events disambiguated. It is not
an empirical accuracy rate, and Gemini noted the same.

## 3. Reproduction

| check | method | result |
|---|---|---|
| Analysis on shipped raw | copied tree to `verification/analysis-rerun/`, ran `score.py` + `map_ocsf.py` | `score.json`, `tables.md`, `ocsf_mapping.json` and all 8 `ocsf_records_*.jsonl` **byte-identical** |
| Full re-run | `verification/full-rerun/run_all.sh` (same image digest, same caps), then score + map | run 01:25:43–01:28:32Z, exit 0, no DNF; 107 S events / 21 admin, 48 D events |
| Scored values | diff of `score.json` with ids, timestamps, ns and load averages masked | **0 differences** in H1, H2 claims inventory, H3 (5/15), H4 detection, H5 error-event keys, H7 parity, field inventories |
| OCSF | `ocsf_mapping.json` re-run vs original | identical (validator verdicts unchanged at 1.9.0 and 1.10.0-dev) |
| Latency (not a finding) | medians | doubled under higher contention: S exchange 38–42 ms vs 19–21 ms, S login 117 vs 76 ms; load average 22–24 vs 18–19. The direction is consistent with "under contention" and the timings stay non-findings |

Independent recomputations from the raw events, outside `score.py`:
- **Event counts.** S has LOGIN 29, TOKEN_EXCHANGE 72, TOKEN_EXCHANGE_ERROR 6 (107). D has 9 / 9 / 12 / 9 / 6 / 3 (48).
- **Signatures.** 131 = 101 S + 30 D, all `sig_verified`.
- **`subject_token_client_id`.** S has it on 72 of 72 successful exchanges and 0 of the 6 refusals. D has it on 9
  exchanges plus 6 refusals, which is the 15.
- **Scope-equality heuristic for H3.** RESULTS asserts this one but `score.py` never computes it. I recomputed it at
  15 of 15 with no ties, so the assertion holds and is now marked as recomputed.

Full masked diff: `verification/rerun-diff.txt`.

## 4. Versions, spend, safety

- **Versions.** Recorded in `driver.log` and RESULTS: Keycloak 26.8.1 by digest, Quarkus 3.40.1, Docker 29.5.3,
  Python 3.12.3, and the pip freeze, which matches `requirements.txt`. The OCSF validator is a live service, and its
  version is selected by URL path.
- **Spend.** Cap $0, actual $0. External calls were the image pull and `schema.ocsf.io`. The verification added one
  Gemini call (18,920 tokens, subscription quota, logged in the agy ledger).
- **Safety.**
  - Containers bind to `127.0.0.1:8080` only.
  - The only plant is a scope string at a localhost dev IdP, with no exploit code.
  - `grep eyJ` over `results/` finds no stored tokens.
  - `fixture-secrets.json` and `realm-config.json` show `redacted-after-run`.
  - Admin-event representations mask client secrets as `**********` and carry no password or `credentials` key.
  - The log hits for "secret" are the `client-secret` auth-method value.
  - `results/.admin-pw` was removed.
  - My re-run copy's runtime secrets were redacted the same way after scoring; I did not grep those values across the re-run's logs and admin events, and rely on the original author's check of the same harness code paths for that. Nothing touches an employer.

## 5. Cross-provider leg (Gemini)

I sent the five main claims with their data excerpts. Prompt and answer are in `verification/gemini/`.

| claim | Gemini | resolution against the data |
|---|---|---|
| 1 parent pointer half present | AGREE. Noted that arm S refusals lack `subject_token_client_id` | **Confirmed in the events**: 0 of 6 S refusals carry it. RESULTS' "72/72 (S) and 15/15 (D) exchange events" mixed denominators, so it is **fixed** to name what each count covers |
| 2 H3 5/15 | AGREE. 5/15 is an artifact of the batching schedule | Consistent with §2: by design, and pre-registered as such. No change |
| 3 reacquire 5/5 vs 0/5; `new` leaves no trace | AGREE. Caveat: "detectable from events alone" assumes chains can be separated, which degrades under interleaving | **Valid.** The detection counts come from single-chain sessions only, and interleaved detection was not scored. RESULTS **hedged** in the headline and the R7 section |
| 4 enforcer refusal not attributable | DISAGREE. Arm D refusals do carry `userId` | **Resolved for RESULTS.** RESULTS already confines the gap to the client-policy refusal path and states that arm D refusals carry `userId`/`subject_token_client_id`. My prompt wording was broader than RESULTS, so RESULTS needed no change |
| 5 OCSF fill 0/81 `parent_uid`; refusal validation error | AGREE | No change |

## 6. Fixes applied in place (RESULTS.md)

Pre-verification copy: `verification/RESULTS.pre-verification.md` (sha256 `6ac1caf24b8f53bf9e9f4119aea5c900be3dcc18426367d67d962a7e00934d8a`, the `final_hashes` value).
Post-fix sha256: `615dc40ba26bc0d8d3e51945b57a14cadbb265201839214c89bf0e2e3257523f`.

1. **H1 row, denominator.** The text now says 72 of 72 S *successful* exchanges, 15 of 15 D (9 successful plus 6
   refusals), and that the 6 S enforcer refusals carry no `subject_token_client_id`.
2. **Headline, admin-event claim.** "an event kind Keycloak does not have" now reads "on the surfaces checked (REST and
   the log at INFO; DEBUG was not checked) this looks like an event kind Keycloak does not have". This matches the
   existing Limits bullet.
3. **Headline, R7 detectability.** It is now scoped to "in single-chain sessions". The R7 section gains a sentence
   saying that sessions shared by several chains inherit the H3 linkage problem and were not scored for detection.
4. **H3 row.** The scope-equality 15/15 is marked as recomputed at verification and not computed in `score.py`.

The run summary returned to the orchestrator repeats the H1 denominator wording ("72/72 arm S, 15/15 arm D"). Read it
with fix 1.

## 7. Claims vs evidence, remaining

The rest of the claims are held to this version, configuration and dev mode, and RESULTS' Limits already say so:
- max one actor hop (3/3 plus server error strings)
- upscoping allowed in delegation mode (3/3)
- `new` dropped (role-backed scope only)
- no interleaved arm D

The evidence tier of B (first-party, single host) is appropriate.

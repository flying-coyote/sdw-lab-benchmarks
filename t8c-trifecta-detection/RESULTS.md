---
type: benchmark-results
title: "T8c trifecta detection: results"
created: 2026-11-09
status: complete (agent-run, not owner-reviewed)
prereg: PREREGISTRATION.md (sha256 7703a4bb3fa38d9e5911de246f27fda2769f8677f9c90bfa1bef31471ca106d9, frozen 2026-11-10T00:54:01Z)
---

# T8c trifecta detection: results

## Headline

At 2,000 benign sessions per seed across three seeds, the only rule that reaches DETECTED on both chain shapes and on all four plant strata is `c2_walk_sql_qualified`, the session rule that walks delegation to the root session and qualifies leg 3 by content (the de-prefixed credential string or an off-allowlist burst of 20 or more calls in 5 minutes): precision 1.0, recall 1.0, 0 false positives on every seed and both engines (`results/coverage.json` lines 2604 to 2660, summary block). The plain session rule `b3_session_sql`, which is the draft essay's design rule as written (one session holding an ingest, a sensitive read and an off-allowlist outbound call), is NOISY at precision 0.1923 / 0.2083 / 0.2128 (min / median / max, line 2385) with recall 0.5, because it misses every delegated chain and fires on 37 to 42 benign sessions per seed (line 2380). So the frozen H2 is falsified on both clauses, and by the pre-registration's own rule the essay's section 7 sequence claim, as stated, should be dropped or rewritten around content qualification and the delegation walk. Three of six hypotheses held (H3, H4, H5) and three were falsified (H1 on the a6 clause, H2, H6).

The run is the bench's own `run.py`, re-run to completion by me on 2026-11-10 UTC after the first run agent stopped. `sha256(results/coverage.json)` is `55666d53e5c4e11f7de9c10c75b04384d8cf4c04eeec4f16926749cb9c5402e0`, which matches both independent verifier runs in `verify/coverage-A.json` and `verify/coverage-B.json`, so three identical runs agree and stop rule (d) did not trip.

## Results by rule

Tier (a) is scored on events against that leg's planted events across all four strata; tiers (b) and (c) on sessions against the 20 chain root sessions. Precision is min / median / max over seeds 20261109, 20261110, 20261111. Every row is from the `summary` block of `results/coverage.json` at the line given (the block for that rule starts there and holds states, precision, recall, false positives per seed and engine agreement for both engines). SQLite and DuckDB return the same matched set wherever both execute.

| Rule | Line | States, 3 seeds | Precision | Recall | FP per seed | DuckDB |
|---|---|---|---|---|---|---|
| a1_ingest_mail | 1838 | NOISY x3 | 0.0123 / 0.0126 / 0.0128 | 0.5 | 781, 806, 771 | same set |
| a2_ingest_repo | 1889 | NOISY x3 | 0.0178 / 0.0181 / 0.0182 | 0.5 | 542, 552, 538 | same set |
| a3_collect_mailbox | 1940 | NOISY x3 | 0.0081 / 0.0083 / 0.0088 | 0.6667 | 2253, 2435, 2394 | same set |
| a4_read_procenv | 1991 | DETECTED x3 | 1.0 | 0.3333 | 0, 0, 0 | same set |
| a5_outbound_offlist | 2042 | NOISY x3 | 0.6024 / 0.651 / 0.6562 | 1.0 | 131, 134, 165 | same set |
| a6_credential_shape | 2093 | NOISY x3 | 0.5 | 0.04 | 10, 10, 10 | same set |
| a7_url_burst (Sigma event_count) | 2144 | NOISY x3 on SQLite | 0.151 / 0.1512 / 0.1783 | 0.96 | 1106, 1349, 1347, all LA4 | MISSED, parser error |
| b1_session_temporal (pySigma temporal) | 2193 | NOISY x3 on SQLite | 0.1923 / 0.2083 / 0.2128 | 0.5 | 38, 37, 42 | MISSED, parser error |
| b2_session_temporal_ordered | 2262 | NOISY x3 on SQLite | 0.1923 / 0.2083 / 0.2128 | 0.5 | 38, 37, 42 | MISSED, parser error |
| b3_session_sql | 2331 | NOISY x3 | 0.1923 / 0.2083 / 0.2128 | 0.5 | 38, 37, 42 | same set |
| b4_session_sql_qualified | 2422 | DETECTED x3 | 1.0 | 0.5 | 0, 0, 0 | same set |
| c1_walk_sql | 2513 | NOISY x3 | 0.3226 / 0.3448 / 0.3509 | 1.0 | 38, 37, 42 | same set |
| c2_walk_sql_qualified | 2604 | DETECTED x3 | 1.0 | 1.0 | 0, 0, 0 | same set |

Where the false positives come from, per seed (`per_seed.<seed>.rules.<rule>.sqlite.fp_by_session_class`; for b3 the blocks start at lines 457, 1059 and 1661): b1, b2, b3 and c1 fire on LA2 27 / 27 / 25 and LA5 11 / 10 / 17 sessions, and on nothing else. a7's false positives are all LA4 docs crawls (blocks at lines 366, 968, 1570). Per-stratum recall for b1 to b4 is 1.0 on CS0066-direct and CS0067-direct and 0.0 on both delegated strata on every seed; c1 and c2 are 1.0 on all four strata (`recall_by_stratum_per_seed` in each summary block, for example line 2390 for b3).

The DuckDB failure for a7, b1 and b2 is `Parser Error: syntax error at or near "end"` (line 370 and its twins at 397 and 429): the pySigma sqlite backend's correlation SQL aliases a column `end`, which DuckDB reserves.

Timings are small at this scale and were taken under contention (1-minute load 10 to 18 on a shared host, `taskset -c 0-3 nice -n 10`, DuckDB `threads=4`). The hand SQL session rules run in 0.013 to 0.089 s median per seed on either engine, the pySigma `temporal` correlation (b1) on SQLite in 0.31 to 0.43 s and the `temporal_ordered` correlation (b2) in 0.78 to 1.33 s (`results/timings.json`). [fixed in verify: the earlier text said 0.013 to 0.047 s and gave only b1's range; b4 on SQLite seed 20261111 is 0.0888 s and b2 runs 0.779 to 1.3284 s] Seed wall time was 115 to 182 s, almost all of it corpus generation.

## Scale check at 20,000 sessions

Pre-registered for the SQL rules on seed 20261109 only (`results/coverage-scale20k.json`, sha256 `265ee12747c7557d7842f2b3c29c3555e0019793df161c6a92295aa1ac2bc6c2`, identical to the verifier's `verify/coverage-scale20k.json`). Every state holds at tenfold background. The NOISY rules get noisier, because the 20 plants stay fixed while the benign sessions grow: a5 falls to precision 0.1457 (line 702), b3 to 0.026 with 374 false positives from LA2 280 and LA5 94 (line 784), and c1 to 0.0508 (line 898). a4, b4 and c2 stay at precision 1.0 with 0 false positives (lines 661, 841, 955), and c2 keeps recall 1.0. The slowest single query median was 0.68 s (c2 on SQLite, `results/timings-scale20k.json`), well inside stop rule (c)'s 20 minutes per rule; the seed's wall time was 1,602 s, nearly all corpus generation under a load average of 10 to 17.

## Hypotheses, scored against the frozen text

- H1, kind vs content, single step: falsified on the a6 clause. a1, a2, a3 and a5 are NOISY on every seed and a4 is DETECTED, as predicted, but a6 is NOISY at 0.5 on every seed (line 2093). The pre-registration says the planted `bash.exec` echo is "planted but not truth for any rule", and a6 matches `bash.exec`, so 10 of its 20 hits per seed are false positives by the author's own frozen definition. That is a design slip in the pre-registration, and the falsification stands.
- H2, sequence buys precision: falsified on both clauses. b3's precision is 0.19 to 0.21, below the predicted [0.6, 0.9) band, and its median (0.2083) is 0.44 below the best kind-matching single-step rule's median (a5, 0.651, line 2076) rather than 0.3 above it. The band was unreachable as designed: a non-walk session rule can score at most 10 true positives (the direct roots), and LA5 alone brings 10 to 17 false positives, so the precision ceiling sat near 0.5 before any other lookalike fired.
- H3, content-qualified session rule: holds. b4 has 0 false positives and recall 1.0 on both direct strata, on all seeds and both engines (line 2422).
- H4, delegation splits the legs: holds. b1 to b4 have recall 0.0 on both delegated strata on every seed; c1 has recall 1.0 and stays NOISY like b3, and c2 has recall 1.0 and stays DETECTED like b4.
- H5, engines: holds. All six tier (a) Sigma rules return identical sets on both engines on all three seeds (`engines_agree_per_seed`, for example line 1861), and a7, b1 and b2 fail to execute on DuckDB.
- H6, ordering: falsified. b2's false positives equal b1's on every seed (38, 37, 42). The stated mechanism was wrong as well, because LA3 sessions hold no leg 1 and so cannot fire either rule in any order, while LA2 and LA5 are generated in 1 then 2 then 3 order.

Predicted confidence delta: the pre-registration said the essay's section 7 claim moves from D toward B only if H2 and H3 hold, and that a failure on the H2 precision-gain clause drops the sequence claim. H2 failed, so the claim as worded does not move and should come out of the essay. What the data does support is narrower: content qualification plus a delegation walk, layered on the session unit, gave the only clean detection across both shapes. No hub hypothesis moves on this bench alone, which is also what the pre-registration said.

## Method as run

As frozen, with the deviations below. One flattened OCSF 1.9.0 `api_activity` table with the `ai_operation` profile, column paths checked against the 1.9.0 schema JSON at corpus write time, written to SQLite and loaded into DuckDB 1.5.3 in memory from the same file. 2,000 benign sessions per seed in three personas with the seven pre-committed lookalike classes, 20 planted chains per seed in four strata of five. Rules: seven Sigma rules for tier (a) and one two-correlation Sigma file for b1 and b2, compiled with pySigma 2.0.3 and pySigma-backend-sqlite 2.1.1, plus hand SQL for b3, b4, c1 and c2 on both engines. Commands, in `logs/run-2026-11-10.txt`:

```bash
taskset -c 0-3 nice -n 10 .venv/bin/python -I run.py
taskset -c 0-3 nice -n 10 .venv/bin/python -I run.py --scale 20000 --seeds 20261109 --sql-only --out results/coverage-scale20k.json
```

Resume or restart: the harness has no resume mode, because `run.py` regenerates each seed's corpus deterministically at the start of the seed, so I restarted it from the top and reused the existing venv. The regenerated corpus is byte-identical to run 1's and the verifier's (VERIFICATION.md records `corpus.sqlite` sha256 `62552d34...` for seed 20261109). Cost: zero spend, local CPU only, inside the pre-registration's line.

## Deviations from the pre-registration

1. Session leg 2 is broader than the leg rules. The pre-registration defines the b1 to b4 legs as "any of the leg rules above except a7", which for leg 2 means a3 or a4 (`/proc/self/environ` only). Both `rules/b_session_temporal.yml` and the `LEGS_CTE` in `run.py` also count `file.read` of `.env` and `credentials.json`. Without that, the CI and coding LA5 sessions could not fire the session rules, which H2 assumed they would, so the pre-registration was internally inconsistent and the author resolved it in the rules. [fixed in verify: the earlier text said LA5 "could not fire the session rules at all". Re-scored with leg 2 exactly as frozen (a3 or a4 only), the inbox LA5 sessions still fire through `mail.search`, and b3 is NOISY at 0.2439 / 0.2326 / 0.2439 with 31, 33, 31 false positives (LA2 27 / 27 / 25, LA5 4 / 6 / 6), so H2 is falsified under either reading of leg 2 and the deviation does not change any verdict.] The rules were written at 00:56Z, after the freeze and before any result, so this is not tuning to a result, but it was not recorded at the time and I record it here. I did not append an amendment to PREREGISTRATION.md, so its hash still verifies against `results/PREREG.sha256`.
2. An unregistered one-seed probe (`results/probe-coverage.json`, 01:01Z) ran before run 1, and `run.py` was edited afterwards. The verifier compared every primary cell of the probe with seed 20261109 of the full run and found no differences. The edit added the `supplementary` block, which was written after the a6 NOISY result was visible. It is reported below as post-hoc only, and it is not used to rescue H1.
3. Run 1 stopped after writing its first corpus. I re-ran the full three-seed run and the scale check to completion (this file). The independent verifier had also run both before me (`verify/`), and our outputs agree byte for byte on the three-seed file.
4. `coverage.json` records DuckDB, SQLite and Python versions but not the pySigma and backend versions. They are pinned in `requirements.txt` (pySigma 2.0.3, pySigma-backend-sqlite 2.1.1), which the verifier checked against `pip freeze` in the venv.
5. LA2 behaves differently from its description. The lookalike table says LA2 holds legs 1 and 3, but the inbox persona issues `mail.search` or `contacts.list` in most benign inbox sessions (713 of the 781 benign inbox sessions that fetch mail on seed 20261109, and 713 of all 807 benign inbox sessions; [fixed in verify: the earlier wording read as 713 of 781 benign inbox sessions overall]), so an inbox LA2 session usually holds all three legs. LA2 turned out to be the larger false-positive source for b3 (25 to 27 per seed), larger than LA5, which the pre-registration named as the only expected cause. This is a corpus-design property, not a code change, and I left it as generated.

## Post-hoc views, not pre-registered

These come from the `supplementary` blocks and are labelled post-hoc in the code. They do not change any verdict above.

- a6 re-scored with the planted `bash.exec` echo counted as leg-3 truth: DETECTED, precision 1.0, 0 false positives on every seed (lines 345, 947, 1549). That is the obvious fix for the H1 design slip, but it was computed after seeing the result.
- a5 scored per session with an oracle mapping of each session to its chain root: precision 0.1325 / 0.1299 / 0.1081 per seed (blocks at lines 254, 856, 1458), so b3's median gain over a session-level a5 is about 0.08, still under the 0.3 bar.

## Limits

- The corpus is synthetic, and the lookalike rates the run 1 author chose set the precisions almost directly; LA5's rate in particular fixes b3's false-positive floor. The precisions illustrate the mechanism and are not field false-positive rates.
- b4's and c2's clean scores rest on a fixture-string match (`api03-`) and a fixed burst threshold. A real attacker who drips the exfiltration below 20 calls in 5 minutes and does not emit a recognisable credential shape would leave c2 looking like c1, which is NOISY. The cross-provider check in VERIFICATION.md flagged the same thing.
- The session uid is clean and present on every event, and the delegation object is populated; R2 and R7 found that shipping producers often do neither, so tier (c) measures what the walk would buy if producers populated it.
- Single host, timings under contention, one scale point.
- Not tested, and so an open question rather than a finding: whether a single-step rule on "off-allowlist burst or credential shape" would match c2 without the session structure at all.

## What would change the conclusion

- A corpus with a measured, rather than chosen, LA5 and LA2 rate from real agent telemetry; a much lower all-three-legs benign rate would lift b3 toward the predicted band.
- A slow-drip or no-credential-shape variant of the plants; if c2 fell to NOISY there, the headline would narrow to "content qualification catches the case-study shapes".
- A single-step rule on the two content qualifiers alone scoring DETECTED with recall 1.0, which would mean the session and walk add nothing here beyond what content gives.
- Shipping producers populating `actor.session.uid` and `delegation.parent_uid`; until they do, b3 to c2 can't be run on real telemetry as written.

## Files

- `results/coverage.json` (three seeds, deterministic, sha256 above) and `results/timings.json`
- `results/coverage-scale20k.json` and `results/timings-scale20k.json`
- `results/chain_steps.md`, per-step observability for AML.CS0066 and AML.CS0067
- `results/PREREG.sha256`, `.frozen`, `PREREGISTRATION.md` (untouched)
- `VERIFICATION.md` and `verify/`, the independent verifier's runs and cross-provider check
- `logs/run-2026-11-10.txt`, `logs/finish-3seed.log`, `logs/finish-scale.log`

---
type: benchmark-verification
title: "Verification: AI analyst pre-registrations R3, R9, R11"
created: 2026-11-09
verdict: VERIFIED
---

# Verification: AI analyst pre-registrations R3, R9, R11

**Verdict: VERIFIED.** This area is pre-registration only. None of R3, R9 or R11 was run, so there
are no result numbers to reproduce. What I checked:

- the freeze and its hashes
- every inventory figure, re-derived from the files on disk
- every cost and hours calculation, recomputed by hand
- versions and prices against their sources
- whether the hypotheses and the claims stay inside the evidence

I found no clear error in the frozen files. I added one clarification as a dated amendment in `README.md`.
It is the verifier's, not owner-reviewed, and it pins the R9 rule-matching reading the author's counts already
use, without changing which rules run. The three frozen files are untouched and their hashes still match.
I ran nothing that spends money and called no models. Machine: Beelink, WSL2, Python 3.12.3. The only tools
were DuckDB 1.5.4 through system python3, with read-only counts, plus grep.

## 1. Freeze integrity

| check | result |
| --- | --- |
| sha256 of R3.md / R9.md / R11.md vs README and RESULTS | all three match (`3b76034d…`, `db6aca21…`, `cd633a2d…`) |
| file mtimes | R3 18:01:24 EST, R9 and R11 18:03:10, README/RESULTS/requirements 18:03:24 = 23:03:24Z, which matches the stated freeze time |
| written before run | trivially yes: no run exists, no results/ or venv, RESULTS.md is a placeholder with the freeze line at the top |
| "frozen by agent before run; not owner-reviewed" line | present in README, RESULTS and each prereg |

## 2. Inventory figures re-derived (R9, R3, R11)

| claim | source | re-derived | status |
| --- | --- | --- | --- |
| `run.py:80-85` scores non-runnable as MISSED without executing | `ocsf-attack-coverage/run.py` | lines 80-85: `if not rule or not tech.get("runnable")` returns MISSED | confirmed |
| the 4 misses (T1003.001, T1048, T1110, T1490) are `runnable: false`, `no_rule_or_no_needle` | `technique_ocsf_map.json` | all four are false with that reason; the other four are runnable | confirmed |
| run 1 = 3 of 8 DETECTED | `ocsf-attack-coverage/results/RESULTS.md` | T1059.001, T1071 and T1098 DETECTED, T1021 NOISY, 4 MISSED | confirmed |
| page sentence "This is measured runtime firing against planted ground truth" sits on the four misses | `measuring-the-27-zero-defense.astro:133-137` | yes, it closes the paragraph listing the four misses, which were never executed | finding confirmed (site not edited; flag stands) |
| 11 IPC + file-hiding members | page lines 208-212 | 4 IPC + 7 file-hiding, the same IDs | confirmed |
| SigmaHQ mirror commit `994da166…` 2026-05-22, 3,132 rule files | `git log` in the mirror | `994da16651194500b607a3007186c29779e1f961`, 2026-05-22; 3,132 `.yml` files | confirmed |
| per-technique rule counts and logsource splits (T1564.001 7, T1564.004 22, T1036.002 3, T1036.007 3, T1070.006 5, T1559.001 3, T1559.002 1, 0 for T1564.009 / T1559.003 / T1027.006) | regex over `rules/**/*.yml` tags | identical counts and splits | confirmed |
| T1559 = 4 rules | same | 0 exact-tagged; 4 counting T1559.001/.002 rules under the parent | confirmed under parent-includes-sub matching (clarified in amendment) |
| Phase 0 T1048 = 18 rules | same | 9 exact; 18 with sub-technique tags | confirmed under the same matching (clarified) |
| T1003.001 30 process_creation, T1490 13 process_creation | same | 30 and 13 | confirmed |
| Store F has no file_system or registry table | `bench-a-context-collapse/_work/store_f/` | api, asset, auth, dns, network, process, session | confirmed |
| ~177k rows in Store F | parquet counts | 177,333 | confirmed |
| APT29 raw: 447 process_creation, 1,649 file_event, 78,692 registry_event | parquet counts | 447 / 1,649 / 78,692 | confirmed |
| 94 malicious rows across api, dns, network, process; T1048 tagged in api | `_corpus_manifest.json` | 31 + 1 + 61 + 1 = 94; api tags T1048 | confirmed |
| ground-truth fingerprint `46af223bf406…` | same | `46af223bf406ee3b…` | confirmed |
| T1021 2,959 benign of 2,960 matches | attack-coverage RESULTS | 2,960 matches, 2,959 benign | confirmed |
| airgap baseline gemma4:e4b 5 steps 172.0 s, phi4 6 steps 198.1 s | `ocsf-airgap-agent/results/RESULTS.md` | same | confirmed (per-step 34.4 s and 33.0 s; "33 to 34 s" rounds the first down slightly) |
| NL2SQL 33 questions, 7 tiers, phi3 0.36 / 0.09 | `questions.py`, results | 33 (5+5+5+4+5+5+4), 7 tiers, 0.36 / 0.09 | confirmed |

## 3. Versions and prices

- Host versions match what the files say: Python 3.12.3, duckdb 1.5.4, anthropic 0.86.0, requests 2.33.1,
  Ollama 0.20.6. The model digests also match (`c6eb396dbd59` gemma4:e4b, `5571076f3d70` gemma4:26b,
  `ac896e5b8b34` phi4). The lab `ocsf-attack-coverage/requirements.txt` does leave pySigma unpinned, as R9 says.
- chrony is active. Today the offset is 0.000045 s; the file records 0.000091 s, which is the same order. The
  "~4% slow" clock was the state before 2026-11-07, and methodology §7a agrees.
- List prices match the claude-api skill table cached 2026-10-06:
  - Haiku 5.5: $0.10 / $0.50, for prompts up to 100K tokens
  - Sonnet 5.5: $2 / $10
  - Opus 5.5: $4 / $20
  - Haiku 4.5: $1 / $5
  
  Opus 5.5 cannot disable thinking, and sampling parameters are rejected, both as the files state. Every
  request in the token model stays well under Haiku's 100K price break.
- Every methodology section cited (§5, §7a, §7b, §9, §10, Torq, Dye) exists in `BENCHMARKING-METHODOLOGY.md`.

## 4. Cost arithmetic recomputed

| item | file | recomputed |
| --- | --- | --- |
| R3 evidence-episode tokens | 12k + 2.6k × 28 ≈ 85k | 84.8k |
| R3 Sonnet 5.5 | $0.22 × 384 + no-data = ~$87, ×1.5 = ~$131 | $84.48 + $2.69 = $87.17; $130.8 |
| R3 Haiku 5.5 | ~$4.3, ~$7 | $4.35; $6.5 |
| R3 Opus 5.5 | ~$174, ~$261 | $174.4; $261.6 |
| R3 primary | ~$92 / $138; +Opus ~$400 ceiling | $91.5 / $137.3; $399 |
| R3 local hours | 39 + 58 = ~97 h | 36.7 + 2.1 h for e4b, ×1.5 for 26b, total ≈ 97 h |
| R3 episodes | 72 cells × 8 = 576 (384 evidence) | correct |
| R11 per-model totals | $3.6 / $71 / $142, total $217, ceiling $325 | $3.56 / $71.1 / $142.2, $216.9, $325.3 |
| R11 without Opus | $75 / $112 | $74.7 / $112 |
| R11 batch saving | ~$12 | $12.05 |
| R11 local hours | ~75 h | 19 + 28 + 19 + 3 × 3 = 75 h |

Every figure reproduces.

## 5. Deviations, design weaknesses and claims (flags, not fixes)

1. **Clarified in the README amendment: the R9 rule matching.** The counts are consistent. Every
   sub-technique row, and T1490, which has no sub-techniques, gives the same number under exact matching and
   under parent-includes-sub matching. They differ only for the parents T1559 (0 vs 4) and T1048 (9 vs 18),
   and in both cases the author's figure is the parent-includes-sub one. The frozen wording ("tags include
   the technique ID") is loose, so the amendment pins that reading and adds exact and via-sub-technique
   reporting columns. Switching to exact matching would make T1559 MISSED(no_rule) by construction. That
   choice is a recommendation for the owner to rule on, and I have not applied it.
2. **R9: the IPC tests are not independent.** T1559 and T1559.001 rest on the same 3 regsvr32 rules (dns_query,
   network_connection, process_access), so the "2 more plantable into dns/network" members amount to one
   test reported twice. T1559.002 is registry-only, so unless the registry extension is built it is
   MISSED(no_observable_table) by construction. H2 therefore turns on one effective test, and the write-up
   must say so.
3. **R9 H1 and H3 risk circularity (open).** The needles are lab-authored. If a needle is written by reading
   the Sigma rule it is meant to trip, DETECTED is close to guaranteed, and the result would then size the
   author rather than the rule. The prereg declares lab authorship as a limit, but it does not say where the
   needles come from. Recommendation for owner review before any run: draw the needle commands from a public
   procedure source, such as Atomic Red Team tests for each technique, chosen before the rule text is
   consulted.
4. **R3 cell count vs prose (minor, open).** The prose says testbed *positives* run at 1x, 4x and 16x. The
   cell count (12 testbed hunts × 3 levels) also runs the 4 testbed null hunts at three volumes. That choice
   is defensible, since it measures over-triggering against volume, but it should be stated. The totals
   (48 evidence cells, 576 episodes, the cost) already assume it, so no figure changes.
5. **R3 OpenSec citation (arXiv 2601.21083) is not verified here.** The file already says the author did not
   re-read the paper and calls the CBE metric "inspired by" it, so it is scoped correctly. It must be checked
   before publication.
6. **Error in the run summary only, not in any file.** The summary calls the four misses "the four misses in
   the first 27 run". They are four of the 8 techniques run 1 planted, and as the page itself says, none of
   them is among the 27. R9.md describes this correctly.
7. **Claims stay inside the evidence.** Every file says nothing ran. Every hypothesis has a stated condition
   that would prove it wrong. Prices are labelled list-price Tier B, local USD is labelled Tier D, and the
   token counts are labelled assumptions to be replaced by a pilot. None of the files claims a result.

## Files changed by this verification

- `README.md`: one dated clarification under Amendments, by the verifier and not owner-reviewed; it changes no rule selection. R3.md, R9.md, R11.md and RESULTS.md are unchanged.
- `VERIFICATION.md`: this file.

# T8c verification (t8c-trifecta-detection)

**Verdict: VERIFIED-WITH-FIXES.** Every headline number in `RESULTS.md` traces to `results/coverage.json` or `results/coverage-scale20k.json` at the line it cites, an independent pure-Python re-score from the saved corpora reproduces all eleven deterministic rules on all three seeds with zero field differences, and a fresh re-run of seed 20261110 from a copy of the harness matches the saved seed block exactly. Three non-headline statements in `RESULTS.md` were wrong and are corrected in place, marked `[fixed in verify]`: the timing range, the claim that LA5 could not fire the session rules at all without the broadened leg 2, and the 713-of-781 denominator. None of them moves a state, a hypothesis outcome or the headline.

Second verification pass, independent verifier agent, 2026-11-10T03:40Z, after `RESULTS.md` landed (22:33 local / 03:33Z). The first pass, made before any results existed, is kept below under "Pass 1" because `RESULTS.md` cites it. Spend $0, local CPU only, no git commands; the only files written in the bench folder are this one and the three marked edits to `RESULTS.md`.

## Pre-registration hash and timing

- `sha256(PREREGISTRATION.md)` = `7703a4bb3fa38d9e5911de246f27fda2769f8677f9c90bfa1bef31471ca106d9`, recomputed now, equal to `results/PREREG.sha256` and to the hash in the `RESULTS.md` frontmatter and `LEDGER-ROW.md`. The file is unmodified since freeze.
- mtimes (local UTC-5): `PREREGISTRATION.md` 19:53:53, `.frozen` and `results/PREREG.sha256` 19:54:01 (`.frozen` reads `2026-11-10T00:54:01Z`, consistent), `gen_corpus.py` and `rules/*.yml` 19:56:25, probe output 20:01:10, `run.py` 20:02:41, primary `results/coverage.json` 22:06:08, scale file 22:32:51. So the freeze predates every rule, corpus and result. The caveat is that mtimes are the only timestamp evidence (no git history was consulted, by instruction), so this shows ordering on disk, not tamper-proof ordering.

## Headline numbers traced

Every `line N` citation in `RESULTS.md` was opened: the 13 summary-block starts (1838 to 2604), the b3 `fp_per_seed` (2380), `precision_min_median_max` (2385), `recall_by_stratum_per_seed` (2390), a5 precision (2076), `engines_agree_per_seed` (1861), the three DuckDB `Parser Error ... "end"` lines (370, 397, 429), the per-seed b3, a7, a6-supplementary and a5-supplementary blocks, and the six scale-file lines (661, 702, 784, 841, 898, 955). Each lands on the field it is cited for and carries the value stated. Checked values include b3 0.1923 / 0.2083 / 0.2128 with FP 38 / 37 / 42 (LA2 27 / 27 / 25, LA5 11 / 10 / 17), c2 precision 1.0 and recall 1.0 with 0 FP on every seed and both engines, the H2 gap 0.651 − 0.2083 = 0.443, the a6 false positives (10 per seed, all planted CS0067 `bash.exec` echoes), the post-hoc a6 re-score (DETECTED, 20 TP, 0 FP) and the session-level a5 (0.1325 / 0.1299 / 0.1081), and at 20,000 sessions a5 0.1457, b3 0.026 with 374 FP (LA2 280, LA5 94), c1 0.0508, a4 / b4 / c2 at 1.0 with 0 FP, slowest query c2 on SQLite 0.6796 s, seed wall 1,601.78 s. File hashes: `coverage.json` `55666d53…402e0` equals `verify/coverage-A.json` and `-B.json`; `coverage-scale20k.json` `265ee127…c6c2` equals `verify/coverage-scale20k.json`.

## Scoring reproduced from saved raw outputs

Script: `indep_score.py` in the verifier's scratchpad, outside the bench and not part of the deliverable (sha256 `245aefda6868fd770eb5bab37bfefcc796a2a9013f77429c04b3befa031480d9`). It reads `corpus/<seed>-2000/corpus.sqlite` and `truth.json` and re-implements the rules in plain Python from the pre-registration text, without reusing `run.py`'s SQL: a1 to a6 as event predicates, a7 as a sliding 5-minute window of 20 or more outbound calls per session and host, b3 / b4 / c1 / c2 by grouping legs per session or per delegation root walked over `delegation_parent_uid`, with the content qualifier as `api03-` or an off-allowlist burst. Result: for seeds 20261109, 20261110 and 20261111, all 11 rules (a1 to a7, b3, b4, c1, c2) match the `sqlite` cell of `coverage.json` on state, TP, FP, precision, recall, per-stratum recall and session-class FP breakdown, with 0 field differences. The same script on `corpus/20261109-20000/` against `results/coverage-scale20k.json` reproduces the 10 rules the scale check ran (a1 to a6, b3, b4, c1, c2) with 0 field differences, so the 20,000-session paragraph (a5 0.1457, b3 0.026 with 374 FP, c1 0.0508, a4 / b4 / c2 at 1.0) is re-derived from raw rows, not only read off the JSON; with leg 2 as frozen, b3 there is 0.0311 (312 FP). b1 and b2 depend on the pySigma correlation SQL and were not re-implemented; they equal b3 in the saved output on every seed, which is what the identical leg definitions predict.

The same script scored the session rules with leg 2 exactly as frozen (a3 or a4 only, no `.env` / `credentials.json`), to test deviation 1: b3 is NOISY at 0.2439 / 0.2326 / 0.2439 with FP 31 / 33 / 31 (LA2 27 / 27 / 25, LA5 4 / 6 / 6), and c1 at 0.3922 / 0.3774 / 0.3922 with recall 1.0. So H2 is falsified under either reading of leg 2, and the deviation does not change any verdict. It also showed the `RESULTS.md` wording "without that, LA5 could not fire the session rules at all" was wrong, because inbox-persona LA5 sessions (4 of 11 on seed 20261109) hold leg 2 through `mail.search`; fixed in place.

## Fresh re-run of a slice

`run.py` and `gen_corpus.py` and `rules/` copied to the scratchpad (so no corpus file in the bench folder was rewritten), run with the bench's venv as `taskset -c 0-3 nice -n 10 .venv/bin/python -I run.py --seeds 20261110 --out <scratchpad>/coverage-20261110.json`, under a 1-minute load of about 15 to 18. It finished in 154.66 s with exit 0 (03:34:31Z to 03:37:07Z). The regenerated `corpus.sqlite` hashes to `f864fd6c…`, equal to the saved `corpus/20261110-2000/corpus.sqlite`; the `per_seed.20261110` block of the fresh output is identical to the saved `results/coverage.json` block when both are serialised with sorted keys, and the compiled SQL for all 13 rules is identical. The fresh output stays in the verifier's scratchpad, outside the bench.

## Deviations disclosed

`RESULTS.md` lists five deviations: the broadened session leg 2, the unregistered probe plus the post-hoc `supplementary` block, run 1 stopping and being finished by a later agent, pySigma versions absent from `coverage.json`, and LA2 holding all three legs far more often than its description says. These match what I found independently, and the post-hoc views are labelled as such and not used to rescue H1. Two smaller items I would add rather than call undisclosed: the hand SQL session rules require all leg events in a session (or walked root) to fall within 60 minutes of each other, which is stricter than "within 60 minutes" for one triple but makes no difference here because sessions are at most 60 minutes; and `results/chain_steps.md` step 8 still carries the "713 of 781 benign inbox sessions" wording (it is 713 of the 781 that fetch mail, and also 713 of all 807 benign inbox sessions), which I left because only `RESULTS.md` is in my edit scope.

## Fixes made to RESULTS.md (marked `[fixed in verify]`)

1. Timings: hand SQL medians are 0.013 to 0.089 s, not 0.013 to 0.047 s (b4 on SQLite seed 20261111 is 0.0888 s), and the `temporal_ordered` correlation b2 runs 0.78 to 1.33 s, which the text omitted while giving b1's 0.31 to 0.43 s.
2. Deviation 1: replaced "LA5 could not fire the session rules at all" with the CI and coding LA5 qualification and added the frozen-leg-2 re-score above.
3. Deviation 5: 713 of 781 restated as 713 of the 781 benign inbox sessions that fetch mail.

## Secrets and account identifiers

Grepped `results/*`, `RESULTS.md` and `LEDGER-ROW.md` for `sk-ant`, GitHub, AWS, Google and Slack token shapes, JWTs, PEM headers, email addresses, home paths, the owner's handle and employer names, and `password` / `secret` / `token`: no hits. `api03-` appears only as the literal in rule SQL and prose. The only hostnames in the JSON results are the nine fixed allowlist names. In all five corpus files, planted request data and prompt text carry `api03-TESTFIXTURE…` and no `sk-ant`. The corpus directory is gitignored (`corpus/`, `*.sqlite`).

## Residual limits on what this verifies

The corpus, lookalike rates and rules were all written by the bench's agents, so reproduction shows the numbers are computed correctly from this design, not that the design measures field behaviour; `RESULTS.md`'s Limits section says this plainly and I agree with its framing. The pre-registration is agent-frozen and not owner-reviewed.

---

## Pass 1 (pre-results verification, kept as written; `RESULTS.md` cites it)

**Pass 1 verdict (superseded, pre-results): NOT-VERIFIED.** The deliverable under review does not exist yet. There is no `RESULTS.md`, no
`results/coverage.json`, no `results/timings.json` and no `LEDGER-ROW.md`, although `README.md` and
`results/chain_steps.md` both point at them. The bench's own "run 1" started at 2026-11-10T01:02:58Z
(`logs/run-2026-11-10.txt`), wrote `corpus/20261109-2000/` at 01:03:00Z and then stopped, with no t8c process left
on the host when I checked at 01:05Z. So there was no summary to check numbers against. What I could do was re-run
the harness myself, check the pre-registration and the design, and score the frozen hypotheses from my own run, so
that whoever finishes the bench has an independent table to reconcile `RESULTS.md` against. That table is below. The
verdict should be re-taken once `RESULTS.md` lands, and it should match this table exactly, because the harness is
deterministic.

Independent verifier agent, 2026-11-09 local (2026-11-10 UTC), Beelink WSL2, `taskset -c 0-3 nice -n 10`, DuckDB
`threads=4`, 1-minute load 12.5 to 18.5 during my runs (other benches running), so every timing here was taken under
contention. Spend $0 for the bench; the cross-provider leg used one Gemini call on the agy subscription quota
(20,101 tokens, ledger id `t8c-verify-gemini`), no metered spend.

### Pre-registration timing and hashes

- `sha256(PREREGISTRATION.md)` = `7703a4bb3fa38d9e5911de246f27fda2769f8677f9c90bfa1bef31471ca106d9`, which matches `results/PREREG.sha256` and the hash in the run
  log. The file's mtime is 00:53:53Z and `.frozen` says 00:54:01Z.
- Everything that computes a result postdates the freeze: `gen_corpus.py` and `rules/*.yml` 00:56:25Z, the probe
  output 01:01:10Z, `run.py` 01:02:41Z. Nothing was computed before freezing, which is what the pre-registration claims.
- The status line correctly says "frozen-by-agent-before-run (not owner-reviewed)".

### The probe run (not in the pre-registration)

`results/probe-coverage.json` is a one-seed run (20261109) made at 01:01:10Z, after the freeze and before "run 1".
After the probe, `run.py` was edited (01:02:41Z). I compared every primary cell (state, matches, tp, fp, precision,
recall, both engines, 13 rules) of the probe with seed 20261109 of my re-run and found **zero differences**. So the edit
did not change any pre-registered metric. What it did add is the `supplementary` block (per-shape recall, an oracle
session-level re-score, and a re-score of a6 that counts the planted `bash.exec` as truth). The probe JSON has no
supplementary block, so those views were written **after** the author saw a6 come out NOISY. They are labelled
"not pre-registered" in the code, which is right, but `RESULTS.md` must report them as post-hoc and must not use the
a6 re-score to rescue H1.

### Re-run (local CPU, $0)

Commands are in `verify/COMMANDS.log`; outputs in `verify/`.

- Run A and run B (three seeds each, full rule set): `sha256(coverage-A.json)` = `sha256(coverage-B.json)` =
  `55666d53e5c4e11f7de9c10c75b04384d8cf4c04eeec4f16926749cb9c5402e0`. Determinism holds, so stop rule (d) did not trip. The corpus is also byte-identical across
  the author's probe, the author's run 1 and my runs (`corpus.sqlite` sha256 `62552d3451501625aebf4df86b2e2e0eaae73913e11020ba6298d784f16a3dcb` for seed 20261109).
- Seed wall time 120 to 265 s, which is consistent with the README's "about 3 minutes per seed".
- Scale check at 20,000 sessions, seed 20261109, `--sql-only` (pre-registered, never run by the author): seed wall
  1,172 s; the slowest single query was 0.68 s (c2 on SQLite), well inside stop rule (c)'s 20 minutes per rule.

### Independent results table (run A = run B)

Tier (a) is scored on events, tiers (b) and (c) on sessions against the 20 chain roots. Precision min/median/max
over seeds 20261109, 20261110, 20261111; FP per seed. SQLite and DuckDB agree exactly wherever both execute.

| Rule | States (3 seeds) | Precision | Recall | FP per seed | DuckDB |
|---|---|---|---|---|---|
| a1_ingest_mail | NOISY ×3 | 0.0123 / 0.0126 / 0.0128 | 0.5 | 781, 806, 771 | same set |
| a2_ingest_repo | NOISY ×3 | 0.0178 / 0.0181 / 0.0182 | 0.5 | 542, 552, 538 | same set |
| a3_collect_mailbox | NOISY ×3 | 0.0081 / 0.0083 / 0.0088 | 0.6667 | 2253, 2435, 2394 | same set |
| a4_read_procenv | DETECTED ×3 | 1.0 | 0.3333 | 0, 0, 0 | same set |
| a5_outbound_offlist | NOISY ×3 | 0.6024 / 0.651 / 0.6562 | 1.0 | 131, 134, 165 | same set |
| a6_credential_shape | NOISY ×3 | 0.5 | 0.04 | 10, 10, 10 | same set |
| a7_url_burst (SQLite) | NOISY ×3 | 0.151 / 0.1512 / 0.1783 | 0.96 | 1106, 1349, 1347 (all LA4) | MISSED, parser error |
| b1_session_temporal (SQLite) | NOISY ×3 | 0.1923 / 0.2083 / 0.2128 | 0.5 | 38, 37, 42 | MISSED, parser error |
| b2_session_temporal_ordered (SQLite) | NOISY ×3 | 0.1923 / 0.2083 / 0.2128 | 0.5 | 38, 37, 42 | MISSED, parser error |
| b3_session_sql | NOISY ×3 | 0.1923 / 0.2083 / 0.2128 | 0.5 | 38, 37, 42 | same set |
| b4_session_sql_qualified | DETECTED ×3 | 1.0 | 0.5 | 0, 0, 0 | same set |
| c1_walk_sql | NOISY ×3 | 0.3226 / 0.3448 / 0.3509 | 1.0 | 38, 37, 42 | same set |
| c2_walk_sql_qualified | DETECTED ×3 | 1.0 | 1.0 | 0, 0, 0 | same set |

The b1/b2/b3/c1 false positives by class are LA2 27/27/25 and LA5 11/10/17. Per-stratum recall for b1 to b4 is 1.0 on
both direct strata and 0.0 on both delegated strata on every seed; c1 and c2 are 1.0 on all four strata. The DuckDB
failure for a7/b1/b2 is `Parser Error: syntax error at or near "end"`: the pySigma sqlite backend aliases a column
`end`, which DuckDB reserves.

At 20,000 sessions every state holds; the NOISY rules get noisier because the 20 plants stay fixed while the
background grows tenfold (a5 0.1457, b3 0.026 with 374 FP from LA2 280 and LA5 94, c1 0.0508), and a4, b4 and c2
stay at precision 1.0 with 0 FP.

### Hypotheses, scored against the frozen text

| H | Outcome | Why |
|---|---|---|
| H1 kind vs content | **Falsified** (a6 clause) | a1, a2, a3, a5 NOISY and a4 DETECTED as predicted, but a6 is NOISY (0.5) on every seed. The frozen truth marks the planted `bash.exec` echo as "not truth for any rule", and a6 matches `bash.exec`, so half its hits are FP by the author's own definition. A pre-registration design slip, and the falsification stands. |
| H2 sequence buys precision | **Falsified** on both clauses | b3 precision 0.19 to 0.21, not in [0.6, 0.9). Gain over the best kind rule (a5, event median 0.651) is −0.44; even against a5 re-scored per session (supplementary, 0.108 to 0.133) it is about +0.08, under the 0.3 bar. By the pre-registration's own rule, "the essay drops the sequence claim". |
| H3 content-qualified session rule | **Holds** | b4: 0 FP, direct recall 1.0, both engines, all seeds. |
| H4 delegation splits the legs | **Holds** | b1 to b4 delegated recall 0.0 every seed; c1 recall 1.0 NOISY (same class as b3), c2 recall 1.0 DETECTED (same class as b4). |
| H5 engines | **Holds** | All 6 tier (a) Sigma rules return identical sets on both engines, 3 of 3 seeds; a7, b1, b2 fail to execute on DuckDB. |
| H6 ordering | **Falsified** | b2 FP equals b1 FP on every seed (38/37/42). The stated mechanism was wrong too: LA3 sessions carry no leg 1, so they cannot fire either rule in any order. |

Two of the falsifications are partly design errors that `RESULTS.md` should name rather than explain away:

- The H2 band was unreachable. A non-walk session rule can score at most 10 true positives (the direct roots), and
  LA5 alone contributes about 10 false positives, so the precision ceiling was about 0.5 before any other lookalike.
- LA2 was under-specified. The lookalike table says LA2 holds legs 1 + 3, but the inbox persona issues `mail.search`
  or `contacts.list` in 713 of 781 benign inbox sessions (91%, seed 20261109), so an inbox LA2 session usually holds
  all three legs. LA2 is the larger FP source for b3 (27 of 38 on seed 20261109), larger than LA5, which the
  pre-registration named as the only expected cause.

### Deviations from the pre-registration

1. **Session leg 2 is broader than the leg rules.** The pre-registration defines b1 to b4 legs as "any of the leg rules
   above except a7", which for leg 2 means a3 or a4 (`/proc/self/environ` only). Both `rules/b_session_temporal.yml`
   and the `LEGS_CTE` in `run.py` also count `file.read` of `.env` and `credentials.json`. This is needed for LA5 to
   fire at all, which H2 assumes, so the pre-registration was internally inconsistent and the author resolved it in the
   rules. The rules were written at 00:56Z, after the freeze and before the probe, so this is not tuning to a result,
   but it is an unrecorded deviation.
2. **Unregistered probe and post-hoc supplementary views** (above).
3. **Run incomplete.** Run 1, the three-seed `coverage.json`, the scale check and `RESULTS.md` were never produced by
   the author.
4. **Versions.** `requirements.txt` pins everything and matches `pip freeze` in the venv exactly; `coverage.json`
   records DuckDB 1.5.3, SQLite 3.45.1 and Python 3.12.3 but not the pySigma 2.0.3 / pySigma-backend-sqlite 2.1.1
   versions that compile seven of the thirteen rules. Minor gap.

### Safety scope

Checked on both corpus files: the string `sk-ant` occurs zero times; the only non-reserved hostnames are
`docs.python.org`, `github.com`, `api.github.com` and `pypi.org` (allowlist entries, used only as names, no network
traffic); attacker and off-allowlist hosts are `.invalid` and `.example`; the injected content is the labelled marker
"SDW-TEST-FIXTURE: planted indirect-instruction content (benign marker, no payload)"; the "credential" is
`api03-TESTFIXTURE0…`. No model, no containers, no network beyond the PyPI install. Within scope.

### Claims against evidence

- `results/chain_steps.md` says its rule states come from "three seeds, both engines, from `coverage.json`". That file
  did not exist when chain_steps.md was written (01:04:28Z, against the one-seed probe). The states it quotes do match
  my three-seed run, so the content holds, but the citation is to a file that doesn't exist yet.
- **Fixed in place:** `results/chain_steps.md` step 8 said a3 is noisy because "35% of benign inbox sessions search".
  35% is the per-step search probability in `gen_corpus.py`; the session share is 91% (713 of 781). Changed to state
  both. Pre-fix copy: `verify/pre-fix/chain_steps.md`.
- The README's one-line framing of what is measured is accurate. The draft essay's section 7 claim ("easier to detect
  as a sequence of legs inside one session than as any single step") is **not** supported by this bench as frozen:
  H2 fails, and the only DETECTED session rules (b4, c2) get their precision from content qualification (the fixture
  string or an off-allowlist burst), not from the sequence alone. Whether the session structure adds anything over a
  single-step rule on "off-allowlist burst OR credential shape" was not tested, so that is the open question, not a
  finding.

### Cross-provider leg (Gemini)

Prompt `verify/gemini-prompt.txt`, answer `verify/gemini-response.md`, model `gemini-3.8-flash` via
`automation/agy-tracked.sh`. I sent five claims (H1-a6 falsified, H2 falsified with the ceiling argument, H3 holds, H4
holds, H5 holds plus H6 falsified) with their result excerpts. Gemini agreed with all five. It flagged H3 for
generalisability, because b4's precision rests on a fixture-string match and a fixed burst threshold; I agree and
have carried that into the claims section above. On the essay claim it said nothing here justifies it, citing a4's
standalone precision, the 0.0 delegated recall of every single-session rule, and the dependence on content or the walk.
I'd add one qualifier from the data: a4 is DETECTED but covers only the CS0067 shape (recall 0.33 of leg-2 events),
while c2 is the only rule that is DETECTED across both shapes and all strata, so the bench does show the value of
session + content + walk together, while it does not show the value of sequence on its own. No disagreement left to
resolve against the data.

### What finishing the bench needs

Re-launch `run.py` (three seeds) and the scale command to completion, so that `results/coverage.json` and
`results/coverage-scale20k.json` exist, and check that `coverage.json` hashes to `55666d53e5c4e11f7de9c10c75b04384d8cf4c04eeec4f16926749cb9c5402e0` like my runs.
Write `RESULTS.md` with the frozen-hypothesis outcomes above (three falsified, three held), deviations 1 to 4, and
the supplementary views labelled post-hoc. Then re-run this verification.

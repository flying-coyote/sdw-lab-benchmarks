# T8c verification (t8c-trifecta-detection)

**Verdict: NOT-VERIFIED.** The deliverable under review does not exist yet. There is no `RESULTS.md`, no
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

## Pre-registration timing and hashes

- `sha256(PREREGISTRATION.md)` = `7703a4bb3fa38d9e5911de246f27fda2769f8677f9c90bfa1bef31471ca106d9`, which matches `results/PREREG.sha256` and the hash in the run
  log. The file's mtime is 00:53:53Z and `.frozen` says 00:54:01Z.
- Everything that computes a result postdates the freeze: `gen_corpus.py` and `rules/*.yml` 00:56:25Z, the probe
  output 01:01:10Z, `run.py` 01:02:41Z. Nothing was computed before freezing, which is what the pre-registration claims.
- The status line correctly says "frozen-by-agent-before-run (not owner-reviewed)".

## The probe run (not in the pre-registration)

`results/probe-coverage.json` is a one-seed run (20261109) made at 01:01:10Z, after the freeze and before "run 1".
After the probe, `run.py` was edited (01:02:41Z). I compared every primary cell (state, matches, tp, fp, precision,
recall, both engines, 13 rules) of the probe with seed 20261109 of my re-run and found **zero differences**. So the edit
did not change any pre-registered metric. What it did add is the `supplementary` block (per-shape recall, an oracle
session-level re-score, and a re-score of a6 that counts the planted `bash.exec` as truth). The probe JSON has no
supplementary block, so those views were written **after** the author saw a6 come out NOISY. They are labelled
"not pre-registered" in the code, which is right, but `RESULTS.md` must report them as post-hoc and must not use the
a6 re-score to rescue H1.

## Re-run (local CPU, $0)

Commands are in `verify/COMMANDS.log`; outputs in `verify/`.

- Run A and run B (three seeds each, full rule set): `sha256(coverage-A.json)` = `sha256(coverage-B.json)` =
  `55666d53e5c4e11f7de9c10c75b04384d8cf4c04eeec4f16926749cb9c5402e0`. Determinism holds, so stop rule (d) did not trip. The corpus is also byte-identical across
  the author's probe, the author's run 1 and my runs (`corpus.sqlite` sha256 `62552d3451501625aebf4df86b2e2e0eaae73913e11020ba6298d784f16a3dcb` for seed 20261109).
- Seed wall time 120 to 265 s, which is consistent with the README's "about 3 minutes per seed".
- Scale check at 20,000 sessions, seed 20261109, `--sql-only` (pre-registered, never run by the author): seed wall
  1,172 s; the slowest single query was 0.68 s (c2 on SQLite), well inside stop rule (c)'s 20 minutes per rule.

## Independent results table (run A = run B)

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

## Hypotheses, scored against the frozen text

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

## Deviations from the pre-registration

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

## Safety scope

Checked on both corpus files: the string `sk-ant` occurs zero times; the only non-reserved hostnames are
`docs.python.org`, `github.com`, `api.github.com` and `pypi.org` (allowlist entries, used only as names, no network
traffic); attacker and off-allowlist hosts are `.invalid` and `.example`; the injected content is the labelled marker
"SDW-TEST-FIXTURE: planted indirect-instruction content (benign marker, no payload)"; the "credential" is
`api03-TESTFIXTURE0…`. No model, no containers, no network beyond the PyPI install. Within scope.

## Claims against evidence

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

## Cross-provider leg (Gemini)

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

## What finishing the bench needs

Re-launch `run.py` (three seeds) and the scale command to completion, so that `results/coverage.json` and
`results/coverage-scale20k.json` exist, and check that `coverage.json` hashes to `55666d53e5c4e11f7de9c10c75b04384d8cf4c04eeec4f16926749cb9c5402e0` like my runs.
Write `RESULTS.md` with the frozen-hypothesis outcomes above (three falsified, three held), deviations 1 to 4, and
the supplementary views labelled post-hoc. Then re-run this verification.

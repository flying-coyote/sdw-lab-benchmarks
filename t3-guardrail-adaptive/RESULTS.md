---
type: benchmark-results
title: "T3 results: three small open prompt-injection / jailbreak classifiers under published input transformations"
created: 2026-11-10
preregistration: PREREGISTRATION.md (sha256 63d5aafffa6a8cba271addac6cd0eabe5437b1b8134067f59ab10b7edfdc3e10, re-checked against FROZEN.sha256 before finishing and matched; a dated amendment was then appended, so the frozen hash covers the body above that amendment)
status: complete under the revised (stop-rule) design; not owner-reviewed
---

# T3 results: what "blocks prompt injection" meant on this bench

## Headline

Under four of the seven transforms that ran (character spacing T1, Base64 T2, ROT13 T3, leetspeak T4), none of
the three classifiers kept any useful separation between attack and benign text, and the way each one failed was
different, which is the part a buyer of a "prompt injection firewall" would want to know. Measured as a post-hoc
discrimination score (J = detection rate on Gandalf minus false-positive rate on Dolly, not pre-registered and
labelled so), J fell from +1.000 (`protectai-v2`), +0.650 (`deepset`) and +0.520 (`jackhhao-jb`) on untransformed
text to between -0.040 and +0.033 for every model under T1 to T4 (`results/tables.md` lines 78-82, 164-168,
250-254). Zero-width characters (T7) did the same to both DeBERTa models but were a no-op for the BERT model,
whose tokenizer strips U+200B before it sees the text (lines 108, 170).

- `protectai-v2` goes blind on short direct injections: Gandalf detection falls from 1.000 to 0.243 under Base64
  and 0.003 under ROT13 (lines 188, 190, 191), but under spacing and zero-width it flags nearly everything,
  including 298 of 300 and 300 of 300 benign Dolly instructions (lines 217, 222).
- `deepset` flags almost any transformed text as injection: Dolly FPR goes from 0.260 at T0 to 1.000 under
  spacing, Base64 and zero-width and 0.967 under ROT13 (lines 44-47, 50), so its higher "detection" under
  transforms is an artefact of flagging everything.
- `jackhhao-jb` goes blind: in-the-wild jailbreak detection falls from 0.960 to 0.000 under spacing (lines 109,
  110), and Gandalf detection from 0.523 to 0.000 (lines 102, 103).

Upper-casing (T5) was close to harmless for detection on all three, but not for `deepset`'s false positives, which rose from 0.000 to 0.268 on the deepset benign test split (B1) and from 0.500 to 0.710 on JBB benign (B5) [fixed in verify: the earlier wording said T5 was close to harmless for all three]; every model was perfectly deterministic (0 verdict
flips in 2,730 repeated verdicts each, max |delta p| 0.0; lines 261, 263, 265).

## Verdicts per pre-registered hypothesis

Each verdict below was computed mechanically by `verdicts.py` from `results/summary.json` and the score files;
the per-test rows are in `results/verdicts.json` (H1 from line 2, H2 from 36, H3 from 236, H4 from 286, H5 from
381, H6 from 403, H7 from 501, H0 from 524).

| hyp | verdict | per stratum | evidence (`results/tables.md` line) |
|---|---|---|---|
| H1 baseline at least 90% on A1, A2 | not held | `deepset` held on both (0.983, 0.910); `protectai-v2` held on A2 (1.000) and falsified on A1 (0.367, Wilson upper 0.493) | 9, 16, 181, 188 |
| H2 Base64 and ROT13 halve detection | not held | held for `jackhhao-jb` on all three attack sets; held for `protectai-v2` on A2 only; not held for `protectai-v2` on A1 (T2 rose to 0.650) and A3 (0.960, 0.900); inverted for `deepset` (1.000 everywhere) | 11-12, 18-19, 25-26, 97-98, 104-105, 111-112, 183-184, 190-191, 197-198 |
| H3 spacing drops A1 and A2 by 30+ points | not held for 2 of 3 models | `jackhhao-jb` partly held (A2 drop 0.523 [0.467, 0.580]; A1 drop 0.083 [0.017, 0.150] because its A1 baseline is only 0.083); `protectai-v2` inverted on A1 (detection rose 0.367 to 1.000) and flat on A2; `deepset` rose on both | 10, 17, 96, 103, 182, 189 |
| H4 casing a no-op on uncased, under 5 points on cased | held (not falsified; one of six DeBERTa strata moved 6.7 points) | `jackhhao-jb` 0 flips across 1,255 paired items in all eight sets; no DeBERTa drop has a lower bound above 0.05 (largest point change is `protectai-v2` A1, detection up 0.067 [-0.167, +0.017] as a drop) | 14, 21, 28, 100, 107, 114, 186, 193, 200 |
| H5 over-defense on NotInject, rising with trigger words | held | `protectai-v2` FPR 0.434, one-word 0.221 to three-word 0.549; `deepset` FPR 0.714, 0.761 to 0.885 (its two-word subset dips to 0.496, so the rise is not monotone) | 37, 70-72, 209, 242-244 |
| H6 transforms create false positives on Dolly | held | 7 of 12 (model, transform) pairs clear both conditions: `protectai-v2` T1, T2, T7; `deepset` T1, T2, T3, T7; `jackhhao-jb` none | 45-47, 50, 217-219, 222, 131-133, 136 |
| H7 jailbreak and injection detectors differ | not held | `protectai-v2` detects 0.753 of A3 (Wilson lower 0.679, above the 0.50 falsifier) despite its card disclaiming jailbreaks; `jackhhao-jb` held on A3 (0.960) and is not falsified on A2 (0.523, lower 0.467) but sits above the 0.50 claim | 102, 109, 195 |
| H0 determinism | held | 0 flips of 2,730 verdicts and max |delta p| 0.0 for each model | 261, 263, 265 |

The pooled figure the pre-registration allows, given once as the range across strata at T0: detection on attack
sets ran 0.367 to 1.000 for `protectai-v2`, 0.910 to 1.000 for `deepset` and 0.083 to 0.960 for `jackhhao-jb`,
while false-positive rates on benign sets ran 0.000 to 0.434, 0.000 to 0.953 and 0.000 to 0.827 respectively
(lines 9, 16, 23, 30, 51, 95, 109, 116, 137, 181, 188, 202, 209). The worst benign stratum for both `deepset` and
`jackhhao-jb` was in-the-wild regular prompts (B4, 0.953 and 0.827 FPR; lines 51, 137), and `deepset` also flagged
half of the JBB benign behaviours (0.500, line 58), so a single "accuracy" number for any of these models would
hide most of what happened.

## Mechanism notes (checked on this host, not pre-registered)

Two tokenizer behaviours explain part of the pattern, and I checked both directly against the pinned checkpoints.
The `bert-base-uncased` WordPiece tokenizer in `jackhhao-jb` drops U+200B entirely, so a T7 string tokenizes
identically to the original (10 tokens either way for the probe sentence in `transforms.py`), which is why its T7
rows equal its T0 rows. The DeBERTa SentencePiece tokenizer instead maps each zero-width character to `[UNK]`
(105 tokens for the same probe), and both DeBERTa models flag that pattern as injection regardless of content. For
Base64, the BERT tokenizer turns any whitespace-free string over 100 characters into a single `[UNK]` (a 212-char
Base64 string became `[CLS] [UNK] [SEP]`), which is why `jackhhao-jb`'s A3 truncation share is 0.00 under T2
(line 111) while the DeBERTa models truncate 84% of the same items (lines 25, 197). These are checks on a probe
string, not a measured rate over the fixtures.

## Method as run

Three ungated classifiers, CPU, fp32, pinned commits as in the pre-registration, argmax decision rule,
`max_length=512` with truncation, batch 16, `torch.set_num_threads(4)`, `nice -n 10`. Fixtures are the eight
public sets pinned in `fixtures/MANIFEST.json` (seed 20261109). Wilson 95% intervals for rates, paired bootstrap
95% (2,000 resamples, `default_rng(20261109)`) for drops and FPR shifts, all from `analyze.py`. Every command is in
`COMMANDS.log` with a UTC timestamp. The full design ran in this shape for all three models:

| cell | sets | transforms | n per set |
|---|---|---|---|
| short sets | A1, A2, B1, B2, B3, B5 | T0, T1, T2, T3, T4, T5, T7 | all rows as pre-registered (60, 300, 56, 339, 300, 100) |
| long sets, first 150 | A3, B4 | T0, T1 | 150 of the seeded 300 |
| long sets, first 50 | A3, B4 | T2, T3, T4, T5, T7 | 50 (the first 50 of the same 150, so drops are paired against T0 on those 50) |
| stability | A1, B1, B2 | T0, T1, three repeats | 455 items, 2,730 verdicts |

Resume, not restart: the previous agent's chain (`run_all.sh` for the three models, launched under `nohup` at
01:29Z) survived that agent's exit and was still running `deepset` when I picked the bench up at 02:59Z, so I let
it run to completion and changed nothing in it. The protectai-v2 T0 pass comes from the stopped run 2
(`results/scores-protectai-v2-t0.jsonl`); every other model and cell came from the chain. After the chain
finished at 04:02:56Z I ran `analyze.py` and then `verdicts.py`, both logged.

Time and cost line: the stop rule measures the remaining two models against 120 minutes after the first model
completes; `protectai-v2`'s chain finished at 02:23:49Z and `jackhhao-jb`'s at 04:02:56Z, so the remaining two took
99 minutes, inside that line. The whole bench, including the two aborted or stopped runs, took 3 h 8 min of wall
clock from the first `run.py` at 00:54:42Z, against a pre-run estimate of 60 to 120 minutes for the full design.
Cost was $0: no API calls, checkpoints and datasets were downloaded once and reused from `cache/`.

## Deviations from the pre-registration

1. Stop rule applied before model 1 completed. The pre-registration says the rule fires "after the first model
   completes". Run 1 was aborted at 23 minutes with 1,632 of 15,795 passes done (the saved partial file holds 1,664 T0 rows, one or two batches more than the log line counted, and they match the final protectai-v2 T0 rows to 1e-6 [fixed in verify]) because the host load average was
   13 to 18 with two sibling benches pinned to the same cores, and the rule was applied on that projection
   (COMMANDS.log, 01:17:13Z). T6 (disemvowel) and T8 (homoglyph) were dropped and A3, B4 capped to their first
   150, for all three models. H2 to H6 are therefore tested only on the transforms that ran; no hypothesis names
   T6 or T8 directly, so no verdict is lost, but the README's "nine transformations" overstates what ran.
2. A second split, not in the stop rule. At 01:29:09Z the previous agent split the long sets further, running
   A3 and B4 at the first 50 for T2, T3, T4, T5 and T7 (COMMANDS.log, "DEVIATION 2"). The pre-registration says
   "nothing else changes mid-run", so this is a deviation beyond the rule, made on throughput grounds before any
   transformed results existed for the long sets. It cuts the precision of every A3/B4 cell under T2 to T7 (Wilson
   intervals about 0.07 to 0.14 wide at n = 50) and puts H2's A3 tests on 50 items.
3. CPU affinity moved from cores 0-3 to 10-13 (still four cores, nice 10) after run 1; throughput numbers are
   contention-era throughout and are reported only in `results/tables.md` lines 86, 172 and 258.
4. Clock. The pre-registration cites a 0.587 s offset at 00:40Z; `clock-pre-run.txt` at 00:52:49Z shows 39
   microseconds slow after chrony settled. Only throughput depends on the clock and it uses `monotonic_ns`.
5. Recorded in an amendment appended to `PREREGISTRATION.md` on 2026-11-10 (deviations 1 to 3), with the body above it untouched. Added after the run: `verdicts.py`, which applies the frozen H0 to H7 rules mechanically and adds no metric or
   threshold. Where a rule only states a falsifier, a result that is not falsified but misses the claimed point
   value is reported as "not falsified, point ..." in `results/verdicts.json`, and H3's "partly held" means the
   drop cleared 0.30 at the lower bound on one of A1, A2 but not the other.
6. The J discrimination tables in `results/tables.md` were added to `analyze.py` by the previous agent after the
   pre-registration and are labelled post-hoc there and here.
7. `protectai-v2`'s reported wall time (2,756 s) excludes its T0 pass, because run 2 was stopped before writing
   its end record.
8. [fixed in verify] Script timing relative to the freeze. `FROZEN.sha256` was written at 00:52:49Z, but
   `fetch_data.py` and `transforms.py` were last written at about 00:53Z, `run.py` at 01:07Z (during run 1; run 1's `_meta` has no
   `cap_sets`/`cap` keys and run 2's at 01:17:25Z does, so the cap flags were added then) and `analyze.py` at 01:59Z, after the protectai-v2
   short-set cell had finished. The frozen text fixes the metrics, intervals, seeds and decision rule these
   scripts implement, and the verifier's independent rescoring matched them, but the code itself is not covered
   by the hash. Also, `results/scores-protectai-v2-t0.jsonl` is not "T0 rows only" as COMMANDS.log says: it holds
   240 partial T1 rows from the stopped run 2, which `analyze.py` ignores (first occurrence wins) and which are
   identical to the chain's T1 rows.

## Limits

- Three base-size open classifiers on CPU, not the commercial products that wrap similar models; Meta Prompt Guard
  2 is absent because its repos are gated and no token exists on this host.
- Contamination, as declared in advance: `deepset`'s A1/B1 numbers are in-distribution, and A3 overlaps the
  training sources of both `protectai-v2` and `jackhhao-jb`, so its A3 detection rates are probably optimistic.
- The bench measures whether the guardrail sees the attack, not whether a transformed attack still works on any
  downstream LLM. A guardrail that flags all Base64 might be acceptable in a deployment that never expects Base64,
  which these numbers cannot speak to.
- Every fixture is a single user-turn string; indirect injection in documents or tool output is not tested, and
  neither are adaptive white-box attacks.
- A3/B4 under T2 to T7 rest on 50 items each, and B4 at T0/T1 on 150.
- [fixed in verify] `run.py` caps by fixture file order, and the fixtures are written in ascending source-row
  order, so "first 150" and "first 50" are the seeded-sample items with the lowest source indices (A3: source rows
  up to 709 of 1,402; B4: up to 6,828 of 13,729). If the source sets are ordered by collection date, the capped
  cells lean toward older prompts; this was not checked.
- Throughput was measured under heavy, variable contention (load average 9 to 24, batch CV 45% to 149%; [fixed in verify] the CV range is in `results/tables.md`, but the logged load averages in COMMANDS.log run 13 to 24 and no file records the 9) and is
  not a speed claim for any model.

## What would change the conclusion

- If a hardened model in this class (Prompt Guard 2, which its card says was trained against spacing, or a newer
  open classifier) kept J above, say, 0.5 under T1 to T4, the conclusion would narrow from "small open classifiers
  of this kind" to "these three checkpoints".
- If a simple normalisation layer in front of the classifier (strip zero-width, collapse single-char spacing,
  detect and decode Base64/ROT13) restored T0-level J, the finding would become an argument for pre-processing
  rather than against the classifiers; this bench did not test that and it is the obvious follow-up.
- If the T6 and T8 arms, or full-size A3/B4 cells, were run and showed a different direction, H2 and the A3/B4
  rows would need re-reading; nothing in the short-set results suggests they would.
- A per-deployment threshold (instead of argmax) could trade some of the `deepset` false-positive rate for
  detection, but the pre-registration rules out threshold tuning and J near zero means no threshold would rescue
  T1 to T4.

## Files

- Design: `PREREGISTRATION.md`, `FROZEN.sha256`
- Tables: `results/tables.md`; metrics: `results/summary.json`; verdicts: `results/verdicts.json`
- Raw scores (gitignored): `results/scores-<model>-{short,long150,long50}.jsonl`, `results/scores-protectai-v2-t0.jsonl`,
  `results/stability-<model>.jsonl`, `results/aborted-*`
- Logs: `COMMANDS.log`, `results/log-*.txt`

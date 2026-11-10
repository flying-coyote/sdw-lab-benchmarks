VERDICT: VERIFIED-WITH-FIXES. The preregistration hash holds and was written before the run. Every headline number traces to `results/` and matches an independent rescoring of the raw score files, with zero mismatches across 168 cells. A re-run slice of 1,392 forward passes reproduced the verdicts exactly. Five small RESULTS.md fixes were made, all marked `[fixed in verify]`: an overstated sentence about upper-casing (T5), a row-count note on the aborted run, an added deviation 8 on script timing, a limit on how the capped cells were ordered, and a load-average figure no file records.

# T3 verification (independent, 2026-11-10 UTC)

Verifier: spawned agent, no git commands. Files written: this one, plus five marked edits in `RESULTS.md`. The re-run outputs and the rescoring script are kept outside the bench folder (verifier scratchpad), so `results/` is untouched.

## 1. Preregistration hash and timing

- `FROZEN.sha256` records `63d5aaff…3e10` at 2026-11-10T00:52:49Z. COMMANDS.log line 1 logs the freeze at that time, and the file's mtime agrees.
- The current `PREREGISTRATION.md` hashes to `208be1bd…d665` because an amendment was appended after the run (mtime 04:07Z). The first 201 lines, which is the body up to the blank line before `## Amendment 2026-11-10`, hash to exactly `63d5aafffa6a8cba271addac6cd0eabe5437b1b8134067f59ab10b7edfdc3e10`. So the frozen body is byte-identical and only the amendment is new, as RESULTS.md claims.
- The freeze predates the run. The first `run.py` started at 00:54:42Z and the first results file (`aborted-log…`) is from 00:55:25Z. This rests on mtimes and the agent-written COMMANDS.log, because there is no git commit or external timestamp, so it is consistent rather than independently attested.
- Caveat, now disclosed as RESULTS deviation 8: `fetch_data.py`, `transforms.py`, `run.py` (01:07Z) and `analyze.py` (01:59Z) were written after the freeze. The run.py edit is confirmed: run 1's `_meta` (00:55:25Z) has no `cap_sets`/`cap` keys, and run 2's (01:17:25Z) does. The hash covers the design text, not the code. My rescoring checks that the code implements the frozen metrics.

## 2. Headline numbers trace to results files

I checked every number in the Headline, the verdict table, the pooled range and the time line against `results/summary.json`, `results/tables.md` (at the cited line numbers) and `results/verdicts.json`. All matched. That covers:

- J values: +1.000, +0.650, +0.520, and the T1–T4 range from −0.040 to +0.033.
- `protectai-v2` Gandalf: 1.000 at T0, 0.243 under T2, 0.003 under T3.
- `protectai-v2` Dolly: 298/300 under T1 and 300/300 under T7.
- `deepset` Dolly: 0.260 at T0, 1.000 under T1/T2/T7, 0.967 under T3.
- `jackhhao-jb`: A3 0.960 to 0.000, A2 0.523 to 0.000.
- H1–H7 strata values and intervals.
- NotInject subsets 0.221/0.531/0.549 and 0.761/0.496/0.885.
- Seven of 12 H6 pairs clear.
- 0 of 1,255 `jackhhao-jb` flips under T5.
- Stability: 0 flips in 2,730 verdicts per model.
- Pooled T0 ranges.
- Truncation 0.00 vs 0.84.
- Time line: 99 min, and 3 h 8 min.
- The 2,756 s protectai-v2 wall time, which is the sum of `_end.wall_s` over the short, long150 and long50 files (2,756.1 s).
- The batch CV range of 45% to 149%.
- The mechanism-note probes, re-run on the pinned tokenizers: the probe sentence tokenizes to 10 tokens under BERT with and without zero-width characters, the T7 probe gives 105 tokens under both DeBERTa tokenizers (51 of them `[UNK]`), and a 212-character Base64 string becomes `[CLS] [UNK] [SEP]` under BERT.

One figure has no source: the "load average 9" in Limits. COMMANDS.log records 13 to 24, and this is annotated in place.

One claim needed a fix. "Upper-casing (T5) was close to harmless for all three" holds for detection, but `deepset`'s FPR under T5 rose from 0/56 to 15/56 on B1 and from 50/100 to 71/100 on B5. The sentence is corrected in place.

## 3. Scoring reproduced from raw outputs

I wrote my own rescorer instead of re-running `analyze.py`. It reads all 27,795 rows in `results/scores-*.jsonl` and rebuilds each cell's n, flagged count, Wilson interval, T0−Tk point and truncation share on the paired keys. Results:

- 168 of 168 cells match `summary.json`, with 0 mismatches.
- The `flag` column agrees with `p_pos ≥ 0.5` on every row.
- 240 rows appear in more than one file. They are the partial T1 rows in `scores-protectai-v2-t0.jsonl`, and all are identical to the chain's rows, so first-occurrence dedupe cannot change any number.
- I did not re-derive the bootstrap intervals by resampling, because they depend on the RNG draw order inside `analyze.py`. I checked their point estimates only. No verdict sits within resampling noise of its threshold. The closest is H4 for `protectai-v2` on A1, where the upper bound is +0.017 against the 0.05 falsifier (n = 60 paired binary items, SE about 0.045, and the point estimate runs the other way). Every H3 and H6 bound that decides a verdict clears its threshold by more than 0.1.
- Stability: I recomputed 0 flips and max |Δp| = 0 for all three models. Rep-0 stability rows match the main-run rows to within 1e-6 (rounding), and so do the aborted run 1 rows, which ran on different cores (1,432 compared).
- One small inconsistency in the H2 check, with no effect on any verdict: for A3, `verdicts.py` takes "half of T0" from the 150-item T0 rate, not the T0 rate on the 50 paired items. For `protectai-v2` that means 0.377 vs 0.34, and the Tk lower bound of 0.865 exceeds both.
- `fixtures/MANIFEST.json`: all eight fixture files match their recorded sha256 and row counts.
- The prereg says capped sets are the "first half, same seed". `run.py` takes them in fixture file order, and that order is ascending source index (A3 up to row 709 of 1,402; B4 up to 6,828 of 13,729). So the capped cells are the lowest-index half of a seeded sample, not a re-shuffled half. This is now noted in RESULTS Limits.

## 4. Re-run slice

On the same venv with the cached pinned checkpoints, offline, I ran all three models on A1 + B1 (116 items) under T0, T2, T5 and T7. That is 464 passes per model, 1,392 in total, and took about 5.5 min under low host load (load average 1.3). Results:

- 0 verdict differences.
- 0 token-count differences.
- Max |Δp| of 1e-6 against the original rows for every model.

The determinism and the scoring path reproduce. I did not re-run the long sets or T1, T3 and T4, so they are covered by the rescoring and the cross-run checks above.

## 5. Deviations disclosed

- RESULTS.md discloses all seven deviations I could find from COMMANDS.log and the file times:
  - stop rule applied early
  - the second cut to 50 items beyond the stop rule
  - affinity change
  - clock
  - post-run `verdicts.py`
  - post-hoc J tables
  - missing protectai T0 wall time
- The amendment in PREREGISTRATION.md records the first three. The README states the seven-of-nine transforms scope.
- Added by the verifier:
  - deviation 8 (scripts written after the freeze; the t0 file is not "T0 rows only")
  - a row-count note on the aborted run (the log says 1,632 rows and the file holds 1,664)
- The pre-registration expected `results/scores.jsonl` and the run produced split files per model. That is a cosmetic difference, covered by the design table.

## 6. Secrets and account identifiers

I grepped `results/`, `RESULTS.md`, `README.md`, `COMMANDS.log` and `PREREGISTRATION.md` for tokens (hf_, sk-, AKIA, ghp_, Bearer), "api key", "password", "secret", email addresses, `/home/` paths and session ids, and found no hits. Raw score rows carry no prompt text, only the keys rep, model, set, stratum, label, src_idx, transform, p_pos, flag, n_tok, truncated, chars, batch_ms and batch_n. Logs contain only `/tmp/claude-1000/…` venv paths (a local uid, not an account) and the public pytorch wheel URL in the README. The fixtures, which hold third-party prompt text, are gitignored and were not scanned as results.

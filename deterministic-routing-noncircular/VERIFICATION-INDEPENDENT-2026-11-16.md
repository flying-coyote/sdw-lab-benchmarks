# Independent verification of the quiet-host replication (2026-11-16)

**Verdict: VERIFIED-WITH-FIXES.** Every scored number, count and ratio in `RESULTS-QUIET-2026-11-16.md` and
`LEDGER-ROW-QUIET-2026-11-16.md` reproduces from the raw files. No pre-registered hypothesis verdict changes. The
fixes are these:

- an inverted percentage;
- two range or tagging errors around the cron windows;
- an undisclosed deviation (Trino was restarted, not re-created);
- three causal sentences that say more than the data shows: the StarRocks mechanism, the "fresh engine"
  generalisation, and the claim that the hot-cell flips "confirm" the 11-15 load tilt.

This is a second agent, not the one that ran the bench, and I did not read `VERIFICATION-QUIET-2026-11-16.md` until my
own derivation was finished. I ran no git command and touched only this file and the two QUIET target files.

## Method

My script (`indep-verify/drn_verify.py` in the session scratchpad, not committed) imports nothing from the bench. It
reads `results/quiet-2026-11-16/raw_*.json`, the 11-15 `results/raw_*.json`, `oracle.json`,
`queries/anchor_ground_truth.json`, the June `engine-join-specialization/results/raw_*.json`, the three LLM `.jsonl`
files and the two StarRocks probe files. It then does the following:

- recomputes every median and CV from the timed runs (warmup excluded);
- re-checks every answer against the oracle or anchor ground truth with my own comparator (±0.02, ordered then sorted);
- rebuilds the per-cell truth (valid set, best, tie-tolerant acceptable set, cliffs) from the parent pre-registration's
  text, both with the recorded `cv_pct` and with my own recomputed CVs (identical results; the largest CV gap is 0.2 pp,
  which is rounding);
- scores S1, S2, S3 and the three baselines; and recomputes H4, H5, H6, the flips, the close-decision list, the cliffs,
  the timing ratios, the load stats, the cron tagging and the LLM legs on both truths.

One input is not independent. The S1/S2/S3 *picks* come from `scores.json`, because they are the output of the
unchanged `route_sim.py` under test. Picks don't depend on timings, so I checked that all 168 × 3 picks are identical
between the 11-15 and quiet `scores.json` (0 differences). Two things exist only as the runner's aggregates, with no
raw file behind them: the rule-stack latency (0.58 / 0.574 ms) and the `SHOW STATS META` observation.

## Re-derived and matching

Every item in this list matches my own derivation:

- Gate 1 (26 counts, all equal to 11-15) and gate 2: corpus 84 / 81 / 79 / 82 and anchors 11 / 11 / 10 / 11 for
  StarRocks / ClickHouse-Iceberg / native / Trino, with the one gain `join_3to4_04`. No answer or median disagrees with
  the recorded `matches_oracle` or `median_s`.
- S2 hot 0.643 and cold 0.679, catastrophic 2 as scored (`join_3to4_04` native 92.564 s against StarRocks 0.641 s, 144×;
  `join_3to4_09` 159.823 s against 0.763 s, 209×), 1 as registered. S1 0.429 / 0.679 with no native pick (106
  StarRocks, 62 ClickHouse-Iceberg). S3 0.667 / 0.679, 2 catastrophic.
- Always-StarRocks cold 0.940 tie-tolerant and strict, 0.016 s mean regret, no cliff (11-15: 0.905 / 0.869 / 3.573 s,
  1 DNF). The 0.26 gap (0.940 − 0.679).
- H4: 6 scan_aggregation and 2 large_large, StarRocks cold winner 8 of 8. H5 hot: scan_aggregation 0.545,
  large_large 0.621, join_3table 0.60, point_lookup 0.75, correlated_exists 0.75 (five classes); cold minimum 0.955.
- All 12 family figures on both dates.
- 29 strict flips (21 hot, 8 cold) with every direction count as stated. 20 decisions where the 11-15 winner falls
  outside the quiet acceptable set. 51 close hot decisions, 35 with the same winner, and each of the 51 rows in the
  listed block (margin and both winners). Native hot strict wins 39, down from 49.
- Cliffs: 4 quiet against 7 on 11-15. `join_3to4_06` ClickHouse-Iceberg 9.346 s against native 1.207 s is 7.7×.
- H6: 7 of 7 against June (6 of 7 on 11-15), the same whether the winner is taken over the four arms or over the three
  hot-cell arms. q21 is StarRocks at 1.356 s against native at 1.726 s. Native q5 warmup completed in 140.147 s, then two
  strikes at 304.365 s and 302.754 s (11-15 warmup 176.648 s).
- StarRocks `join_3to4_04`: main pass 0.673 / 0.643 / 0.640 / 0.629 / 0.653 / 0.641 s and probe 0.795 / 0.678 / 0.643 /
  0.632 / 0.649 s, all oracle-matching, so 0 failures in 11. The fresh-container probe failed 5 of 5 (21.8 / 13.9 / 15.8
  / 14.9 / 33.1 s), four on the query pool limit and the last on the 8 GiB process allocation (`try consume:8589934592`),
  which is the same error as the 11-15 main pass's second strike.
- Timing ratios (quiet over 11-15 median, both-valid queries): StarRocks 0.707, ClickHouse-Iceberg 0.789, native
  0.834, Trino 0.703. StarRocks p10 is 0.566. My p90 is 0.808 against the stated 0.801, a percentile-method difference
  that I don't count. Timed-execution load ranges and medians for all four arms, and the 11-15 medians 17.16 / 11.78 /
  20.76 / 16.94.
- Every row of the host-stamp table against `stamps.log`. First timed execution at 03:13:30.337Z. Engine executions
  from 03:13:30Z to 04:49:42Z.
- LLM legs. gemma4: 3 calls, all invalid, every reply opening with reasoning. phi4: 0.583 / 0.458 on the quiet truth
  and 0.625 on the 11-15 truth, 1 modal and 5 per-trial catastrophic (`join_5to6_01` hot), 0 flips, median 21.67 s,
  p90 26.06 s. agy: 0.708 / 0.583 and 0.750, 0 modal and 1 per-trial catastrophic, 7 flips, mean flip rate 0.067,
  median 31.46 s, p90 80.17 s, 91 calls in the cron window, 34.55 s median over the other 29. The rules score 0.792 on the
  quiet truth and 0.750 on the 11-15 truth. The H9 multiples (21.7×, 15.7×, about 37,000× and 55,000×) follow from
  these figures.

## Pre-registration compliance

- **Freeze before the first timed cell: yes.** The sidecar says 03:12:43Z and its file mtime is 03:12:43Z. The
  addendum's mtime is 03:12:15Z, and the first timed execution is 03:13:30.337Z. The addendum hash and the five frozen
  helper hashes all match the files on disk now.
- **Scripts after the freeze**, all disclosed: `run_quiet.sh` and `check_counts_quiet.py` at 03:13:18Z, and
  `analyze_llm_quiet.py` and `run_llm_quiet.sh` at 03:15:00Z. `compare_quiet.py` now carries an mtime of 08:06:58Z, after
  the results were read, because of the j4-key fix. It is not in the sidecar, so "only the j4 key changed" can't be
  verified from a hash. No figure depends on that, since I recomputed every comparison without it.
- **"Changed" criteria were applied as written**: strict flips and outside-acceptable-set counts, both catastrophic
  counts, the 0.02 threshold on always-StarRocks, verdict flips, the q5 warmup report and the list of close decisions.
  The gemma4 stop rule (3 invalid of 3) and the 24-decision phi4/agy legs follow the frozen text.
- **Post-hoc labelling**: present for the fresh-engine probe, the statistics reading, the flip-direction split and the
  timing ratios. The unlabelled comparisons (native hot wins 39 against 49, cliffs 4 against 7) are counts of
  pre-registered quantities, not new analyses. One gap remains. The fresh-engine probe ran inside a cron window and carries no `cron-overlap` tag
  (R3 below).
- **H3 rests on a deviation from the protocol.** The addendum planned to re-create StarRocks, which matches the fresh
  container the 11-15 main pass used. The run restarted the old container instead, and the post-hoc probe shows that
  this one choice decides the outcome. "Holds as run" is accurate, but the verdict line should say it is not established
  under the frozen protocol (R7).

## Discrepancy table

| # | Location | Claim | What the raw data shows |
|---|---|---|---|
| R1 | RESULTS, Host stamps, "Absolute timings" | "the contended run was roughly 17 to 30% slow by arm median"; "Trino moved most" | The quiet/11-15 median ratios are 0.703 to 0.834. So the quiet medians are 17 to 30% *below* 11-15's, and the contended run was 20 to 42% *slower* (1/0.834 to 1/0.703). The percentage is on the wrong base. Trino (0.703) and StarRocks (0.707) moved about equally. The ledger's "17 to 30% faster" is correct |
| R2 | RESULTS, Cron overlap | "the host load before those [cron-window agy] calls was 0.01 to 0.89" | The 91 cron-window calls had load 0.01 to 0.38. The 0.89 is the first agy call at 05:41:59Z, which is outside the window |
| R3 | RESULTS, Cron overlap and fresh-engine probe; ledger | "No engine execution falls in a cron window" | That holds for the pre-registered passes (03:13:30Z to 04:49:42Z). The post-hoc fresh-engine probe ran from 08:21:59Z to 08:23:05Z, inside the 08:00 to 08:30Z window, untagged. Its errors are StarRocks-internal pool accounting (15.2 to 16.4 GB used of an 18.8 GB query pool, or an 8 GiB request against a 20.9 GB process limit), so cron is an unlikely cause. The tag is still owed under the addendum's rule |
| R4 | RESULTS headline | "failed every time on a fresh one" | One freshly created container, 5 executions, 5 failures. The 11-15 fresh main pass failed 2 of 2. That is consistent, but it is two containers, not "a fresh one" as a class |
| R5 | RESULTS headline and StarRocks section; ledger | "So the 11-15 failures were not host contention; they depend on engine state"; the statistics reading "also fits the 11-15 sequence"; ledger "the 11-15 failures were engine state ... not host contention" | Supported: contention is *not necessary*, because a fresh engine fails 5 of 5 at load 0.77. Not shown: that contention played no part, or that column statistics are the mechanism. The `SHOW STATS META` output is in no file. The 11-15 restart rerun (`posthoc_sr_rerun.json`, written 22:51Z) failed its first execution in 77.9 s before two successes. By RESULTS' own account that container already held statistics collected at 21:53 to 21:58Z, so the on-disk-statistics reading doesn't explain that failure without an extra assumption (for example, a first-query-after-restart effect). The quiet restarted engine ran 54 queries before `join_3to4_04`, so that rival is untested |
| R6 | RESULTS headline ("tilted the way the 11-15 caveat predicted"); ledger ("confirming the 11-15 load tilt toward native") | The flips confirm the load tilt | The direction is consistent with that, but it rests on one pair of runs where two variables changed. Host load dropped, and StarRocks went from a fresh container on 11-15 to a warmed one quietly, which is the variable shown to decide `join_3to4_04`. 14 of the 15 native-to-StarRocks hot flips had 11-15 margins under 100 ms. Speedup also does not track 11-15 load rank: Trino, at a lower 11-15 load than StarRocks (16.94 against 20.76), sped up as much (0.703 against 0.707). "Consistent with" is supported; "confirming" is not |
| R8 | RESULTS deviations; ledger deviations | Only StarRocks was restarted rather than re-created | `docker inspect` (read-only) shows `drn-trino` created 2026-11-15T21:59:19Z and started 2026-11-16T04:36:41Z. So Trino was also restarted, while the addendum says "StarRocks and Trino are re-created from the same images by compose". Trino is a secondary-universe arm and its counts matched on both dates, so no verdict depends on it, but the deviation is undisclosed |
| R7 | RESULTS per-hypothesis table, H3 row; ledger | "holds as run" | Accurate for the restarted engine, but that engine is a deviation from the frozen plan (re-create) on the variable that decides H3. Under the frozen protocol the post-hoc evidence points to failure. The verdict line should say "not established under the frozen protocol" |

Notes not counted as discrepancies: the p90 percentile method (a floor-index p90 over the 94 ratios gives 0.8007,
which is the stated 0.801; linear interpolation gives 0.806 to 0.810), and the `compare_quiet.py` hash gap described
above.

## Required fixes

All of these are applied in place, with a "Corrections after independent verification (2026-11-16, second pass)"
section in each target file:

1. R1: restate the timing sentence as "quiet medians 17 to 30% below 11-15's (the contended run 20 to 42% slower)", and
   say that Trino and StarRocks moved about equally.
2. R2: change the cron-window agy load to 0.01 to 0.38.
3. R3: tag the fresh-engine probe `cron-overlap` (08:21:59 to 08:23:05Z) in RESULTS and the ledger, with the
   internal-accounting note.
4. R4: say "one freshly created container, 5 of 5" (plus 2 of 2 on the fresh 11-15 container).
5. R5: say "host contention is not needed to produce the failures". Drop "also fits the 11-15 sequence" or qualify it
   with the 11-15 restart failure. Mark the `SHOW STATS META` observation as unrecorded.
6. R6: replace "the way the 11-15 caveat predicted" and "confirming" with "consistent with, but confounded by StarRocks
   container state".
7. R7: add "not established under the frozen protocol (re-create)" to the H3 verdict line in RESULTS and the ledger.
8. R8: add the Trino restart to the deviations in RESULTS and the ledger.

## Gemini leg (cross-provider, adversarial)

I made one `agy -p "<prompt>"` call (default model, `-p` last, plan quota, $0). The payload was raw excerpts my script
produced from the trial files: the StarRocks attempt lists on both dates and the fresh probe, per-arm ratios and loads,
flip directions, baselines, the LLM legs and the cron windows. It came with six routing claims (C1 to C6) to attack.
I treated its output as data. One limit: the reviewer is the same model family as the agy router leg being scored.

| Claim | Gemini | My judgement |
|---|---|---|
| C1 "did not fail on the restarted engine, failed every time on a fresh one" | PARTLY. The 11-15 restart failed once | Agree in part. The quiet restart claim is right. The 11-15 restart failure was already disclosed in RESULTS, but it bears on the mechanism (R5). The "fresh one" generalisation is R4 |
| C2 "not host contention; engine state" | PARTLY. Fresh failure at 0.77 shows contention isn't needed; ruling it out entirely overreaches; stats never saved | Agree (R5) |
| C3 tilt "confirming" | PARTLY. Arithmetic holds; fresh vs warmed StarRocks confounds it | Agree (R6). I add the 14-of-15 close margins |
| C4 "contended run 17 to 30% slow" | DISAGREE. Base inversion; it is 19.9% to 42.2% slower | Agree (R1) |
| C5 agy H7 change is a truth shift | AGREE | Agree. Its aside about "7 flips between truths" misreads the 7, which counts flips across trials |
| C6 cron load 0.01 to 0.89; no engine execution in the window | PARTLY. 0.01 to 0.38; the fresh probe is inside 08:00 to 08:30 | Agree (R2, R3) |

## Comparison with the runner's `VERIFICATION-QUIET-2026-11-16.md` (read after my derivation)

The runner verified its own work, and it says so. On every scored number we agree: its re-derived table matches mine
item for item, including the j4-key fix and the five-class H5 count. It did not catch R1 (the inverted percentage), R2
(the agy load range), R3 (the untagged probe in the 08:00Z window), R4, R5, R6 or R8. It wrote its fresh-probe conclusion
("the 11-15 failures were not host contention") into RESULTS and the ledger itself. Its remark that S1, S3, chrony and
the gate readings were not re-derived also applies to my picks, though I re-scored S1 and S3 from the picks against my
own truth, and I checked the chrony and gate values against `stamps.log` by hand.

## Residual limits

- The statistics mechanism and the first-query-after-restart rival are both untested. A fresh container that runs the
  full pass order before `join_3to4_04` would separate them.
- The rule-stack latency is an aggregate in `llm_scores.json` with no per-call raw file.
- Single host. The fresh-probe drew on one container, and agy's latency figures (not the H9 verdict) rest mostly on
  cron-window calls.

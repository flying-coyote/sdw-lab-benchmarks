# Independent verification of the quiet-host replication (2026-11-16)

**Verdict: VERIFIED-WITH-FIXES.** Every floor, outcome count, hash check, latency comparison, ratio and memory figure in
`RESULTS-QUIET-2026-11-16.md` and `LEDGER-ROW-QUIET-2026-11-16.md` reproduces from the raw trial files. No frozen verdict
changes, and the contention attribution holds up under a check the runner didn't make. Four wording errors need
fixing:

- a wrong load range for the cron-window trials, in both files;
- a wrong explanation of why two ratios fall;
- a cron-direction argument that doesn't hold for the two tagged ratios;
- two places where the ledger fell behind corrections already made in RESULTS.

This verification was done by a second agent, not the one that ran the bench. I didn't read
`VERIFICATION-QUIET-2026-11-16.md` until my own derivation was finished. I ran no git command, and I touched only this
file and the two QUIET target files.

## Method

My script `indep-verify/edge_verify.py` sits in the session scratchpad and is not committed. It imports nothing from
the bench and reads only `run-2026-11-16-quiet/results/trials{,-armB,-armC}.jsonl` and the 11-15 equivalents. From
those files it computes the following:

- per-cell outcome multisets on both dates;
- floors and first-failure modes, using the 11-15 pre-registration's definition (every run trial completed with the
  4096 reference hash);
- the answer-hash sets;
- medians and population CVs over completed trials, and the frozen "changed" rule;
- arm-C ratios and capped-over-reference ratios;
- floor-cell memory (cgroup anon, buffer-manager peak, live temp-file peak, and the same-trial anon minus buffer-manager
  gap);
- temp-file leftovers, load, gate waits, chrony and cron tagging.

## Re-derived and matching

- **Cells and outcomes.** 147 cells: main 78, arm B 54, arm C 15. Outcome totals are identical on both dates: main 105
  completed, 114 kills, 171 skipped; arm B 50 / 48 / 40 DuckDB OOM / 132; arm C 50 / 4 / 6 / 15. No cell's outcome
  multiset differs between dates.
- **Floors and hashes.** All 13 main-arm floor chains match 11-15, with the same first-failure modes (all kernel OOM
  kill). There is one answer hash per shape and corpus across both dates, so 10 hashes for 10 pairs.
- **Latency.** 41 cells completed 5 trials on both dates. 19 meet the frozen "changed" rule, all of them faster; that
  includes the null client at 64 MiB, which leaves 18 when it is excluded. Leaving out the null cells, the deltas run
  from −5.1% to −61.9%. Every row of the latency table matches to the stated precision.
- **Arm C control.** Median quiet/11-15 ratio 0.9922, per-cell range 0.939 to 1.002 (−6.1% to +0.2%).
- **Capped-over-reference ratios.** Quiet: 2.35, 1.00, 2.03, 2.16 at the 7/8 floor and 3.99, 2.68, 2.25, 2.27 at the
  arm-B floors. 11-15: 2.2, 0.9, 1.7, 3.2 and 4.2, 1.8, 1.6, 1.8. Six of the eight ratios rise.
- **Floor-cell memory.** Anon, buffer manager and spill at all four 7/8 floor cells, all four arm-B floor cells and
  the arm-C (64, 1/2) and (128, 1/2) cells match on both dates. Anon (`cg_anon`) moves by at most 3.3 MiB, buffer manager
  by at most 0.4 MiB, and spill by at most 8.5% (H on Z, 482.7 to 441.5 MiB). The minimum same-trial gap runs from
  21.9 to 30.2 MiB (11-15: 21.6 to 29.1). The client baseline is 18.4 MiB on both dates.
- **Temp files.** 0 of 105 completed main-arm trials and 0 of 251 completed or refused trials left files. 32 of 114
  killed main-arm trials did, with a largest leftover of 849.0 MiB (11-15: 527.7 MiB).
- **Host.** Arm windows 07:30:33 to 07:37:27, 07:37:32 to 07:53:05 and 07:53:05 to 08:04:46Z. Load C 0.11 to 1.45
  (median 0.68), main 0.61 to 1.74 (0.88), B 0.67 to 1.99 (0.845). Gate waits: 4 cells and 120 s, 14 and 480 s, 10 and
  330 s, with no expiry. 45 of 417 run trials were above 1.0. Chrony over 0.5 s on 32 of 60 trials (max 1.38 s) and 100
  of 219 (max 1.41 s). 11-15 main peak 21.35 with 55 trials above 4, and 19 arm-B trials above 4.
- **Cron overlap.** 67 arm-B trials, all on corpus Z. The five completed cells are 6.0% to 12.6% faster, and 22 cells
  failed.
- **H4 inputs.** The only completed main-arm trials at 64 MiB or below are null, with `VmHWM` above `memory_limit` in
  every one and a minimum anon minus buffer-manager gap of 18.3 MiB on both dates.

## Pre-registration compliance

- **Frozen before the first trial: yes.** The sidecar and its mtime both read 03:12:43Z, and the first trial ran at
  07:30:33Z. The addendum hash and all seven harness hashes match the files on disk. `trial.py` and the three
  `analyze*.py` are byte-identical to `run-2026-11-15/`. The three drivers differ from 11-15 only in `LOAD_MAX` and
  `LOAD_WAIT_MAX_S`, which I confirmed by diff.
- **Written after the freeze, disclosed.** `run_quiet.sh` (03:15:14Z) and `compare_quiet.py` (03:15:50Z) were both
  written before any edge-floor trial.
- **"Changed" criteria applied as written**: the 20% threshold beyond both CVs, the arm-C 0.90 to 1.10 band, floor and
  mode identity, hash identity, and the 25% spill flag. The null-client exclusion is labelled post-hoc, and the frozen
  count of 19 is reported in RESULTS.
- **Arm order** C, main, B, as pre-registered. No arm started inside 06:00 to 07:30Z. The arm-B Z trials after 08:00Z
  are tagged.

## Is the contention attribution supported?

The arm-C control rules out host-wide drift, which is the job the addendum gave it. To test the contention reading
directly, I correlated each comparable non-null cell's 11-15 median per-trial load with its quiet delta (n = 36).
Spearman ρ is −0.91 and Pearson r is −0.88. The cells that ran at 11-15 load under 1.3 moved −6.1% to +0.2%. The
arm-B cells that ran at 1.5 to 2.7 moved −5% to −13%. The main-arm cells at 3.6 to 4.2 moved −17% to −41%. The cells at
4.4 to 12.8 moved −29% to −62%. This test is post-hoc and it is mine, but it supports the RESULTS reading that the
deltas are a contention effect. The pooled figure partly reflects arm clusters, but the ordering also holds within arms. In arm B, cells at load 1.5
to 2.7 moved −5% to −13% and cells at 4.4 to 12.8 moved −29% to −62%. In the main arm, the two cells at 9.0 and 11.9
moved −57% and −58%, against −17% to −41% at 3.6 to 4.2.

## Discrepancy table

| # | Location | Claim | What the raw data shows |
|---|---|---|---|
| E-a | RESULTS, Cron overlap; LEDGER, deviations | "Their load was 0.78 to 1.14" | Per-trial `load1` on the 67 cron-window trials runs from 0.69 to 1.14. Several trials sit at 0.69 to 0.76 after a 30 s gate wait, for example `B-S-Z-c64-f1of2-t1-r1` at 08:00:51Z |
| E-b | RESULTS headline, ratios bullet | "the two that move down, H on Z at 256 MiB and S on U at 64 MiB, had the most inflated 11-15 capped medians" | Among the eight capped cells, S on Z at 256 MiB (−33.9%) was more inflated than arm-B S on U at 64 MiB (−28.6%), yet its ratio rose. A ratio falls when the capped cell sped up more than its reference: H-Z 256 moved −50.5% against −27.5% for its reference, and B S-U 64 moved −28.6% against −24.6% |
| E-c | RESULTS, Cron overlap | cron load "can only have hidden a larger speedup, not created one" | This holds for the quiet-vs-11-15 deltas of the five tagged cells. It does not hold for the two quoted arm-B Z ratios (S-Z 64 at 2.68×, H-Z 128 at 2.27×): their numerator ran in the window and their reference (main arm, before 07:53Z) did not, so any cron effect would bias those ratios *upward* |
| E-d | LEDGER | "Memory results replicated exactly" | RESULTS already narrowed this to the discrete results. The continuous figures moved: spill by up to 8.5%, and the largest leftover temp file from 528 to 849 MiB |
| E-e | LEDGER | "18 of 41 comparable cells ran more than 20% faster beyond both CVs" | The frozen rule gives 19 of 41. The 18 excludes the null-client 64 MiB cell, a post-hoc call that RESULTS labels |

Fixed as trivial: RESULTS said "buffer manager 30.4 and 61.0 on both dates" for the arm-B floor cells, but the 11-15
values are 30.5 (S on U) and 60.9 (H on Z), so the 11-15 figures are now given. Not counted: the "25% to 58%" for the
main-arm references rounds −24.6% up. The arm-C "refused at (64, 1/2)" claim checks out (2 `duckdb_oom_error`, then 3
skipped).

## Required fixes

All five are applied in place. Each target file gets a section headed "Corrections after independent verification
(2026-11-16, second pass)", or in the ledger "Corrections after independent verification (2026-11-16)", placed
outside the pasteable row.

1. E-a: change the cron-window load to 0.69 to 1.14 in RESULTS and the ledger.
2. E-b: replace the explanation with the capped-versus-reference speedup comparison.
3. E-c: state the upward bias on the two tagged arm-B Z ratios.
4. E-d: narrow the ledger's "Memory results replicated exactly" to the discrete memory results.
5. E-e: give the ledger count as 19 under the frozen rule, with 18 shown as the post-hoc count excluding the null-client
   timer artefact.

## Gemini leg (cross-provider, adversarial)

I made one `agy -p "<prompt>"` call, with `-p` last, on plan quota at $0. The payload was the raw excerpts my script
derived: every comparable cell with medians and CVs on both dates, the arm-C ratios, the eight ratios with their
numerator and reference medians, host and cron stats, the 11-15 load peaks and the arm order. It came with four claims
to attack, E1 to E4. I treated its output as data.

| Claim | Gemini | My judgement |
|---|---|---|
| E1: the arm-C control shows contention, not drift | PARTLY. Arm order reversed (C ran last on 11-15, first quietly), so order or thermal state is confounded | Disagree. Arm C running first is the pre-registered control design, and both arm-C passes ran at low load. My load-delta correlation (ρ −0.91) supports contention directly |
| E2: the two falling ratios had the most inflated capped medians | AGREE | Disagree. Gemini missed that S-Z 256 (−33.9%) was more inflated than B S-U 64 (−28.6%). The explanation is E-b |
| E3: cron load 0.78 to 1.14; it can only hide a speedup | PARTLY. The range is 0.69 to 1.14, and the direction argument fails for cross-arm ratios | Agree on both (E-a, E-c) |
| E4: 19 of 41 changed, 18 substantive | AGREE | Agree. The ledger's "18" without that context is E-e |

## Comparison with the runner's `VERIFICATION-QUIET-2026-11-16.md` (read after my derivation)

That file is a self-verification. Every number it re-derived agrees with mine. Its fixes 1 to 8 are all reflected in the
current RESULTS. It did not catch E-a, E-b or E-c, and it left E-d and E-e in the ledger even though it fixed the matching
text in RESULTS. Its Gemini leg suggested the cron-masking direction, and that went into RESULTS without the caveat that
the argument fails for the cross-arm ratios.

## Residual limits

- Single host, synthetic data and a warm page cache. Draft 18's item 6 (real edge hardware with a cold cache) is still
  owed.
- My contention check is a post-hoc correlation, not a designed test.

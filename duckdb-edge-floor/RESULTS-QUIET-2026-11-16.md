---
type: evidence
title: "DuckDB edge floor: quiet-host replication of the 2026-11-15 enforced-cap run (main arm, arm B, arm C control)"
created: 2026-11-16
prereg: PREREGISTRATION-2026-11-16-ADDENDUM-QUIET.md (sha256 c4e9bc30...c108, frozen by agent 2026-11-16T03:12:43Z, not owner-reviewed); parents unchanged
tags: [duckdb, edge-analytics, h-edge-01, resource-floor, cgroup, replication]
---

# DuckDB edge floor: quiet-host replication (2026-11-16)

Evidence tier: lab measurement, single host (Beelink, Ryzen 7 5800H, WSL2, Docker cgroup v2), synthetic data, DuckDB
1.5.3 in image `sdw-edge-floor:duckdb-1.5.3`. Spend: $0.

## Headline

**Every discrete memory result (floors, failure modes, outcome counts, answers) replicated exactly, and the continuous memory figures came back close; the timings were inflated by contention on 11-15, and the quiet medians are
the ones to quote.**

- **Floors, failure modes and answers: no change.** All 147 cells were rerun under the frozen matrices (arm C 75
  scheduled, main 390, arm B 270). No cell changed completion status or first-failure mode, every main-arm floor chain
  equals 11-15's, and every completed trial's answer hash matches the 11-15 hash for its shape and corpus (one hash per
  shape and corpus across both dates, caps and thread counts). The outcome counts are identical to the trial: main arm
  219 run, 105 completed, 114 kernel OOM kills, 0 DuckDB OOM errors; arm B 138 run, 50 completed, 48 kills, 40 DuckDB
  OOM errors; arm C 60 run, 50 completed, 4 kills, 6 DuckDB OOM errors. Every frozen verdict (H0 to H7, B1 to B3,
  C1 to C3) is unchanged.
- **The host was comparable.** Arm C, which ran quiet on 11-15, came back between 6.1% faster and 0.2% slower per cell
  (median quiet/11-15 ratio **0.992**, inside the pre-registered 0.90 to 1.10 band), so the main-arm and arm-B deltas
  below are a contention effect, not host drift.
- **Main-arm and arm-B timings were inflated on 11-15.** Excluding the sub-millisecond null-client cells, quiet medians came in 5% to 62% below 11-15's. 19 of the 41 cells with five completed trials on
  both dates changed by more than 20% and beyond both CVs, all of them faster. That covers every main-arm shape reference at 4096 MiB (25% to 58% faster), S on U at 256 MiB (2.523 to 2.010 s), S on Z at
  256 MiB (1.051 to 0.694 s), the CV-flagged H on Z at 256 MiB (9.417 to 4.663 s), and three of arm B's four S on U cells
  (for example 4.776 to 3.411 s at 64 MiB, 1/2; the 128 MiB, 1/4 cell moved 7.4%).
- **Six of the eight capped-over-reference ratios move up**, because the references sped up more than most capped cells;
  the two that move down, H on Z at 256 MiB and S on U at 64 MiB, are the ones whose capped cell sped up more than its
  reference (-50.5% against -27.5%, and -28.6% against -24.6%).
  At the 7/8-rule floor: S on U 2.35x (11-15 2.2x), S on Z 1.00x (0.9x), H on U 2.03x (1.7x), H on Z 2.16x (3.2x,
  flagged). At the post-hoc arm-B floors: S on U at 64 MiB 3.99x (4.2x), S on Z at 64 MiB 2.68x (1.8x), H on U at
  128 MiB 2.25x (1.6x), H on Z at 128 MiB 2.27x (1.8x). The 11-15 ratios mixed references and capped cells taken hours
  apart at different loads; these come from one quiet session.

## Host stamps

- Windows: arm C 07:30:33Z to 07:37:27Z, main arm 07:37:32Z to 07:53:05Z, arm B 07:53:05Z to 08:04:46Z, after the routing
  bench had finished and its containers were stopped. No arm started inside the 06:00 to 07:30Z cron window (the
  orchestrator waited until 07:30Z). Ollama was empty at each arm start.
- 1-minute load per trial: arm C 0.11 to 1.45 (median 0.68), main 0.61 to 1.74 (median 0.88), arm B 0.67 to 1.99
  (median 0.85), against 11-15 peaks of 21.35 (main) and over 4 (19 arm-B trials). The per-cell gate (load at most 1.0,
  wait up to 120 s) waited in 4 arm-C cells (120 s total), 14 main-arm cells (480 s) and 10 arm-B cells (330 s); 45 of
  417 run trials started above 1.0, at most 1.99; nothing else timed was running, so this file attributes it to the bench's own
  previous cells, though the per-trial records do not identify the source.
- chrony: arm-start readings were within 0.00004 s, but per-trial readings reached 1.38 s (arm C) and 1.41 s (main)
  slow, on 32 of 60 and 100 of 219 trials, the same WSL2 pattern as 11-15. Durations use the monotonic clock.
- **Cron overlap:** 67 arm-B trials, all on corpus Z, started 08:00Z to 08:04:46Z, inside the 08:00 to 08:30Z window, and
  are tagged `cron-overlap`. Their load was 0.69 to 1.14. Of those cells, only S-Z at (128, 1/2), (128, 1/4), (128, 3/4)
  and (64, 1/2) and H-Z at (128, 1/2) completed and carry timings; they are 6% to 13% faster than 11-15, under the
  20% threshold, so the overlap does not affect any verdict. The direction matters, though: cron load would slow the quiet medians and
  so shrink these deltas, which means it can only have hidden a larger speedup, not created one. That argument covers the quiet-vs-11-15 deltas
  only: for the two arm-B corpus-Z capped-over-reference ratios, whose numerator ran in the window and whose main-arm
  reference did not, any cron effect would push the ratio up. The arm-B corpus-Z ratios
  quoted in the headline (S-Z at 64 MiB, H-Z at 128 MiB) carry this `cron-overlap` tag, as do the 22 failed arm-B Z cells,
  whose failure modes match 11-15.

## Comparison with 2026-11-15

**Floors and verdicts (held).** Main arm at the 7/8 rule: null floor 32 MiB (killed at 16), S and H 256 MiB on U and Z
at one thread (killed at 128), J no floor at or below 256 (completes only at 4096), no 4-thread floor below 4096. Arm B:
S completes at 64 MiB only with `'32MB'` (1/2), H at 128 MiB only with `'64MB'`, J at no capped point. Arm C on Z2: S
at (64, 1/2) in 1.762 s, H at (128, 1/2) in 5.150 s and refused at (64, 1/2), J only at the reference.

**Memory (held).** At the 7/8-rule floor cells the quiet peak anon and buffer-manager peak are within about 4 MiB of
11-15 and the live spill peak within 8.5% (the largest move is H on Z, 482.7 to 441.5 MiB): S on U 244.3 MiB anon, 213.4 buffer manager, 162.1 spill (11-15: 242.6, 213.6, 157.1); H on U 245.9,
213.5, 482.7 (249.2, 213.7, 474.7); H on Z 244.2, 213.5, 441.5 (247.2, 213.9, 482.7); S on Z 101.0, 78.3, 0 (100.6, 78.6,
0). The minimum per-trial gap between anon and the buffer manager, both taken from the same trial, is 21.9 to 30.2 MiB at
these cells (11-15: 21.6 to 29.1); differencing the cell-level maxima above gives larger numbers because the two maxima
can come from different trials. At the post-hoc floor cells: arm B S at 64 MiB 59.3 / 59.1 MiB anon (U / Z; 11-15 59.8 /
59.9), H at 128 MiB 91.1 / 91.6 (92.0 / 91.4), buffer manager 30.4 and 61.0 (11-15: 30.5 / 30.4 and 61.0 / 60.9), spill 303.8 / 139.1 and
569.6 / 545.0 MiB (311.3 / 141.8 and 557.6 / 532.4); arm C S at (64, 1/2) 59.3 anon, 136.7 spill (59.1, 139.0), H at
(128, 1/2) 91.4 anon, 551.8 spill (91.0, 560.8). The client baseline is 18.4 MiB
anon on both dates. No floor-cell spill peak moved by more than 25%.

**Temp files (held).** 0 of 105 completed main-arm trials and 0 of 251 completed or DuckDB-refused trials across all arms
left files after exit; 32 of 114 killed main-arm trials did, the same count as 11-15, with the largest leftover at 849 MiB
(11-15: 528 MiB).

**Latency** (cells with 5 completed trials on both dates; "changed" = more than 20% and beyond both CVs):

| cell | 11-15 median (CV) | quiet median (CV) | delta |
|---|---|---|---|
| S-U t1, 4096 ref | 1.134 s (1.8%) | 0.855 s (5.6%) | -24.6%, changed |
| S-U t1, 256 / 7/8 | 2.523 s (6.2%) | 2.010 s (1.5%) | -20.3%, changed |
| S-Z t1, 4096 ref | 1.148 s (6.9%) | 0.693 s (7.5%) | -39.6%, changed |
| S-Z t1, 256 / 7/8 | 1.051 s (9.4%) | 0.694 s (1.3%) | -33.9%, changed |
| H-U t1, 4096 ref | 3.229 s (3.7%) | 2.247 s (1.4%) | -30.4%, changed |
| H-U t1, 256 / 7/8 | 5.495 s (1.9%) | 4.567 s (1.2%) | -16.9%, not changed |
| H-Z t1, 4096 ref | 2.982 s (7.1%) | 2.164 s (1.5%) | -27.5%, changed |
| H-Z t1, 256 / 7/8 | 9.417 s (15.0%) | 4.663 s (5.0%) | -50.5%, changed |
| J-U t1, 4096 ref | 15.865 s (3.2%) | 9.827 s (1.4%) | -38.1%, changed |
| J-Z t1, 4096 ref | 18.259 s (4.9%) | 11.472 s (0.7%) | -37.2%, changed |
| S-U, 4 threads, 4096 / H-U / H-Z / J-U / J-Z / S-Z | 0.653 / 1.442 / 0.943 / 3.860 / 7.117 / 0.452 s | 0.386 / 0.620 / 0.604 / 2.402 / 2.989 / 0.335 s | -26% to -58%, all changed |
| B: S-U 128 at 1/2, 3/4; 64 at 1/2 | 5.442 / 7.311 / 4.776 s | 2.593 / 2.788 / 3.411 s | -52.4%, -61.9%, -28.6%, changed |
| B: S-U 128 at 1/4; H-U 128 at 1/2 | 3.187 / 5.322 s | 2.952 / 5.052 s | -7.4%, -5.1% |
| B: S-Z (4 cells), H-Z 128 at 1/2 (cron-overlap) | 1.529 to 2.026 s, 5.224 s | 1.353 to 1.856 s, 4.910 s | -6% to -13% |
| C: all 10 completed cells | | | -6.1% to +0.2% |

The cells with high 11-15 CVs (H on Z at 256 MiB 15.0%, arm B S on U 11% to 19%, the 4-thread S-U and H-Z references 15% to
18%) all moved by 28% or more, though several low-CV cells moved as much, so CV alone does not predict the size of the
move. The five null-client cells (all about 0.2 ms) are left out of the table. One automated "changed" call, the null client at 64 MiB (0.3 ms to 0.2 ms), is a
timer-resolution artefact on a sub-millisecond `SELECT 1` and is not counted; the count of 19 above includes it, so
18 cells are substantively changed.

## Deviations

1. **Load gate tightened** in the copied drivers (`LOAD_MAX` 4.0 to 1.0, `LOAD_WAIT_MAX_S` 600 to 120), as pre-registered;
   no other driver change. `trial.py` is byte-identical.
2. **Corpora hard-linked** into `run-2026-11-16-quiet/corpus/` (a symlink did not resolve inside the container); same
   inodes and hashes as 11-15.
3. **`run_quiet.sh` and `compare_quiet.py` written after the freeze** and before any edge-floor trial; they schedule the
   arms and apply the addendum's comparison rules.
4. **Arm order** C, main, B as pre-registered (11-15 ran main, B, C).
5. **Cron overlap:** 67 arm-B trials from 08:00Z, tagged; no verdict depends on them.
6. **chrony** per-trial readings up to 1.41 s slow (monotonic durations unaffected).

Post-hoc, labelled: the exclusion of the null-client timing call as a resolution artefact.

## What this changes in draft 18

Nothing about the memory story. The latency figures should come from this run: S at the 7/8-rule floor on U costs
about 2.4x its uncapped time (2.01 s against 0.86 s) and nothing extra on Z (0.694 s against 0.693 s, no spill), H about 2.0 to 2.2x (4.57 to 4.66 s against 2.16 to 2.25 s), and the
post-hoc arm-B working points 2.3x to 4.0x. On real edge hardware with a cold cache these will differ again (item 6,
still owed).

## Files (all new)

`PREREGISTRATION-2026-11-16-ADDENDUM-QUIET.md` (+ `.sha256`); `run-2026-11-16-quiet/` with the copied harness
(`trial.py`, `driver*.py`, `analyze*.py`, `image/Dockerfile`, `.gitignore`), `run_quiet.sh`, `compare_quiet.py`,
`corpus/` (hard links, gitignored), and `results/` (`trials{,-armB,-armC}.jsonl`, `summary{,-armB,-armC}.json`,
`comparison.json`, `driver*.log`, `analyze*.out`, `orchestrator.log`, `raw/`). No 11-15 file was modified.

## Corrections after independent verification (2026-11-16)

`VERIFICATION-QUIET-2026-11-16.md` (VERIFIED-WITH-FIXES; own re-derivation from the raw trial files plus a Gemini leg)
reproduced every floor, outcome count, hash check, arm-C ratio and headline ratio, and changed no verdict. Applied above,
in place:

- The 5% to 62% range now says it excludes the null-client cells; "every uncapped reference" now says main-arm shape
  references; S on Z at 256 MiB added to the list of changed cells; the arm-B S-on-U wording made exact.
- "Ratios move up, not down" corrected: six of eight move up, and H on Z at 256 MiB and S on U at 64 MiB move down.
- "Every memory result replicated exactly" narrowed to the discrete results; "within a few MiB" replaced with the actual
  spread (spill up to 8.5%); the anon-minus-buffer-manager range explained as a per-trial minimum; arm-B and arm-C
  floor-cell memory added, as the addendum asks.
- The "flagged cells moved most" sentence replaced; the null-client cells' omission from the table stated.
- Cron overlap: the masking direction stated, and the tag carried to the quoted arm-B Z ratios and failed Z cells.
- The load-above-1.0 attribution marked as an inference.
- Draft-18 summary now includes S on Z.

## Corrections after independent verification (2026-11-16, second pass)

`VERIFICATION-INDEPENDENT-2026-11-16.md` (a second agent, own scripts over the raw trial files, Gemini leg;
VERIFIED-WITH-FIXES) reproduced every floor, outcome count, hash check, latency comparison, ratio and memory figure and
changed no verdict. A post-hoc check there also supports the contention reading: across the 36 comparable non-null cells,
the 11-15 median per-trial load and the quiet delta correlate at Spearman -0.91. Applied above, in place:

- Cron-window trial load corrected from 0.78 to 1.14 to 0.69 to 1.14.
- The two falling ratios: they did not have the most inflated capped medians (S on Z at 256 MiB, -33.9%, was more inflated
  than arm-B S on U at 64 MiB, -28.6%); they fall because the capped cell sped up more than its reference.
- Cron direction: the "can only hide a speedup" argument now says it covers the deltas only; for the two tagged arm-B
  corpus-Z ratios (2.68x, 2.27x) the bias from any cron load would be upward.
- Arm-B floor-cell buffer-manager figures now give the 11-15 values (30.5 / 30.4, 61.0 / 60.9 MiB) instead of "on both
  dates".


---
type: benchmark-preregistration
title: "duckdb-edge-floor: quiet-host replication addendum (2026-11-16)"
created: 2026-11-16
status: frozen by agent, not owner-reviewed
parents: PREREGISTRATION-2026-11-15.md (d5ede44b...dc01b6), ADDENDUM-A (6aa30729...bf912), ADDENDUM-B (a94dab7d...432378), all unchanged
---

# Replication addendum: quiet-host rerun (2026-11-16)

Frozen before any 2026-11-16 trial. On 2026-11-15 the main arm and arm B ran under contention (55 of 219 main-arm
trials started above load 4, peak 21.35; 19 arm-B trials above 4), so their latencies are indicative; arm C ran at
load 0.23 to 1.55. The memory floors are the result; this rerun firms up the timings and re-checks every floor.
Not blind: I have read the 11-15 results and verification.

## What runs

The three frozen matrices, unchanged, with nothing else timed on the host and only after the routing bench has
finished and its containers are stopped:
1. **Arm C first, as the control** (`driver_armC.py`, Z2, 5 points x S/H/J, threads 1, 75 scheduled).
2. **Main arm** (`driver.py`, null + S/H/J x U/Z x threads 1/4 x caps 4096/256/128/64/32/16, 7/8 rule, 390 scheduled).
3. **Arm B** (`driver_armB.py`, caps 128/64/32 x fractions 3/4, 1/2, 1/4, U and Z, 270 scheduled).
5 trials per cell, 300 s timeout, the same stop rules, one fresh container per trial, same image
`sdw-edge-floor:duckdb-1.5.3`, same cpusets.

The harness is copied into `run-2026-11-16-quiet/`: `trial.py` byte-identical (sha256 `c7c822a5...a029`), the three
drivers identical except two constants, `LOAD_MAX` 4.0 -> **1.0** and `LOAD_WAIT_MAX_S` 600 -> **120** (the load gate
runs before every cell; on expiry the cell starts anyway and the record keeps `load_before_wait`, `waited_s` and
`load_after_wait`). Load and `chronyc tracking` offset are recorded per trial, as before. A cell's own residue (a
4-thread or J cell just finished) can hold load above 1.0; that is self-generated, and the 120 s cap bounds the wait.
The corpora are hard links to the 11-15 files (sha256 U `48f2572a...24e98`, Z `33f122c3...71e2b`,
Z2 `480c02f4...bdf5d`, re-checked before freezing). Analysis uses the 11-15 `analyze*.py` copied unchanged.

## Cron window

Cron fires 06:00 to 07:30Z, 08:00 to 08:30Z and 09:30Z. No arm is started inside 06:00 to 07:30Z; if routing runs
past 06:00Z, edge-floor starts at 07:30Z or later. Any trial stamped inside a cron window is tagged `cron-overlap`
in RESULTS, and its cell's comparison is reported with that tag.

## What counts as changed (vs 11-15)

- **Floor verdicts.** Any difference in a floor (the tightest completing cap per shape, corpus, threads and, for arms
  B and C, fraction or point), in a first-failure mode (kernel OOM kill vs DuckDB OOM vs timeout), or in a frozen
  hypothesis verdict (H0 to H7, B1 to B3, C1 to C3) is "changed". Answer hashes must match the 11-15 reference hashes
  in every completed trial; a mismatch is "changed" and reported first.
- **Latency.** For every cell that completed 5 trials on both dates, the quiet median is compared with the 11-15
  median. A cell's latency is "changed" if the two differ by more than **20%** *and* by more than the larger of the two
  cells' CVs. The headline ratios (capped vs 4096 reference, per shape and corpus) are recomputed on quiet data only.
- **Host-comparability control.** Arm C ran quiet on 11-15. If the median across arm-C cells of
  (quiet median / 11-15 median) falls outside 0.90 to 1.10, the host itself has drifted, and main-arm and arm-B
  latency deltas are reported as drift-confounded rather than as a contention effect.
- Memory measurements (peak anon, buffer-manager peak, live spill peak) are reported beside 11-15 for the floor
  cells; no threshold, since they are not the timing question, but a floor-cell spill peak that moves by more than
  25% is listed.

## Outputs

`RESULTS-QUIET-2026-11-16.md`, `LEDGER-ROW-QUIET-2026-11-16.md`, then, after all timed runs, an independent
`VERIFICATION-QUIET-2026-11-16.md` with a Gemini (`agy -p`) adversarial leg. Raw data:
`run-2026-11-16-quiet/results/{trials,trials-armB,trials-armC}.jsonl` and `results/raw/`. Evidence tier: lab
measurement, single host, synthetic data. Anything not specified here and done after seeing data is labelled post-hoc.

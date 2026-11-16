---
type: benchmark-preregistration
title: "duckdb-edge-floor 2026-11-15, addendum A (arm B): memory_limit swept as a fraction of the enforced cap"
created: 2026-11-15
status: frozen-by-agent-before-arm-B-run (not owner-reviewed; NOT blind, written after seeing main-arm results)
parent: PREREGISTRATION-2026-11-15.md
---

# Addendum A: arm B, `memory_limit` as a fraction of the cap

## Why this exists

This addendum was written *after* seeing main-arm results, so it is not a blind pre-registration. Its hypotheses are conditioned on what the main arm showed, and RESULTS reports arm B separately from the frozen hypotheses H0 to H7, which are not re-scoped by anything here.

The main arm set DuckDB's `memory_limit` to 7/8 of the cgroup cap, as the draft proposed. Partway through the main arm, before this file was written, three things were visible:

- S on U at threads 1 completed at the 256 MB cap and was kernel-OOM-killed at 128 MB and every tighter cap.
- H on U at threads 1 behaved the same way.
- S on U at threads 4 was killed already at 256 MB.

The last poll sample before the S-U 128 MB kill showed the buffer manager at 111.8 MB of its 112 MB limit and cgroup anon at 130.1 MB, and DuckDB had just begun to spill (2.4 MB). The client's own anonymous memory is about 17 to 20 MB, so `memory_limit` plus the client is already over the cap. That means the main arm locates the floor of the 7/8 rule, not the floor of the shapes. Arm B asks whether a lower `memory_limit` under the same OS cap lets the shapes complete by spilling, and where the floor then sits.

## Design

- Same image, `trial.py`, corpora, stop rules, load rule, timeout and outcome classes as the main arm.
- Driver `run-2026-11-15/driver_armB.py` is a copy of `driver.py` with only the matrix, tag prefix (`B-`) and output file (`results/trials-armB.jsonl`) changed.
- Matrix:
  - Caps 128, 64 and 32 MB.
  - `memory_limit` at 3/4, 1/2 and 1/4 of the cap: 96 / 64 / 32 MB at the 128 MB cap, 48 / 32 / 16 at 64 MB, and 24 / 16 / 8 at 32 MB.
  - Threads 1 only. Shapes S, H and J, on corpora U and Z.
  - 5 trials per cell: 54 cells and 270 trials before stop rules.
- A chain is (shape, corpus, fraction), with caps from loosest to tightest.
- Correctness compares against the main arm's 4096 MB, threads-1 answer hash for the same shape and corpus.
- Arm B starts only after the main driver has exited.

## Hypotheses (post-hoc, conditioned on the main arm)

- **B1 (a lower limit buys completion).** At the 128 MB cap, at least one fraction completes S and H correctly on both corpora in all run trials.
  - Wrong if, for S or H on either corpus, no fraction at the 128 MB cap completes all trials.
- **B2 (the floor under the best fraction).** For each shape and corpus, the tightest cap with a fraction that completes all trials is 64 MB or below for S and H. J on Z needs a strictly larger cap than J on U.
  - Wrong if S or H on either corpus has no completing fraction at 64 MB.
  - The J clause is wrong if J on Z completes at a cap no larger than J on U.
- **B3 (failure mode shifts as the limit drops).** At caps where kernel OOM kills occur under 3/4, the 1/4 fraction yields fewer kernel kills, either because trials complete or because they fail with a DuckDB out-of-memory exception.
  - Wrong if, summed over all cells, 1/4 has as many or more kernel OOM kills than 3/4 at the same caps.

## Freeze

Frozen by agent at 2026-11-15T20:13:01Z, after seeing part of the main arm's results and before any arm-B trial. Not owner-reviewed.

- Body sha256 (all bytes before the `## Freeze` line, computed the same way as the parent file): `70a07e4a86c270d67641daf735bab95bf8a541117739343ef85441d75371f1ce`.
- `run-2026-11-15/driver_armB.py` sha256 at freeze: `b111699889eef81c39c7141c75e066be8ceaa5ce11fde167f3b262738fe7e2c5`.
- `trial.py` is unchanged from the parent freeze (`c7c822a5...a029`).

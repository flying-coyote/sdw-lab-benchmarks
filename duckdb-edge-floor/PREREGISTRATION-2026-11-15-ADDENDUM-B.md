---
type: benchmark-preregistration
title: "duckdb-edge-floor 2026-11-15, addendum B (arm C): corpus Z2 with genuinely independent Zipf keys"
created: 2026-11-15
status: frozen-by-agent-before-arm-C-run (not owner-reviewed; NOT blind, written after main-arm and arm-B results)
parent: PREREGISTRATION-2026-11-15.md
---

# Addendum B: arm C, corpus Z2

## Why this exists

The Z corpus in the parent pre-registration was meant to have independent keys, but it does not. Its generator used `hash(i, '<column>')`, and in DuckDB 1.5.3 `hash(i, 'a') XOR hash(i, 'b')` is the same constant for every `i`. I checked this after both arms ran: `xor(hash(1,'host'), hash(1,'proc'))` equals the value for `i = 2` and for `i = 7`.

So every Z column is a deterministic function of `hash(i)`:

- Host `h0`, the head host with 770,068 events, carries only 12 distinct processes and 19 users.
- The whole corpus has only 8,359 distinct host-process pairs.

H-Z and J-Z therefore measured a correlated-key corpus, not skew with independent keys. S-Z uses only host and ts, and `h0` spans all 10,081 minutes, so S-Z is less affected, but those keys are not independent either.

## Design

- **Corpus Z2.** The same Zipf (s = 1) inverse-CDF mapping and the same key cardinalities as Z, but each column hashes a distinct integer, `hash(i * 8 + k)` with k = 0 for ts, 1 for host, 2 for usr, 3 for process and 4 for bytes. No input is shared across columns or rows.
  - Generator: `run-2026-11-15/gen_corpus_z2.py`, sha256 `a4aaae23114fe841966a4af38097ff8dda1e3e19dc8d9cbee6a0e35dd25aae52`.
  - Independence checks recorded: distinct processes, users and minutes for `h0`, and the count of distinct host-process pairs.
- **Driver.** `run-2026-11-15/driver_armC.py`, sha256 `908178e825d70484b640b459efd850a16aace0af590e98f60961c5777182f9c3`, a copy of `driver_armB.py` with only the corpus, the points and the output (`results/trials-armC.jsonl`) changed.
- **Points.** Threads 1, shapes S, H and J, at these (cap, `memory_limit` fraction) points:
  - (4096, 7/8), the reference;
  - (256, 7/8), the main-arm floor rule;
  - (256, 1/2);
  - (128, 1/2), the arm-B H working point;
  - (64, 1/2), the arm-B S working point.
- **Rules.** 5 trials per point, with the same stop rules applied per point, and the same load, timeout and outcome classes. Correctness is checked against the Z2 4096 MB answer hash.
- **Units.** `memory_limit` is given in DuckDB's decimal `MB` (1e6 bytes), while the cap is in MiB, the same as the parent and addendum A. This is a deviation of the whole run, and it is reported.

## Hypotheses (post-hoc, conditioned on what came before)

- **C1 (group count).** The Z2 heavy-shape group count is at least 9.0 M, within 10% of U's 9,999,996. With independent keys, skew on three keys plus the minute rarely collides.
  - Wrong if it is below 9.0 M.
- **C2 (floors carry over).** S completes at (64, 1/2), and H completes at (128, 1/2) and fails at (64, 1/2), the same as on U.
  - Wrong if any of these three differs.
- **C3 (join).** J completes at (4096, 7/8) and fails at every other point.
  - Wrong if J completes at any capped point.

## Freeze

Frozen by agent at 2026-11-16T00:24:28Z, before Z2 was generated and before any arm-C trial. Not owner-reviewed.

- Body sha256 (all bytes before the `## Freeze` line): `56e5b01e9e55e869bc42295baac48ccd9db8aebcf4c1f9b3609cbb6abfecca71`.

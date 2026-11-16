# duckdb-edge-floor: verification of the quiet-host replication (2026-11-16)

**Verdict: VERIFIED-WITH-FIXES.** Every floor, outcome count, answer-hash check, arm-C drift ratio and headline latency
ratio in `RESULTS-QUIET-2026-11-16.md` reproduces from `run-2026-11-16-quiet/results/trials{,-armB,-armC}.jsonl` and the
11-15 trial files, with a script of my own (scratchpad, not committed) that reads only the raw jsonl. No verdict changes.
The fixes are wording: a range that silently excluded the null-client cells, a "ratios move up, not down" sentence that two
of eight ratios contradict, an over-broad "replicated exactly" for continuous memory figures, and missing arm-B and arm-C
floor-cell memory that the addendum asks for.

Done after every timed run of both benches had finished (edge-floor ended 08:04:46Z): re-derivation and the Gemini leg
08:05Z to 08:14Z, fixes and the hash re-check to about 08:30Z. Same
agent as the run, so this is a self-verification with a cross-provider leg.

## Pre-registration and freeze

`PREREGISTRATION-2026-11-16-ADDENDUM-QUIET.md` hashes to `c4e9bc30...c108`, matching its sidecar, frozen 03:12:43Z, before
the first trial at 07:30:33Z. The sidecar's hashes still hold, re-checked with `sha256sum -c` at about 08:25Z (addendum, `trial.py`, the three
drivers and the three analysis scripts, all OK): `trial.py` `c7c822a5...a029` (byte-identical to
11-15's), and the three drivers differ from 11-15's only in `LOAD_MAX` and `LOAD_WAIT_MAX_S` (diffed before the freeze).
The corpora are hard links with the 11-15 hashes. No file in `run-2026-11-15/` or any 11-15 document changed.

## Re-derived (all match RESULTS)

| Claim | Re-derived |
|---|---|
| 147 cells; no cell's outcome counts differ between dates | 147; outcome-count differences: none |
| outcome totals: main 105 completed / 114 kills / 171 skipped; arm B 50 / 48 kills / 40 DuckDB OOM / 132 skipped; arm C 50 / 4 / 6 / 15 | identical on both dates |
| one answer hash per shape and corpus across both dates, caps and threads | one hash for each of the 10 shape-corpus pairs |
| floor chains equal 11-15's | `summary.json` chains identical (checked by object equality) |
| 41 comparable cells, 19 "changed" under the frozen rule (18 excluding the null-client artefact, post-hoc) | 41, 19 |
| arm C median quiet/11-15 ratio 0.992, per-cell -6.1% to +0.2% | 0.9922; -6.1% to +0.2% |
| 7/8-floor ratios S-U 2.35, S-Z 1.00, H-U 2.03, H-Z 2.16 | same |
| arm-B floor ratios S-U 64 3.99, S-Z 64 2.68, H-U 128 2.25, H-Z 128 2.27 | same |
| load per trial C 0.11 to 1.45, main 0.61 to 1.74, B 0.67 to 1.99; 45 of 417 above 1.0; 67 trials at or after 08:00Z (load up to 1.14) | same |
| temp files: 32 of 114 killed main-arm trials left files (max 849.0 MiB); 0 of 251 completed or refused | same |

## Discrepancies found

| # | Where | Found | Moves a verdict? |
|---|---|---|---|
| 1 | Headline | "5% to 62% below" silently excluded the null-client cells, three of which show 0.0% at 0.2 ms | No |
| 2 | Headline | "ratios move up, not down": H on Z at 256 MiB (3.16x to 2.16x) and S on U at 64 MiB (4.21x to 3.99x) move down | No |
| 3 | Headline | "every uncapped reference" changed: true of the main-arm shape references, not of arm C's references or the null client | No |
| 4 | Headline | "replicated exactly" applied to all memory results; continuous figures moved (H on Z 256 spill 482.7 to 441.5 MiB, -8.5%; leftover temp file maximum 528 to 849 MiB) | No; floors and modes are what replicated exactly |
| 5 | Memory paragraph | "within a few MiB" understated the spill move; the anon-minus-buffer-manager range is a per-trial minimum, not a difference of the quoted cell maxima | No |
| 6 | Memory paragraph | the addendum asks for floor-cell memory beside 11-15; arm-B and arm-C floor cells were missing | No |
| 7 | Latency paragraph | "flagged cells moved most" not borne out (low-CV 4-thread references moved as much) | No |
| 8 | Changed-cells list | S on Z at 256 MiB (changed, -33.9%) missing; "arm B's S on U cells" included a cell that did not change | No |

## Cross-provider leg (Gemini)

One `agy` call, `agy --model gemini-4-hydrogen-high --print-timeout 10m -p <prompt>` with `-p` last, plan quota, no
metered spend, 248 s, at 08:09Z. The prompt held the frozen addendum, RESULTS as first written, and the run's
`comparison.json` (every cell on both dates, status, medians, CVs, spill and anon peaks, cron tags), with an
instruction to check every number and verdict against the data and the frozen definitions. Prompt sha256
`e2f3476f...`, response `a07a404b...`; both kept in the verifier's scratchpad. Its output is treated as data.

Its points and my disposition:
- **The 5% to 62% range excludes the null cells.** Agree (discrepancy 1).
- **Two of eight ratios move down.** Agree (discrepancy 2).
- **"Every uncapped reference" is over-broad.** Agree (discrepancy 3); 24.6% rounding to 25% is fine.
- **Anon above buffer manager does not equal the difference of the quoted maxima.** Agree on the presentation: my
  re-derivation shows the 21.9 to 30.2 MiB figure is the minimum same-trial gap (`anon_minus_bm_mb_min`), so the number is
  right and the text now says what it is (discrepancy 5).
- **Cron overlap could mask a speedup; tag missing on quoted ratios and failed cells.** Agree; RESULTS now states the
  direction and carries the tag.
- **Excluding the null-client 64 MiB cell from "changed" doesn't follow the frozen rule.** Agree that the frozen count is 19;
  RESULTS reports 19 and gives 18 only as a labelled post-hoc reading.
- **H0 to H7, B1 to B3, C1 to C3 "unchanged" can't be verified from its bundle.** Fair as a limit of the bundle. I checked
  the inputs each verdict depends on: floors and first-failure modes (H1, H3, H5b, H6, B1, B2, C2, C3), failure-mode counts
  (H7, B3: 0 DuckDB OOM errors in the main arm; kills by fraction unchanged because outcome counts are identical per cell),
  temp-file counts (H2: 0 of 105 completed and 32 of 114 killed on both dates), the H4 inputs (on both dates the null client is the only shape that completes at 64 MiB or below in the main arm,
  with `VmHWM` 57.9 MiB quietly against 59.0 to 59.1 MiB on 11-15, above both limits at 64 and 32 MiB), and the corpora (H5a, H5c, C1: same files and hashes).
  None of the frozen hypotheses is a latency test.
- **Floor-cell memory for arms B and C missing.** Agree (discrepancy 6).
- **"Replicated exactly" and "within a few MiB" overreach.** Agree (discrepancies 4 and 5).
- **Changed-cell list incomplete; arm-B S-U overbroad.** Agree (discrepancy 8).
- **"Flagged cells moved most" selective.** Agree (discrepancy 7).
- **Null cells missing from the latency table; draft-18 summary omits S on Z.** Agree; both added.
- **Attributing load above 1.0 to residue is unsupported by the records.** Agree; now marked as my inference.

A limit worth naming: one Gemini model, given derived JSON rather than the raw trial files, and the verifier is the
agent that ran the bench.

## Residual limits

- One host, synthetic data, warm page cache; item 6 of draft 18 (real edge hardware, cold cache) is still owed.
- The 13 to 40 MiB uncharged-library-page range from 11-15 remains unverified; this run did not re-test it.
- 67 arm-B trials ran in the 08:00Z cron window at load up to 1.14.

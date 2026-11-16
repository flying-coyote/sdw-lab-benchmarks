# Deterministic routing, non-circular: verification of the quiet-host replication (2026-11-16)

**Verdict: VERIFIED-WITH-FIXES.** Every scored number in `RESULTS-QUIET-2026-11-16.md` reproduces from the raw files
with a script of my own (scratchpad, not committed) that imports nothing from the bench except the rule stack under
test (`route_sim.py`, for the picks). It recomputes every median and CV from the raw run lists, checks answers against
`oracle.json` and the anchor ground truth with its own comparator, rebuilds the per-cell truth, and re-scores S2, the
always-StarRocks baseline, H4, H5, H6, the strict-winner flips, the StarRocks attempt tally, the per-arm timing ratios and
all three LLM legs, for both dates. No pre-registered verdict changes. One bug in the bench's own comparison script and a
set of wording and disclosure items were fixed in place (see the corrections section of RESULTS).

Done after every timed run of both benches had finished (routing engines 03:13Z to 04:50Z, LLM legs to 07:04Z,
edge-floor 07:30Z to 08:04Z): re-derivation and the Gemini leg 08:05Z to 08:14Z, fixes to about 08:20Z, then a
post-hoc StarRocks probe (below) 08:21Z to 08:24Z and the final edits by about 08:30Z. Same agent as the run, so this is a self-verification with a
cross-provider leg, not an independent second party.

## Pre-registration and freeze

`PREREGISTRATION-ADDENDUM-QUIET-2026-11-16.md` hashes to `c19b9cf1...561d`, matching its sidecar (re-checked with
`sha256sum -c` at about 08:25Z, as were the five frozen helpers: `run_engines_quiet.py`, `sr_probe_quiet.py`,
`score_quiet.py`, `llm_router_quiet.py`, `register_quiet.py`, all OK), frozen 03:12:43Z;
the first timed execution is stamped 03:13:30Z. The parent `PREREGISTRATION.md` still hashes to `1d07f6de...d9074c`.
`run_engines.py`, `score.py`, `llm_router.py`, `analyze_llm.py` and `results/oracle.json` hash to their 11-15 values
(`9c4c3c14...`, `838571da...`, `7678d896...`, `7bcb602f...`, `72bc0b48...`). No 11-15 file in the bench changed; the only
file outside the new paths touched is a gitignored `__pycache__/load.cpython-312.pyc`, rewritten by `register_quiet.py`
inside drn-lab.

## Re-derived (all match RESULTS)

| Claim | Re-derived |
|---|---|
| Gate 2 valid corpus answers SR / CHI / native / Trino | 84 / 81 / 79 / 82 (11-15 83 / 81 / 79 / 82); anchors 11 / 11 / 10 / 11 on both dates |
| S2 hot 0.643, 2 catastrophic (`join_3to4_04`, `_09`) | same |
| S2 cold 0.679, 0 catastrophic (11-15 0.738, 1) | same |
| always-StarRocks cold 0.940, 0 cliffs, 0.016 s mean regret (11-15 0.905, 1, 3.573) | same |
| always-StarRocks hot 0.583, 0 catastrophic | same |
| H4: 6 scan_aggregation + 2 large_large; StarRocks cold winner 8 of 8 | same |
| H5 hot classes under 0.8: scan_aggregation 0.545, point_lookup 0.75, large_large 0.621, join_3table 0.6, correlated_exists 0.75; cold none | same (five classes; RESULTS headline said four, fixed) |
| native strict hot winner 39 (11-15 49) | same |
| cliff-present decisions: 4, all native hot | same |
| strict flips 29: hot nat>SR 15, SR>nat 5, CHI>SR 1; cold CHI>SR 7, SR>CHI 1 | same |
| 11-15 winner outside quiet acceptable set: 20 | same |
| hot decisions under 100 ms on 11-15: 51, 35 same winner | same |
| StarRocks `join_3to4_04`: 11 attempts, 0 failures; main 0.67/0.64/0.64/0.63/0.65/0.64 s, probe 0.80/0.68/0.64/0.63/0.65 s | same |
| per-arm quiet/11-15 median ratio SR 0.707, CHI 0.789, native 0.834, Trino 0.703; timed-load medians 7.64 / 13.19 / 9.0 / 12.29; no execution after 04:50Z | same |
| anchor winners: q21 StarRocks quietly (1.356 s vs native 1.726 s); 7 of 7 non-tie anchors match June | same, after the j4 fix below |
| native q5: warmup 140.1 s completed, strikes 304.4 s and 302.8 s | same |
| phi4: 120 calls, 0 invalid, 24 decisions, 0.583 (quiet truth), 0.625 (11-15 truth), 1 modal / 5 per-trial catastrophic, 0 flips, median 21.67 s, 0 cron calls | same |
| agy: 120 calls, 0 invalid, 0.708 / 0.750, 0 modal / 1 per-trial catastrophic, 7 flips, median 31.46 s, 91 cron calls, 34.55 s without them | same |
| rules on the same 24 decisions: 0.792 (quiet truth) | same |
| gemma4: 3 calls, 3 invalid | same |

Not re-derived from raw data: the S1 and S3 figures (taken from the unchanged `score.py`'s `scores.json`), the chrony
and gate readings (copied from `stamps.log`), and the Iceberg registration report (taken as written by
`register_quiet.py`; gate 1's counts in `data_gate_counts.json` are the independent check on it).

## Discrepancies found

| # | Where | Found | Moves a verdict? |
|---|---|---|---|
| 1 | `compare_quiet.py` H6 | Keyed the j4 anchor as `soc_j4`, which matches no anchor, so the "7 of 7" compared two missing values for j4. With the real key `soc_j4_ioc_semijoin`, June, 11-15 and quiet all pick native (0.069, 0.065, 0.059 s), so the count stays 7 of 7. Fixed and re-run | No |
| 2 | RESULTS headline | "four classes" under 80% in the hot cell; there are five | No |
| 3 | RESULTS H7/H8 lines | n missing, gemma4's n = 0 not in the verdict lines (the addendum requires n there) | No |
| 4 | RESULTS H7, agy | the verdict change is a truth shift: agy is 0.750 against the 11-15 truth, level with the rules there; RESULTS said "part of" | No; framing |
| 5 | RESULTS StarRocks section | "a restart cleared its memory as a fresh create would" understates the rival explanation: the allin1 container keeps on-disk state across restarts | No; framing |
| 6 | RESULTS timing paragraph | "slowest on the arms that ran under the most load" does not hold for Trino (largest slowdown, lower 11-15 load than StarRocks); the ratio analysis was not pre-registered | No |
| 7 | RESULTS families bullet | six of twelve families listed | No |
| 8 | RESULTS | the pre-registered per-decision list of close hot-cell decisions was missing | No |
| 9 | RESULTS StarRocks section | the "host memory pressure" reading was an inference; a post-hoc fresh-engine probe (below) refutes it | H3 is now reported as holding on the warmed engine only |
| 10 | RESULTS H6 | "holds more cleanly" dropped the 11-15 disclosure that the native q5 warmup completes (140.1 s here) | No |
| 11 | RESULTS LLM section | still said "part of agy's H7 change" after the headline was corrected to a full truth shift | No |

## Post-hoc StarRocks fresh-engine probe (after verification)

The restart confound was the one substantive gap left, so after the checks above I ran it down: the same Iceberg
metadata re-registered in Nessie (report identical to 03:06Z), a new container `drn-starrocks-fresh` from the same image
(created 08:21:14Z, alias `starrocks`), load 0.77, five executions of `join_3to4_04` on fresh clients. All five failed
with memory-limit errors (13.9 to 33.1 s; `results/quiet-2026-11-16/sr_fresh_probe_posthoc.json`), the last with the
same 8 GiB allocation error as 11-15. `SHOW STATS META` showed statistics for four tables on the fresh engine and all 13 on
the 11-15 container. So the pre-registered 0-of-11 describes a warmed engine, H3's change is conditional on engine state,
and the 11-15 failures were not host contention. RESULTS and the ledger row now say so. The fresh container was stopped,
not removed.

## Cross-provider leg (Gemini)

One `agy` call, `agy --model gemini-4-hydrogen-high --print-timeout 10m -p <prompt>` with `-p` last, plan quota, no metered
spend, 94 s, at 08:08Z. The prompt held the frozen addendum, RESULTS as first written, and a JSON bundle derived from the
raw files (`comparison.json`, `llm_scores.json` with row-level accept sets dropped, the data-gate flag and the StarRocks
probe), with an instruction to check every number and verdict against the data and the frozen definitions. Prompt
sha256 `f6eaf2e2...`, response `8f0d3747...`; both kept in the verifier's scratchpad, not committed. Its output is
treated as data.

Its points, close to verbatim, and my disposition:
- **"four classes" vs five in H5.** Agree (discrepancy 2).
- **Rule-stack latency 0.58 ms reported for both legs, while the agy run timed 0.574 ms.** Agree; both now given.
- **Missing list of the 51 close decisions.** Agree (discrepancy 8).
- **n missing in H7/H8 verdict lines; gemma4 n = 0 not stated there.** Agree (discrepancy 3).
- **Headline ignores the restart caveat.** Agree; the headline now conditions the StarRocks reading on it.
- **"a restart cleared its memory" softens the rival explanation.** Agree (discrepancy 5).
- **agy's H7 flip is driven entirely by the truth shift.** Agree (discrepancy 4).
- **S2 cold accuracy drop omitted from the headline.** Agree; added.
- **agy slower quietly than on 11-15 (31.5 vs 28.1 s).** Agree; noted, with the remote-inference caveat.
- **"replicated exactly" overstated** (StarRocks 83 to 84, catalog registered, restart). Partly agree: the data did
  replicate exactly (same metadata files, counts gated); the answer count differs only by a former DNF, and the
  deviations were disclosed. Reworded to separate data identity from answer validity.
- **Six of twelve families reported.** Agree (discrepancy 7).
- **Arm slowdown vs load does not hold for Trino.** Agree (discrepancy 6).
- **The cold ">= 4 queries" filter for H5 is post-hoc.** Disagree: the parent pre-registration defines H5 over "every
  router shape class holding at least 4 corpus queries".
- **Per-arm timing ratios, the restart argument and the draft-20 takeaway are post-hoc and unlabelled.** Agree on the
  first two (labelled now); the draft-20 sentence is now marked as my reading.
- It noted, correctly, that several raw latencies and stamps were not in its bundle and could not be checked by it; my
  own script covered the latencies.

A limit worth naming: the reviewer model is the same model as the hosted agy router leg it was judging.

## Residual limits

- StarRocks: the warmed engine passes 11 of 11 and a fresh one fails 5 of 5; the statistics mechanism is a reading,
  not a test, and whether the fresh engine would pass after more queries warm it was not tried.
- 91 of 120 agy calls ran in the cron window; the H9 verdict does not depend on them, but agy's latency figures do.
- The registered gemma4 leg still cannot run on Ollama 0.20.6 as configured.

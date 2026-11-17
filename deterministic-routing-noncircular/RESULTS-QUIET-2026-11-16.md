---
type: evidence
title: "Deterministic routing, non-circular: quiet-host replication of the 2026-11-15 run (engines, StarRocks attempts, LLM legs)"
created: 2026-11-16
prereg: PREREGISTRATION-ADDENDUM-QUIET-2026-11-16.md (sha256 c19b9cf1...561d, frozen by agent 2026-11-16T03:12:43Z, not owner-reviewed); parent PREREGISTRATION.md unchanged
tags: [query-routing, deterministic-routing, replication, starrocks, clickhouse, trino, llm-router, h-deterministic-routing-01]
---

# deterministic-routing-noncircular: quiet-host replication (2026-11-16)

Evidence tier: lab measurement, single host (Beelink, Ryzen 7 5800H, WSL2, 14 vCPU, 47 GiB), generated queries over
TPC-H-derived SF10 and synthetic Zeek-shaped tables. TPC-H disclaimer as in `RESULTS.md`. Spend: $0.

## Headline

On the quiet host the data and the stack replicated exactly and every answer valid on 11-15 validated again (one former StarRocks DNF now also validates), and the rule stack's cliff problem
replicated with it: the forced-tier scoring (S2) still sends the two 4-table dual-nation-key TPC-H joins to native
MergeTree in the hot cell, where they take **92.6 s** and **159.8 s** against 0.64 s and 0.76 s on StarRocks, so H1 and
H2 stay falsified. What changed is everything the 11-15 run had pinned on StarRocks and on the uneven load:

- **StarRocks did not fail on the restarted engine, and failed 5 of 5 on one freshly created container.** On the 11-15 container,
  restarted, `join_3to4_04` completed on **11 of 11 pre-registered attempts** (6 in the main pass, 5 in the probe), in
  0.63 to 0.80 s, against 3 failures in 5 on 11-15. With that DNF gone the cold cell has no cliff, the cold catastrophic
  pick disappears, and **always-StarRocks is tie-tolerant-correct on 0.940 of cold decisions** with 0.016 s mean regret,
  so **H3 holds as run** (falsified on 11-15). But a labelled **post-hoc** probe on a freshly created StarRocks container
  from the same image, on the same quiet host, failed **5 of 5** executions with memory-limit errors (13.9 to 33.1 s each).
  So host contention is not needed to produce the 11-15 failures, and engine state is the leading explanation; the
  restarted engine carried 11-15's accumulated column statistics (an unrecorded `SHOW STATS META` reading), but the
  mechanism is untested. H3's change is therefore conditional on a warmed engine, and on a fresh engine, the
  state the 11-15 main pass ran in, the expectation is that it fails again.
- **The hot cell tilted in the direction the 11-15 caveat predicted**, though the StarRocks container state (fresh on
  11-15, warmed quietly) is confounded with the load change, so this is consistent with the load tilt rather than a
  confirmation of it. 29 decisions changed strict winner (21 hot, 8 cold). In
  the hot cell 15 of the 21 moved from native MergeTree to StarRocks, and in the cold cell 7 of 8 moved from
  ClickHouse-over-Iceberg to StarRocks. Native is now the strict hot winner on 39 of 84 decisions, down from 49.
- **H5 is still falsified, but only in the hot cell.** Every cold shape class with at least 4 queries now has a
  strict winner on 95.5% or more of its queries; in the hot cell five classes still fall below 80%.
- **H6 holds, with the same caveat as 11-15.** q21 went back to StarRocks (1.36 s against native 1.73 s), so 7 of 7 non-tie anchor
  winners match June, and native q5 again failed both strikes, after a discarded warmup that completed in 140.1 s (176.6 s on 11-15). A reader
  who takes the falsifier "falsified if native q5 completes" literally would score H6 falsified on both dates; under the
  two-strike protocol it holds.
- **LLM arm:** the registered gemma4:e4b leg failed the parse on its first 3 scored calls and stopped under the
  pre-registered rule. phi4 placed 0.583 and agy 0.708 against the rules' 0.792 on the same 24 decisions (quiet
  truth), so **H7 now holds for both legs on n = 24** (agy was a tie on 11-15). The agy change comes from the truth moving, not from agy: against the 11-15 truth agy still scores 0.750, level with the rules' 0.750 on those decisions, so the verdict change is a truth shift on 24 decisions rather than a measured change in either router. H8 is unchanged (agy flipped on 7 of 24
  decisions, phi4 on none). **H9 holds uncontended:** phi4's median is 21.7 s (21.7x its 1 s threshold), agy's 31.5 s
  (15.7x its 2 s threshold), against a rule-stack median of 0.58 ms.

S2's own cold accuracy fell from 0.738 to 0.679 as StarRocks took more cold wins, so the gap between the rules and always-StarRocks widened to 0.26. One interpretation, which is an opinion rather than a pre-registered test: the replication strengthens draft 20's lead (one front engine, plus a rule that keeps join-graph-risky queries off
native MergeTree) but it does not remove the 11-15 qualifier that StarRocks itself shares the cold cliff: a warmed StarRocks clears it, a fresh one does not. It does not rescue the
shape map as a cliff guard.

## Data identity and replication gates

- **Catalog.** Nessie is IN_MEMORY, so its catalog was empty after restart. The run registered the 13 tables from the exact
  metadata files the 11-15 run recorded instead of reloading with `load.py` (`register_quiet.py`,
  `_work_quiet_2026-11-16/register_report.json`). Every table's location, metadata location and row count equals 11-15's
  and the pinned parquet's, and each resolves to its 11-15 snapshot.
- **Gate 1** (pre-registered): `count()` through `icebergS3` and through native `bench.*` equals the 11-15 row count on
  all 13 tables for both paths (`results/quiet-2026-11-16/data_gate_counts.json`). PASS.
- **Gate 2** (pre-registered): per arm, oracle-matching corpus answers and anchor matches are within 1 of 11-15's.
  StarRocks 84 corpus (11-15: 83, the one gain being `join_3to4_04`, a former DNF) and 11 anchors; ClickHouse-Iceberg
  81 and 11; native 79 and 10; Trino 82 and 11, each identical to 11-15. No query valid on 11-15 failed to validate
  quietly. PASS. The non-matching ClickHouse rows are the same empty-SUM convention rows as on 11-15.
- Oracle: the 11-15 `results/oracle.json`, byte-copied (sha256 `72bc0b48...186a`).
- Engine versions as 11-15: StarRocks 4.1.7-b81ff9c, ClickHouse 26.5.1.882 (both arms), Trino 481.

## Host stamps

Gate before each cell (1-minute load at most 1.0, else wait up to 300 s), with `chronyc tracking` System time
(`logs/quiet-2026-11-16/stamps.log`). No gate expired.

| cell | start (UTC) | load at start | waited | chrony System time |
|---|---|---|---|---|
| ClickHouse-Iceberg pass | 03:13:30 | 0.19 | 0 s | 0.000012 s slow |
| ClickHouse-native pass | 03:23:19 | 0.98 | 165 s | 0.000047 s fast |
| StarRocks pass | 04:29:11 | 0.80 | 135 s | 0.897 s slow |
| StarRocks attempt probe | 04:36:34 | 0.78 | 210 s | 0.917 s slow |
| Trino pass | 04:37:09 | 0.88 | 15 s | 0.000019 s slow |
| gemma4 leg | 04:52:34 | 0.89 | 135 s | 0.000057 s fast |
| phi4 leg | 04:54:43 | 0.88 | 90 s | 0.964 s slow |
| agy leg | 05:41:59 | 0.89 | 135 s | 1.086 s slow |

The chrony readings jump between near zero and about 1 s slow, as the 11-15 notes describe for this WSL2 guest.
Durations use the monotonic clock, so this doesn't touch any figure. Inside each pass the load is the engine's own work
and is not gated: timed-execution 1-minute load ran 0.26 to 17.39 (median 13.19) on ClickHouse-Iceberg, 1.67 to 13.02
(median 9.0) on native, 1.19 to 21.56 (median 7.64) on StarRocks and 4.02 to 16.58 (median 12.29) on Trino, against 11-15
medians of 17.16, 11.78, 20.76 and 16.94. Nothing else timed ran on the host; Ollama was empty before the passes and
between legs. Run window: engines 03:13:23Z to 04:49:44Z, LLM legs 04:52:34Z to 07:04:16Z.

**Cron overlap.** No execution in the pre-registered engine passes falls in a cron window (every timestamp is between
03:13Z and 04:50Z); the post-hoc fresh-engine probe (08:21:59Z to 08:23:05Z) falls in the 08:00 to 08:30Z window and is
tagged `cron-overlap` (see the StarRocks section). 91 of the
120 agy calls started between 06:00 and 07:04Z and are tagged `cron-overlap`; agy's inference is remote, the host load
before those calls was 0.01 to 0.38, and its median excluding them is 34.5 s (n = 29) against 31.5 s with them, so the
H9 verdict doesn't depend on them. phi4 and gemma4 finished before 06:00Z.

**Absolute timings.** On queries valid on both dates, the quiet median over the 11-15 median is 0.707 on StarRocks
(p10 to p90 0.566 to 0.801), 0.789 on ClickHouse-Iceberg, 0.834 on native and 0.703 on Trino, so the quiet
medians were roughly 17 to 30% below 11-15's by arm (the contended run 20 to 42% slower; post-hoc summary, not a
pre-registered comparison). Native, the least loaded arm on 11-15, moved least; Trino and StarRocks moved about equally
(0.703, 0.707) although Trino's 11-15 load was lower, and StarRocks's container state also differed between the dates.

## Per-hypothesis comparison

Scored with the unchanged `score.py` against the quiet run's own measured truth (`results/quiet-2026-11-16/scores.json`,
`comparison.json`).

| H | 11-15 | quiet 2026-11-16 | status |
|---|---|---|---|
| H1 S2 placement >= 0.90 both cells | falsified (0.643 hot, 0.738 cold) | falsified (**0.643** hot, **0.679** cold) | held (verdict) |
| H2 zero catastrophic S2 picks | falsified: 3 as scored, 2 as registered | falsified: **2** as scored (`join_3to4_04` hot, `_09` hot), **1** as registered (`_09` excluded) | held (verdict), count changed |
| H3 always-StarRocks cold: no cliff, mean regret <= 0.25 s | falsified (DNF; 3.57 s at the DNF price) | **holds as run** on the restarted engine (a deviation from the frozen re-create): no cliff, 0.016 s mean regret, 0.940 tie-tolerant; not established under the frozen protocol, since a post-hoc fresh engine fails `join_3to4_04` 5 of 5 | **changed, conditional on engine state** |
| H4 UEBA misclassified, StarRocks wins cold | holds (8 of 8 flat or non-depth; StarRocks 8 of 8) | holds (6 scan_aggregation, 2 large_large; StarRocks 8 of 8) | held |
| H5 within-shape stability >= 80% | falsified (hot 5 classes, cold scan_aggregation 0.773) | falsified (hot: correlated_exists 0.75, join_3table 0.60, large_large 0.621, point_lookup 0.75, scan_aggregation 0.545; cold: none) | held (verdict), cold now stable |
| H6 native q5 DNF, >= 6 of 7 anchors match June | holds (6 of 7; q21 moved; warmup completed 176.6 s) | holds (**7 of 7**; native q5 timeouts 304.4 s and 302.8 s after a warmup that completed in 140.1 s) | held (literal falsifier contested on both dates) |
| H7 each LLM leg below rules (modal tie-tolerant) | phi4 holds, agy falsified (tie 0.750), n = 24 | phi4 holds (0.583 vs 0.792), **agy holds** (0.708 vs 0.792), n = 24; gemma4 n = 0 (stopped) | **changed for agy** (truth shift) |
| H8 each LLM leg flips | agy holds, phi4 falsified, n = 24 | agy holds (7 of 24, mean flip 0.067), phi4 falsified (0 of 24); gemma4 n = 0 | held |
| H9 median added latency > 1 s local, > 2 s agy | holds (contended) | holds uncontended (21.7 s, 31.5 s) | held, newly tested uncontended |

Other pre-registered comparisons:

- **Always-StarRocks cold** 0.905 -> **0.940** tie-tolerant (strict 0.869 -> 0.940), a change above the 0.02 threshold.
- **Strict-winner flips:** 29 of 168 decisions (21 hot, 8 cold). The 11-15 strict winner falls outside the quiet
  tie-tolerant set on 20 decisions. Of the 51 hot decisions whose 11-15 margin between the top two valid engines was
  under 100 ms, 35 kept their winner and 16 flipped. Hot flips by direction: native to StarRocks 15, StarRocks to native
  5, ClickHouse-Iceberg to StarRocks 1 (`join_3to4_04`, where StarRocks now answers). Cold: ClickHouse-Iceberg to
  StarRocks 7, StarRocks to ClickHouse-Iceberg 1 (`large_large_05`).
- **Cliffs present.** 11-15 had 7 cliff-present decisions; quiet has 4, all native in the hot cell (`join_3to4_04`
  144x, `join_3to4_09` 209x, and the two 5-to-6-table timeouts). Gone: both StarRocks DNFs, and ClickHouse-Iceberg's
  soft cliff on `join_3to4_06` (30.2 s on 11-15, 9.3 s quietly against native's 1.21 s, 7.7x, under the 10x rule).
- **S1 and S3:** S1 0.429 hot, 0.679 cold, no catastrophic pick (it never picks native); S3 0.667 hot, 0.679 cold, 2
  catastrophic in the hot cell.
- **Families (S2, tie-tolerant hot / cold, quiet; 11-15 in brackets):** `scan_agg` 0.625 / 0.25 (0.875 / 0.50),
  `point_lookup` 0.75 / 0.00 (0.75 / 0.00), `dim_enrichment` 0.75 / 1.00 (0.375 / 0.875), `ioc_match` 0.75 / 0.50
  (0.625 / 0.875), `two_stream` 1.00 / 1.00 (0.833 / 1.00), `large_large` 1.00 / 0.833 (0.833 / 1.00), `join_3to4` 0.40 /
  1.00 (0.50 / 0.90; both catastrophic picks here), `join_5to6` 1.00 / 1.00 (same), `topn_agg` 0.75 / 0.75 (same),
  `correlated_exists` 0.25 / 1.00 (0.50 / 1.00), `ueba_two_level` 0.375 / 0.25 (0.50 / 0.375), `window_seq` 0.25 / 0.00
  (same). The cold losses are now almost all to StarRocks.

## StarRocks failure count

Attempts as pre-registered: main pass `join_3to4_04` warmup plus 5 trials (0.67, 0.64, 0.64, 0.63, 0.65, 0.64 s, all
oracle-matching) and 5 probe executions on fresh clients (0.80, 0.68, 0.64, 0.63, 0.65 s, all oracle-matching;
`results/quiet-2026-11-16/sr_attempts_probe.json`). **0 failures in 11 attempts.** The container was the 11-15 one
restarted (created 2026-11-15T21:51:39Z, started 04:26:21Z), not freshly created as the addendum planned, and the
allin1 container keeps its on-disk state across restarts.

**Post-hoc fresh-engine probe (not pre-registered; run after verification, 08:21 to 08:23Z).** To test that rival
explanation the run created a second container from the same image (`drn-starrocks-fresh`, created 08:21:14Z, network alias
`starrocks`, 24g, the 11-15 container left untouched) after re-registering the same Iceberg metadata in Nessie (report
identical to the 03:06Z one), gated at load 0.77, and ran `join_3to4_04` 5 times on fresh clients (08:21:59Z to 08:23:05Z, inside the 08:00 to
08:30Z cron window, tagged `cron-overlap`; the errors are StarRocks-internal pool limits, so cron is an unlikely cause)
(`sr_fresh_probe_posthoc.py`, `results/quiet-2026-11-16/sr_fresh_probe_posthoc.json`). **All 5 failed**: four with
"Memory of query_pool exceed limit" (13.9 to 21.8 s) and the last with "Memory of process exceed limit ... try
consume:8589934592" (33.1 s), the same 8 GiB allocation error as the 11-15 failures. That refutes the host-memory-pressure
reading this file gave before this probe. `SHOW STATS META` on the fresh engine afterwards (output not saved to any file) showed column statistics for only four
tables, collected during the probe itself, while the 11-15 container holds statistics for all 13 tables collected on
11-15 (21:53 to 21:58Z) and one more column during this morning's pass. An untested interpretation (Tier D): StarRocks's
automatic statistics collection on the Iceberg tables decides whether this q5-class join gets a plan that fits in memory,
which fits the failure on the fresh 11-15 main pass but not cleanly the 11-15 restart, which failed its first execution
after those statistics had been collected (21:53 to 21:58Z) and then succeeded twice; a first-query-after-restart effect
is an untested rival. Whatever the mechanism, the pre-registered StarRocks count (0 of 11) describes a warmed engine only.

## LLM-router arm

`results/quiet-2026-11-16/llm_scores.json`, scored with `analyze_llm.py`'s own functions (via `analyze_llm_quiet.py`).

| leg | decisions x trials | modal acc tie-tol / strict (quiet truth) | vs 11-15 truth | catastrophic modal / per trial | flips | invalid | latency median / p90 |
|---|---|---|---|---|---|---|---|
| rule stack S2 | 24 x 5 | 0.792 / n.a. | 0.750 | 0 / 0 | 0 of 24 | 0 | 0.58 ms / 1.00 ms (phi4 run); 0.574 / 0.962 ms (agy run) |
| gemma4:e4b (registered) | stopped after 3 calls | n.a. | n.a. | n.a. | n.a. | 3 of 3 | n.a. |
| phi4:latest | 24 x 5 | 0.583 / 0.458 | 0.625 | 1 / 5 of 120 | 0 of 24 | 0 | 21.7 s / 26.1 s |
| agy `gemini-4-hydrogen-high` | 24 x 5 | 0.708 / 0.583 | 0.750 | 0 / 1 of 120 | 7 of 24 | 0 | 31.5 s / 80.2 s |

- **gemma4:e4b.** All three scored replies began with reasoning ("The user wants me to select the fastest engine...")
  despite top-level `"think": false` on Ollama 0.20.6, the same failure as 11-15, so the leg stopped under the frozen
  rule. The registered 48-decision test of H7 to H9 on gemma4 is still not runnable on this runtime.
- **phi4** made the same catastrophic pick as on 11-15 (`join_5to6_01` hot to native, all five trials) and its picks are
  identical across seeds. Its other misses send hot queries to native and cold ones to ClickHouse-Iceberg where
  StarRocks is now faster.
- **agy** flipped on 7 of 24 decisions; one of five trials on `join_5to6_01` hot again picked native, the timeout. Its
  latency was higher than on 11-15 (31.5 s against 28.1 s); its inference is remote, so "uncontended" describes the host,
  not the hosted service, and most calls ran in the cron window (see above).
- **H9 margins.** Over the registered thresholds: phi4 21.7x (11-15: 31x contended), agy 15.7x (11-15: 14x). Over the
  rule stack's median per decision (0.58 ms, timed at load 0.10): about 37,000x for phi4 and 55,000x for agy.
- The rule stack's accuracy on these 24 decisions rose from 0.750 to 0.792 because the quiet truth moved; agy's H7
  change is that movement (agy scores 0.750 against the 11-15 truth, level with the rules there, and 0.708 against the
  quiet one).

## Deviations

1. **Catalog registered, not reloaded** with `load.py`: the 11-15 metadata files were registered in Nessie, which
   restores the identical snapshots; declared in the addendum.
2. **StarRocks restarted, not re-created** (see above). Trino was also restarted rather than re-created (`drn-trino`
   created 2026-11-15T21:59:19Z, started 2026-11-16T04:36:41Z); found by the second verification, no verdict depends on it.
3. **Orchestration scripts written after the freeze** (03:12:43Z), before the first timed execution (03:13:30Z), both
   infrastructure with no scoring logic: `run_quiet.sh` and `check_counts_quiet.py`. `compare_quiet.py`,
   `analyze_llm_quiet.py` and `run_llm_quiet.sh` were written during the engine passes, before any quiet result was
   read, and apply the addendum's definitions. Frozen helper hashes are in `PREREGISTRATION-ADDENDUM-QUIET-2026-11-16.sha256`.
4. **gemma4 leg stopped** under its pre-registered rule after 3 calls; the phi4 and agy legs ran on the 24 `_01`
   decisions as on 11-15, not on the 48 registered for gemma4.
5. **agy calls in the cron window** (91 of 120), tagged; the H9 verdict is reported with and without them.
6. **chrony** offsets of up to 1.09 s slow at some stamps (durations are monotonic).
7. **Light host activity during the passes:** short read-only inspection commands (log tails, `grep`) and file writes by
   the agent ran during the engine passes; no other timed or CPU-heavy work ran.
8. **Post-hoc container:** `drn-starrocks-fresh` was created for the fresh-engine probe and left stopped, not removed.

Post-hoc, labelled: the fresh-engine StarRocks probe and the statistics reading (the earlier host-memory-pressure
reading is withdrawn), and the per-direction
breakdown of winner flips (the addendum asked for flips; the direction split is an addition beyond it).

## Files (all new)

`PREREGISTRATION-ADDENDUM-QUIET-2026-11-16.md` (+ `.sha256`), `register_quiet.py`, `check_counts_quiet.py`,
`run_engines_quiet.py`, `sr_probe_quiet.py`, `score_quiet.py`, `compare_quiet.py`, `llm_router_quiet.py`,
`analyze_llm_quiet.py`, `run_quiet.sh`, `run_llm_quiet.sh`; `_work_quiet_2026-11-16/`;
`results/quiet-2026-11-16/` (`raw_{starrocks,clickhouse_iceberg,clickhouse_native,trino}.json`, `oracle.json`,
`data_gate_counts.json`, `sr_attempts_probe.json`, `scores.json`, `comparison.json`, `llm_local_gemma4.jsonl`,
`llm_local_phi4.jsonl`, `llm_agy.jsonl`, `llm_scores.json`); `logs/quiet-2026-11-16/`. No 11-15 file was modified.

## Hot-cell decisions settled by under 100 ms on 11-15 (pre-registered list)

Format: query, 11-15 margin between the top two valid engines in ms, 11-15 winner > quiet winner (SR StarRocks, nat
native MergeTree, CHI ClickHouse-Iceberg). 51 decisions, 35 same winner, 16 flipped (`comparison.json`
`hot_close_decisions_lt100ms_1115`).

correlated_exists_02 3.6 SR>nat; correlated_exists_03 35.3 nat>nat; correlated_exists_04 7.5 nat>nat; correlated_exists_06 8.9 SR>nat; correlated_exists_07 32.3 nat>nat; correlated_exists_08 19.1 nat>nat; dim_enrichment_01 22.4 nat>nat; dim_enrichment_02 48.0 nat>nat; dim_enrichment_03 24.3 nat>SR; dim_enrichment_04 30.0 SR>SR; dim_enrichment_05 10.6 nat>SR; dim_enrichment_06 43.4 nat>nat; dim_enrichment_07 43.9 SR>SR; dim_enrichment_08 13.7 nat>SR; ioc_match_01 4.3 nat>SR; ioc_match_02 76.4 nat>nat; ioc_match_03 92.6 nat>nat; ioc_match_05 20.7 nat>SR; ioc_match_06 94.9 nat>nat; ioc_match_07 87.2 nat>nat; join_3to4_05 47.2 nat>SR; join_3to4_10 32.3 SR>SR; large_large_01 74.6 SR>SR; large_large_04 4.7 nat>SR; large_large_06 88.2 SR>SR; point_lookup_02 51.7 nat>nat; point_lookup_03 17.3 nat>nat; point_lookup_04 5.0 SR>SR; scan_agg_01 81.2 nat>nat; scan_agg_02 45.2 nat>nat; scan_agg_03 14.9 nat>SR; scan_agg_04 35.3 nat>SR; scan_agg_05 49.6 nat>nat; scan_agg_06 41.7 nat>nat; scan_agg_07 20.5 SR>SR; scan_agg_08 78.1 nat>nat; topn_agg_01 76.7 SR>SR; topn_agg_03 81.8 nat>nat; topn_agg_04 23.0 nat>nat; topn_agg_07 62.8 nat>nat; topn_agg_08 23.7 nat>nat; two_stream_01 40.5 nat>SR; two_stream_05 4.2 nat>SR; ueba_two_level_02 61.8 SR>SR; ueba_two_level_04 30.8 nat>SR; ueba_two_level_05 4.8 SR>SR; ueba_two_level_06 10.2 nat>SR; ueba_two_level_07 36.1 nat>nat; ueba_two_level_08 26.9 nat>nat; window_seq_01 7.8 nat>SR; window_seq_03 70.0 SR>SR.

## Corrections after independent verification (2026-11-16)

`VERIFICATION-QUIET-2026-11-16.md` (VERIFIED-WITH-FIXES; own re-derivation from the raw files plus a Gemini leg)
reproduced every scored number and changed no verdict. Applied above, in place:

- The hot cell has **five** shape classes under 80%, not four (the table already listed five).
- H7 and H8 verdict lines now state n = 24 and that gemma4 scored n = 0; the headline says the agy H7 change is a truth
  shift (agy is 0.750 against the 11-15 truth, level with the rules there).
- Headline: the replication wording now separates data identity from answer validity; S2's cold drop (0.738 to 0.679)
  and the widened gap to always-StarRocks are stated; the draft-20 sentence is marked as an interpretation and conditioned on
  the restart caveat.
- Restart caveat: an allin1 restart keeps on-disk state. A post-hoc fresh-engine probe, run after verification, then
  failed 5 of 5, so H3 is now reported as holding on the warmed engine only, and the host-memory-pressure reading is
  withdrawn.
- H6: the 11-15 disclosure restored (the native q5 warmup completed again, in 140.1 s).
- The LLM section's "part of agy's H7 change" now matches the headline (the change is the truth shift).
- Absolute-timing summary relabelled post-hoc and the load attribution softened (Trino breaks the ordering).
- All 12 families now listed with their 11-15 values; rule-stack latency given for both LLM runs (0.58 and 0.574 ms);
  agy's higher latency than 11-15 noted.
- The pre-registered list of 51 close hot-cell decisions added (above).
- `compare_quiet.py` keyed the j4 anchor as `soc_j4`, which matches no anchor, so its H6 count compared two missing
  values for that anchor. Corrected to `soc_j4_ioc_semijoin` and re-run: June, 11-15 and quiet all give native for j4,
  so H6 stays 7 of 7 (11-15: 6 of 7); the number above was right for the wrong reason before the fix.
- Post-hoc labels added: the per-arm timing ratios and their load reading, and the restart argument.

## Corrections after independent verification (2026-11-16, second pass)

`VERIFICATION-INDEPENDENT-2026-11-16.md` (a second agent, own scripts over the raw files, Gemini leg; VERIFIED-WITH-FIXES)
reproduced every scored number, count and ratio and changed no hypothesis verdict. Applied above, in place:

- Absolute timings: "the contended run was roughly 17 to 30% slow" had the percentage on the wrong base; the quiet medians
  are 17 to 30% below 11-15's (ratios 0.703 to 0.834), so the contended run was 20 to 42% slower. Trino and StarRocks moved
  about equally (0.703, 0.707).
- Cron overlap: load before the 91 cron-window agy calls was 0.01 to 0.38, not 0.01 to 0.89 (0.89 was the first,
  pre-window call). The post-hoc fresh-engine probe ran 08:21:59Z to 08:23:05Z, inside the 08:00 to 08:30Z window, and is
  now tagged `cron-overlap`.
- StarRocks: "failed every time on a fresh one" narrowed to one freshly created container (5 of 5; the fresh 11-15
  container failed 2 of 2). "The 11-15 failures were not host contention" narrowed to "host contention is not needed to
  produce them". The `SHOW STATS META` reading is marked unrecorded, and the claim that the statistics reading fits the
  11-15 sequence is qualified: the 11-15 restart failed once after its statistics existed.
- Hot-cell tilt: "the way the 11-15 caveat predicted" now says consistent with, not confirming, because StarRocks's
  container state (fresh on 11-15, warmed quietly) changed along with the load, and 14 of the 15 native-to-StarRocks flips
  had 11-15 margins under 100 ms.
- Deviation 2 now also records that Trino was restarted, not re-created as the addendum planned (`drn-trino` created
  2026-11-15T21:59:19Z, started 04:36:41Z); no verdict depends on Trino.
- H3 row: "holds as run" now says the engine was a deviation from the frozen re-create and that H3 is not established
  under the frozen protocol.
- Not changed: the StarRocks timing p90 (0.801; another percentile method gives 0.808). `compare_quiet.py` was edited at
  08:06:58Z and is not in the frozen sidecar; every comparison it produces was recomputed independently and matches.


---
type: benchmark-spec
title: "PRE-REG: STREAM-FRESHNESS sweep, where streaming's freshness edge starts to pay (batch poll interval x detection shape)"
status: frozen
created: 2026-11-06
hypotheses: [H-IMPL-01, H-STREAMING-01]
evidence-tier: B
depends_on:
  - "[[H-IMPL-01-feldera-v2-verdict-2026-11-05]]"
  - "[[PRE-REGISTRATION-LEDGER]]"
tags: [h-impl-01, stream-complexity, freshness, micro-batch, poll-interval, ioc-match, pre-registration, m6, frozen]
---

# PRE-REG: STREAM-FRESHNESS sweep (frozen 2026-11-06)

**Status: FROZEN 2026-11-06 at owner ruling, before any harness change or run.** The lab copy is `~/sdw-lab-benchmarks/stream-complexity/PRE-REG-stream-freshness-2026-11-06.md`, frozen on top of lab `f36e23a`; this hub file is the identical mirror. Smoke runs that make the harness work are not scored runs (M6), and every number under "Frozen predictions" is fixed at that copy.

## Why this block exists

The v2 result (`RESULTS-v2-2026-11-03.md`, lab `f36e23a`) found that on a real clock the Kafka 4.3.1 + Flink 2.2.1 arm beat the batch arm by about 3.0 s of median freshness (2.18 s against 5.20 s, n=1), or about 0.7 s once the file lander's WSL sleep overshoot is set aside. That finding is narrower than it sounds, and I want the narrowness tested rather than argued. The batch arm in v2 was a tight micro-batch, one Parquet file per 60 event-seconds and a DuckDB job polling every 5 s, and the detection was a 60-second tumbling window that no arm can alert on before the window closes. So the 3 s mostly measures two settings, Flink's 2-second watermark against batch's 5-second poll, and it says nothing about the batch schedules most SOCs actually run (scheduled searches every 5 to 15 minutes) or about detections that have no window at all, where I'd expect streaming to win by much more.

The claim under test, stated so it can fail: *for a windowed detection that alerts at window close, the freshness gap between streaming and batch is set by the batch poll interval, and a short-interval micro-batch closes most of it; for a single-event match, batch freshness is bounded below by its landing cadence, so streaming keeps a structural edge that no poll interval removes.*

This is a benefit-side bench. It does not re-score the complexity axes and does not move H-IMPL-01's confidence in either direction (that hypothesis is about cost, and its 2/5 direction-only score stands on the v2 cost axes). What it gates is the wording every surface uses when it quotes the freshness side: the streaming-decision page, the book's Ch05 `[^streamcx]` footnote, and the site's `StreamingFreshnessTrade` figure.

## Question

Over the same seed-20260719, 500,000-event synthetic OCSF-shaped auth corpus, on a real-time clock, how fresh is each arm's alert for (1) the July windowed detection and (2) a new single-event IOC match, as the batch poll interval moves from 5 s to 15 minutes, and what does each poll interval cost in CPU and query invocations?

## Detections

- **W, windowed (July, unchanged):** ≥5 failed logins per (user, src_ip) within a 60-second epoch-aligned event-time tumbling window → alert. Ground truth 30 alerts, 30 planted near-misses that must not alert.
- **I, IOC match (new):** any auth event whose `src_ip` is in a fixed 30-address IOC list → one alert per matching event. Ground truth: 30 planted events.

**IOC planting.** `gen_corpus.py` gains a `--plant-ioc 30` flag that generates the base corpus exactly as today and then inserts 30 extra events, each a successful logon from one of 30 dedicated IOC addresses (disjoint from the 1,200 background and 20 attacker addresses), at seeded event times spread across the 2-hour span (seed 20260719 + 1, at least 120 s apart, none within 5 s of a window boundary so the landing-cadence effect isn't confounded with boundary timing). Because they are successes from fresh addresses they can't create or break a failure window. **Gate before any scored run:** with the planted corpus, the W ground truth must still be exactly the July 30 alerts and 30 non-alerting near-misses, byte-compared against `compare_answers.py`'s ground truth on the unplanted corpus. If it isn't, the planting is wrong and gets fixed before freeze.

## Arms (all run concurrently in each trial, fed from one shared replay clock)

- **S, streaming:** the July/v2 Kafka 4.3.1 (one KRaft broker) + Flink 2.2.1 stack, unchanged except that the Flink job carries a second `INSERT` for detection I (a stateless filter joined against a 30-row IOC table), writing to its own topic and drain file. Watermark stays at 2 s.
- **B-5, B-60, B-300, B-900, batch:** the July `land_microbatches.py` lander, one instance, landing one file per 60 event-seconds into one directory. Four `batch_job.py` processes read that same directory, each with its own state and output files, at `--poll-interval` 5, 60, 300 and 900 s. Each runs both detections on each new file. B-900 stands in for a 15-minute scheduled search, which is about the most common SIEM schedule I've seen.
- **B-5/L300, buffered-collector batch (added at owner ruling 2026-11-06):** a second lander instance writing one file per 300 event-seconds (five 60-second windows per file, the shape of a Firehose-style or 5-minute file-roll collector) into its own directory, read by a fifth `batch_job.py` at `--poll-interval 5`. The detection logic is unchanged, since rows are grouped by `floor(time / 60)` inside the file; the job's filename parsing and prior-window re-scan are generalised to a file that spans several windows, and the W ground-truth gate runs on this arm too.
- **Out of scope:** Feldera (its Terms of Service are unread, and v2 showed its freshness tracks S's because both are their 2-second lateness bound) and the containerised batch arm (v2 showed BC within 0.6 s of B on freshness).

**Harness fixes carried from v2:**

1. **Lander sleep overshoot.** v2's 1× lander made one ~58 s `time.sleep` per window and overshot by about 2.3 s on this host. The lander now sleeps in chunks of at most 1 s and records, per window, the lag between the window's scheduled wall-clock end and the file rename. Predicted p95 lander lag < 0.2 s. Batch latencies are reported raw and with lander lag subtracted.
2. **Real clock only for scored freshness.** Poll intervals are wall-clock and windows are event time, so any replay factor other than 1× distorts the comparison (the v2 lesson). Every scored trial runs at 1×.

## Measures

1. **Freshness, W:** wall-clock from the alert's window closing (scheduled wall time of the window end) to the alert landing in the arm's output file. This is the July/v2 baseline, unchanged.
2. **Freshness, I:** wall-clock from the matching event's scheduled replay time to its alert landing. (A window-close baseline means nothing for a stateless match.)
3. Both reported as p50, p95 and max per arm per trial, plus pooled p50 across trials.
4. **Cost of polling:** per batch process, CPU-seconds over the trial (from `/proc/<pid>/stat`), count of poll wake-ups, and count of DuckDB query executions. For S, container CPU-seconds from `docker stats` sampling at 10 s (the v2 sampler). This is a proxy, not dollars.
5. **Not measured:** config LOC. Adding detection I changes S's job and every batch job, so this run's line counts can't be compared with July's or v2's, and none are reported (owner ruling 2026-11-06).
6. **Answer equality:** on every scored trial, every arm produces W = 30/30 (0 missing, 0 extra, 0 duplicate) and I = 30/30, pairwise identical. An arm that fails equality on a trial has no freshness number quoted for that trial.

## Frozen predictions

Model behind the numbers: for W, batch's delay after window close is the wait for the next poll (uniform over the interval, so about half of it at the median) plus query time, while streaming's is its 2 s watermark plus about 0.2 s; for I, batch adds the wait for the event's file to land (uniform over the 60 s landing cadence, so about 30 s at the median) before the poll wait starts, while streaming's stateless filter doesn't wait on the watermark at all.

| Arm | W p50 (s) | I p50 (s) |
|---|---|---|
| S | 1.8 to 2.6 | < 1.0 |
| B-5 | 2.0 to 4.5 | 25 to 40 |
| B-60 | 20 to 40 | 45 to 75 |
| B-300 | 100 to 200 | 130 to 230 |
| B-900 | 300 to 600 | 330 to 630 |
| B-5/L300 | 80 to 170 | 130 to 180 |

The B-5/L300 W band comes from where a window sits in its 300-second file: the last window of a file waits 0 s for landing and the first waits 240 s, so across five positions the median wait is about 120 s, plus the poll and query. Its I band is the 150 s median wait for a 300-second file plus the poll.

- **P1 (the headline):** on W, S beats B-5 by less than 3 s at the median on every trial, once lander lag is subtracted.
- **P2:** on W, the batch arms' p50 rises roughly linearly with poll interval: each of B-60, B-300 and B-900 lands within ±40% of (interval / 2 + 0.5 s).
- **P3:** on I, S beats B-5 by at least 20 s at the median on every trial, so tightening the poll does not close the gap for a stateless match.
- **P4:** lander lag p95 < 0.2 s on every trial.
- **P5 cost:** the four batch processes land within 2× of each other on CPU-seconds, because `batch_job.py` only runs a query when a new file has landed (about 120 files per trial), so a tighter poll mostly adds cheap directory listings. B-5 makes about 1,440 poll wake-ups per trial and B-900 about 8, while query executions stay within ±10% of each other across all four. S's CPU-seconds exceed B-5's by at least 10×.
- **P6 equality:** 30/30 on W and 30/30 on I for every arm on every scored trial.
- **P7 landing cadence:** on I, B-5/L300's p50 is at least 3.5× B-5's on every trial, so the collector's file cadence, not the job's poll interval, sets single-event freshness once the poll is short.

## What each result would mean (frozen decision rules)

- **SUPPORTED** (the gap on windowed detections is set by poll interval; single-event matches keep a structural streaming edge): P1, P2 and P3 all hold on both trials. Then the streaming-decision page, Ch05 `[^streamcx]` and the `StreamingFreshnessTrade` figure get a dated rule, roughly: for a detection that alerts at window close, a micro-batch whose poll interval is a few seconds gets within a few seconds of Kafka + Flink; for a single-event match, batch can't be fresher than its landing cadence, which is where streaming earns its running cost. The measured crossover numbers go in, with the boundaries below.
- **FALSIFIED, streaming has an edge beyond configuration:** on W, S beats B-5 by more than 10 s at the median on either trial, with lander lag p95 < 0.2 s. Then the v2 "about 3 s" figure was flattering batch, and every surface quoting it gets corrected.
- **FALSIFIED, landing cadence doesn't bound batch:** on I, S beats B-5 by less than 10 s on either trial. Then my model of batch latency is wrong, and the I numbers get explained before anything is quoted.
- **INDETERMINATE:** anything else. The numbers are reported as measured with no rule written, and no surface changes its wording beyond adding the measured table.
- **P7 landing-cadence result** is reported either way. If it holds, the wording rule carries a second clause: on a buffered collector, shorten the file roll before buying a stream processor. If it fails, the I model is wrong and gets explained before any I number is quoted.
- **P5 cost result** is reported either way. If P5 fails because tight polling costs much more CPU than predicted, that cost goes next to the B-5 freshness number wherever it is quoted.
- **No confidence change** to H-IMPL-01 under any outcome. If SUPPORTED, H-STREAMING-01 gets the I result attached as first-party context at its next gate.

## Run budget at ~1 hr/day

| Phase | What | Estimate |
|---|---|---|
| Harness | `--plant-ioc` + W ground-truth gate, IOC query in `batch_job.py`, second Flink `INSERT` + drain, five concurrent batch processes, a 300-second lander and multi-window file handling for B-5/L300, chunked lander sleep + lag log, I-baseline latency scorer, CPU/poll/query counters | 2.5 to 3.5 sessions |
| Smoke | one short 1× run (`--limit`, about 15 min) to check every output file appears and the scorers agree | 1 session |
| Scored | two full 1× trials, about 2 h 15 min each, **unattended**; can run back to back overnight | 0 attended + about 4 h 30 min unattended |
| Score and write | RESULTS, ledger row, wording proposals for the three surfaces | 1 to 2 sessions |

Roughly 4 to 6 one-hour sessions plus one overnight window, about one to two calendar weeks.

## Threats to validity

- **Concurrent arms share one host** (Ryzen 5800H, Docker Desktop on WSL2). The workload is light (500,000 events over 2 hours), but S's containers and four Python processes compete for CPU and timers. The CPU sampler records host load; if host CPU exceeds 50% for more than 5% of samples, the trial is flagged.
- **Landing cadence is fixed at 60 s.** Real collectors often buffer longer (Kinesis Data Firehose allows up to 900 s, and many file shippers roll every 5 minutes), which would push every batch I number up. So the I numbers here are a best case for batch, and that is stated wherever they're quoted.
- **Local polling is cheap; cloud scheduled searches aren't.** `batch_job.py` lists a directory and queries only on new files. A SIEM scheduled search or a warehouse task usually re-executes its query on every schedule, so P5's "tight polling is nearly free" doesn't carry to those platforms and must not be quoted as if it did.
- **Watermark fixed at 2 s.** A smaller watermark would make S fresher on W and drop more late events; this bench doesn't sweep it.
- **Two detection shapes, n = 2 trials, synthetic corpus, single node every arm.** The planted IOC events are the only IOC hits, so the I detection is never under load.
- **Who ran it:** the bench author is the hub's own agent. The pre-registration, the W ground-truth gate and pairwise answer equality are the protections.

## Honesty boundaries (carried into any RESULTS verbatim)

Single host, Docker Desktop/WSL2, synthetic seeded corpus (no real telemetry), two detection shapes (one 60-second window, one stateless IOC match), single-node every arm, two real-clock trials. Kafka 4.3.1 + Flink 2.2.1 as the streaming arm; DuckDB micro-batch over 60-second Parquet files at four poll intervals. Freshness and a CPU proxy only, not dollars, staffing or on-call burden. The batch arms' landing cadence (60 s) is shorter than many production collectors', so batch's single-event numbers are a best case.

## Paste-ready ledger bullet (for `PRE-REGISTRATION-LEDGER.md` "Next pre-registrations"; not applied)

```markdown
- **STREAM-FRESHNESS sweep: batch poll 5/60/300/900 s + 5 s over 300 s files vs Kafka+Flink, windowed + IOC detections** (FROZEN
  2026-11-06; `~/sdw-lab-benchmarks/stream-complexity/PRE-REG-stream-freshness-2026-11-06.md`, hub mirror
  `02-projects/PRE-REG-DRAFT-stream-freshness-sweep-2026-11-06.md`). Benefit-side follow-up to v2's "about 3 s" finding; no H-IMPL-01 score change under any
  outcome. SUPPORTED = windowed gap vs 5 s poll < 3 s, batch p50 tracks interval/2, IOC gap vs 5 s poll ≥ 20 s.
  Falsifiers = windowed gap > 10 s, or IOC gap < 10 s. P7: 300 s files ≥ 3.5× the 5 s poll's IOC p50.
```

## Frozen at owner ruling 2026-11-06 (answers to the open questions)

Jeremy, hub tab, 2026-11-06, "1. Yes 2. Yes 3. Yes":

1. **B-900 stays** as the 15-minute scheduled-search arm.
2. **Detection I goes into the existing Flink job** as a second `INSERT`, and config LOC is not reported for this run.
3. **B-5/L300 is added** (5-second poll over 300-second files) with prediction P7, to show what a buffered collector costs on single-event freshness.

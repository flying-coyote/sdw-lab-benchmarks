# STREAM-FRESHNESS sweep: results against the frozen pre-registration (2026-11-06)

Binding plan: `../PRE-REG-stream-freshness-2026-11-06.md`. It was frozen before any harness change or run, at `80c81fc`, which documents written before 2026-11-06 cite as `1ae54f1` (see `../HASH-MAP-2026-11-06.md`). Deviations D1–D4 were dated and recorded before the scored runs. Raw outputs are in `fresh/trial1/` and `fresh/trial2/`, and the run log is `fresh/scored-run.log`.

## Verdict: SUPPORTED

The frozen SUPPORTED rule needs P1, P2 and P3 to hold on both trials, and they do. Neither falsifier fired. P4, P6 and P7 hold too. P5, the polling-cost prediction, missed on two of its three legs, and the reason is below. Under its own rule that miss is reported next to the freshness numbers and does not change the verdict.

What this supports: for a detection that alerts when a 60-second window closes, the freshness gap between Kafka + Flink and batch comes from the batch poll interval. A micro-batch polling every 5 seconds lands within about a second of the streaming stack. For a single-event IOC match, batch can't alert before the event's file lands, so the collector's file cadence sets a floor that no poll interval removes. This is where streaming keeps a structural edge.

## Freshness, pooled median over 4 phase-stratified replicas per batch arm (seconds)

| Arm | W p50, trial 1 | W p50, trial 2 | W band (frozen) | I p50, trial 1 | I p50, trial 2 | I band (frozen) |
|---|---|---|---|---|---|---|
| S (Kafka 4.3.1 + Flink 2.2.1) | 2.18 | 2.16 | 1.8–2.6 | 0.01 | 0.01 | < 1.0 |
| B-5 | 3.13 (2.40 lag-sub) | 2.92 (2.85 lag-sub) | 2.0–4.5 | 29.51 | 29.51 | 25–40 |
| B-60 | 30.64 | 30.00 | 20–40 | 58.51 | 58.51 | 45–75 |
| B-300 | 150.01 | 150.01 | 100–200 | 177.01 | 177.01 | 130–230 |
| B-900 | 450.01 | 450.01 | 300–600 | 479.53 | 479.53 | 330–630 |
| B-5/L300 (5 s poll over 300 s files) | 120.63 | 120.63 | 80–170 | 153.64 | 153.64 | 130–180 |

W is measured from the window close to the alert landing, and I from the event's scheduled replay time to the alert landing. Every arm landed inside its frozen band on both trials. The batch I medians are identical across the two trials because the planted IOC times and the stratified poll phases are deterministic, so the only thing that varies between trials is jitter in the lander and the poll loop.

## Predictions

| # | Frozen prediction | Trial 1 | Trial 2 | Result |
|---|---|---|---|---|
| P1 | On W, S beats B-5 by < 3 s at the median, lander lag subtracted | 0.22 s | 0.70 s | **HIT** (raw gaps 0.95 s and 0.76 s) |
| P2 | B-60, B-300 and B-900 W medians within ±40% of interval/2 + 0.5 s | 30.6 / 150.0 / 450.0 against 30.5 / 150.5 / 450.5 | 30.0 / 150.0 / 450.0 | **HIT** (all within 1%) |
| P3 | On I, S beats B-5 by ≥ 20 s at the median | 29.5 s | 29.5 s | **HIT** |
| P4 | Lander lag p95 < 0.2 s | 0.008 s (60 s files), 0.036 s (300 s files) | 0.007 s, 0.165 s | **HIT** (one 1.78 s outlier on a 60 s file in trial 1; it isn't the p95) |
| P5a | Batch CPU-seconds within 2× of each other | B-5 3.7 s against B-900 1.2 s (3.2×) | 3.8 against 1.1 (3.4×) | **MISS** |
| P5b | Query executions within ±10% across the batch arms | B-5 and B-60 120, B-300 24–25, B-900 9 | same | **MISS** |
| P5c | S CPU-seconds ≥ 10× B-5 | 3,205 against 3.7 (about 870×) | 3,224 against 3.8 | **HIT** |
| P6 | Answer equality: W 30/30 and I 30/30, every arm and replica, pairwise identical | pass | pass | **HIT** |
| P7 | On I, B-5/L300 p50 ≥ 3.5× B-5 | 5.2× | 5.2× | **HIT** |

Tally: 8 hits, 2 misses. Host load stayed low throughout: median 3.7–3.8% CPU, max 13.6%, no sample over 50%, so neither trial is flagged.

**Why P5 missed.** I predicted that every arm would run about one query per landed file, so query counts would match and CPU would differ only through cheap directory listings. In fact `batch_fresh.py` runs one query per tick over every file that has landed since the last tick. A 900-second poll therefore folds fifteen 60-second files into one query: 9 queries a trial against 120 for the 5-second poll. So the CPU difference came from queries, not from polling. That cuts against the cost half of my model, but the absolute numbers are tiny next to the streaming stack's: 3.7 CPU-seconds for the 5-second poll over a 2¼-hour trial, against about 3,200 for Kafka + Flink, most of which is the broker. The P5 rule requires this cost to sit next to the B-5 freshness figure wherever that is quoted: here, a 5-second poll cost about three times the CPU of a 15-minute schedule, and about 0.1% of the streaming stack's.

## What it means, and what it doesn't

- **Windowed detections.** A 60-second-window rule that alerts at window close gets within about a second of Kafka + Flink from a micro-batch polling every 5 seconds. The gap grows linearly with the poll interval, at about half the interval, so a 15-minute scheduled search adds about 7.5 minutes.
- **Single-event matches.** An IOC hit reached the streaming arm's output in about 10 ms. Batch couldn't alert until the event's file had landed, about 30 s at the median on 60-second files and about 150 s on 300-second files, before any poll wait. Shortening the collector's file roll mattered more than tightening the poll: with 300-second files, the 5-second poll's IOC median was 5.2× its median on 60-second files.
- **Boundaries** (from the pre-registration, carried verbatim in spirit):
  - single host, Docker Desktop on WSL2, a synthetic seeded corpus, two detection shapes, single-node arms, two real-clock trials;
  - landing cadence fixed at 60 s and 300 s, so many production collectors buffer longer and batch's I numbers here are a best case;
  - local file polling, which is cheap, whereas SIEM scheduled searches usually re-run the query on every schedule, so P5's CPU numbers don't carry to those platforms;
  - the watermark was fixed at 2 s.
- **Hypotheses.** H-IMPL-01 doesn't move under any outcome of this bench; its 2/5 rests on the v2 cost axes. The I result attaches to H-STREAMING-01 as first-party context at its next gate.

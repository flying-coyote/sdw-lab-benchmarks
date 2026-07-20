# STREAM-COMPLEXITY — results (2026-07-19)

Batch vs streaming operational complexity for one identical detection outcome. Pre-registration frozen before any scored trial: `../PRE-REG-stream-complexity-2026-07-19.md`. Target hypotheses: H-IMPL-01 (Streaming Architecture Hidden Costs, 1/5 after the 2026-07-09/10 fabrication sweep left it with zero literature legs) and the operational-burden position of `contradictions/streaming-hidden-costs-complexity.md`. Owner-declared 20-hour quiet-box window. **Honesty boundary: single host (Ryzen 5800H, Docker Desktop/WSL2), synthetic seeded corpus, ONE detection shape, Kafka+Flink as the canonical streaming stack, complexity proxies are not dollars/headcount/on-call. This measures the operational-surface DIRECTION of H-IMPL-01, not its retired cost multipliers. Tier B.**

## What ran
- Detection: "≥5 failed logins per (user, src_ip) within a 60-second event-time window → alert" over a seeded 500,000-event OCSF-shaped auth corpus (seed 20260719), with planted brute-force bursts and 4-failure near-misses. Ground truth computed by an independent dict-grouping reference implementation that shares no code with either arm.
- Batch arm: micro-batch Parquet files (one per 60 event-seconds) processed by a single DuckDB job on a scheduler loop (bare host process, no container).
- Streaming arm: the same events produced to Kafka (KRaft, `apache/kafka:4.3.1`) and aggregated by a Flink SQL tumbling-window job (`flink:2.2.1`, jobmanager + taskmanager, checkpointing on), alerts sunk to a second topic and drained by a consumer.
- 3 scored trials (BENCHMARKING-METHODOLOGY CV requirement) + a 3-injection fault battery + a moving-parts/config snapshot.

## P5 — answer equality (the pre-registration gate): PASS ×3
Every one of the 3 scored trials: both arms produced 30/30 distinct alerts, identical to each other and to ground truth (missing=0, extra=0, duplicates=0). A first scored attempt (trial 1, pre-fix) diverged 22/30 on the stream arm — diagnosed to a harness bug (the alert consumer exited during a data-dependent 57-second alert-free gap and orphaned 8 tail alerts still sitting in the Kafka topic; Flink itself was exactly right, all 30 present in the sink). Fixed by draining the consumer on an explicit stop-file after the sink end-offset goes stable rather than on alert-stream idleness (commit `409649d`), and the fix held across all 3 rerun trials. No complexity number is quoted from a run whose answers diverged.

## The three complexity axes (predictions vs measured)

| Axis | Prediction | Measured | Verdict |
|---|---|---|---|
| P1 moving parts | streaming ≥3× (4-5 vs 1-2) | stream 3 containers + 1 host process, 2 distinct images totaling ~913 MB (Kafka 238 MB + Flink 674 MB); batch 0 containers + 1 host process | **HOLDS** — 4 runtime units vs 1, and the streaming images are heavyweight where batch has none |
| P2 config surface | streaming ≥3× config LOC | stream 197 LOC vs batch 131 LOC = **1.5×** | **FAILS the threshold** — the streaming config is larger but nowhere near 3×; the operational burden is in the running infrastructure, not the lines of config |
| P4 freshness (the benefit side) | streaming p50 < 5s; batch ≈ tick/2 | stream p50 **0.26s** (CV 0.38), batch p50 **2.27s** (CV 0.62, accelerated-clock equivalent ≈ tick/2) | **HOLDS** — streaming buys roughly an 8-9× freshness improvement, and this is reported alongside the cost, never separately |

## P3 — fault recovery: operational-effort asymmetry measured; recovery-CORRECTNESS not cleanly measured
The battery injected three faults (Kafka broker kill, Flink taskmanager kill, batch-job kill mid-tick) on a dedicated 5,000-event corpus. The operational-effort side came out as predicted and is the honest half of this axis:

| Fault | Recovery steps | Wall-clock to infra restored |
|---|---|---|
| Kafka broker kill | 2 | 18.1s |
| Flink taskmanager kill | 2 | 21.5s |
| Batch-job kill mid-tick | 1 | 0.02s |

That asymmetry is real and supports the direction: bringing a streaming component back is a multi-step, ~20-second operation, while the batch arm is a single instant process restart. **But** post-recovery answer-equality came back `False` for all three in the scored run, unlike the abbreviated smoke test where all three recovered to a correct alert set. Reading the harness honestly: the recovery scripts restart the killed infrastructure (containers confirmed back to Running) but the scored fault path does not re-drive the replay window that was lost during the outage, so the post-recovery compare is measuring "did the missed events get re-injected" (they didn't, by harness construction) rather than "can the system recover correct output." So **recovery-correctness is a harness limitation here, not a systems verdict** — I am not claiming either arm fails to recover; I am saying this bench did not cleanly measure it, and a future pass needs a recovery path that replays the lost window before comparing.

## Falsifier check and disposition
The frozen falsifier was "streaming within 1.5× of batch on two or more of the three complexity axes, OR batch requiring more recovery steps than streaming." Only ONE axis (config LOC, at exactly 1.5×) is near-parity; moving parts (4× units, 2 heavyweight images vs none) and fault-effort (2 steps/~20s vs 1 step/0.02s) both clearly separate streaming as the heavier system, and batch never needed more steps than streaming. **The falsifier is NOT triggered.**

But P2 failed its threshold and P3's correctness leg was not cleanly measured, so the full P1-P3 hold the pre-reg required to move H-IMPL-01 from 1/5 to 2/5 is **not** met. The honest outcome: this run gives H-IMPL-01 its FIRST first-party evidence — the operational-complexity DIRECTION (more runtime infrastructure, heavier failure-mode handling) is now measured and supported, against a hypothesis that had zero surviving quantitative legs — but it does not deliver a clean magnitude, and the "more config to write" framing is specifically weak (1.5×, not 3×). The interesting nuance the bench surfaced, worth carrying into any writeup: for an equivalent detection outcome the streaming penalty is concentrated in running-and-recovering infrastructure, not in configuration effort, and it buys a real ~9× freshness gain that has to be weighed against it.

**Confidence: staged, not applied.** Recommendation for the owner / next gated pass: keep H-IMPL-01 at 1/5 on magnitude, but record that the operational-complexity direction now has a first-party leg (the moving-parts + fault-effort asymmetry), and route the correctness-recovery gap to a harness fix (replay the lost window post-recovery) before any P3 claim. Reproduce: `bash run_scored.sh` (fresh `docker compose down -v`, full 500k corpus, 3 trials + faults + snapshot; ~50 min).

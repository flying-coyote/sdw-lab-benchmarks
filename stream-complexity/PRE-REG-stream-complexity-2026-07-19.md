# PRE-REG — STREAM-COMPLEXITY (batch vs streaming operational complexity), 2026-07-19

**Frozen 2026-07-19, before any scored run** (M6 discipline: this block does not change after results exist; a smoke test to make the harness function is not a scored run). Target hypotheses: H-IMPL-01 (Streaming Architecture Hidden Costs, 1/5 after the 2026-07-09/10 fabrication sweep — zero literature legs remain) and, adjacently, the operational-burden bullet of `contradictions/streaming-hidden-costs-complexity.md`. Computed selector rank 2 (score 5.100, BENCHMARK-BACKLOG M5 table 2026-07-18). Owner authorization: 20-hour quiet-box window declared 2026-07-19.

## Question

For the same detection outcome on the same events — "≥5 failed logins per (user, src_ip) within a 60-second event-time window → alert" over a seeded synthetic OCSF-shaped auth corpus — what does the canonical streaming stack (Kafka + Flink) cost in operational complexity relative to a micro-batch path (files + DuckDB on a scheduler loop), measured as moving parts, config surface, and fault-recovery effort, against the freshness benefit it buys?

## Arms

- **Batch arm**: seeded generator lands micro-batch Parquet files every T=60s (accelerated event-time replay); a single scheduled DuckDB/Python job processes new files per tick and appends alerts to `alerts-batch.jsonl`.
- **Streaming arm**: the same events produced to a Kafka topic (KRaft single broker); a Flink job (event-time windows + watermarks) consumes, aggregates, and appends alerts to `alerts-stream.jsonl`.
- Identical seeded corpus, identical detection semantics, identical alert schema. **Answer-equality gate**: on a clean run both arms must produce the identical alert set (matching planted ground truth); a mismatch invalidates the bench until explained and fixed — no complexity result may be quoted from a run whose answers diverge.

## Measures

1. **Moving parts**: running containers/processes per arm; distinct images; total image size.
2. **Config surface**: lines of config+orchestration per arm (compose + engine config + job definition + scheduler), counted by script with a stated inclusion rule.
3. **Fault recovery**: scripted fault injections — (a) kill the Kafka broker mid-run; (b) kill the Flink taskmanager mid-run; (c) kill the batch job mid-tick. For each: operator steps to recovered-correct-output (scripted steps counted honestly), wall-clock to recovery, and post-recovery correctness vs ground truth (missed alerts / duplicate alerts).
4. **Freshness**: event-ingest→alert-emit wall-clock latency, median over ≥3 scored trials + CV per BENCHMARKING-METHODOLOGY (gap claimed only when it exceeds max CV).

## Frozen predictions

- **P1 (moving parts)**: streaming ≥3× batch containers (predict 4–5 vs 1–2).
- **P2 (config surface)**: streaming ≥3× batch config LOC.
- **P3 (fault recovery)**: streaming needs MORE operator steps than batch for at least two of the three injections, but BOTH arms recover to a correct alert set (streaming via replay/checkpoint, batch via reprocessing the tick); predicted asymmetry is in steps and time, not final correctness.
- **P4 (freshness)**: streaming p50 event→alert < 5 s; batch ≈ tick/2 + processing (~30–60 s at T=60s). This is the benefit side and must be reported WITH the complexity side, never separately.
- **P5 (equality)**: identical alert sets on the clean run.

**Predicted confidence delta**: P1–P3 holding at the stated thresholds moves H-IMPL-01 1/5 → 2/5 (Tier B, single-host, complexity-proxy — NOT TCO; the karen → hypothesis-validator → contradiction-detector gate rules before any number moves). **Falsifier (frozen)**: streaming within 1.5× of batch on two or more of the three complexity axes, OR batch requiring more recovery steps than streaming — either outcome means the hidden-costs direction gains no first-party support, and H-IMPL-01 is formally downgraded to directional-only and leaves the needs-validation rotation. A falsifying result is a real result and ships the same way.

## Honesty boundaries (carried into any RESULTS.md verbatim)

Single host, Docker Desktop/WSL2, synthetic seeded corpus (injection-surface boundary: no real telemetry), ONE detection shape, Kafka+Flink as the canonical stack — lighter stacks (Redpanda, RisingWave) would score differently and this bench does not speak for them; complexity proxies are not dollars, headcount, or 24/7 on-call burden, so this measures the operational-surface direction of H-IMPL-01, not its retired cost multipliers. Assumption under test: the canonical streaming stack carries structurally more operational surface than an equivalent-outcome batch path.

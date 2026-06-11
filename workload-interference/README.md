# Workload-interference bench — where the scheduled load breaks the interactive experience

**Status: PRE-REGISTERED 2026-06-10, before any scored run.** This README is the
pre-registration; the design, thresholds, stop rules, and predictions below are committed
ahead of the first timed pass and will not be edited after scoring starts (errata get
appended, not rewritten). Program home: the transition-point program
(project1 `02-projects/securitydataworks/transition-point-program-2026-06-10.md`, §6 —
approved by Jeremy 2026-06-10).

## Why this axis

Vendor benchmarks test isolated queries; production SOCs run two query populations at
once — a scheduled detection load that fires on its period regardless of how the last
cycle went, and analysts probing interactively on top of it. The transition the audience
actually hits is the scheduled:ad-hoc mix crossing the point where the interactive
experience degrades, and nothing in the public benchmark landscape measures it. This
bench locates that knee per engine and characterizes its failure shape (graceful /
plateau / cliff / silent-wrong, per the program's taxonomy).

## Mechanism

Two query populations against one engine at a time:

1. **Background scheduled load — open-loop.** A fixed-period generator modeling a
   detection scheduler: the cron fires on its period whether or not the last cycle
   finished. (A closed-loop client self-throttles and hides exactly the knee being
   measured — open-loop arrivals are the declared modeling choice.) K=6 pre-registered
   shapes carried verbatim from existing canonical texts:
   - j1, j4 from the engine-join-specialization SOC suite
   - port_scan and long_duration from the zeek-flagship-rerun suite
   - the H-ARCH-02 concurrency-sweep scan-aggregate
   - a 5-minute additive rollup
   Staggered in a 60 s cycle, rate scaled uniformly across the ladder.
2. **Foreground interactive probes** on a fixed 5 s schedule
   (coordinated-omission-safe), measuring p95 inflation against the R=0 baseline.

## Thresholds (pre-registered, from the program's operational definitions)

- Interactive: p95 < 10 s (flow) / < 30 s (tolerable) / > 60 s (broken)
- Scheduled: cycle utilization (Σ scheduled runtime per cycle ÷ cycle length) < 1.0;
  utilization approaching 1.0 is the early-warning signal under test (P3)
- Hard breaks: OOM, DNF (>300 s, two strikes), planner failure, server death

Full p95-vs-R curves publish with the results so any reader can re-derive the knee at
their own threshold — the 10 s / 30 s lines are ours, the curve is theirs.

## Sweep protocol

Per arm: R=0 baseline first (house protocol verbatim: 1 discarded warmup + 7 trials,
median + CV, oracle answer-equality against DuckDB); then a demand ladder ×2 per step
(U_demand ≈ 0.125 → 4.0); 60 s warm-in + 300 s measured window per step.

**Stop rule (mechanical, identical for every arm):** first of —
probe p95 > 30 s (the 10 s crossing recorded en route) · measured utilization ≥ 1.0
with monotone backlog growth · outstanding-query cap 64 · hard break — then one step
past the knee to characterize failure shape. A knee is claimable only on 3×
reproduction at the same ladder step.

## Arms (7)

| arm | notes |
|---|---|
| starrocks | MV rewrite off |
| starrocks_mv | pre-built async MVs covering the scheduled set, EXPLAIN-verified rewrite; labeled an UPPER BOUND — hand-built total coverage on a static table |
| clickhouse_iceberg | pinned metadata |
| clickhouse_native | the stats-less-layout control; its q5 cliff is prior art for this arm's failure shape |
| trino | — |
| dremio | Reflections off |
| duckdb_parquet | embedded, byte-identical files |

Reuses the engine-join-specialization compose stack and sha256-pinned corpora; the ejs
volumes persisting makes setup near zero. Note the ejs ClickHouse volume now carries
materialized statistics (task #29) — the clickhouse_native arm's baseline must declare
the stats state it runs with, and reproducing the historical q5 DNF requires dropping
them or `use_statistics=0`.

## Predictions (pre-registered; probabilities committed before any run)

- **P1 (~60%)** ch_native sustains the highest scheduled rate before the 10 s probe
  crossing; Trino knees first among server arms.
- **P2 (~55%)** duckdb_parquet fails gracefully but early.
- **P3 (~65%)** utilization is a valid early-warning signal — every graceful arm
  crosses U≈0.7 at least one full step before p95 crosses 10 s.
- **P4 (~55%)** every server arm sustains ≥60 scheduled queries/min on this corpus
  before the knee — i.e. the workload-mix transition does NOT arrive at modest
  detection-content counts on one host.
- **P5 (~60%, conditional on verified rewrite)** starrocks_mv shifts the knee right
  ≥2 ladder steps — the first measured coordinate for "the scheduled fraction at which
  the MV layer pays."
- **P6 (~50%)** at least one arm fails by cliff.
- **P7 (exploratory)** per-shape knees invert at least one pairwise ordering vs the
  suite knee.

## Isolation and tuning-risk controls (declared)

- cpuset 12/2 engine/client split — a declared deviation from the 14-thread join bench —
  gated by a **null-load calibration**: client-added latency must stay < 5% of the
  baseline probe median at max generator rate, or the run doesn't score.
- Result caches off; seeded parameter rotation so repeats don't measure caches.
- Mix composition pre-registered (this file); ladder and stop rule mechanical, derived
  from each arm's own baselines; the 18 GB ClickHouse cap carried and declared;
  open-loop arrivals declared as the modeling choice; thresholds pre-registered with
  full curves published.
- Single host (Beelink 5800H, WSL2 48 GB/14t), Tier B. What travels is ordering and
  shape; absolute coordinates ride with the caveat every time they appear.

## Feasibility

~2 h per arm-run ≈ 14 h of timed passes across 2–3 evenings. Scored runs happen in
quiet machine windows only (no concurrent benches, no foreground sessions competing
for the cpuset).

## Outputs

`results/RESULTS.md` (per-arm knee coordinate + failure shape + the P1–P7 scoring),
raw per-step JSON, and the p95-vs-R curve data. Findings feed the transition-atlas
dimension 2 gap (the scheduled:ad-hoc mix axis) and the program's §7 navigation map.

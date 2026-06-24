# RESULTS — SIGMA-EXEC scheduled-arm decomposition (2026-06-24)

Check A from the MDR-0034 measurement rethink. Tier B, single host, synthetic, DuckDB 1.5.3 in-process
(pySigma 1.3.3 / backend-sqlite 1.1.3; the `event_count` emit is byte-identical across the generic-SQL
engines, so the deployment-model question is engine-independent). Pre-registered:
`PRE-REG-scheduled-arm-2026-06-24.md`. Harness: `scheduled_arm_execution.py` → `results/scheduled_arm.json`.
Deterministic (`SEED=0x51614`; re-runs byte-identical). Adversarially verified read-only before recording
(a skeptic re-derived faithfulness, corpus correctness, and caught a DuckDB-truncation bug in the first
phase-sweep arm — fixed to true floor division; the corrected phase result is below).

## Question

The prior legs ran pySigma's windowless `event_count` emit (the `timespan: 10m` dropped) as ONE unbounded
scan over a 7-day corpus and reported precision 0.286 / 50 decoy FP. A real detection runs on a SCHEDULER
that bounds the input to a rolling lookback. Is the over-fire a property of the dropped timespan, or of the
unbounded-scan deployment? The harness re-runs the verbatim emit under a tumbling scheduler (the emit's
predicate applied per `(timestamp − BASE − phase) // L` bucket, unioned) and sweeps the lookback L.

## Verbatim emit under test

```sql
SELECT actor_user, COUNT(*) AS event_count FROM (SELECT * FROM logs WHERE outcome='FAILURE') AS subquery
GROUP BY actor_user HAVING event_count >= 10
```

(No time bound. The 10-minute window is gone.)

## Results

Corpus 1 — original (decoys = 12 failures spread over 7 days, ~14h apart; never ≥10 in any 10m bucket):

| arm | flagged | recall | precision | decoy FP |
|---|---|---|---|---|
| UNBOUNDED (verbatim emit, all history) | 70 | 1.00 | **0.286** | 50 |
| scheduled L=5m (< timespan) | 0 | 0.00 | — | 0 |
| scheduled L=10m (= in-rule window) | 20 | 1.00 | 1.000 | 0 |
| scheduled L=1h | 20 | 1.00 | 1.000 | 0 |
| scheduled L=6h | 20 | 1.00 | 1.000 | 0 |
| scheduled L=24h | 20 | 1.00 | 1.000 | 0 |
| scheduled L=48h | 20 | 1.00 | 1.000 | 0 |
| scheduled L=7d | 70 | 1.00 | 0.286 | 50 |

Corpus 2 — replanted (decoys = 12 failures spread over 24h, ~2h apart; still never ≥10 in any 10m bucket,
but ≥10 within a daily batch):

| arm | flagged | recall | precision | decoy FP |
|---|---|---|---|---|
| UNBOUNDED | 70 | 1.00 | 0.286 | 50 |
| scheduled L=5m | 2 | 0.10 | 1.000 | 0 |
| scheduled L=10m | 20 | 1.00 | 1.000 | 0 |
| scheduled L=1h | 20 | 1.00 | 1.000 | 0 |
| scheduled L=6h | 20 | 1.00 | 1.000 | 0 |
| scheduled L=24h | 70 | 1.00 | 0.286 | 50 |
| scheduled L=48h | 70 | 1.00 | 0.286 | 50 |
| scheduled L=7d | 70 | 1.00 | 0.286 | 50 |

Decoy-FP by grid phase {0%, 25%, 50%, 75% of L} at each lookback (the over-fire's phase sensitivity):

| lookback | corpus 1 | corpus 2 |
|---|---|---|
| ≤ 48h (corpus 1) / ≤ 6h (corpus 2) | `[0,0,0,0]` | `[0,0,0,0]` |
| corpus 1 L=7d / corpus 2 L=24h | `[50,0,0,0]` | `[50,0,0,0]` |
| corpus 2 L=48h | — | `[50,0,50,50]` |
| corpus 2 L=7d | — | `[50,50,50,50]` |

## Findings

1. **The 0.286 / 50-decoy-FP headline is a deployment artifact, not a property of the dropped timespan.**
   On the original corpus the windowless emit fires CORRECTLY (precision 1.0, 0 decoy FP) at every
   realistic scheduled batch lookback from 10m to 48h. The over-fire returns only as the lookback
   approaches the 7-day span over which the decoys accumulate ≥10 failures. The unbounded scan and the
   7-day lookback are the same regime.

2. **The window-drop CAN over-fire under a batch scheduler — but only under two joint conditions, and the
   magnitude is phase-contingent, not intrinsic.** It over-fires when (a) the scheduler lookback ≥ the span
   over which a benign entity accumulates ≥N events, AND (b) that accumulation lands within one scheduler
   bucket. At the threshold lookback (corpus 2 at L=24h, where a benign user's ≥10 daily failures just fit
   a daily batch) the over-fire is a knife-edge BEST-CASE phase: 50 decoy FP at the BASE-aligned grid, **0
   at every off-phase** — a real wall-clock-aligned daily batch would see the 22h accumulation straddle the
   midnight boundary as a phase coin-flip. The over-fire becomes phase-robust only when the lookback far
   exceeds the accumulation span (corpus 2 at L=7d → 50 FP at all phases).

3. **Under-fire is the other failure direction.** A scheduled lookback SHORTER than the rule's timespan
   (L=5m < 10m) collapses recall (0.00 / 0.10) — a 10-minute burst splits across two 5-minute windows of
   ~6 each, below the threshold. A naive rolling window narrower than the rule's own timespan silently
   MISSES real bursts.

## Net read (refines the H-SIGMA-01 claim; no confidence move)

The count-family window-drop is a **real but deployment-contingent** coverage risk, not an intrinsic 0.286
over-fire:

- The dropped timespan is **benign** under a scheduler whose lookback ≈ the rule's timespan (precision 1.0).
- It becomes a real over-fire risk as the **batch lookback grows past the span over which benign entities
  accumulate ≥N events** — i.e., for coarse hourly/daily batch detection — but the magnitude is phase- and
  span-contingent, never the 0.286 single number.
- A naive lookback SHORTER than the rule's timespan silently under-fires (misses real bursts).
- The earlier unbounded-scan leg measured the single configuration that maximizes AND stabilizes the
  over-fire; that 0.286 is the extreme, not the expected scheduled-batch case.

So the qualitative finding (pySigma drops the count-family in-rule window at the conversion layer, uniform
across the two compile paths tested) **holds**, but the 0.286 / 50-decoy-FP figure is an artifact of the
unbounded / phase-aligned regime and should not be quoted as the expected over-fire rate. The honest claim
is the **mechanism and its deployment-contingency**, not the number. H-SIGMA-01 is unmoved at 3/5 — this
tempers the magnitude of the supporting evidence within-band; it does not clear either 3.5 gate condition.
No confidence move banked.

## Limitations

Synthetic, single corpus family, single host, DuckDB only (sufficient — the emit and the deployment model
are engine-independent). The scheduler is tumbling; an overlapping/sliding schedule (step < lookback) would
trade boundary-miss for some double-counting and is not modeled here. The decoy corpora are
deliberately-constructed to isolate the lookback:accumulation-span relationship — the rates are not
transferable; the transferable findings are the three mechanisms above.

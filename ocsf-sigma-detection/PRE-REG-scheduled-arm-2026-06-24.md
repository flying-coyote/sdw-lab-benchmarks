# PRE-REG — SIGMA-EXEC scheduled-arm decomposition (2026-06-24)

Frozen before running. Loop-eng M6. Tier B, single host, synthetic. DuckDB in-process (the emit is
byte-identical across the generic-SQL engines, so the deployment-model question is engine-independent).

## Question

Is the headline over-fire (windowless `event_count` emit flags all 50 decoys → precision 0.286) a
property of the **dropped in-rule timespan**, or an artifact of the **deployment** the bench chose —
running the windowless emit as one unbounded full-table scan over all 7 days? A real detection runs on
a scheduler that bounds the input to a rolling lookback. Decompose the over-fire by lookback.

## Method

Run the **verbatim** pySigma-emitted windowless query (`SELECT actor_user FROM logs WHERE outcome =
'FAILURE' GROUP BY actor_user HAVING count(*) >= 10`) but with the input bounded to a tumbling schedule
window `[BASE + i·step, BASE + i·step + lookback)` (step = lookback, aligned to BASE), unioning firings
across all windows that cover the 7-day corpus. Faithful splice: the emit runs against a CTE
`logs AS (SELECT * FROM logs_all WHERE timestamp >= lo AND timestamp < hi)`, so the query is unchanged —
only the scheduler bounds the input. Reuse `ppl_execution.gen_corpus` + the existing `score()`.

Arms:
1. **Unbounded** — no time bound (reproduce the existing result).
2. **Scheduled sweep, original corpus** — lookback ∈ {5m, 10m, 1h, 6h, 24h, 48h, 7d}.
3. **Sub-timespan lookback** — lookback = 5m (< the rule's 10m), original corpus (the under-fire direction).
4. **Re-planted 24h-cadence decoys** — a NEW corpus variant: decoys accumulate 12 failures spread over
   24h (still never ≥10 in any 10m bucket; true/benign unchanged), swept at the same lookbacks. Tests
   whether the window-drop over-fires at a **realistic daily-batch lookback**, not only at 7 days.

The in-query-windowed control (tumbling `// 600` bucket) is run alongside as the 0-FP "do it right" baseline.

## Frozen predictions

- **Arm 1 (unbounded):** flagged 70, recall 1.0, precision 0.286, 50 decoy FP (reproduces the prior legs).
- **Arm 2 (original corpus sweep):** decoy FP = 0 and precision = 1.0 for lookback ≤ ~48h; decoy FP rises
  toward 50 only as lookback approaches the decoy spread (~5.25 days — decoy failures are ~14h apart, so
  ≥10 need a window ≳ 9·14h ≈ 5.25d). At lookback = 7d, ≈ the unbounded result (precision ~0.286). True
  recall stays 1.0 across lookbacks ≥ 10m (schedule aligned to BASE).
- **Arm 3 (lookback 5m):** recall collapses (≈ 0) — 12 failures uniformly over 10m give ~6 in any 5m
  window, < 10 → true bursts stop firing. The naive-rolling **under-fire** direction.
- **Arm 4 (24h-cadence decoys):** decoy FP ≈ 0 for lookback ≤ ~12h, then **returns to ~50 at lookback =
  24h** (the daily-batch cadence) → precision drops to ~0.286 at 24h; recall stays 1.0. Demonstrates the
  window-drop bites at a realistic lakehouse batch lookback, not only at an unbounded scan.

## Falsifier (what would weaken the MDR-0034 finding)

If decoy FP is **0 at every lookback > the rule timespan in BOTH the original AND the 24h-cadence corpus**
(i.e., the windowless emit never over-fires at any realistic batch cadence, only under a literal
unbounded scan), then the 0.286 is a pure unbounded-scan artifact with no realistic-cadence analog, and
the count-family survivability finding is substantially weakened (the dropped timespan would be benign
under any scheduler). Prediction: the falsifier does **not** fire — Arm 4 over-fires at 24h.

Conversely, if the **original** corpus over-fires at a micro-batch lookback (≤ 1h), the
no-scheduler-artifact critique is wrong and the original 0.286 is robust as-published. Prediction: this
also does not happen — the original corpus needs a ~5-day lookback.

## Known limitation (stated up front)

The schedule grid is aligned to BASE, so true-burst recall is flattered (bursts land cleanly in one
window) — same alignment as the original control. The result of interest is the **decoy-FP-vs-lookback
curve**, not true recall at window boundaries (that is the separate boundary-straddler check G). No
confidence move is gated to this run; it informs the MDR-0034 conditioning only.

## Actual vs predicted (recorded 2026-06-24 after the run)

- **Arm 1 (unbounded):** PREDICTED 70 / 0.286 / 50 FP — **MATCHED exactly.**
- **Arm 2 (original sweep):** PREDICTED precision 1.0 / 0 FP for lookback ≤ ~48h, over-fire only as
  lookback → ~5–7d — **MATCHED** (1.0 / 0 FP at 10m–48h; 0.286 / 50 FP at 7d).
- **Arm 3 (L=5m):** PREDICTED recall collapse — **MATCHED** (0.00 original, 0.10 replanted).
- **Arm 4 (24h-cadence decoys):** PREDICTED decoy FP returns to ~50 at L=24h — **MATCHED at the
  BASE-aligned phase.**
- **SURPRISE (not predicted): the over-fire at the threshold lookback is grid-phase-sensitive.** The
  first phase-sweep arm was buggy (DuckDB `//` truncates toward zero → a negative phase offset merged the
  sub-BASE slice into bucket 0, falsely showing 50 FP at all phases); an adversarial skeptic caught it,
  and the corrected floor-division sweep shows corpus-1 L=7d = `[50,0,0,0]` and corpus-2 L=24h =
  `[50,0,0,0]` across phases {0, ¼, ½, ¾}. So the daily-batch over-fire is a BEST-CASE-phase existence
  proof, not an expected rate — it becomes phase-robust only when lookback ≫ accumulation span (corpus-2
  L=7d = `[50,50,50,50]`). This narrows Arm 4's claim and is carried into the RESULTS findings.
- **Falsifier:** did NOT fire — the windowless emit does over-fire under a scheduler (corpus 2, L≥24h),
  so the dropped timespan is not benign under every scheduler. But the phase caveat substantially narrows
  the original "0.286" framing: that number is the unbounded / phase-aligned extreme, not the expected
  scheduled-batch case.

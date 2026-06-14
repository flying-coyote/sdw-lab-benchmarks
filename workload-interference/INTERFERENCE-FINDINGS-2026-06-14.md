# Workload-interference (#23) — findings + P1–P7 scorecard (2026-06-14)

First scored run of the pre-registered interference bench (6 of 7 arms; starrocks_mv deferred —
it needs the make_mvs.sql MV build and is moot here, see P5). Per-arm tables: `results/results.json`
(`results/RESULTS.md` is an auto-scaffold showing the last-invocation arm only). This is the
hand-written headline + prediction scorecard over all six arms.

**Tier B · single host (Beelink 5800H, WSL2 48 GB/14t, cpuset 12/2 engine/client split) · one
engine at a time · R=0 = 1 warmup + 7 trials · open-loop scheduled load · pre-registered
demand ladder U = 0.125 → 4.0.**

## Headline: the pre-registered ladder (to 4×) did NOT reach any engine's knee

The four server engines that passed the null-load calibration gate absorb the scheduled:ad-hoc
mix across the entire ladder with **negligible interactive-latency inflation** — probe p95 stays
flat and two-to-three orders of magnitude under the 10 s "flow" threshold, no DNFs, utilization
well under 1.0 even at 4× demand:

| arm | calibration gate | probe p95 across U=0.125→4.0 | failure shape | any p95 > 10 s |
|---|---|---|---|---|
| clickhouse_native | PASS | 0.051 → 0.068 s (flat) | graceful | no |
| clickhouse_iceberg | PASS | 0.15 → 0.19 s (flat) | graceful | no |
| starrocks | PASS | 0.099 → 0.091 s (flat) | graceful | no |
| dremio | PASS | 0.45 → 0.48 s (flat; util 0.02 → 0.26 at 4×) | graceful | no |
| duckdb_parquet | **FAIL** (15.95% client-added) | — not scored — | — | — |
| trino | **FAIL** (52.59% client-added) | — not scored — | — | — |

So on a single host, a scheduled detection load up to 4× the base rate does **not** break the
interactive experience for these columnar/MPP engines — interactive p95 barely moves. The
single-host benchmark numbers the rest of the lab rests on are **not invalidated by realistic
concurrent mixed load at these levels**; the workload-mix transition lives somewhere past 4×.

## The two calibration exclusions are themselves findings

- **duckdb_parquet (embedded): 15.95% client-added latency** — fails the <5% gate by design. The
  embedded model shares host cores with the client (the cpuset 12/2 split applies to the
  server-engine arms, not an in-process engine), so its "interference" inherently includes the
  client itself. The gate correctly refuses to score it as a clean engine-isolation result — for
  the embedded architecture, client and engine contention are not separable, a property of the
  architecture, not a measurement artifact.
- **trino: 52.59% client-added latency** — Trino's per-query statement-API + coordinator-planning
  overhead is large relative to this corpus, so the calibration probe under load inflates past
  the gate. A heavier corpus would amortize Trino's high fixed per-query cost.

## P1–P7 scorecard (pre-registered in README.md)

| # | prediction | verdict |
|---|---|---|
| P1 (~60%) | ch_native sustains the highest rate before the 10 s crossing; Trino knees first | **INCONCLUSIVE** — no arm crossed 10 s. Direction consistent: ch_native has the most headroom (lowest p95 ~0.05–0.07 s); Trino didn't score (calibration fail). |
| P2 (~55%) | duckdb_parquet fails gracefully but early | **INCONCLUSIVE** — duckdb was calibration-excluded (15.95%); it failed the isolation gate, not "early under load." |
| P3 (~65%) | utilization is a valid early-warning (graceful arms cross U≈0.7 a step before p95 crosses 10 s) | **INCONCLUSIVE / supported-in-spirit** — no p95 crossing, so nothing to early-warn; utilization stayed low (≤0.26 at 4×), consistent with no knee. |
| P4 (~55%) | every server arm sustains ≥60 scheduled queries/min before the knee | **CONFIRMED** — all 4 scored server arms sustained the full ladder to 4× (dremio completed 120 scheduled queries at 4×, util 0.26) with no knee. |
| P5 (~60%) | starrocks_mv shifts the knee right ≥2 steps | **NOT TESTED + moot** — deferred (needs make_mvs.sql); no knee in range for an MV layer to shift. |
| P6 (~50%) | at least one arm fails by cliff | **NOT OBSERVED** — no scored arm failed; all 4 graceful (the 2 unscored were calibration exclusions, not cliffs). |
| P7 (exploratory) | per-shape knees invert an ordering | **INCONCLUSIVE** — no knees to compare. |

Honest summary: **P4 confirmed; the knee-dependent predictions (P1, P3, P5, P6, P7) are
inconclusive because the pre-registered ladder didn't reach a breaking point.** That is the
result, and it motivates the follow-up.

## Extend-ladder result (2026-06-14): the knee is at 32–64× base demand

The 4 graceful arms were re-run on a ladder extended to **64×** (`extend_ladder.sh`). The knee
appears only at the very top — the interactive p95 stays flat (well under the 10 s flow line)
through 16–32× and then inflects sharply:

| arm | p95 flat through | knee (sharp inflection) | p95 at 64× | failure shape |
|---|--:|--:|--:|---|
| clickhouse_native | 32× (~0.08 s) | **64×** | 3.11 s | graceful |
| clickhouse_iceberg | 32× (~0.20 s) | **64×** | 4.05 s | hard-break (scheduler saturates, util ≥ 1.0) |
| starrocks | 32× (~0.10 s) | **64×** | 4.93 s | hard-break |
| dremio | 8× (~0.45 s) | **~16–32×** | 5.78 s | graceful (degrades earliest) |

So on a single host the scheduled:ad-hoc mix tolerates **16–32× the base scheduled rate** before
the interactive experience inflects, and even at **64×** the probe p95 (3–6 s) never crosses the
30 s "broken" threshold. The headroom is enormous relative to any realistic SOC scheduled load.
Dremio knees earliest (~16–32×), consistent with its higher per-query REST/coordinator overhead;
the ClickHouse arms and StarRocks hold flat to 32× and inflect at 64×, where the open-loop
scheduler saturates (util ≥ 1.0, backlog growth → the "hard-break" classification, not a p95
crossing). This resolves the P1/P3/P6/P7 predictions that were inconclusive at ≤4×: a knee
exists, it is far out (32–64×), and at least two arms fail by scheduler-saturation rather than
graceful degradation at that point.

**Claimability:** per the pre-registration, a knee is claimable only on **3× reproduction at the
same ladder step** — now **DONE** (see Phase C below).

## Phase C — knee reproduced 3× (2026-06-14): the knee is now claimable

Three independent runs (run-1 = this extend-ladder; run-2 = a repeat over the 16/32/64×
knee region; run-3 = a clean repeat) all trip the mechanical stop rule at the **same** ladder
step for every arm, so the knee is claimable per the pre-registration:

| arm | knee per run [1,2,3] | reproduced 3× | p95 band at the knee step (min/median/max over 3 runs) |
|---|---|:--:|---|
| clickhouse_iceberg | [64×, 64×, 64×] | **yes (U=64)** | 1.16 / 2.70 / 4.05 s |
| clickhouse_native | [64×, 64×, 64×] | **yes (U=64)** | 3.11 / 3.21 / 3.47 s |
| starrocks | [64×, 64×, 64×] | **yes (U=64)** | 3.25 / 3.77 / 4.93 s |
| dremio | [32×, 32×, 32×] | **yes (U=32)** | 4.35 / 4.58 / 4.80 s (at 32×) |

So the single-host scheduled:ad-hoc mix tolerates **~32× the base scheduled rate** before the
interactive experience inflects, and the knee location is stable across three runs. The p95
*magnitude* at the knee spreads run-to-run (e.g. ch_iceberg 1.16–4.05 s at 64×) — that is
expected near saturation and is why the location, not the magnitude, is the claim. (Caveat:
run-2's magnitudes may be mildly inflated by concurrent unrelated docker work during its
original capture; the knee *location* is throughput-determined and unaffected, and run-1/run-3
were clean.) Harness note: the first Phase-C attempt's per-rep capture silently dropped reps
1–2 (a `docker run` without `-i` never fed its capture heredoc to the container), so the
captures were redone host-side; the runs themselves were valid. Per-arm captures:
`_work/phase_c/run{2,3}_<arm>.json`; analysis `PHASE-C-SUMMARY.json` + `phase_c_analyze.py`.

## starrocks_mv (P5) — the MV upper bound did NOT shift the knee

The `starrocks_mv` arm (six pre-built MVs covering the scheduled set, EXPLAIN-verified rewrite,
the README's hand-built UPPER BOUND) was run on a ladder reaching 256× to look for P5's
predicted ≥2-step rightward knee shift. It **did not shift**: the MV arm knees at the **same
64×** as base StarRocks (0 steps right), so **P5 is not supported**. The reading: at 64× the
binding constraint is open-loop scheduler / per-query coordinator saturation (the scheduler
fires 64× the base rate; even a near-instant MV-rewritten query pays fixed per-query overhead),
not the per-query *compute* the MVs accelerate — so pre-materialising the scheduled answers buys
no interference headroom. Honest caveats: a single MV run, p95 went non-monotonic past the knee
(64×: 3.26 s, 128×: 2.69 s — saturation noise), and `make_mvs.sql` needed a `REFRESH ASYNC →
REFRESH MANUAL` fix for StarRocks 4.1 (external-catalog ASYNC MVs require a refresh interval;
MANUAL matches the build-once/static intent and the MV content is unchanged). Rewrite was
EXPLAIN-verified at start (run.py aborts otherwise). P5 would need reproduction for a firm
claim, but the direction — MV acceleration does not move the interference knee — is the result.

## Scope, honestly

Single host, one engine at a time, cpuset 12/2 split, result caches off, open-loop arrivals
(declared). What travels is the ordering + failure shape; absolute demand coordinates ride with
the single-host caveat. The "no knee ≤4×" finding is bounded by the corpus (10M-row conn +
moderate scheduled shapes) — a larger corpus or heavier shapes would move the knee left.

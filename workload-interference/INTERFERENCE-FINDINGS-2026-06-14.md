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

## Next step (motivated by this result): extend the ladder to find the knee

Since nothing kneed at ≤4×, the open question is *where* the single-host mix breaks. The
follow-on extends the ladder to 8× / 16× / 32× (or a heavier scheduled-shape mix) on the 4
graceful arms to locate the actual knee + its failure shape, with the pre-registered 3×
reproduction at the knee step before any knee is claimable. starrocks_mv (the MV upper bound) is
worth running once a knee exists for it to shift.

## Scope, honestly

Single host, one engine at a time, cpuset 12/2 split, result caches off, open-loop arrivals
(declared). What travels is the ordering + failure shape; absolute demand coordinates ride with
the single-host caveat. The "no knee ≤4×" finding is bounded by the corpus (10M-row conn +
moderate scheduled shapes) — a larger corpus or heavier shapes would move the knee left.

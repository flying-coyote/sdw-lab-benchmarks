# MV-rewrite at matched freshness — Dremio Reflections vs StarRocks async MV (task #25)

**Status: PRE-REGISTERED 2026-06-10, before any scored run.** This README is the
pre-registration; design, thresholds, and predictions are committed ahead of the first
scored pass and will not be edited after scoring starts (errata get appended, not
rewritten). Scored runs happen in quiet machine windows only. Program home:
transition-point program §8 item 5 — the Dremio-fairness follow-up from the
engine-join-specialization bench and the cross-engine companion to the
workload-interference bench's P5.

## Why this bench

The join bench ran Dremio with Reflections OFF (fairness: no other arm had a
materialization layer), which measured Dremio's planner, not the product as sold. The
interference bench's starrocks_mv arm is a declared upper bound (hand-built total
coverage, static table). What neither measures is the comparison buyers actually face:
two transparent-rewrite implementations at the SAME freshness budget on a LIVE table —
acceleration is easy on static data; the honest test is acceleration while the table
moves and both layers pay their refresh bills.

## Mechanism

Shared Iceberg table (ejs compose stack, sha256-pinned corpora), with a fixed-rate
appender writing micro-batches so the base table advances continuously. Two
acceleration arms at matched freshness, two controls:

| arm | notes |
|---|---|
| dremio_reflections | raw + aggregation Reflections covering the query set; refresh policy set to the matched freshness budget T |
| starrocks_mv | async MVs covering the same query set, identical definitions where dialects allow; REFRESH ASYNC every T |
| dremio_base | Reflections off — the join-bench configuration, the control |
| starrocks_base | MV rewrite off — the control |

**Matched freshness:** both acceleration layers refresh on the same budget
(T = 5 min, declared; one ladder step at T = 1 min if the 5-min runs complete clean).
Rewrite must be EXPLAIN-verified per query per arm — a query that silently falls
through to base scan is scored as a rewrite miss, not as the accelerated path.

**Query set:** the six scheduled shapes carried verbatim from the interference
pre-registration (j1, j4, port_scan, long_duration, scan-aggregate, 5-min rollup) —
deliberately the same shapes, so P5's within-engine result and this bench's
cross-engine result compose.

## Measurements (per arm, house protocol: 1 discarded warmup + 7 trials, median + CV)

1. **Rewrite hit rate** — EXPLAIN-verified, per query.
2. **Accelerated latency** vs the arm's own base control (the honest speedup) and
   cross-engine at matched freshness (the buyer's comparison).
3. **Staleness** — measured event-to-queryable lag through the acceleration layer at
   refresh boundaries (worst-case within T), not the configured T.
4. **Refresh cost** — engine CPU-seconds and wall time per refresh cycle while the
   appender runs.
5. **Answer equality** — accelerated answers vs the live base table vs the DuckDB
   oracle, sampled at refresh boundaries where staleness divergence is maximal; a
   wrong answer from a stale-but-claimed-fresh layer is a silent-wrong finding,
   reported in the failure-shape taxonomy.

## Stop rules / validity gates

- An arm whose rewrite cannot be EXPLAIN-verified on a query scores that query as a
  miss; if total coverage < 3 of 6 queries, the arm's cross-engine comparison is
  reported as coverage-limited rather than scored on latency.
- Refresh falling behind the appender (cycle time > T for 3 consecutive cycles) is a
  finding (the freshness budget is unsustainable at this rate), not a retry.
- DNF / OOM rules carried from the house protocol (>300 s two strikes, hard breaks
  recorded).

## Predictions (pre-registered; probabilities committed before any run)

- **P1 (~60%)** StarRocks async MV achieves a higher EXPLAIN-verified rewrite hit rate
  on these six shapes than Reflections (SPJG rewrite breadth on join-bearing shapes).
- **P2 (~55%)** Reflections show lower refresh cost per cycle at matched T (Dremio's
  incremental reflection maintenance vs full MV refresh on at least one shape).
- **P3 (~65%)** Both arms' worst-case measured staleness exceeds T/2 at the refresh
  boundary — configured freshness understates delivered staleness for both products.
- **P4 (~50%)** At least one query in one arm silently returns stale data outside its
  declared freshness window (the silent-wrong class) — caught only by the
  answer-equality sample.
- **P5 (exploratory)** The accelerated-latency ordering at matched freshness inverts
  the join bench's base-engine ordering on at least one shape (the MV layer, not the
  engine, decides the buyer-visible ranking).

## Feasibility

~2 evenings: one for Reflection/MV definition + EXPLAIN verification + null-load
calibration, one for the timed passes. Reuses the ejs compose stack and pinned corpora;
the appender is the streaming-cadence bench's writer pointed at the ejs table. cpuset
and quiet-window discipline carried from the interference pre-registration.

## Outputs

`results/RESULTS.md` (hit rates, matched-freshness latency, staleness, refresh cost,
answer-equality findings, P1–P5 scoring). Feeds: Matrix C3's semantic-layer/Reflections
criterion and the new routability row's transparent-rewrite leg (through the karen +
hypothesis gate), the interference bench's P5 interpretation, and the single-front-engine
essay's MV-layer section.

Single host (Beelink 5800H, WSL2 48 GB/14t), Tier B. What travels is ordering and
shape; absolute coordinates ride with the caveat every time they appear.

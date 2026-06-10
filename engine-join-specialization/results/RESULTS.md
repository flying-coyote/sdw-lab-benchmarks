# RESULTS — joins on shared Iceberg: StarRocks wins the deep joins, the spread is small, and ClickHouse's one DNF is its own native table

**Tier B · single host (WSL2, 48 GB / 14 threads, High Performance power plan verified
pre-run) · 2026-06-10 · one engine timed at a time, 1 discarded warmup + 7 trials per
query, all claims gated on gap % > max(CV_a, CV_b) · every reported answer identical to
the DuckDB ground-truth oracle across all five arms (54 of 55 cells; the 55th is a loud
timeout DNF, not a wrong answer).**

Engines: StarRocks 4.1 (allin1) · ClickHouse 26.5.1.882 (two arms: Iceberg via pinned
`icebergS3`, native MergeTree `ORDER BY tuple()`) · Trino 481 · Dremio OSS 26.0
(reflections OFF, v3 job-API overhead included as its serving path) — all reading the
same Nessie-cataloged Iceberg tables on MinIO, byte-identical files. TPC-H disclaimer:
F1 is *derived from* TPC-H (DuckDB dbgen SF10); not audited, not comparable to published
TPC-H results.

## Completion

| arm | completed | the gap |
|---|---|---|
| starrocks | 11/11 | — |
| clickhouse_iceberg | 11/11 | — |
| clickhouse_native | **10/11** | **tpch_q5 timeout (>300 s, both strikes)** — the same engine reads the same data via Iceberg in 1.35 s |
| trino | 11/11 | — |
| dremio | 11/11 | — |

## F1 — TPC-H-derived join subset (SF10, medians of 7)

| query | starrocks | ch_iceberg | ch_native | trino | dremio |
|---|---|---|---|---|---|
| q3 (3-table) | **0.990 s** | 1.504 s | 1.364 s | 3.300 s | 3.106 s |
| q5 (6-table) | **1.178 s** | 1.347 s | DNF | 2.453 s | 4.926 s |
| q9 (6-table, heaviest) | **1.863 s** | 5.217 s | 5.041 s | 4.011 s | 5.754 s |
| q18 (agg-join) | 1.893 s | 1.485 s | **1.186 s** | 6.345 s | 6.141 s |
| q21 (correlated EXISTS) | **1.288 s** | 4.257 s | 1.908 s | 6.740 s | 11.143 s |
| **sum** | **7.21 s** | 13.81 s | (DNF) | 22.85 s | 31.07 s |

StarRocks wins 4 of 5 (all CV-claimable; the narrowest, q5 vs ch_iceberg, is a 14.3% gap
against a 10.0% max-CV gate). The exception is q18, the most aggregation-shaped query,
where both ClickHouse arms beat it (ch_iceberg 1.27× faster, claimable). On the heaviest
join (q9) StarRocks is 2.15× faster than Trino, 2.7–2.8× than both ClickHouse arms, and
3.1× than Dremio. Family sums: StarRocks 1.9× faster than ClickHouse-Iceberg, 3.2× than
Trino, 4.3× than Dremio.

## F2 — SOC join suite (medians of 7)

| query | starrocks | ch_iceberg | ch_native | trino | dremio |
|---|---|---|---|---|---|
| j1 dim-enrichment (10M × 14.8k) | 0.167 s | 0.215 s | **0.126 s** | 0.564 s | 0.847 s |
| j2 large-large (53.0M pairs) | 0.856 s | 0.874 s | 0.862 s | 1.411 s | 1.170 s |
| j3 two-streams agg join | 0.100 s | **0.083 s** | **0.086 s** | 0.231 s | 0.353 s |
| j4 IOC semi-join | 0.124 s | 0.140 s | **0.069 s** | 0.286 s | 0.405 s |

- j2 is a **statistical three-way tie** (StarRocks / both CH arms within 0.7–2.1%, CVs
  4.4–8.0%): a 10M × 1M correlation join producing 53.0 million pre-aggregation pairs
  completes in ~0.86 s on three different engines.
- j1: ch_native first (claimable, 32.5% > 16.2%); StarRocks ahead of ch_iceberg
  (claimable, 28.7% > 6.7%).
- j3: the two CH arms tie with each other (3.6% < 8.8%) ahead of StarRocks
  (claimable, 20.5% > 8.8%).
- j4: ch_native first (claimable, 79.7% > 12.7%); StarRocks vs ch_iceberg NOT claimable
  (12.9% < 15.2%).
- Every arm answers every SOC join between 0.07 s and 1.41 s.

## F3 — join tax (median T_join / median T_flat, same answer both ways)

| arm | tax |
|---|---|
| clickhouse_native | 1.76× |
| clickhouse_iceberg | 1.83× |
| dremio | 1.85× |
| starrocks | 1.88× |
| trino | **4.35×** |

The pre-registered prediction (#6: StarRocks smallest, CH-Iceberg largest) was wrong:
StarRocks, both ClickHouse arms, and Dremio all pay essentially the same ~1.8× tax, and
Trino is the outlier at 4.35×. In absolute terms the tax is 77 ms on StarRocks
(88 → 165 ms) — at this scale the join is not a reason to denormalize on four of the
five arms.

## Predictions scorecard (pre-registered, committed before any scored run)

1. **SOC ordering SR > CH ≈ Trino > Dremio (~55%/~65%): partly right.** Dremio-last
   confirmed everywhere. But ch_native took j1 and j4 outright, so "StarRocks first"
   holds on F1, not F2; among the Iceberg-reading arms StarRocks leads where the gate
   passes.
2. **Per-shape (~40–60%): mixed.** j4-to-ClickHouse confirmed; j1-to-StarRocks wrong
   (ch_native took it); j2 was predicted the highest-variance cell and landed as a tie.
3. **Completion (~60%): wrong in the most interesting way.** Everyone completed q21 —
   including ClickHouse, whose 26.x decorrelation handled the correlated EXISTS on both
   arms. The DNF came on **q5, on the native arm**, while the Iceberg arm ran it in
   1.35 s.
4. **CH native > CH Iceberg on every join (~70%): mostly held, with two exceptions** —
   q9 is a statistical tie (3.5% gap < 5.8% CV), and q5 is the DNF. Where claimable,
   native wins by 1.1–2.2× (q21: 2.2×).
5. **Compressed spread (~75%): confirmed, and it is the headline.** Across 11 join
   queries and five arms, every completed median is 0.069–11.1 s; the SOC suite never
   exceeds 1.5 s on any engine; the F1 family spread is 4.3× end to end. The 3–26× of
   the vendor marketing literature (and the Tier-C "30–120 s vs 5–30 s" anchor the
   public assets carry) describes a different scale, not this one.
6. **Join tax (~55%): wrong.** Four arms cluster at ~1.8×; Trino is the 4.35× outlier.

## The findings worth keeping

1. **Engine specialization on joins is real but small at SOC single-node scale.**
   StarRocks is measurably the join leader (4 of 5 TPC-H-derived wins, 2.7–2.8× on the
   deepest join) and ClickHouse measurably wins the aggregation-shaped work (q18, j3,
   j4) — the deck's role assignments point the right way — but the magnitudes are
   single-digit ×, mostly under 3×, and several cells are statistical ties. The
   assignment criteria that should drive engine choice at this scale are catalog
   maturity, concurrency, and ops, not the join-latency war.
2. **The one completion failure is ClickHouse's own native table.** Same engine, same
   query (q5, 6-table), same host: >300 s twice on stats-less MergeTree
   (`ORDER BY tuple()`, the declared layout control), 1.35 s over Iceberg. "Native is
   always faster" fails loudly on exactly one join shape; where it completes, native
   wins by 1.1–2.2×.

   **Post-run EXPLAIN diagnostic (2026-06-10).** The run-day inference (statistics-dependent
   — the Iceberg read path carries column stats the bare MergeTree copy lacks) was half
   right. Instrumented: *neither* arm carries column statistics (`SHOW CREATE TABLE` shows
   none; `materialize_statistics_on_insert=0`; no `system.statistics`). The difference is
   that the native path engages 26.5's greedy join reordering
   (`query_plan_optimize_join_order_limit=10`), which, planning on raw table row counts
   alone, reordered q5 dimension-first through the many-to-many
   `c_nationkey = s_nationkey` step — a measured 1,203,307,921-row intermediate with
   lineitem (60M rows) still to come as a hash-build side. With
   `query_plan_optimize_join_order_limit=0` the plan reverts to the written TPC-H order and
   the same native table answers in 5.3 s wall with the oracle-matching result. The
   `icebergS3` table-function arm keeps the written join order, which is why it never saw
   the cliff. Same manageability lesson, sharper mechanism: the optimization engages
   stats-blind on the native path.
3. **The join tax does not justify flattening on this hardware for four of five
   engines** (~1.8×, sub-second absolute), and Trino's 4.35× is the measured version of
   why federation engines get handed the pre-joined copies.
4. **Dremio without Reflections is last or near-last on every query** (8.65× behind
   StarRocks on q21), with its v3 job-API orchestration overhead counted as analysts
   experience it — the measured confirmation that Dremio's acceleration story *is* the
   Reflections layer, which this bench deliberately did not enable. The
   Reflections-vs-StarRocks-MV rewrite tier remains unmeasured by anyone, including us
   (named follow-up).

## Scope, honestly

Single host, 10M–60M-row tables, hot/warm only, one engine at a time, engine defaults
plus declared accommodations (CH: 18 GB per-query cap, alias relaxation, metadata pin;
SR: planner-timeout guard raised; Dremio: Nessie source). Magnitudes are parameters of
this corpus and scale — the Tier-C TB-scale vendor claims are neither confirmed nor
refuted; they are about a different regime. Dremio ran reflections-off by design.
TPC-H-derived results are not comparable to audited TPC-H publications. Raw trials,
answers, and the full pairwise CV-gate matrix: `results/raw_*.json`,
`results/comparison.json`.

## What this moves

H-ARCH-06 (first first-party lab evidence: per-shape join winners measurably differ) ·
H-ARCH-02 (join shapes added to the workload matrix) · Matrix Component 3 (StarRocks
Archetype-B "CBO joins" score can move Tier C → Tier B measured; the
starrocks-clickhouse-pair reference's vendor-published 30–120 s / 5–30 s anchor should
be replaced with these first-party numbers and a scale caveat) · deck slide 16's
"broader joins untested" is now true-in-the-past · the single-front-engine essay
(placeholders) · the routing assessment's compressed-spread gate (task #13/#14
realignment next).

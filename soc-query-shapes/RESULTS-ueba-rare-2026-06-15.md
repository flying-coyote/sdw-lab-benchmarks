# SOC query-shape bench #2+3 — UEBA Z-score + rare-value (2026-06-15)

The other two external-review P4 backlog shapes, run across the 4 Iceberg-reading engines on the
shared `soc.conn` (10.3M, structured flow; aggregate output only). Each shape timed vs a flat
aggregation baseline to test P4's question: do these regimes reorder the engines the flagship ranked?
Tier B, single host (ejs).

- **UEBA volume Z-score** — two-level aggregation: hourly connection volume per host → per-host
  baseline mean/stddev → flag hosts whose peak hour is `Z = (peak-mean)/stddev > 3`.
- **rare-value / first-seen** — high-cardinality `count(DISTINCT)`: destinations contacted by exactly
  one source.

## Latency + ranking (the valid finding)

| engine | flat | UEBA (2-level agg) | UEBA / flat | rare (count-distinct) | rare / flat |
|---|---|---|---|---|---|
| ClickHouse-Iceberg | 0.037 s | 0.378 s | 10.3× | 1.255 s | 34.1× |
| StarRocks | 0.064 s | **0.207 s** | 3.2× | 1.303 s | 20.3× |
| Trino | 0.089 s | 0.421 s | 4.8× | 3.412 s | 38.5× |

(Dremio arm withheld under its benchmark-publication terms.)

- **flat ranking:** CH-Iceberg < StarRocks < Trino (ClickHouse wins flat single-level agg, as
  in the flagship).
- **UEBA ranking INVERTS the top:** StarRocks (0.207 s) < ClickHouse-Iceberg (0.378 s) <
  Trino. **StarRocks overtakes ClickHouse** on the two-level aggregation — an 82% gap, far above the
  3.2% CV, so claimable. This is the headline: the regime *does* reorder the leaders.
- **rare-value:** ClickHouse keeps the lead on the high-cardinality `count(DISTINCT)`, and the
  StarRocks-overtakes-ClickHouse top-of-ranking inversion seen in UEBA does NOT recur here.

## What it means

P4 hypothesized that SOC query shapes beyond flat scan-aggregation can invert the engine ranking.
**Supported, but shape-specific:**
- the **window/lag** shape (beaconing, bench #1) did **not** invert the order;
- the **two-level aggregation** shape (UEBA) **does** — StarRocks overtakes ClickHouse, exactly the
  pattern from the engine-join bench (StarRocks wins multi-step relational/aggregation work, ClickHouse
  wins flat single-level scans). So the inversion isn't random; it tracks the **multi-step vs
  single-level** axis. This sharpens the engine-specialization / Matrix framing: ClickHouse for flat
  scans + single-level agg, StarRocks once the query gains a second aggregation/join level.

## Limitation (honest)

Both detections returned **0 rows** — synthetic `soc.conn` has no UEBA volume spikes and no
single-source destinations (resp_h is drawn from a small pool), so the *detection correctness* /
answer-equality is **unvalidated** for these two shapes (the reported "answer-equal" is the trivial
empty-set match — disregard it). The expensive aggregation still ran fully (HAVING filtered at the
end), so the **latency/ranking finding stands**. Detection-correctness with answer-equality was
demonstrated on planted ground truth in bench #1 (beaconing, 100% recall, exact cross-engine equality);
validating UEBA/rare the same way needs planted anomalies (a volume-spike host set + single-source
destinations) — owed if the detection arm is wanted. ClickHouse-Iceberg worked here (soc.conn is not
a fresh table, unlike the beacon-planted run). Gate before any hypothesis confidence move.

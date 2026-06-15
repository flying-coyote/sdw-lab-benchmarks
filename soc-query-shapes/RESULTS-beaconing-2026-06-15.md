# SOC query-shape bench #1 — C2 beaconing (window-function regime), 2026-06-15

First of the external-review P4 backlog shapes (the SOC shapes the flagship flat-aggregation + needle
benches don't cover). The question P4 raised: does a **window/sort-heavy** regime (per-pair
inter-arrival gap variance — `LAG` over time-ordered connections, then coefficient-of-variation of
the gaps) **invert the engine ranking** the flagship established? Tier B, single host (ejs stack),
Iceberg-reading engines over the shared catalog. **Safety:** structured Zeek conn flow only
(ts/IPs/ports/proto); output is aggregate (per-pair gap stats, counts, latencies); no raw event rows
surfaced — see [[feedback_security_telemetry_injection_surface]].

## Two parts

**(A) Window-regime ranking — real corpus, 4 engines, 10.3M rows (`soc.conn`).**
The window query (PARTITION BY orig_h,resp_h ORDER BY ts → `lag` gap → `stddev_pop(gap)/avg(gap)`)
ran full machinery over all 10.3M rows; a matched flat aggregation (`GROUP BY proto`) is the
baseline.

| engine | beacon (window) median | flat median | window / flat |
|---|---|---|---|
| ClickHouse-over-Iceberg | 1.608 s | 0.037 s | 43.5× |
| StarRocks | 1.742 s | 0.061 s | 28.3× |
| Trino | 5.811 s | 0.103 s | 56.5× |
| Dremio | 7.160 s | 0.420 s | 17.1× |

- **The ranking did NOT invert.** Window order = flat order = ClickHouse-Iceberg < StarRocks < Trino
  < Dremio. P4's hypothesis (window/sort-heavy reorders the engines) is **not supported** on this
  four-engine set — the columnar leaders stay ahead.
- The window regime is **17–57× more expensive** than the flat aggregation (the partition+sort cost),
  so it *is* a materially different regime — it just doesn't change *who wins*.
- `soc.conn` has **no beacon structure** to detect (8.9M distinct pairs, max 3 connections/pair, 0
  pairs ≥9) — so this run measures the regime *latency/ranking* honestly, not detection. Detection is
  Part B.

**(B) Detection correctness — planted ground truth, 805K rows (`soc.conn_beacontest`).**
Synthetic corpus (`gen_beacon_corpus.py`, seed 42): 800K random background TCP flows + **120 planted
regular-interval beacons** (25–45 callbacks, interval ∈ {30,60,300}s + ≤8% jitter) + **30 irregular
decoy heavy-talkers** (must NOT rank as beacons). Fully synthetic — no real/adversarial telemetry.

| engine | beacon median | recall (of 120) | precision @150 | pairset |
|---|---|---|---|---|
| StarRocks | 0.202 s | **100%** | 80% | identical |
| Trino | 0.407 s | **100%** | 80% | identical |
| Dremio | 0.690 s | **100%** | 80% | identical |
| ClickHouse-Iceberg | — | DNF | — | (see note) |

- **100% recall** on all three catalog engines: every planted beacon surfaced, and the CV ranking put
  the 120 beacons above the 30 decoys (the "80% precision" is just the 30 decoys filling the LIMIT-150
  tail; at LIMIT 120 it is ~100%). The deterministic detection works and is correct.
- **Answer-equality holds exactly:** StarRocks, Trino, and Dremio return byte-identical top-150 pair
  sets (same pairs, same per-pair connection counts) — the lab's signature cross-engine equality on
  known truth.
- **ClickHouse-Iceberg DNF'd on the freshly-created table** (returned 0 rows in 13 ms). This is the
  known `icebergS3()` catalog-less metadata-resolution fragility on a just-written pyiceberg table
  (Nessie's non-sequential metadata naming) — it read the older `soc.conn` fine in Part A but could
  not resolve `conn_beacontest`'s data. A real, documented limitation of CH's catalog-less Iceberg
  read path (see `reference_clickhouse_icebergs3_stale_snapshot`); routing CH through a REST
  DataLakeCatalog would fix it — owed if a 4-engine detection arm is wanted.

## Net

The beaconing window-function shape is a genuinely different (17–57× costlier) regime, but on this
four-engine set it **does not reorder the engines** — so the flagship's columnar-leaders ranking is
robust to the window regime, narrowing P4's "this shape inverts the ranking" hypothesis. The
deterministic beacon detection is **portable and correct** (100% recall, exact cross-engine
answer-equality on planted truth). Gate before any hypothesis confidence move (karen →
hypothesis-validator → contradiction). Candidate home: the two-regime / engine-specialization frame
(window-regime is a third regime alongside scan-aggregation and point-lookup). Dialect note: with `ts`
as a double epoch the query is portable except `lag`→`lagInFrame` and `stddev_pop`→`stddevPop` for
ClickHouse — a small common-subset gap, consistent with the routing-assessment dialect findings.

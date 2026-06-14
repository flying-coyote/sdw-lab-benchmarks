# Flagship — triple-run band on the two-regime core (2026-06-14)

Three independent draws of the flagship 4-arm benchmark (the 145×→two-regime number). Tier B,
single host (Beelink 5800H, WSL2 48 GB/14t), one engine up at a time, 1 warmup + 7 trials,
engine-cold, CV-gated. Draws:

- **draw-1** = `results/` (the canonical published draw)
- **draw-2** = `results_revalidation_2026-06-14/` (the Jeremy-priority revalidation)
- **draw-3** = `results_revalidation3_2026-06-14/` (this pass; ClickHouse arms via `draw3_proper.sh`,
  OpenSearch via `finish_draw3.sh` with readiness-gating)

The corpus, answer-equality, and two-regime split are identical across all draws (answer-equality
ALL IDENTICAL each draw — same data, same answers). What the band shows is how stable the
*multiples* are run-to-run.

## The two-regime core is triple-validated (tight bands)

| metric | draw-1 | draw-2 | draw-3 | band | what it is |
|---|--:|--:|--:|---|---|
| OpenSearch foil ÷ ClickHouse-Iceberg (scan aggregation) | 10.1× | 10.6× | 11.3× | **~10–11×** | the columnar lakehouse engine beats the inverted-index foil on scan-heavy aggregation |
| ClickHouse-Iceberg ÷ ClickHouse-native (open-format tax) | 4.6× | 4.3× | 4.2× | **~4.2–4.6×** | the cost of reading Iceberg over the engine's native store |

Per-arm avg-of-medians latency (s):

| arm | draw-1 | draw-2 | draw-3 | draws |
|---|--:|--:|--:|:--:|
| clickhouse_native | 0.0610 | 0.0573 | 0.0573 | 3 |
| clickhouse_iceberg | 0.2821 | 0.2438 | 0.2428 | 3 |
| opensearch (foil 3.7.0) | 2.8537 | 2.5816 | 2.7549 | 3 |
| dremio_iceberg | 0.7865 | 0.7571 | — (failed) | **2** |

So the durable two-regime claim — index/sorted storage wins point lookups (see
`NEEDLE-FINDINGS-2026-06-14.md`), columnar engines win scan-heavy aggregations — holds across three
independent draws with a tight ~10–11× foil-vs-columnar multiple and a ~4.2–4.6× open-format tax.
The absolute latencies drift ~5–10% draw-to-draw (common-mode single-host page-cache); the ratios
travel, which is exactly why the literature quotes multiples and the split rather than a single ms.

## The headline "145×" is a range, and it is the extreme arm-pair

The original 145× was the most extreme pairing (ClickHouse-native vs Dremio-Iceberg on count). That
pairing measures **76.6× (draw-1) / 85.9× (draw-2)** here — a 2-draw range, because Dremio's draw-3
arm did not complete (below). Quote it as a range and lead with the two-regime split + the
triple-validated ~10–11× foil multiple, not the single extreme number.

## Honest caveat — Dremio stays 2×

The Dremio arm failed to score in draw-3 (three automated attempts). The failure is a Dremio-26
startup/auth race: after the per-arm container restart the REST port on :9347 opens before the auth
service is ready, so `Dremio()._login` gets `Connection reset by peer` even behind a readiness poll.
This is consistent with the documented B-DREMIO Dremio-26 friction over the Nessie `register_table`
path. It is an **automation/orchestration** failure, not a measurement disagreement — Dremio's
draw-1/draw-2 numbers (0.7865 / 0.7571 s, ~3.4–3.6× the foil on the heavy aggregation per the
B-DREMIO arm) stand and agree. Dremio therefore stays double-validated; a clean third Dremio draw
needs a login-success readiness gate (poll an authenticated endpoint, not just the open port) or a
longer fixed warmup before the arm. The stale draw-3 dremio output was removed, not reported.

## Net

The flagship's two-regime core is now **3×-validated** (ClickHouse native + Iceberg + OpenSearch
foil), with stable multiples; Dremio is 2×-validated with a known orchestration caveat. The
"validate the key Splunk-vs-ClickHouse-vs-Dremio number" ask is met for the part the literature
leans on — the columnar-vs-foil multiple and the regime split — and the absolute-ms drift is bounded
and explained.

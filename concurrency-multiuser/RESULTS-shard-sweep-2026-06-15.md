# OpenSearch shard-count concurrency — is the foil's 6.73× scaling a single-shard artifact? (2026-06-15)

The `concurrency-multiuser` bench (RESULTS-2026-06-15.md) ran the OpenSearch foil on `zeek_conn`
(**1 shard**) and found it scaled **6.73×** to N=16 while the columnar Iceberg engines had ~no
concurrency headroom, with the foil p50 *tying* ClickHouse-Iceberg/StarRocks at N=16. The open
rebuttal: "you used one shard." This leg reindexes the same 10M-doc corpus at S ∈ {1,2,4,8} shards
(force-merged to 1 segment each), re-runs the identical closed-loop top-talkers concurrency curve on
each, and measures how shard count moves the N=1 latency and the scaling. `shard_sweep.py`;
raw `results/shard_sweep_summary.json` + per-config `results/shardsweep_s*.json`. Tier B, single host,
single node, 14 CPUs.

## Result

| shards | N=1 p50 (ms) | N=1 QPS | QPS ceiling | QPS_max/N1 | N=16 p50 (ms) |
|---|--:|--:|--:|--:|--:|
| 1 | 849 | 1.15 | 7.09 | 6.16× | 2373 |
| 2 | *1983* | *0.55* | 7.34 | *13.35×* | 2273 |
| 4 | 224 | 3.85 | 7.64 | 1.99× | 2300 |
| 8 | 218 | 4.45 | 7.75 | 1.74× | 2088 |

*(s2 is a cold-cache artifact — it was freshly reindexed immediately before its run and the single
warmup query did not fully warm a 2-shard index, so its first levels ran partly cold: the curve is
non-monotone, 0.55→1.0→5.04→6.69→7.34 QPS as the page cache filled mid-run. Its N=1 baseline and the
13.35× "scaling" are excluded; its ceiling 7.34 is consistent with the others.)*

## What it says

**The single-host throughput ceiling is shard-invariant.** Every configuration tops out at **~7.1–7.7
QPS** regardless of shard count — adding shards does not raise the ceiling, because the ceiling is the
14-core host saturating, and the cores are the limit whether the work is split across 1 shard or 8. The
small rise (7.09 → 7.75 from 1 → 8 shards) is the extra intra-query parallelism doing marginally more
useful work before saturation, not a new throughput tier.

**The "6.73× foil scaling" was a single-shard-baseline artifact, not real concurrency headroom.** A
single shard makes the N=1 query *slow* (one shard's worth of work, 849 ms here / ~1052 ms in the
original draw), which leaves the box's other cores **idle at N=1**, so adding concurrent clients simply
fills idle capacity — that *looks* like 6× scaling but is really "we under-used the box at N=1." With 4–8
shards the N=1 query is **~3.8× faster** (218–224 ms — intra-query parallelism uses the cores at N=1), so
there is little idle capacity left and the curve "scales" only **1.7–2.0×** to the *same* ceiling. The
scaling ratio is an inverse function of how well a single query already uses the host, not a property of
OpenSearch's concurrency.

**Consequence for the H3 concurrency leg.** The honest reading of the concurrency-multiuser finding
sharpens: the foil and the columnar engines **both converge to the same single-host CPU ceiling** (the
original bench already said this — ~6–7 QPS); the foil's headline 6.73× was inflated by the single-shard
slow-N=1 baseline, and the columnar engines' ~no-headroom (1.10–1.27×) is the *same* phenomenon seen from
the other end — their N=1 query already uses the box well (fast single query), so there is no idle
capacity for concurrency to fill. "Columnar has no concurrency headroom" and "the single-shard foil
scales 6.73×" are the **same host-ceiling story at two different N=1 baselines**, not two different
concurrency behaviors. The N=16 convergence (foil ties columnar) is robust — it is the ceiling.

**Directional fairness note (needs a same-session columnar re-run to quantify).** A 4–8-shard foil has a
*much faster* N=1 (218–224 ms) than the single-shard foil the original used (~1052 ms), which is far
closer to the columnar engines' N=1 (~159 ms ClickHouse in the original draw). So the dramatic "columnar
wins single-query latency ~6×" gap is *itself* partly a single-shard-foil artifact: with a properly
sharded foil the low-concurrency latency gap narrows toward ~1.4×. This is **directional only** here —
the shard-sweep foil numbers are a different (warm) session than the original columnar draw, so the
narrowed gap must be confirmed by running the columnar arms in the same session before it is claimed.

## Caveats (Tier B)

- Single host, single node, 14 CPUs; the ceiling is this host's, the *shape* transfers.
- **Absolute N=1 latencies are confounded by sequential page-cache warmth** across the four index builds
  (s1 = the pre-warmed existing index, s2 = coldest as first-rebuilt). The shard-INVARIANCE of the
  *ceiling* is robust to this (all configs saturate at N≥8); the absolute N=1 numbers are not — the
  clean within-warmth comparison is s4 vs s8 (224 vs 218 ms: past ~4 shards, more shards barely help this
  query on 14 cores, diminishing returns).
- One query shape (the heavy top-talkers scan-aggregation), closed-loop, warm. A point-lookup would
  shard differently.
- The cross-bench "columnar edge narrows to ~1.4×" claim is **not** made — it is flagged as the next
  same-session run.

# Iceberg compaction → scan-latency recovery (B-COMPACT)

Built 2026-06-14, pre-registered in project1 `BENCHMARK-BACKLOG.md` as the P1 one-arm
extension of the `zeek-flagship-rerun` corpus. It answers one question with a first-party,
CV-gated number: **when a streaming security table fragments into many small files, how much
scan latency does compaction recover?**

This replaces a hand-wave. The `iceberg-maintenance.astro` essay used to assert a precise
"60s → 12–20s, a 3-to-5x speedup, at the 2 PB/day deployment"; the 2026-06-13 conflation
untangle established (via git provenance) that those specifics were AI-drafted blog color
ported from the retired blog with no first-party source, and that "2 PB/day" is Atlassian's
(analyzed-not-operated) scale. The essay was softened to "directionally a 3-to-5x
improvement." This bench makes it a measurement.

## Design (single host, Tier B)

1. The pinned 10M-row Zeek conn corpus (`../zeek-flagship-rerun/_work/zeek_conn_10m.parquet`,
   sha256 recorded in `results/results.json`) is written to a local Iceberg table (pyiceberg
   0.11.1, SqlCatalog) as **500 small appends** — each its own commit, simulating frequent
   small streaming writes → 500 small data files (the fragmented state real streaming reaches).
2. A 4-query scan battery (the flagship's shapes) runs against the fragmented table via DuckDB's
   `iceberg_scan`, **1 warmup + 7 trials/query, median + CV**.
3. **Compaction.** pyiceberg 0.11 has no native `rewrite_data_files`, so compaction is
   `table.overwrite()` with the full dataset — it rewrites the 500 small data files into a few
   large ones at the default `write.target-file-size` (the essence of `rewrite_data_files`),
   followed by `expire_snapshots`. Compaction wall-time is recorded.
4. The same battery runs against the compacted table; 7 trials/query.
5. Per-query recovery ratio (before median ÷ after median), claimed only when the gap exceeds
   `max(CV_before, CV_after)`; answer-equality verified pre/post (identical extracted answers).

## Result (Tier B · single host · DuckDB iceberg_scan · 2026-06-14)

500 small data files → 4 large (**125× file reduction**); compaction took **2.8 s**;
answer-equality **identical** on every query pre/post.

| query | fragmented (500 files) | compacted (4 files) | recovery | claimable |
|---|--:|--:|--:|:--:|
| count_all | 0.0840 s | 0.0035 s | **24.0×** | yes |
| protocol_distribution (full agg) | 0.1138 s | 0.0213 s | **5.3×** | yes |
| long_duration_scan (selective filter) | 0.2848 s | 0.0889 s | **3.2×** | yes |
| bytes_by_source (group-by sum) | 0.2470 s | 0.1107 s | **2.2×** | yes |

The data-scanning queries — the "90-day scan" shape the essay is about — recover **3.2× to
5.3×**, which lands squarely in the directional "3-to-5x" the essay had softened to. So the
essay can now quote a measured SDW number: *compaction recovered a fragmented Iceberg
security table's scan latency by 3.2–5.3× on hunting-shaped scans (2.2–24× across the battery,
count-shaped queries the most), 500→4 files, single host, Tier B, CV-gated, answers verified
identical.* The metadata-bound `count_all` recovers most (24×) because it is dominated by
file-planning, not data volume.

## Recovery scales with fragmentation severity

The recovery is a function of how badly the table fragmented, not a constant. A smoke run at
**20 appends** (500k-row files, ~18 MB each) recovers only ~1× on the data scans
(`long_duration` 0.99×, `bytes_by_source` 1.0×) and 2.4× on `count_all` — at that file size the
scan is data-bound, not file-count-bound. The 500-file result above is the realistic
"frequent small commits" regime where per-file open/planning overhead and small row groups
dominate. So the honest claim is conditional: *the more a streaming table fragments, the more
compaction recovers* — at heavy fragmentation (hundreds of small files) it is 3–5× on scans;
at light fragmentation it is marginal.

## Sort-clustered arm (2026-06-14) — the pruning benefit on top of file-count

The result above measured compaction as **file-count reduction only** (random-order overwrite),
which is the floor — it can't improve row-group min/max pruning. `run_sorted.py` adds the arm a
real `rewrite_data_files` with a sort order would give: it shuffles the corpus (so `ts` is
scattered across files, the multi-source-streaming state), then compares the SAME data as 500
fragmented appends vs an unsorted overwrite vs an **overwrite ORDER BY ts**, on a selective
time-range scan (5% `ts` window) and a full-scan hunt.

| query | fragmented (500 files) | compact, unsorted (4 files) | compact, sorted-by-ts (4 files) |
|---|--:|--:|--:|
| **time-range scan** (5% ts window) | 0.337 s | 0.056 s (**6.0×**, file-count) | 0.033 s (**10.1× total**) |
| full-scan hunt (port_scan) | 0.591 s | 0.300 s (2.0×, file-count) | 0.329 s (no gain) |

So sort-by-ts compaction adds **~1.7× pruning** on top of the ~6× file-count recovery for the
selective time-range scan — total **~10×** — because the time-clustered row groups let the
scanner skip the files outside the window (answers identical). On a **full scan** the sort adds
nothing (~0.9×, expected — a full scan prunes nothing), and the file-count effect alone gives
~2×. The lesson for the essay: the base B-COMPACT 3.2–5.3× is the file-count floor; a
**well-sorted** compaction recovers more (~10× here) on the time-range "90-day scan" shape that
motivated the claim — *if* the sort key matches the query's range predicate. Machine-readable in
[`results/sorted.json`](results/sorted.json). (Caveat: the full-scan `port_scan` answer differs
across layouts only because that query is `ORDER BY ... LIMIT 5` with ties — a non-deterministic
tie-break, not a layout correctness issue; the time-range scan's count+sum is identical
everywhere.)

## Honesty boundary

- **Single-host WSL2**, hot/warm cache (no OS page-cache drop), 1 warmup discarded — the
  compaction duration (2.8 s) and the absolute latencies are illustrative, **not** a cloud-spot
  price or a multi-node figure. What travels is the recovery ratio and its dependence on
  fragmentation, with the single-host Tier-B caveat.
- **Conservative measurement: file-count effect only.** The appends are random slices, so the
  `overwrite` compaction does not re-sort/cluster the data — it only reduces file count. Real
  `rewrite_data_files` with a sort order (e.g. by time) would additionally improve *pruning* on
  selective queries, recovering more than measured here. This bench isolates the small-file
  penalty alone, which is the lower bound.
- **Does NOT cover** the unsourced $/day spot-compute cost or the FTE-burden figures the
  untangle also softened — those want named-operator published numbers, not a single-host bench.

## Run

```bash
.venv/bin/python iceberg-compaction/run.py [N_APPENDS]   # default 500
```

Outputs `results/results.json` (per-query before/after medians + CVs + answers, file counts,
compaction duration, corpus sha256). Hypothesis: re-grounds the `iceberg-maintenance.astro`
compaction claim from directional to measured.

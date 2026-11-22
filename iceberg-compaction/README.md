# Iceberg compaction → scan-latency recovery (B-COMPACT)

## What it measures

Built 2026-06-14, pre-registered in a private planning backlog (not in this repo) as the P1 one-arm
extension of the `zeek-flagship-rerun` corpus. It answers one question with a first-party,
CV-gated number: **when a streaming security table fragments into many small files, how much
scan latency does compaction recover?**

This replaces a hand-wave. The `iceberg-maintenance.astro` essay used to assert a precise
"60s → 12–20s, a 3-to-5x speedup, at a very-large-scale deployment"; the 2026-06-13 conflation
untangle established (via git provenance) that those specifics were AI-drafted blog color
ported from the retired blog with no first-party source (an unattributed, analyzed-not-operated
scale figure). The essay was softened to "directionally a 3-to-5x
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

### Attribution, as of the 2026-11-16 manifest arm (current)

The ratios above are measured and stand as numbers for compacting a fast-append table, and the 2026-11-16
manifest arm reproduced them (21.6×, 6.5×, 3.5× and 2.3×). What changed is what they are credited to.
pyiceberg's default append writes one manifest per commit, so the 500-file table also carried 500
manifests, and rewriting the manifests alone, with all 500 data files still in place, recovered 5.08× on
`count_all`, 2.97× on `protocol_distribution`, 2.15× on `long_duration_scan` and 1.41× on
`bytes_by_source` (re-derived from `results/manifest_arm_2026-11-16.json`, `shape_b_zeek_500`). In
log-ratio terms the manifest rewrite accounts for 41% to 61% of each query's recovery and the data-file
reduction for the rest (as a share of milliseconds saved it is about 51% to 84%, so the attribution
depends on the measure; corrected 2026-11-22 from "41% to 62%"), so "file-count reduction only" below should read "manifest and data-file
reduction together". The same holds for the sort-clustered arm below, whose 500 fragmented appends were
written the same way (`run_sorted.py:54`), so its 500-file-to-4-file ratios (6.0× and 2.0×) also include
the manifest effect, and only its sorted-against-unsorted comparison (about 1.7×) isolates layout. A table written by Iceberg Java, which merges manifests by default above 100, would
show a smaller recovery from compaction. Full tables in
[`RESULTS-MANIFEST-ARM-2026-11-16.md`](RESULTS-MANIFEST-ARM-2026-11-16.md), which is post hoc.

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
selective time-range scan *(corrected 2026-11-17: the ~6× and the 2.0× in the table are file-count and
manifest recovery together, per the attribution note above; the 1.7× is the layout-only figure)* — total **~10×** — because the time-clustered row groups let the
scanner skip the files outside the window (answers identical). On a **full scan** the sort adds
nothing (~0.9×, expected — a full scan prunes nothing), and the file-count effect alone gives
~2×. The lesson for the essay: the base B-COMPACT 3.2–5.3× is the file-count floor *(corrected
2026-11-17: the manifest-and-data-file floor, see the attribution note)*; a
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
  penalty alone, which is the lower bound. *(corrected 2026-11-17: the 2026-11-16 manifest arm shows the
  measured recovery is not the file-count effect alone, because each of the 500 appends also wrote its
  own manifest, and manifests account for roughly 41% to 61% of it in log-ratio terms (about 51% to 84% of milliseconds saved); see the attribution note above.)*
- **Does NOT cover** the unsourced $/day spot-compute cost or the FTE-burden figures the
  untangle also softened — those want named-operator published numbers, not a single-host bench.

## What would have made it fail

Each recovery ratio is claimed only when the before-and-after gap exceeds the larger CV, and answers are
checked identical before and after, so a recovery inside the noise or a changed answer would have shown.
The 20-append smoke run, which recovered about 1×, shows the measure can come out near zero. The manifest
arm is the control the June run lacked, separating manifest count from data-file count.

## Pre-registration

The README's opening says the bench was pre-registered in a backlog file outside this repository, so the
registration cannot be checked from the tree, and no pre-registration file exists in this folder. The
manifest arm and the sorted arm were added afterwards and are labelled as such.

## Reproduce

```bash
.venv/bin/python iceberg-compaction/run.py 500   # the published result; the script's default is 200
.venv/bin/python iceberg-compaction/run_sorted.py        # the sort-clustered arm
.venv/bin/python iceberg-compaction/manifest_arm.py --skip-3000 && .venv/bin/python iceberg-compaction/manifest_arm_report.py
```

Outputs `results/results.json` (per-query before/after medians + CVs + answers, file counts,
compaction duration, corpus sha256). Hypothesis: re-grounds the `iceberg-maintenance.astro`
compaction claim from directional to measured. The corpus must exist first:
`../zeek-flagship-rerun/_work/zeek_conn_10m.parquet`, built by that bench and git-ignored. The
manifest arm took about 20 minutes on the run host.

## Results

- `results/results.json` (2026-06-14), the entry point; this README is its only rendering.
- `results/sorted.json` (2026-06-14), the sort-clustered arm.
- [`RESULTS-MANIFEST-ARM-2026-11-16.md`](RESULTS-MANIFEST-ARM-2026-11-16.md), with
  `results/manifest_arm_2026-11-16.json` and `.log`, current for attribution. The aborted-run log that file
  cites (`results/manifest_arm_2026-11-16-aborted-n3000.log`) is kept on the run host and excluded by the
  repo's `*.log` ignore rule, so it is not in the published tree.

## Versions and pins

No requirements file. `results/results.json` records DuckDB 1.5.3, and the README and the manifest-arm file
name pyiceberg 0.11.1 and pyarrow 24.0.0, the versions the lab's other Iceberg benches pin
(`../ocsf-read-scan/requirements.txt`). DuckDB's iceberg extension is installed at run time and its version
is not recorded.

## Evidence tier and limits

Tier B, single host, warm cache, local SqlCatalog. The June results carry no rig stamp (methodology §7b);
the manifest arm names its host.

## Corrections

- *(corrected 2026-11-17: added the manifest-arm attribution as current; the June numbers are unchanged
  and re-derive from `results/results.json`, `per_query`: 24.0, 5.34, 3.2, 2.23.)*

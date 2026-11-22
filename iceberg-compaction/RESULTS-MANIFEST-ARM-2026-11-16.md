---
type: evidence
title: "Manifest arm: manifest count vs data-file count in the planning and scan receipts (POST-HOC)"
created: 2026-11-16
tags: [iceberg, compaction, manifests, pyiceberg, planning, tier-b, post-hoc]
---

# Manifest arm (POST-HOC, 2026-11-16)

**Post hoc, not pre-registered. Tier B: single host (Beelink, WSL2), warm cache, synthetic corpora.**
Run 2026-11-16 13:55-14:16 UTC by `manifest_arm.py --skip-3000`; raw output
`results/manifest_arm_2026-11-16.json`, console log `results/manifest_arm_2026-11-16.log`, tables
printed by `manifest_arm_report.py`. An earlier attempt that included N = 3,000 was aborted during the
3,000-append build (`results/manifest_arm_2026-11-16-aborted-n3000.log`); its N = 10/100/1,000 lines
agree with this run's within run-to-run variance.

**Why it exists.** A review of the "lock-in moved to the compaction schedule" essay (Fable, 2026-11-16)
pointed out that the planning receipt (`bench-d-tiered-realization`, 2026-06-16) and the scan receipt
(this bench, 2026-06-14) were both built with pyiceberg's default fast-append, so each append also added
one manifest (`TableProperties.MANIFEST_MERGE_ENABLED_DEFAULT = False` in pyiceberg 0.11.1), and the
original runs credited the whole recovery to data-file count and compaction. Iceberg Java defaults to
`commit.manifest-merge.enabled = true` with `commit.manifest.min-count-to-merge = 100` (Iceberg
configuration page, read 2026-11-16). This arm separates the two effects.

**Versions resolved:** pyiceberg 0.11.1, DuckDB 1.5.3 (both as in the originals), pyarrow 24.0.0,
Python 3.12.3.

## Conditions

- **default**: pyiceberg fast-append, no manifest merge (N appends give N data files and N manifests).
- **merge_on**: the same appends into a table created with `commit.manifest-merge.enabled=true` and the
  default min-count-to-merge of 100, so nothing merges below 100 manifests (as on a Java-written table).
- **rewrite_manifests**: the default table, then manifests rewritten with no data rewrite. pyiceberg
  0.11.1 has no `rewrite_manifests`, so this is emulated with an empty `merge_append` commit after setting
  `commit.manifest-merge.enabled=true` and `commit.manifest.min-count-to-merge=2`; data-file count and
  answers are unchanged (checked).
- **compacted**: the rewrite_manifests table, then `table.overwrite(full)`, the same compaction mechanism
  as the originals.

## Differences from the originals (read before comparing absolute numbers)

- Shape A uses the bench-d corpus generator (`bench_d_integrating.gen_corpus(700000, 14)`) and the same
  planning (pyiceberg `plan_files()`, 5 trials, no warmup) and scan (`recent_window` count, 2 warmup + 5
  trials) protocols, but on pyiceberg's local SqlCatalog on the local filesystem, not Nessie over MinIO in a
  container. Absolute ms are not comparable with the 2026-06-16 table (4,083 ms at 1,000 files there,
  1,227 ms here); compare conditions with each other.
- Shape B matches the original scan receipt: pinned 10M-row Zeek conn corpus, 500 appends, local
  SqlCatalog, the same four queries, 1 warmup + 7 trials.
- N = 3,000 was dropped (local fast-append build grows roughly O(N^2) in metadata and was about 40 minutes
  out).

## Results

### Shape A: planning sweep (700,000 rows, separate table per N)

| N | condition | data files | manifests | plan median ms (CV%) | scan median ms (CV%) | answer = default |
|---:|---|---:|---:|---:|---:|---|
| 10 | default | 10 | 10 | 13.8 (9.4) | 5.7 (7.9) | True |
| 10 | merge_on | 10 | 10 | 12.3 (1.9) | 5.7 (6.2) | True |
| 10 | rewrite_manifests | 10 | 1 | 2.3 (3.4) | 3.7 (4.7) | True |
| 10 | compacted | 1 | 1 | 1.6 (5.9) | 4.4 (1.0) | True |
| 100 | default | 100 | 100 | 116.4 (1.4) | 37.3 (1.4) | True |
| 100 | merge_on | 100 | 1 | 14.5 (104.9) | 9.8 (13.0) | True |
| 100 | rewrite_manifests | 100 | 1 | 7.0 (4.3) | 10.0 (10.5) | True |
| 100 | compacted | 1 | 1 | 1.6 (4.4) | 5.0 (7.5) | True |
| 1,000 | default | 1,000 | 1,000 | 1227.0 (2.4) | 428.2 (4.3) | True |
| 1,000 | merge_on | 1,000 | 10 | 71.5 (26.0) | 53.6 (5.6) | True |
| 1,000 | rewrite_manifests | 1,000 | 1 | 65.7 (29.4) | 46.4 (2.5) | True |
| 1,000 | compacted | 1 | 1 | 1.7 (7.6) | 9.8 (4.5) | True |

Ratios against default (plan / scan):

| N | merge_on | rewrite_manifests | compacted |
|---:|---:|---:|---:|
| 10 | 1.1x / 1.0x | 6.1x / 1.5x | 8.5x / 1.3x |
| 100 | 8.0x / 3.8x | 16.7x / 3.7x | 70.5x / 7.5x |
| 1,000 | 17.2x / 8.0x | 18.7x / 9.2x | 743.2x / 43.8x |

### Shape B: Zeek conn, 10,000,000 rows as 500 appends

| condition | data files | manifests | plan ms | count_all | protocol_distribution | long_duration_scan | bytes_by_source |
|---|---:|---:|---:|---:|---:|---:|---:|
| default | 500 | 500 | 666.0 | 108.1 (5.3) | 163.9 (10.5) | 367.9 (7.2) | 325.9 (6.3) |
| merge_on | 500 | 5 | 40.8 | 19.1 (2.5) | 50.0 (6.3) | 169.9 (7.6) | 235.2 (4.5) |
| rewrite_manifests | 500 | 1 | 33.7 | 21.3 (8.9) | 55.2 (6.4) | 171.5 (3.5) | 231.7 (4.3) |
| compacted | 4 | 1 | 2.2 | 5.0 (14.2) | 25.2 (3.4) | 106.1 (2.3) | 140.5 (4.6) |

Recovery against default (default median / condition median):

| condition | plan | count_all | protocol_distribution | long_duration_scan | bytes_by_source |
|---|---:|---:|---:|---:|---:|
| merge_on | 16.3x | 5.65x | 3.28x | 2.17x | 1.39x |
| rewrite_manifests | 19.8x | 5.08x | 2.97x | 2.15x | 1.41x |
| compacted | 299.5x | 21.59x | 6.50x | 3.47x | 2.32x |

Answer equality vs default: {'merge_on': True, 'rewrite_manifests': True, 'compacted': True}

CVs above 20% (merge_on at N = 100, 104.9%; merge_on and rewrite_manifests at N = 1,000, 26-29%) are
flagged: read those medians loosely. The other cells are under 15%.

## Reading

1. **Planning is mostly manifest count, and the rest is data-file count.** At 1,000 appends, rewriting the
   manifests alone, with all 1,000 data files still in place, took planning from 1,227 ms to 66 ms
   (18.7x), which is about 95% of the time compaction removed. Compaction then took it from 66 ms to
   1.7 ms, so the data-file count still carries a further ~40x at the small end. The original essay's
   "several hundred times on planning at a thousand files" is the product of the two, and most of the
   absolute milliseconds belong to the manifests.
2. **A Java-default writer would not show the linear curve.** With merge on at the default threshold,
   planning at 1,000 files was 71.5 ms (10 manifests), against 1,227 ms for fast-append. Below 100
   manifests nothing merges (N = 10: 12.3 vs 13.8 ms).
3. **Scans split roughly in half, in ratio terms.** On the 500-append Zeek table, rewriting manifests
   alone recovered 5.1x on `count(*)`, 3.0x on the full aggregation, 2.15x on the selective filter and
   1.4x on the group-by sum; full compaction recovered 21.6x, 6.5x, 3.5x and 2.3x. In log-ratio terms
   the manifest rewrite accounts for 41% to 61% of each query's compaction recovery (count 53%, full
   aggregation 58%, selective filter 61%, group-by sum 41%), and the data-file reduction for the rest.
   *(Corrected 2026-11-22: these read 59% and 62% for the middle two queries and 41% to 62% overall;
   recomputed from the raw medians in `results/manifest_arm_2026-11-16.json`, `shape_b_zeek_500`. As a share
   of milliseconds saved rather than of the log ratio, the manifest rewrite accounts for 84%, 78%, 75% and
   51%, so the attribution depends on which measure is used.)* The compacted table was still the fastest on
   every query; the review's scratch observation that a merged-manifest 500-file table beat the single
   file did not reproduce here.
4. **The compaction ratios reproduce the 2026-06-14 receipt** (21.6 / 6.5 / 3.5 / 2.3x here against
   24.0 / 5.34 / 3.2 / 2.23x then), so the original numbers stand as compaction-of-a-fast-append-table
   numbers; what changes is the attribution.
5. **Answers identical** across all four conditions in both shapes.

## Limits

Single host, warm cache, synthetic data, local filesystem catalog; post hoc; one run per cell with the
stated trials. `rewrite_manifests` is emulated (see Conditions). The sorted arm (`sorted.json`) compares two
compacted tables and is unaffected.

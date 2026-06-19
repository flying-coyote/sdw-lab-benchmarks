---
type: evidence
title: "BENCH-D Integrating Run — Null Wins at Lab Scale (H-TIERED-REALIZATION-01, 2026-06-16)"
created: 2026-06-16
tags: [bench-d, tiered-realization, ducklake, iceberg, h-tiered-realization-01, null-result]
---

# BENCH-D integrating run — RESULTS: the null wins at lab scale (H-TIERED-REALIZATION-01, 2026-06-16)

The first end-to-end test of the *integrating* claim this hypothesis owns — does DuckLake-hot →
Iceberg-warm → compacted-cold behind one read contract beat a single backend run end-to-end? Every
prior leg (commit-tax, z-order, BENCH-D commit floor, MV accelerator) scored an individual matrix
*cell* and left the integrating claim explicitly untouched at HOLD 2.5/5. This run tests it head-to-head
against the hypothesis's own null, and the **null wins on all three pre-registered SLOs at lab scale.**

Pre-registration (committed before any number, Platt strong inference, 6 adversary fixes folded in):
`PRE-REGISTRATION-integrating-2026-06-16.md`. Harnesses: `bench_d_integrating.py` (Window 1 nulls),
`bench_d_integrating_tiered.py` (Window 2 head-to-head + correctness oracle), `bench_d_integrating_sweep.py`
(Window 3 planning-cliff + storage parity). Tier B, single host, warm-cache, ejs-network vantage
(see `STATUS-integrating-2026-06-16.md`). CV blowout ceiling 30 % (a blown trial set is not claimed).

## Verdict against the pre-registered decision rule

The multi-tier arm earns its complexity only if it beats *both* nulls on a named SLO by a margin above
both arms' CV, with the crossover in a plausible range and no correctness invariant failing. It cleared
**none** of the three:

1. **Freshness SLO (1 s) — null wins.** No arm comes within 6× of the 1 s line. The tiered arm's
   hot-ingest freshness (27.8 ms) *ties* a single DuckLake (26.5 ms) within CV — the pre-registered
   locality tie, because the tiered hot tier *is* a local DuckLake, so it structurally cannot beat one.
   Its post-handoff freshness (181 ms) sits in the single-Iceberg object-store regime (153–160 ms).
   Tiering buys no freshness a single backend can't get.
2. **Planning SLO (200 ms) — null wins.** A fragmented single Iceberg table *does* cliff hard
   (47 ms → 541 ms → 4,090 ms as data files go 10 → 100 → 1,000; crosses 200 ms around ~40 files), but
   that is a **compaction** story, not a **tiering** story: compacting to one file drops planning back to
   ~10 ms at every file count, and the pre-registered null (a single Iceberg *compacted on the same
   schedule*) gets the identical flat ~10 ms the tiered cold tier does. The cross-backend handoff adds
   nothing on planning that a within-backend compaction policy doesn't already give.
3. **Storage SLO (fewer bytes + fewer files at parity) — null wins.** At matched codec (ZSTD), a single
   DuckLake is *smaller* than Iceberg (14.7 MB vs 18.7 MB on 700k rows). The Window-1 appearance that
   "Iceberg is smaller" (18.7 vs 21.4 MB) was entirely the codec default (pyiceberg ZSTD vs DuckLake
   Snappy), not an architectural storage advantage — the BENCH-E writer/codec confound, caught by the
   footer capture and resolved at parity.

On top of the three SLOs, the tiered `conn_all` UNION is **slower on scan** than either single backend
on all four SOC queries (cold-aggregation 15.2 ms tiered vs 5.2 ms single DuckLake, ~3× and above CV) —
the read contract has a real per-query cost.

The one thing the tiered architecture uniquely provides is **read-contract correctness**, and the run
proves it is both necessary and achievable (oracle below) — but that is a correctness *requirement* if
you choose to tier, not a performance *reason* to tier.

**Recorded verdict: one backend suffices at lab scale, on one host, across the swept range.** A single
compacted Iceberg (or a single DuckLake) is good-enough across hot/warm/cold here; the cross-backend
handoff is the unnecessary part. This is a strong-inference result the Karen flag asked for — the
tiered-polyglot answer flatters the SDW open-architecture narrative, the run was built to let the null
win, and it did. The honest bound: the regime that actually motivates tiering — multi-day retention,
hot-store $/GB/day, the Splunk economics the whole thesis rides on — is **not reached on one host**, so
the verdict removes the *lab-scale performance* justification for tiering and shifts its entire remaining
case onto that unmeasured cost regime.

## Window 1 — single-backend null baseline

Two nulls, the bar the tiered arm had to beat. Freshness is a no-warmup fresh-commit-per-trial harness
(fix C); planning latency and scan are CV-gated `time_trials`; storage and `plan_files` count are
deterministic. `results/bench_d_integrating_null.json`.

| scale | arm | freshness ms (cv) | plan-lat ms (cv) | storage | files | scans ms |
|---|---|---|---|---|---|---|
| 700k×14 | Null-B DuckLake (local) | 26.5 (8.1) | 8.0 (4.7) | 21.4 MB Snappy | 8 | 5.5–10.7 |
| 700k×14 | Null-A Iceberg (MinIO) | 160.5 (7.8) | 9.1 (12.3) | 18.7 MB ZSTD | 14 | 7.0–11.7 |
| 2.8M×14 | Null-B DuckLake (local) | 25.3 (**36.6 BLOWN**) | 8.8 (15.4) | 79.0 MB Snappy | 8 | 6.5–22.5 |
| 2.8M×14 | Null-A Iceberg (MinIO) | 153.5 (16.8) | 9.4 (**42.4 BLOWN**) | 71.7 MB ZSTD | 14 | 7.3–21.7 |

Freshness is **flat in table size** (DuckLake ~25 ms, Iceberg ~155 ms across 140k/700k/2.8M), confirming
the bounded-partition probe prunes and the prior leg's growth-confound is fixed. Answer-equality
(`logical_fingerprint` corpus == Null-B == Null-A) **PASS at every scale**. Two CV blowouts at 2.8M are
flagged invalid by the 30 % ceiling (medians track the 700k numbers — transient contention, not a level
shift).

## Window 2 — multi-tier arm, read contract, and the correctness oracle

DuckLake-hot → Iceberg-warm/cold behind one watermark-fenced `conn_all` view (hot `event_day > wm`;
warm/cold `<= wm`), W_hot = 2 days, 700k×14, same DuckDB reader for every arm.
`results/bench_d_integrating_tiered.json`.

**The correctness oracle (deterministic, gate-blocking) is the sharpest finding.** Conservation held at
all 12 handoff promotes. The overlap-window probe — one day staged into both tiers during the
commit-then-delete window — returns:

| read contract | count | expected | result |
|---|---|---|---|
| **reader-pinned** (one watermark, both branches) | 700,000 | 700,000 | ✓ correct |
| naive per-branch-live (branches at different watermarks during the advance) | 750,000 | 700,000 | **duplicates** the 50k in-flight day |
| stale-pin-after-delete (reader pinned old wm, hot row already purged) | 650,000 | 700,000 | **drops** the 50k in-flight day |

So the watermark-fenced read contract is *necessary and sufficient* for handoff correctness: a naive
implementation silently duplicates or drops exactly the day being moved. This validates the read-contract
design the hypothesis owns — and equally, it quantifies the correctness burden tiering imposes that a
single backend never carries.

**Head-to-head** (median ms / cv %), tiered `conn_all` vs the two single backends:

| query | tiered | Null-A Iceberg | Null-B DuckLake |
|---|---|---|---|
| freshness_probe | 9.25 / 4 | 7.16 / 5 | 6.62 / 5 |
| recent_window | 11.89 / 12 | 7.39 / 7 | 6.78 / 9 |
| cold_aggregation | 15.21 / 6 | 8.36 / 9 | 5.17 / 3 |
| needle_lookup | 16.26 / 8 | 11.70 / 4 | 11.90 / 8 |

Freshness: tiered hot-ingest **27.8 ms ties Null-B 26.5 ms** within CV (locality tie, as pre-registered);
tiered post-handoff **181 ms** in Null-A's object-store regime. Answer-equality PASS across
corpus/tiered/null_a/null_b.

## Window 3 — planning-cliff sweep + storage at parity

Single Iceberg table swept to N small data files, then compacted (the cold tier's `overwrite` +
`expire_snapshots` mechanism). Planning latency = time to walk the manifest list (CV-gated); the file
*count* is deterministic (fix D). `results/bench_d_integrating_sweep.json`.

| N appends | fragmented files | frag plan-lat ms | frag scan ms | compacted files | comp plan-lat ms | comp scan ms |
|---|---|---|---|---|---|---|
| 10 | 10 | 43.6 | 6.7 | 1 | 10.3 | 4.9 |
| 100 | 100 | 480.9 | 34.0 | 1 | 10.0 | 5.3 |
| 1,000 | 1,000 | 4,083.3 | 344.5 | 1 | 9.7 | 5.8 |
| 3,000 | 3,000 | 12,769.1 | 1,140.2 | 1 | 13.0 | 8.1 |
| 10,000 | _resource-capped_ | — | — | — | — | — |

Fragmented planning is ~linear in file count (44 → 481 → 4,083 → 12,769 ms over 10 → 100 → 1,000 → 3,000
files), crossing the 200 ms SLO around ~40 files and reaching nearly **13 seconds to plan** at 3,000
files; compaction returns it to a flat ~10–13 ms at every N. (An independent first pass agreed within
clean-box variance: 47.5 / 541.2 / 4,090.3 ms at 10/100/1,000.) **N = 10,000 is resource-capped, disclosed
not silently dropped:** building 10,000 sequential Iceberg commits exhausted the container before it
completed (metadata-list bloat per commit — itself a datapoint that the fragmented path is operationally
untenable well before 10,000 files); the cliff shape is established by the four completed points. The cliff
is real and it is the breaking-points map for Iceberg planning — but it is owned by **compaction**, a
within-backend policy the pre-registered null also runs, not by cross-backend tiering.

**Storage at parity (700k rows, codec isolated):** DuckDB ZSTD **14.7 MB** · DuckDB Snappy 19.1 MB ·
DuckDB uncompressed 32.2 MB — vs Iceberg ZSTD 18.7 MB and DuckLake Snappy 21.4 MB. At matched ZSTD the
single DuckLake is the smallest; the Window-1 "Iceberg smaller" was purely the codec default.

## What moves, and what stays labeled

- **The integrating claim's null is now first-party-supported at lab scale.** The lab-scale performance
  motivations for tiering (freshness, planning, storage, scan) all go to the single backend; the
  planning cliff is a compaction argument, not a tiering one.
- **The read-contract correctness design is validated** (oracle: pinned correct, naive corrupts) — a
  positive for *how* to tier if you must, separable from *whether* to.
- **Caveats (Tier B):** single host, warm-cache (OS page cache not dropped — the cold object-store cost
  is the named follow-up), synthetic uniform-random conn corpus (aggregate-only output, honoring the
  security-telemetry injection-surface boundary), W_hot = 2, n = 1 per cell, two CV blowouts at 2.8M
  flagged. **The decisive unmeasured regime is multi-day retention + hot-store $/GB/day** — the only
  arena where tiering's cost case can still hold, and the next rig that would actually stress this null.
- **Degenerate control:** the Window-3 *compacted single Iceberg* is the effective degenerate-on-one-
  backend control — flat planning on one backend proves the cross-backend handoff is the part that adds
  no planning benefit (Design 2's tiering-as-policy vs tiering-across-backends distinction, returned as a
  first-class verdict).

## Gate

Route the confidence disposition through karen-evaluator → hypothesis-validator → contradiction-detector
before any H-TIERED-REALIZATION-01 move. Recommended: the integrating leg attaches as a **null-supporting**
result that removes the lab-scale-performance basis for tiering and narrows the claim to the unmeasured
cost regime; confidence on the tiering-superiority reading moves **down toward 2/5** (from 2.5/5), or
HELD 2.5/5 with the basis sharply narrowed — the gate decides. Jake Thomas signs the decision rule before
the verdict is read as final (Platt precondition; the rule was committed in the pre-registration).

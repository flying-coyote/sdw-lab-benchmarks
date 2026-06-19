---
type: tracker
title: "BENCH-D Integrating Run — Status Checkpoint (2026-06-16)"
created: 2026-06-16
tags: [bench-d, tiered-realization, run-status, checkpoint, iceberg, ducklake]
---

# BENCH-D integrating run — STATUS / checkpoint (2026-06-16)

Resume note for the staged clean-box run. Pre-registration:
`PRE-REGISTRATION-integrating-2026-06-16.md`. Harness: `bench_d_integrating.py`.

## Vantage (important for any re-run)

The integrating Iceberg arm runs **inside the ejs network**, in the `ejs-lab` container, not from the
host. Reason: Nessie's REST iceberg catalog advertises the *internal* MinIO endpoint (`minio:9000`) in
its config, which overrides a host-passed `localhost:9300`, so `pyiceberg` `load_table`/`append`/
`plan_files` only resolve from inside the network. This is the pre-registered single-vantage decision
(every tier's read path shares one network reality), and it also keeps DuckDB's `iceberg_scan` reading
the same MinIO the writer used.

Run recipe (host → container):

```bash
cd ~/sdw-lab-benchmarks
docker exec ejs-lab mkdir -p /work/bench-d-tiered-realization /work/lib /work/results
docker cp bench-d-tiered-realization/bench_d_integrating.py ejs-lab:/work/bench-d-tiered-realization/
docker cp lib/common.py ejs-lab:/work/lib/common.py
docker exec -e S3_ENDPOINT=http://minio:9000 -e NESSIE_URI=http://nessie:19120/iceberg/ \
  -e MINIO_HOST=minio:9000 -e OUT_DIR=/work/results \
  ejs-lab python3 /work/bench-d-tiered-realization/bench_d_integrating.py
docker cp ejs-lab:/work/results/bench_d_integrating_null.json bench-d-tiered-realization/results/
```

DuckDB `iceberg_scan` form: pass the pinned `metadata.json` with **no** `allow_moved_paths` (probed
2026-06-16 — `allow_moved_paths=true` doubles the absolute s3:// manifest path → 404).

## Window 1 — DONE (single-backend NULL baseline)

Two nulls established, the bar the Window-2 multi-tier arm must beat. Tier B, single host,
warm-cache (OS page cache not dropped — cold object-store regime is the named follow-up). CV blowout
ceiling 30% (committed); a blown trial set is not claimed.

| scale | arm | freshness (ms) | plan-lat (ms) | storage | files | scans (ms) |
|---|---|---|---|---|---|---|
| 700k×14 | Null-B DuckLake (local) | 26.5 (cv 8.1) | 8.0 (cv 4.7) | 21.4 MB Snappy | 8 | 5.5–10.7 |
| 700k×14 | Null-A Iceberg (MinIO) | 160.5 (cv 7.8) | 9.1 (cv 12.3) | 18.7 MB ZSTD | 14 | 7.0–11.7 |
| 2.8M×14 | Null-B DuckLake (local) | 25.3 (**cv 36.6 BLOWN**) | 8.8 (cv 15.4) | 79.0 MB Snappy | 8 | 6.5–22.5 |
| 2.8M×14 | Null-A Iceberg (MinIO) | 153.5 (cv 16.8) | 9.4 (**cv 42.4 BLOWN**) | 71.7 MB ZSTD | 14 | 7.3–21.7 |

(QUICK 140k×14 smoke also passed: Null-B 24.6 ms, Null-A 163.0 ms, answer-equality PASS.)

**Findings (baseline only — not yet a hypothesis verdict; that needs the Window-2 head-to-head):**

1. **Answer-equality PASS at every scale** — `logical_fingerprint(corpus) == Null-B == Null-A`. The
   gate-blocking correctness precondition holds; latency numbers are comparable.
2. **Freshness is flat in table size** (DuckLake ~25 ms, Iceberg ~155–160 ms across 140k/700k/2.8M),
   which confirms the bounded-partition probe prunes and the prior leg's growth-confound is fixed (its
   ~290 ms was a full re-scan of a growing table; this is one pruned day regardless of size).
3. **Both nulls clear the 1 s freshness SLO by ~6–40×.** Per the pre-registered rule, no arm crossing
   1 s predicts the **null wins on freshness**. The ~6× DuckLake-local-vs-Iceberg-object-store gap is
   the locality finding (prior leg re-confirmed: a local hot store beats object-store read-after-write),
   not evidence a cross-backend handoff earns its keep — that is what Window 2 tests.
4. **Planning latency ~8–9 ms on both, far under the 200 ms SLO at 14 data files** — no cliff exists at
   this file count. The cliff hunt is the Window-3 file-accumulation sweep (10→10,000 appends); 14
   per-day files is the floor. `plan_files()` count = 14 (deterministic).
5. **Storage cannot be scored yet — codec confound is live.** Iceberg is *smaller* (18.7 vs 21.4 MB;
   71.7 vs 79.0 MB) but only because pyiceberg defaults ZSTD while DuckLake defaults Snappy (footers
   confirm: DuckLake `event_day` PLAIN_DICTIONARY + bloom; Iceberg RLE_DICTIONARY, no bloom). The
   storage SLO is made only at parity-normalized layout (Window 3). The footer capture surfaced the
   confound rather than letting it ride as a result — the BENCH-E lesson applied.
6. **Two CV blowouts at 2.8M** (Null-B freshness 36.6 %, Null-A planning 42.4 %) → those two trial sets
   are invalid by the committed 30 % ceiling and are not claimed; their medians track the 700k numbers,
   so it reads as transient contention at the larger scale, not a level shift. Re-run on a quieter pass
   if either becomes load-bearing.

Results JSON: `results/bench_d_integrating_null.json`.

## Window 2 — NEXT (multi-tier arm + head-to-head)

The crux: does DuckLake-hot → Iceberg-warm → compacted-cold behind one read contract beat *both* nulls?
Build into the same harness (clearly-marked seams already in `bench_d_integrating.py`):

- watermark-advance lifecycle: hot=DuckLake `INSERT`, warm=pyiceberg `append`, cold=`overwrite` +
  `expire_snapshots` (assert success); commit-then-delete ordering, whole-closed-day promotion.
- `conn_all` watermark-fenced disjoint-predicate UNION view (hot `event_day >` watermark, warm/cold
  `<=`), pinned warm metadata.
- **correctness oracle (fix E):** reader-pinned vs per-branch-live watermark run during an in-flight
  handoff; conservation invariant computed against the reader's *own* pinned watermark (not a live
  corpus count). Gate-blocking.
- degenerate all-Iceberg three-table control (isolate cost-of-tiering from cost-of-two-engines).
- head-to-head vs Null-A + Null-B on the 4 SOC queries; the freshness asymmetry is pre-registered
  (tiered hot-freshness must tie Null-B within CV by construction — a null-confirming prediction).

## Window 3 — breaking-point sweep + RESULTS + gate

File-accumulation sweep (10→100→1,000→10,000 appends, ±compaction) to find the planning cliff;
parity-normalized storage SLO; then `RESULTS-<date>.md` and the
karen-evaluator → hypothesis-validator → contradiction-detector gate before any H-TIERED-REALIZATION-01
confidence move.

## Sign-off still owed

- [ ] Jake Thomas reviews the decision rule + null-wins conditions before the Window-2 head-to-head is
  read as a verdict (Platt precondition; the rule is already committed in the pre-registration).

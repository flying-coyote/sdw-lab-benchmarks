---
type: benchmark-spec
title: "BENCH-D Integrating Run — Pre-Registration (H-TIERED-REALIZATION-01)"
created: 2026-06-16
tags: [bench-d, pre-registration, tiered-realization, ducklake, iceberg, h-tiered-realization-01]
---

# BENCH-D integrating run — pre-registration (H-TIERED-REALIZATION-01)

_Written before any integrating-run numbers exist (Platt strong inference: the prediction is
registered first so it can't be moved to fit the result). Tier B, single host, ejs stack. Decision
rule + null-wins conditions below are to be signed by Jake Thomas before execution._

## What this run is for, and the bar the null already sets

The completed commit-freshness leg (`RESULTS-2026-06-15.md`) did the honest demolition of the easy
story: the three write/commit paradigms, measured separately, all commit sub-second at the storage
layer (DuckLake 16–80 ms, ClickHouse 61–100 ms, Iceberg 71–124 ms), and the real divergence sits in
read-after-write and streaming cadence, not commit. The "1–5 min file-write" band turned out to be a
Flink micro-batch knob, not an Iceberg property. That left the question this hypothesis actually owns
untouched: whether stitching the paradigms into a tiered lifecycle (DuckLake hot → Iceberg warm →
compacted Iceberg cold) behind one read-contract buys anything a single backend run end-to-end can't
get cheaper.

The hypothesis body states its own null plainly — a V4-efficient materialized Iceberg table becomes
good-enough across all three temperatures, making the tiering needless operational complexity — and
the body's own evidence updates concede the null is, if anything, the better-evidenced reading right
now (the unified read-contract is still copy-bridged, the virtual hot tier has no named production
deployment). The Karen flag is the governing constraint: the tiered-polyglot answer flatters the SDW
open-architecture and Capability-Matrix story (more components to evaluate = more to sell), so this
run is built to let the null win, and I expect it to. A null win here is a real strong-inference kill
of the over-eager tiering claim, not busy-work dressed as rigor. The way I protect a null is to give
the *treatment* every fair advantage (best-tuned multi-tier, generous CV gating that makes a gap hard
to claim) and then see if it still clears a bar written down before the run.

One honesty point stated up front rather than discovered later: a single host never hits the failure
that motivates real-world tiering, which is hot-store cost or cardinality blowup at retention scale.
So the verdict this rig can return is bounded to "at lab scale, on one host, across the swept range,
one backend suffices (or doesn't)," and the unmeasured regime — multi-day retention, hot-store
$/GB/day, the Splunk economics this whole thesis rides on — is named as the follow-up that would
actually stress the null, not pretended away.

## Adversary fixes folded in (design panel `wj6zv61h0`, audit verdict FIX-FIRST)

Six defects from the adversarial audit are corrected here before any code runs:

- **A (blocker) — the inherited corpus has no age axis.** `bench_d.py:41` generates
  `ts = 1.781e9 + random()*86400`, a single 24-hour span, so every row lands in one `event_day` and no
  hot→warm→cold flow exists. **Fix:** the integrating corpus spans `DAYS` distinct event-days
  (`ts = BASE_EPOCH + day_index*86400 + rng.random()*86400`), and `DAYS` is a swept parameter, because
  the number of distinct `event_day` partitions drives how many handoffs fire and how large cold grows.
- **C — `time_trials` warmup destroys the freshness measurement.** `time_trials(warmup=2)` discards the
  first two (cold) reads and times steady-state cached reads; freshness *is* the cold first-read after a
  commit. **Fix:** freshness is measured by a dedicated no-warmup harness — one fresh commit + fresh
  reader/re-pinned snapshot per trial, timer wrapping commit-confirm → first successful read, 7
  independent fresh-read trials reported as `{median, min, max, cv}`. `time_trials` is used only for
  planning-latency and scan-latency, where steady-state is the right question.
- **D — planning count vs planning latency are different metric classes.** `plan_files()` returns a
  *count* (deterministic for a given table state), not a latency. **Fix:** the `plan_files()` count is
  reported raw, deterministic, no CV — it is the file-accumulation x-axis itself. The `EXPLAIN ANALYZE`
  planning *latency* is CV-gated. They are never lumped.
- **E — the conservation oracle can false-pass during the overlap window.** A count invariant checked
  against a live corpus count while the reader holds a pinned watermark can pass while a row is dropped.
  **Fix:** the conservation oracle computes its expected count from the *same pinned watermark the
  reader used*, and asserts both (a) `count(reader's hot ∪ warm) == corpus_count` and (b) no row appears
  in both branches under the pinned watermark. (Applies to the multi-tier arm — Window 2.)
- **#5 — page/metadata cache is the real single-host freshness/planning confound.** On one idle host
  MinIO objects serve from page cache after first touch, so a second-time Iceberg "object-store round
  trip" is a local memory read, not the ~100–290 ms cold S3 cost. **Fix (Window 1):** the freshness
  harness defeats DuckDB/pyiceberg *metadata* cache (fresh connection + re-pinned metadata each trial);
  the OS *page* cache is not dropped (that needs sudo `drop_caches`, declared as the cold-regime
  follow-up, not run autonomously), so all timed numbers are labeled **warm-cache, single-host** and the
  cold object-store cost is named as the unmeasured regime. The hot-stays-in-cache size artifact (small
  hot tier survives cache while a monolithic null's larger working set evicts) is controlled in Window 2
  by reporting working-set size per arm alongside the freshness number.
- **F — no "say" in the decision rule.** Every threshold below is a committed number with a
  justification, signed before the run.

## The corpus and how it flows hot → warm → cold

One synthetic conn-like corpus, generated once via `lib.common` (seeded `new_rng(sub_seed=4)`,
`BASE_EPOCH` anchor — not the harness's local `random.seed(7)`), so it is reproducible run-to-run and
fingerprintable with `logical_fingerprint`. Schema is `bench_d.py`'s `gen_batch`
(`ts, orig_h, resp_h, resp_p, proto, orig_bytes, resp_bytes`) plus a derived `event_day`
(`floor((ts - BASE_EPOCH)/86400)`) as the deterministic age axis. The same generated rows feed every
arm — multi-tier, both nulls, the degenerate control — with nothing regenerated per-arm (regenerating
reintroduces the parallel-writer non-determinism the lab got burned by in the chDB layout case).

Three physical homes on the live ejs stack:

- **Hot = DuckLake** (DuckDB 1.5.3, local catalog + parquet at `/tmp/benchd_data`, as `arm_ducklake`
  attaches it). Fresh batches land by `INSERT … SELECT`, catalog-inline. Hot holds a bounded trailing
  window of `W_hot` event-days (start at 1 day so a handoff fires inside one run).
- **Warm = Iceberg via Nessie + MinIO** (pyiceberg `RestCatalog` at `http://localhost:19320/iceberg/`,
  MinIO S3 `http://localhost:9300`, creds `ejsbench`/`ejsbench123`). Days that age out of hot land here
  as appends — many small data files.
- **Cold = compacted Iceberg** (same Nessie table after a compaction pass). pyiceberg 0.11.1 has no
  native `rewrite_data_files`, so compaction is `table.overwrite(full)` + `maintenance.expire_snapshots()`
  (the mechanism proven in `iceberg-compaction/run.py:132-137`). `expire_snapshots` success is asserted,
  not swallowed, so the before/after byte count isn't confounded by retained snapshots. Warm and cold are
  the same Iceberg table at different compaction states — a layout difference, not a row boundary.

**Handoff trigger = an event-time watermark, not wall-clock**, so the move replays. Promotion fires per
whole closed day (never a partial day — that wholeness is what makes mid-handoff double-counting
avoidable). Warm→cold compaction is a separate trigger: a file-count threshold.

**Handoff mechanism = commit-then-delete, in this order** (the load-bearing discipline): (1) read the
closing day out of DuckLake into a pyarrow table (transactional snapshot read); (2) `conn_warm.append`
via pyiceberg — one commit, new snapshot, confirm it's visible via the catalog; (3) only after the
commit is confirmed, advance `:warm_high_watermark`, then `DELETE FROM dl.conn WHERE event_day = :d`
as its own transaction. Append-then-delete means a crash mid-handoff leaves the day in *both* tiers
(recoverable; idempotent re-run drops the already-committed day by `event_day` membership in the warm
snapshot, since rows have no unique key — whole-day idempotency, not row-hash), never in neither.

## The one read contract, and how it avoids double-counting mid-handoff (Window 2)

A single DuckDB reader is the read engine for *every* arm (methodology within-class rule — one engine,
so the variable is the architecture, not the client). DuckDB↔Iceberg interop is copy/compat, not a
transparent REST backend (the body's 2026-05-29 catalog-coherence update — a finding to restate, not
work around), so the contract names each tier's source explicitly. One query surface every workload
runs against:

```sql
CREATE OR REPLACE VIEW conn_all AS
  SELECT *, 'hot' AS _tier FROM dl.conn                              -- DuckLake attached
    WHERE event_day > :warm_high_watermark
  UNION ALL
  SELECT *, 'warm_cold' AS _tier FROM iceberg_scan(:warm_metadata)  -- pinned snapshot
    WHERE event_day <= :warm_high_watermark;
```

Double-count avoidance is the **watermark-fenced disjoint predicate** (half-open `>` vs `<=` on the
same committed watermark, advanced at commit-confirm *before* the DuckLake delete), not a `DISTINCT`
and not a post-hoc dedup. Snapshot pinning (`:warm_metadata` pinned at view-evaluation start, routed
through Nessie) is the control for the ClickHouse-icebergS3 stale-snapshot trap. The correctness oracle
runs the **reader-pinned** contract against a **per-branch-live** naive contract during an active
handoff, asserting the pinned contract returns the exact corpus count + matching `logical_fingerprint`
every time, with the conservation invariant (fix E) computed against the reader's own pinned watermark.
Correctness failure blocks the run before any latency number is reported (flagship answer-equality
precondition).

## Workload and metrics, with the CV-gating line drawn explicitly

Four SOC-shaped queries, reused verbatim across every arm against the same view name: (a) freshness
probe — `count(*) WHERE event_day = :today` right after a fresh insert; (b) recent-window scan crossing
the hot/warm boundary (last 2 days); (c) cold-only historical aggregation (top `resp_p` by bytes over
full retention); (d) needle point-lookup by `orig_h` spanning all tiers.

| Metric | Class | Gating |
|---|---|---|
| Hot-tier ingest freshness (write→queryable in DuckLake) | latency | **CV-gated**, no-warmup harness |
| Post-handoff freshness (visibility lag for a just-moved day) | latency | **CV-gated**, no-warmup harness |
| Query-planning *latency* (`EXPLAIN ANALYZE`) | latency | **CV-gated**, `time_trials` |
| Scan latency (the 4 queries) | latency | **CV-gated**, `time_trials` |
| `plan_files()` *count* (planner-visible files) | structural | **deterministic**, raw, no CV |
| On-disk bytes / file count / row-group count / codec | structural | **deterministic**, `parquet_manifest` |
| `logical_fingerprint` equality + conservation invariant | correctness | **deterministic**, gate-blocking |

CV-gating rule (the flagship `run_bench.py` rule, lived by in the z-order leg): a delta between arms is
claimable only when `gap_pct > max(cv_a, cv_b)`. **Committed CV blowout ceiling: 30%** — a timed dim
returning `cv_pct > 30` invalidates that trial set (re-run on a quieter box), not averaged in (anchors
to the z-order leg's ~30.8% CV that correctly ruled a 29% gap non-claimable). Clean-box precondition for
all timed dims: host idle, one bench at a time, `env_characterize.py` re-run if the host changed.

## The null, the controls, and the pre-committed decision rule

Two nulls that fail differently (the most useful contrast this rig returns):

- **Null-A = single Iceberg table** holding the whole lifecycle, every batch appended, compacted on the
  same schedule as the tiered arm, queried by the same DuckDB reader with no tier predicates. The
  hypothesis body's literal null; the strong null for the **storage/planning** claim.
- **Null-B = single DuckLake table** for the whole lifecycle, catalog-inline. The strong null for the
  **freshness** claim, and fully *local* — the deliberate locality control. If the tiered arm only beats
  Null-A on freshness, the honest reading is "a local hot store beats object-store freshness" (prior leg
  re-confirmed), not evidence the cross-backend handoff earns its keep.

Plus a **degenerate-tiering control = all-Iceberg three tables** (hot/warm/cold as three Iceberg tables,
no DuckLake, same compaction cadence), which isolates *cost of tiering across backends* from *cost of
mixing two engines* — letting the run distinguish "tiering as a policy is unnecessary" from "the
cross-backend handoff specifically is unnecessary." (Window 2.)

**Pre-registered freshness asymmetry (fix B/locality).** The tiered arm's hot tier is DuckLake-local
and Null-B is DuckLake-local, so on the hot-freshness probe they read the same engine on the same local
store and must tie within CV by construction. That predicted tie *confirms the locality control worked*;
it must not be mis-read post-hoc as "no freshness signal." The only freshness dimension the tiered arm
*can* win is post-handoff visibility — where it structurally cannot beat a pure-local backend — which is
itself a null-favoring prediction.

**Decision rule (committed numbers, no "say"; Jake Thomas signs before any numbers exist).** The
multi-tier arm earns its complexity only if, at some point on the swept axis, it beats *both* nulls on a
named SLO by a margin exceeding the CV of both arms, with the crossover inside a plausible operating
range and no correctness invariant failing:

1. **Freshness SLO — 1 s end-to-end visibility (hard).** Expected: *no* arm crosses 1 s at lab scale
   (prior leg: hot ~8 ms, Iceberg read-after-write ~290 ms), so the null is predicted to win on
   freshness. A freshness win for the tiered arm counts only if it beats *both* nulls by
   `gap_pct > max(cv)` *and* is operationally meaningful, defined concretely as: the losing arm crosses
   the 1 s SLO and the tiered arm does not (no separate fuzzy "SOC-relevant" number — the 1 s line is the
   operational boundary).
2. **Planning SLO — 200 ms `EXPLAIN ANALYZE` planning latency (anchored to the prior leg's 181 ms
   manifest walk, rounded up).** Tiering earns planning keep only if Null-A's planning latency crosses
   200 ms as files accumulate *before* the tiered arm does, *and* the tiered arm's advantage *persists
   across the small-file sweep* (10→100→1,000→10,000 appends), not at a single file count.
3. **Storage SLO — strictly fewer bytes *and* fewer planner-visible files** than both nulls at matched
   corpus state and matched compaction policy, at parity-normalized layout (deterministic, no CV).

**Null wins — and I report it won — if** the tiered arm clears at most one SLO, or clears them only by
sub-CV margins, or if Null-A matches Null-B and matches the tiered arm within CV across the board (the
strongest null: the cross-backend handoff machinery is what's unnecessary). Equal-within-CV on freshness
*and* no storage win = null wins, simplicity breaking the tie per the Karen flag. The recorded verdict
in that case: "one backend suffices at lab scale on one host across the swept range," with the
retention/cost regime named as the unmeasured follow-up that would actually stress the null.

## The swept variables (breaking-points spine), in priority order

1. **Warm/cold file accumulation** (primary — drives planning cost): un-compacted appends
   10 → 100 → 1,000 → 10,000, with and without compaction. Where a planning cliff appears.
2. **Total corpus volume / cold-tier depth** via `scale_sweep` across ≥2 scales (the chDB lesson: a
   cheap small scale hides the knee).
3. **Commit cadence** (micro-batch 1k / 10k / 100k) — does a faster hot cadence move the crossover.
4. **Query mix** (the four shapes) — broad vs narrow benefit.

Cliff-vs-graceful *shape* is read off the planning-latency curve against accumulated file count: a knee
where planning blows up as small-file count climbs is a cliff; a flat-then-linear curve is graceful.

## Confounds and controls

- **Parquet writer/codec (the BENCH-E founding miss):** DuckLake defaults Snappy / 122,880-row-groups,
  pyiceberg defaults ZSTD / 1M. Force codec, row-group size, page size, Parquet version identical across
  both writers; read footers with `parquet_manifest` to confirm the knob took; report default *and*
  parity numbers separately. The cold-vs-null storage claim is made only at parity.
- **Mid-handoff double-count/drop:** append-then-delete ordering + half-open disjoint predicates +
  pinned-vs-naive oracle + conservation invariant (fix E, reader-pin-shared) measured *during* an
  in-flight handoff; `scale_sweep` so a timing race can't hide at a cheap scale.
- **Growth-confounded freshness (prior leg):** every freshness probe targets a bounded partition
  predicate with pruning on (one day, regardless of total size); freshness swept at multiple corpus
  sizes to confirm it's flat in table size — if not, pruning isn't working and the result is reported
  confounded.
- **Locality:** Null-B fully local; decision rule requires beating both nulls.
- **Compaction-schedule conflated with tiering:** degenerate all-Iceberg arm holds compaction cadence
  equal; storage reported at both pre- and post-compaction snapshots.
- **Stale-snapshot read:** explicit metadata-location pin, routed through Nessie; pin-staleness measured
  as a freshness metric, not leaked into a latency number.
- **Reader asymmetry:** all decisive head-to-heads are same-engine (DuckDB); any ClickHouse reference
  point is reported within-ClickHouse, never latency-diffed against DuckDB arms.
- **Cache (fix #5):** metadata cache defeated per-trial for freshness; OS page cache labeled
  warm-cache/single-host with the cold regime named; working-set size reported per arm (Window 2).
- **Single-host generalization:** disclosed and scoped, not controlled — verdict bounded to lab scale,
  one host, swept range; `scale_sweep` ×2 scales + the chDB precaution as the partial hedge.
- **Corpus realism:** uniform-random conn corpus is a stated Tier-B limitation;
  `lib.common`-generated, fingerprinted, aggregate-only output (honors the security-telemetry
  injection-surface boundary — no raw rows into context).

## Window plan

- **Window 1 (this window):** pre-register (this doc) + scaffold `bench_d_integrating.py` (N-day corpus
  generator, fix A) + build & run the **single-backend NULL baseline** (Null-A single Iceberg, Null-B
  single DuckLake): no-warmup freshness, CV-gated planning latency + scan latency, deterministic storage
  + `plan_files()` count, and `logical_fingerprint` equality across the two nulls (gate-blocking).
  Checkpoint + STATUS doc; commit lab + project1 touched-paths-only; pause for "window 2 open".
- **Window 2:** the multi-tier arm + watermark lifecycle + pinned-vs-naive correctness oracle +
  conservation invariant + degenerate all-Iceberg control; head-to-head vs both nulls.
- **Window 3 (if warranted):** the breaking-point sweep (file-accumulation primary) + `RESULTS-<date>.md`
  + the karen → hypothesis-validator → contradiction-detector gate.

## Sign-off

- [ ] Decision rule + null-wins conditions reviewed by **Jake Thomas** before execution (Platt
  strong-inference precondition; written into this README ahead of any integrating-run numbers).

## Key paths

- Build target (new): `bench-d-tiered-realization/bench_d_integrating.py` + `RESULTS-<date>.md`
- Existing commit-freshness leg: `bench-d-tiered-realization/bench_d.py` + `RESULTS-2026-06-15.md`
- Helpers: `lib/common.py` (`time_trials`, `logical_fingerprint`, `parquet_manifest`, `pin_artifact`,
  `scale_sweep`, `new_rng`, `BASE_EPOCH`)
- Methodology: `BENCHMARKING-METHODOLOGY.md`
- Proven warm-tier mechanics: `iceberg-compaction/run.py` (append-fragment → `overwrite` compaction →
  `expire_snapshots`, `plan_files()` planning proxy, `iceberg_scan()` read);
  `mv-rewrite-freshness/` (snapshot-advance freshness pattern)
- Hypothesis body + prior Evidence Updates: `01-knowledge-base/hypotheses/extended-hypotheses.md`
  (H-TIERED-REALIZATION-01)

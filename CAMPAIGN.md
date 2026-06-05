# Extended benchmark campaign — plan, findings, corrections

A standing record for the high-performance benchmark campaign: what we run (resource-ordered), what we
find, which prior assumptions the results correct, and the essays the findings could feed. Every run is
under [`BENCHMARKING-METHODOLOGY.md`](BENCHMARKING-METHODOLOGY.md): CV reported, config-parity (or
same-files registration when writers differ), isolation, High-Performance power plan, single-machine
caveat. Heavy runs are serialized (never co-run a timing bench — it inflates CV).

## Corrected assumptions (from the audit + the format decomposition)

1. **"DuckLake reads faster than Iceberg."** Real under defaults (~1.1–1.7×) but confounded. Matched
   codec+row-group narrows it to ~1.1–1.18×; byte-identical data collapses it to **~parity (1.00–1.05×)**.
   The read-speed lever is the Parquet **writer/encoder**, not the table format.
2. **"Matched codec = fair format comparison."** No. At the same codec+level, PyArrow writes 193 MB
   where DuckDB writes 114 MB on identical data (PyArrow dictionary-encodes high-cardinality columns;
   pyiceberg exposes no per-column control). Only same-files registration removes the encoder variable.
3. **"Iceberg is more storage-efficient."** Inverted: at matched codec DuckLake's files are *smaller*
   (zstd 1.14 vs 1.93 GB). The original gap was Iceberg defaulting to ZSTD vs DuckLake's Snappy.
4. **"A 10M-row benchmark is enough."** chdb showed CV up to 55% at 10M (queries 5–50ms, noise-
   dominated). Several "DuckDB faster" calls are ties within CV. Scale must put the signal above the CV.
5. **"Parquet is a reproducible serialization."** Logically yes, physically no — parallel row order makes
   bytes/SHA non-deterministic; integrity workflows must hash logical content, not file bytes.
6. **"WSL2 needs a native-Linux host for clean benchmarks."** No — the Windows High-Performance power
   plan drops CV 5.8%→0.8% (sustained) and 19.8%→2.7% (short). A power-plan setting, not a migration.
7. **"Compression choice is a storage decision."** It's also a read-latency lever (~5–13%, Snappy
   decompresses cheaper) and a determinism lever (order-sensitive encoding).
8. **"Context-collapse imposes a uniform fidelity tax on detection."** No — it splits into two distinct
   failure modes that land on whichever rule keys the field a given coarsening knob touched (R1): a rule
   either goes *blind* (dropped evidence → recall→0, the rare-DNS-sampled C2) or *cries wolf* (flattened
   distinction → precision collapse, MFA-absence coerced to false). Fidelity has to be evaluated against
   the detections you actually run, not as one number; and the worst case is silent (recall→0 raises no
   alert at all). Strengthens H-OCSF-CONTEXT-COLLAPSE-01 with a SOC-facing metric.
9. **"Over an open format the query engine is interchangeable; the answers always agree."** Falsified at
   scale (R3). chDB 4.1.8's Parquet equality-filter silently undercounts in tail row groups of a
   many-group file — a deterministic wrong answer, no error, that a timing-only benchmark would have
   published as a win. Interchangeability holds for SQL portability and ~latency, but carries a
   *correctness* asterisk; the cross-engine answer-equality gate is essential, not ceremony. For
   security data a `count(*) WHERE` is a detection threshold or compliance figure, so silent-and-fast is
   worse than slow-and-right. (Candidate upstream bug report — Jeremy to file with the reproduction.)

## Campaign backlog — resource-ordered (ascending)

Status: [ ] pending · [~] running · [x] done. Each is single-box and dependency-light unless noted.

- [x] **R0 large_scan 1B CV redo** — DONE (`18a7873`). Signal queries CV 0–6% (stable); full_count
  sub-5ms noise (CV 32%, discounted). Reproduces the codec-default confound at 1B: Iceberg 13.3 GB
  (ZSTD) reads 1.1–1.55× slower than DuckLake 21.6 GB (Snappy); same_files isolates it to ~parity.
- [x] **R1 Sigma over Store N** — DONE. The same portable Sigma rules that fire cleanly on Store F
  split two ways on the coarse store: **rare-DNS sampling → C2 recall 1→0** (the one C2 resolution is
  the only sub-3 query in the corpus, dropped), **absence-coercion → no-MFA precision 1.0→0.0037**
  (267 routine MFA-failures join the 1 needle), while truncation (indicator at char 26 < 64 cap) and
  flow rollup (RDP traffic already temporally sparse) leave their rules untouched (controls).
- [x] **R2 BENCH-A second corpus / dose-response** — DONE (already built+committed earlier this
  session). Dose-response is **flat-then-step**: headline +0.719 from light through the documented
  default, stepping to +0.829 only under heavy/very-heavy coarsening, routine control clean (0.000) at
  every rung — most of the adversary-tail gap is binary (atomic detail kept-or-gone), the step is the
  timing-tolerant queries failing once the rollup window perturbs order. Second chain: chain B
  (different actor/subnet, SMB lateral T1021.002) tracks chain A within **0.0095** (0.7095 vs 0.719),
  both routine-clean, canonical corpus fingerprint-restored. The +0.72 result isn't an artifact of one
  attack instance.
- [x] **R3 clickhouse-vs-duckdb at 1M/10M/100M** — DONE. (a) CV collapses with scale: mean CV ~19% (1M)
  → ~5% (10M) → ~4% (100M); sub-100ms micro-queries are noise below 10M. (b) **The headline is a silent
  correctness bug.** At 100M the cross-engine answer-equality gate *failed*: chDB 4.1.8 returned a
  selective-lookup count 49 rows short of DuckDB over the same Parquet, no error. Isolated + reproduced
  (`correctness_divergence.py`, cheap at 10M/rg=12288 → 814 groups, −52 rows across 6/8 probe values):
  chDB's Parquet equality (`=`/`IN`) filter drops matching rows in tail row groups, while `LIKE`,
  chDB's own MergeTree, and DuckDB all match the generator's ground truth. The gate is the only reason
  it surfaced. Strongest vindication of the lab's method.
- [x] **R4 ZSTD schema-trained dictionary on OCSF data** — DONE (`60c5c22`). Regime crossover, measured:
  per-event dict lift 2.74× (zstd-19 1.36→3.72×), decaying to ~1.0× by 1000-event blocks; columnar
  Parquet 9.45× (zstd-3 no-dict) beats every per-event approach. The regime sets the right compression,
  not the codec name — and security ingestion's per-event hot path is exactly where the trained dict
  pays. Held-out trained dictionary (disjoint row range). Reframed honestly: not "dict on Parquet" but
  "dict in the streaming regime; the lake gets it from the format."
- [x] **R5 Materialized-view acceleration** — DONE (`12253c9`). Read speedup is the robust win (45–77×
  serving a 12–2000-row MV vs scanning 20M); incremental maintenance is scale-dependent (2.9× cheaper
  than recompute for low-cardinality, break-even for high-cardinality at this base — the win grows with
  base:batch); storage negligible (+0.0–0.002%). MV is a bet on a fixed question set; ad-hoc still pays
  the base scan. Maintenance aggregates the in-hand batch, not regenerated rows.
- [ ] **R6 Iceberg-vs-DuckLake planning baseline at 1M/10M/100M** (moderate) — isolate catalog-traversal
  from scan; the clean current-Iceberg baseline the V4 tracking priority needs.
- [ ] **R7 Streaming write-contract** (moderate-heavy) — micro-batch cadence (5–500 rows), throughput +
  commit p50/p95 + concurrent read-while-write coherence; where does DuckLake inlining invert?
- [ ] **R8 same-files at 1B** (heavy) — the definitive format-neutrality result at scale, not just 100M.
- [ ] **R9 DWPD under sustained ingest** (heavy, 4–6h, run ALONE) — measured device bytes-written via
  smartctl across a multi-hour ingest + compaction; converts H-STORAGE-ENDURANCE-01 B/C→A.

Deferred (need external deps / humans, not in the autonomous single-box run): BENCH-C OBDA arm (Ontop +
R2RML setup), BENCH-B frontier leg (needs ANTHROPIC_API_KEY), BENCH-A named-practitioner realism sign-off.

## Essay slate (findings → /writing pillars)

- **The encoder is the read lever** (lakehouse) — formats are read-neutral on identical bytes; pick on
  write path, not a read benchmark. Backed by same-files arm.
- **Same codec, different sizes** (lakehouse) — codec name ≠ compression; the encoder variable. compression_probe.
- **The query engine returned the wrong answer and didn't tell you** (detection / economics) — the C3
  100M divergence: chDB's Parquet equality-filter silently undercounts; DuckDB matches ground truth; the
  cross-engine answer-equality gate is the only thing that caught it. The campaign's strongest piece —
  verify across engines, don't trust the speed. Backed by correctness_divergence.py. **(highest priority)**
- **How to run a benchmark that doesn't lie to you** (economics) — the CV/parity/same-files/power-plan
  methodology, with the C3 gate-catch as its opening case; companion to independent-measurement.
  BENCHMARKING-METHODOLOGY + env_characterize + correctness_divergence.
- **Parquet files don't hash the way security tools assume** (detection) — chain-of-custody/WORM/dedup
  break on byte-hashing; hash logical content. ocsf-parquet-determinism.
- **Scale before you measure** (economics) — chdb 55% CV at 10M; know your noise floor. env_characterize.
- **The write pattern is the architectural decision** (lakehouse) — streaming vs bulk vs correlation
  writes map differently onto the two formats. large-scan + parity.

(All require the voice-consistency + publication gates before any securitydataworks publish.)

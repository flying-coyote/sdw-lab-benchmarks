# Extended benchmark campaign — plan, findings, corrections

> Read-together narrative + thesis mapping: [`SYNTHESIS.md`](SYNTHESIS.md).

A standing record for the high-performance benchmark campaign: what we run (resource-ordered), what we
find, which prior assumptions the results correct, and the essays the findings could feed. Every run is
under [`BENCHMARKING-METHODOLOGY.md`](BENCHMARKING-METHODOLOGY.md): CV reported, config-parity (or
same-files registration when writers differ), isolation, High-Performance power plan, single-machine
caveat. Heavy runs are serialized (never co-run a timing bench — it inflates CV).

## Corrected assumptions (from the audit + the format decomposition)

1. **"DuckLake reads faster than Iceberg."** Real under defaults (~1.1–1.7×) but confounded. Matched
   codec+row-group narrows it to ~1.1–1.18×; byte-identical data collapses it to **~parity (1.00–1.05×)**
   for the filter and the low/moderate-cardinality rollups. The read-speed lever is the Parquet
   **writer/encoder**, not the table format — *with one measured exception at 1B (R8): a heavy
   high-cardinality aggregation (16.7M-distinct GROUP BY) ran 1.30× faster on DuckLake over byte-identical
   data, beyond CV. With the encoder gone that residual is the engine's per-format read/spill path (the two
   DuckDB extensions), not the format's bytes — so "~parity on identical bytes" is query-shape-dependent,
   not unconditional (mechanism a candidate, not isolated — see R8).*
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
- [x] **R6 Iceberg-vs-DuckLake planning baseline** — DONE (`653c4b8`). Engine held constant (DuckDB reads
  both formats), commit ladder 10→200 files at 5M rows: Iceberg end-to-end grows **6.5×** and its
  planning (pyiceberg `plan_files`) **17.6×** as files accumulate, while DuckLake's SQL-catalog
  resolution (`ducklake_list_files`) stays flat (~3 ms, 1.2×). The small-files tax is a metadata-location
  property; DuckLake's catalog is the architectural answer to what Iceberg V4 targets. Answers identical.
- [x] **R7 Streaming write-contract / cadence** — DONE (`1fca206`, `ocsf-streaming-cadence/`). Inlining's
  throughput edge is largest at the tiniest cadence (3.93× at 5 rows/commit, p95 12ms vs Iceberg 133ms)
  and narrows monotonically to 2.13× at 500 — the inversion *direction*; inline still leads at 500 so the
  crossover is beyond the swept range (the small-files penalty is a tiny-batch phenomenon). Iceberg commit
  p95 is ~constant (~133ms) regardless of batch (fixed file+manifest+metadata per-commit overhead); inline
  writes 0 files; read-while-write coherent at every cadence (running count exact throughout).
- [x] **R8 same-files at 1B** (heavy) — DONE (E: SSD, `--trials 3`, 28GB cap, 11.41 GB/copy). Bytes AND
  answers identical across catalogs (the cross-engine equality gate held at 1B). **Three of four queries at
  parity on byte-identical data** — filtered 1.00×, byte_rollup 1.01×, subnet_rollup 1.01× (CV ≤2.5%) —
  confirming format-neutrality at 1B, not just 100M. The fourth diverged: **topn_src (16.7M-distinct GROUP
  BY) ran 1.30× faster on DuckLake** (Iceberg 1,280,927ms CV 1.2% vs DuckLake 986,384ms CV 9.3%), a gap
  wider than the combined CV. With the encoder removed and no predicate to plan around, the residual
  isolates to the two DuckDB *extensions'* scan/spill path over identical bytes — but at a 28GB cap a
  16.7M-group hash aggregate likely spills to the (drvfs) temp dir, and DuckLake's elevated CV (9.3%) is
  consistent with variable spill, so the 1.30× may be an extension × memory-cap × drvfs-spill interaction,
  not a pure format property. Real, beyond-CV, direction-reproducible; mechanism a candidate, not isolated.
  drvfs inflates the absolute ms; the parity ratios and the one divergence are what transfer. Follow-up →
  Phase E (bare `read_parquet(glob)` third arm + a no-spill / higher-cap re-run to separate scan-path from
  spill).
- [DEFERRED] **R9 DWPD under sustained ingest** — Tier-A (device-measured) **not viable on this box**:
  WSL2 doesn't expose the physical NVMe (no `/dev/nvme*`; only VHDX-backed `sd*` virtual disks with no
  real SMART), so `smartctl` can't read the SSD's Data-Units-Written counter. `/proc/diskstats` gives a
  guest-level write-volume proxy (FS-level amplification, a lower bound) but can't reach the physical-NAND
  figure, so it can't promote H-STORAGE-ENDURANCE-01 to A. Decision (Jeremy, 2026-06-05): **defer to
  another system — native-Linux boot or AWS**, where `/dev/nvme0` + `smartctl -A` give true, isolated
  Data-Units-Written. Not run here; no proxy run.

Deferred (need external deps / humans, not in the autonomous single-box run): BENCH-C OBDA arm (Ontop +
R2RML setup), BENCH-B frontier leg (needs ANTHROPIC_API_KEY), BENCH-A named-practitioner realism sign-off.

## New benchmark work the findings spawned (Phase E backlog)

Added 2026-06-06 from the post-R8 review. Resource-light unless noted; each maps to a hypothesis.

- [x] **Cross-engine Parquet correctness probe — DONE** (`clickhouse-vs-duckdb/multi_engine_correctness.py`,
  `MULTI-ENGINE-CORRECTNESS.md`). The R3 chDB undercount was generalized across **13 distinct Parquet
  readers/executors** reading byte-identical Parquet (the ~814-row-group trigger), all via SQL, vs the
  generator's ground truth: DuckDB, DataFusion, Polars, pyarrow/Acero, Daft, fastparquet (in-process) +
  Trino, ClickHouse-server, Spark, StarRocks, Dremio, Postgres-native-load (containerized). Engine set
  chosen by *distinct reader* per `ENGINE-LANDSCAPE-SURVEY.md`. **Result: 11 readers correct; 2 distinct
  readers silently wrong** — and both isolated to a mechanism and confirmed default-config, not
  misconfiguration:
  - **chDB / ClickHouse v3 Parquet reader** undercounts `=`/`IN` via **default-on Bloom-filter pushdown**
    (`input_format_parquet_bloom_filter_push_down=1`). `LIKE` is correct (no Bloom probe), MergeTree is
    correct. **Disambiguated:** clickhouse-server **25.10** (older reader) reads the same file correctly, and
    `use_native_reader_v3=0` fixes it — so DuckDB's Bloom filter is conformant and the defect is the **v3
    reader's Bloom probe** (v3 default since 25.11; chDB 4.1.8 embeds CH 26.3). `mechanism_chdb_bloom.py`,
    `CHDB-UPSTREAM-BUG-REPORT.md`.
  - **fastparquet** (pure-Python, non-Arrow, retired) silently **mis-decodes DuckDB's `PLAIN_DICTIONARY`**
    string column (4,672/1M rows wrong on all three predicates); a pyarrow-written copy of the same data
    reads perfectly → a writer×reader decode bug. `mechanism_fastparquet_dict.py`, `FASTPARQUET-DECODE-NOTE.md`.
  - **Cross-engine-without-ground-truth (alternative-hypothesis test):** every divergence was a single
    reader against a unanimous rest (no ambiguous split), so a ≥3-engine majority catches it even without a
    generator — but two engines agreeing on a wrong answer would defeat majority, so the durable control is
    *validate against ground truth where you can, cross-engine majority where you can't*.
  - **Both bugs vanish under pyarrow's encoding** → the writer's encoding choices (Bloom filters,
    `PLAIN_DICTIONARY`) are a *correctness* variable across readers, not just performance. Ties to
    encoder-is-the-read-lever. Deferred (recorded, not skipped): RisingWave (`file_scan` has no local-FS
    backend — only s3/gcs/azblob; reader is arrow-rs), Feldera (per-file SQL-program compile; arrow-rs reader).
  - **Upstream report drafted** for a human to file (`CHDB-UPSTREAM-BUG-REPORT.md`); fastparquet note records
    the retired-engine guidance (use pyarrow).
- [x] **De-gamed BENCH-A — DONE** (`ocsf-context-collapse-apt29/`). The R1/R2 context-collapse finding was
  re-run with every gameability lever removed: **unmodified upstream SigmaHQ rules** (cloned verbatim, run
  via pySigma→SQL), on the **real MITRE ATT&CK APT29 evaluation** telemetry (OTRF/Mordor day 1), with the
  adversary/routine split coming from each rule's **own `attack.tXXXX` tags** vs MITRE's published APT29
  technique set, against a **documented** Store-N coarsening applied blind to the rules. Metric (no lab
  needle): per rule firing on the fidelity store, `recall_loss = 1 − matches_N/matches_F`, decomposed into
  blinding vs over-match. **Result: the disproportionality replicates de-gamed** — adversary-tail rules
  mean recall-loss **0.35 / 31% went fully blind** vs routine **0.16 / 16%** (Δ +0.19), and the blinded
  adversary rules are the expected ones (Base64/encoded-PowerShell + long-script-block rules killed by
  command-line/script-block truncation — APT29's encoded-PowerShell tradecraft). Mechanism validated with
  nothing lab-authored. Caveats: modest fired sample (54 rules; APT29 exercises a subset of techniques),
  one dataset/coarsening config, recall-loss vs the fidelity store (not absolute labels), and the
  independent-reviewer "is Store N realistic" gate stays open. Strengthens H-OCSF-CONTEXT-COLLAPSE-01.
- [x] **R8 `topn_src` divergence chase — DONE (T2.5, `ocsf-read-scan/topn_isolation.py`)**: three arms on
  byte-identical 100M Parquet (Iceberg ext · DuckLake · bare `read_parquet(glob)`) under a high cap vs a
  forced-spill low cap. **It's spill, not the read path** — no-spill arms at parity (iceberg/ducklake 0.93×,
  Iceberg even slightly faster), gap appears only under forced spill (1.15× toward DuckLake). R8's 1.30× at
  1B was the 28 GB-cap × drvfs-spill interaction; same-files read-neutrality holds for in-memory aggregates,
  resolving H-ICEBERG-INTERFACE-01's "not-unconditional" caution to a spill-regime caveat.
- [x] **Broader Parquet-writer encoding comparison — DONE (T2.6, `ocsf-read-scan/writer_read_lever.py`)**:
  one OCSF table (20M) written by DuckDB, PyArrow (default + dict-forced), and pyiceberg at a matched
  codec/row-group, read by the same engine. The writer's encoding **is** a read lever — it moves the
  high-cardinality group-by **~1.65×** (DuckDB-written 629 ms vs pyiceberg-written 381 ms) with everything
  but the encoding held constant — but the effect is **not size-monotonic**: pyiceberg's RLE-dictionary
  `src_ip` is smallest (212 MB) *and* fastest, DuckDB's PLAIN is mid-size (228 MB) but slower on the
  group-by, PyArrow-default is biggest (365 MB) and slowest. So "pick the writer, not just the codec" now
  rests on read latency, not only bytes; the lever's direction is query/data-shape-dependent. Backs the
  encoder-is-the-read-lever / same-codec-different-sizes essays.
- **R9 DWPD on native-Linux / AWS** — the deferred device-measured endurance (true `smartctl -A`
  Data-Units-Written), the only path to promote H-STORAGE-ENDURANCE-01 D→A; not viable under WSL2.
  External system.
- **BENCH-B frontier leg** (needs ANTHROPIC_API_KEY) and **BENCH-C OBDA arm** (Ontop + R2RML) — external-dep
  gated, as above.

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

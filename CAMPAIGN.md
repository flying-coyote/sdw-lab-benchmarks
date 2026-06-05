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

## Campaign backlog — resource-ordered (ascending)

Status: [ ] pending · [~] running · [x] done. Each is single-box and dependency-light unless noted.

- [~] **R0 large_scan 1B CV redo** — the audit's last item; 3 trials + CV + confound caveat. (running)
- [ ] **R1 Sigma precision over Store N** (light, ~5m) — same rules, coarsened store; does OCSF
  normalization degrade detection *precision* (noise) as well as the adversary-tail F1? Bridges
  context-collapse × sigma. Store N already on disk.
- [ ] **R2 BENCH-A second corpus / dose-response** (light, ~20m) — a second seeded chain + a
  normalization-severity sweep; turns H-OCSF-CONTEXT-COLLAPSE-01 from one chain into a curve.
- [ ] **R3 clickhouse-vs-duckdb at 100M** (moderate, chdb) — re-run at the scale the 10M CV said we need;
  resolves the noise-dominated micro-query ratios with stable CV.
- [ ] **R4 ZSTD schema-seeded dictionary on OCSF Parquet** (moderate, ~45m) — H-MV-ZSTD-01: schema-trained
  dict vs generic zstd vs snappy vs Parquet-native dict; size + read latency, held-out training set.
- [ ] **R5 Materialized-view acceleration** (moderate) — H-MV-SECURITY-01: pre-aggregated SOC-dashboard
  views vs base scan; ratio + write-amplification + storage cost. Reuses R4 corpus.
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
- **How to run a benchmark that doesn't lie to you** (economics) — the CV/parity/same-files/power-plan
  methodology; companion to independent-measurement. BENCHMARKING-METHODOLOGY + env_characterize.
- **Parquet files don't hash the way security tools assume** (detection) — chain-of-custody/WORM/dedup
  break on byte-hashing; hash logical content. ocsf-parquet-determinism.
- **Scale before you measure** (economics) — chdb 55% CV at 10M; know your noise floor. env_characterize.
- **The write pattern is the architectural decision** (lakehouse) — streaming vs bulk vs correlation
  writes map differently onto the two formats. large-scan + parity.

(All require the voice-consistency + publication gates before any securitydataworks publish.)

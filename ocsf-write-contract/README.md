# BENCH-D — hot-tier write contract

How does data *enter* the store under streaming ingest, and does that contract
differentiate the backends? Three realizations of the hot-tier write:

- **file-write** — classic Iceberg: a new data file, a manifest, and a fresh
  `metadata.json` on every commit. *(measured, via pyiceberg + a local SQL catalog)*
- **SQL-transaction** — DuckLake: an ACID transaction against a catalog that inlines small
  batches. *(measured, via the DuckDB `ducklake` extension)*
- **never-write** — Streambased ISK: producing to Kafka is the write. *(pending: vendor-
  published, seed-stage, no independent deployment to measure — recorded, not estimated)*

The decisive case is small-batch streaming, where the per-commit overhead of the
file-write contract is paid most often. Metrics per arm × batch size: commit latency
p50/p95/p99, files written per commit (the metadata churn), storage bytes, and a
read-contract-coherence check — does one engine (DuckDB) read both tiers and return
identical answers for the same logical data?

## Result (first pass, Tier B)

On the small-commit rung, file-write costs **~4 files per commit** vs DuckLake's **1**, with
roughly **2× the commit latency** and several times the storage; the gap narrows on large
batches, because the per-commit overhead amortizes over more rows. The unified read contract
**holds**: one engine reads both tiers identically (after writing a `version-hint.text` that
DuckDB's Iceberg reader needs and pyiceberg doesn't emit — a small real interop wrinkle).
Full numbers in [results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
.venv/bin/python ocsf-write-contract/run.py        # both arms, both rungs, coherence check
.venv/bin/python ocsf-write-contract/run.py --render-only
```

The OCSF ingest corpus is seeded and identical for both arms (fair input); commit latencies
are machine-specific medians reported with spread, never asserted as constants.

## Evidence tier

Tier B: single machine, synthetic OCSF ingest, two of three contracts. The write-contract
differentiation and the read-contract-coherence verdict are real measured findings at this
tier; the latencies are this host's medians. The never-write (ISK) arm is unmeasured
(vendor-blocked). The integrating "tiering beats one backend" claim and the Iceberg-V4
efficient-materialization null both need the third arm and a production-volume run, and a
named reviewer (Jake Thomas) on whether this resembles a real tiered build.

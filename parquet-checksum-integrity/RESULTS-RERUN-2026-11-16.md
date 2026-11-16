---
type: benchmark-results
title: "Page-checksum bake-off, post-hoc version re-check (2026-11-16)"
created: 2026-11-16
evidence_tier: B (first-party, single host, deterministic byte-flip, agent-run; post-hoc re-check, not pre-registered)
---

# Page-checksum verification: version re-check (run 2026-11-16)

**What this is.** A re-run of the 2026-06-06 bake-off (`results/RESULTS.md`) on two build sets, to check whether
the per-reader class (verifies by default / opt-in / none) still holds on current releases. It is a post-hoc
re-check, not a new pre-registered experiment. `rerun_2026_11_16.py` imports the unmodified write, corrupt and
reader functions from `run.py`; no tracked file was modified, and `results/results.json` and `results/RESULTS.md`
are untouched.

**One addition.** `run.py`'s `CAPABILITY` table is hard-coded from June research, so re-running the stock adapters
alone could not notice a newly added verification knob. The re-run therefore also probes each reader's own surface
for any setting or parameter named like `checksum`, `crc` or `verif`: DuckDB `duckdb_settings()` and the
`read_parquet` parameter list, DataFusion `SHOW ALL`, the Polars `read_parquet` / `scan_parquet` signatures, the
pyarrow `read_table` signature, and chDB `system.settings`. Any knob found would have been tried on the same
corrupted file (`extra_opt_in_from_probe`); none was found beyond the June ones.

**Run.** 2026-11-16T13:15:03Z (June pins) and 13:15:05Z (current), Beelink (AMD Ryzen 7 5800H, WSL2
6.6.87.2-microsoft-standard-WSL2), Python 3.12.3, two venvs built earlier on 2026-11-16 for the session's other re-runs and reused unmodified
(full sets in `requirements-rerun-2026-11-16-*.txt`).
`chronyc` system time within 0.0001 s of NTP; no timings are reported. Agent-run, not independently re-run.

| build set | pyarrow | DuckDB | Polars | DataFusion | chDB |
|---|---|---|---|---|---|
| june-pins | 23.0.1 | 1.5.3 | 1.41.2 | 53.0.0 | 4.1.8 |
| current | 26.0.1 | 2.0.0 | 2.1.0 | 55.0.0 | 4.4.0 |

chDB 4.1.8 resolved `chdb-core` 26.11.1 in the June-pins venv; whether the June run used the same core is not
recorded in the June `results.json`, so the June-pins row reproduces the June chDB version, not necessarily its core.

## Result: the June split holds on both build sets

| reader | stock config, checksummed file (both sets) | verification on (both sets) | no-checksum control |
|---|---|---|---|
| chDB | caught it (`Page CRC checksum verification failed`) | n/a, on by default (`input_format_parquet_verify_checksums`=1) | silent wrong (+1) |
| pyarrow | silent wrong (+1) | caught it (`page_checksum_verification=True`) | silent wrong (+1) |
| Polars | silent wrong (+1) | caught it only via `use_pyarrow=True` passthrough | silent wrong (+1) |
| DuckDB | silent wrong (+1) | no knob found | silent wrong (+1) |
| DataFusion | silent wrong (+1) | no knob found | silent wrong (+1) |

Sources: `results/rerun-2026-11-16-june-pins.json`, `results/rerun-2026-11-16-current.json`
(`with_checksum_stock`, `opt_in_verification`, `knob_probe`, `no_checksum_control`). Truth sum
72,623,864,790,332,856; every silent-wrong reader returned truth + 1.

Probe details worth keeping: DuckDB 1.5.3 lists only `debug_verify_blocks` and `debug_verify_vector`, which cover
DuckDB's own storage (as the June note says), and DuckDB 2.0.0 lists neither; DataFusion 55.0.0's `SHOW ALL` has no
checksum key among its `datafusion.execution.parquet.*` settings; Polars 2.1.0's `scan_parquet` gained a
`decryption` parameter but nothing for checksums.

## Reading

Nothing moved in five months: on DuckDB 2.0.0, DataFusion 55.0.0, Polars 2.1.0, pyarrow 26.0.1 and chDB 4.4.0 a
flipped byte in a checksummed page still comes back as a wrong sum from four of five readers in their stock
configuration, and chDB is still the only one that catches it by default. The class per reader is the transferable
finding and should be re-checked on the next upgrade.

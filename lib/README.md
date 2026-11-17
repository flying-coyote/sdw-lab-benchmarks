# lib

`common.py` is the shared determinism and measurement core. It holds one `MASTER_SEED` (20260601) and a
fixed epoch anchor (`BASE_EPOCH`, 2026-01-01T00:00:00Z), so a bench that draws its randomness through
`new_rng(sub_seed)` and its timestamps from the anchor regenerates the same corpus on every run. It also
carries the helpers those benches share: `connect()` and `configure_duckdb()` for a DuckDB connection with
a host-scaled memory limit and a native-disk spill directory, `prf1()` for precision, recall and F1 over
answer sets, `time_trials()` for a median-and-CV timing loop, and `pin_artifact()`, `logical_fingerprint()`,
`parquet_manifest()` and `scale_sweep()` for pinning a correctness finding to its exact file and checking
it at more than one scale (methodology principle 9).

36 of the 80 bench folders import it, through a short path shim at the top of their scripts. The rest
seed their own generators or need no generator at all, and the top-level README says which is which. A
change here touches every bench that imports it, so a change that could alter a generated corpus or a
query answer needs the affected benches re-run before it lands.

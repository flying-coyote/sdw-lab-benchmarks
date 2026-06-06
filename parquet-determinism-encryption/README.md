# Compute determinism + Parquet encryption interop

Lower-level bake-off #5 — two properties that sit under "verify the answer" and bite a regulated, multi-engine
security lakehouse: whether a floating-point aggregate is deterministic (across SIMD width and across engines),
and whether an encrypted Parquet file is portable across engines at all.

## Result (Tier B)

Five engines (DuckDB, pyarrow, Polars, DataFusion, chDB), bit-pattern comparison, exact integer controls:

- **Arm A(a) — SIMD dispatch is not a determinism risk.** Arrow forced to `none` / `sse4_2` / `avx2` via
  `ARROW_USER_SIMD_LEVEL` returns a **byte-identical** sum of 2,000,000 doubles at every level — the reduction
  doesn't change with vector width. (AVX-512 is absent on this CPU; the rung tested is none→SSE4.2→AVX2.)
- **Arm A(b) — cross-engine float aggregates genuinely diverge.** The same float column summed by the five
  engines lands on **three distinct** last-ULP results: DuckDB on its own, the pyarrow/Polars/DataFusion
  cluster together (all on Arrow/parquet-rs reduction), chDB on its own. `mean` splits the same way. The
  controls hold — integer `sum`, `count`, `min`, and `max` are bit-identical across all five — which proves the
  divergence is the floating-point *reduction order/algorithm*, not a read bug.
- **Arm B — Parquet Modular Encryption locks out every other engine.** pyarrow wrote a PME-encrypted file via
  an in-memory KMS and reads it back with the key; **every other reader is locked out entirely** — DuckDB
  detects the encryption but can't open it, Polars/DataFusion/chDB fail to parse, and even pyarrow without the
  key can't read it.

The two arms cut opposite ways, which is the point. Exact-typed answers (integer sum, count, min, max) are
safe to compare for equality and to hash for chain-of-custody; a float-derived metric needs a stated tolerance
and can't be hashed across engines. And turning on at-rest encryption *inside* the Parquet file silently
revokes the open read contract the whole MOAR swap story depends on — so for regulated data that must be
encrypted, either standardize on one PME-capable engine + KMS, or keep encryption at the storage layer
(encrypted volume / SSE) so the file stays engine-portable. Full tables in [results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
pip install -r parquet-determinism-encryption/requirements.txt
python parquet-determinism-encryption/run.py
```

The SIMD arm spawns one subprocess per vector level (env set before pyarrow imports). Determinism and interop
are the transferable findings and are version-bound — re-check on any engine upgrade. Tier B, single machine.

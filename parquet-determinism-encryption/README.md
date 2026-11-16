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

## Hypothesis mapping

Advances **H-ENGINE-ANSWER-EQUIVALENCE-01**: the float-divergence arm establishes which answer
types are safe to compare bit-for-bit across engines and which need a stated tolerance. The
Arm-B PME lockout additionally feeds **H-ICEBERG-METADATA-INTEGRITY-01** — in-file encryption
silently revokes the open multi-engine read contract. *(IDs recorded 2026-06-10 per the
benchmark-alignment audit.)*

## Corrections (2026-11-16)

- **Arm A(b), "last-ULP".** Decoded, the three float64 sums are 600,001,453,123,075.625 (DuckDB),
  600,001,453,124,023.5 (pyarrow, Polars, DataFusion) and 600,001,453,124,023.25 (chDB). chDB is 2 ULPs from the
  Arrow-family value; DuckDB is 7,583 ULPs away (947.875 absolute, about 1.6e-12 relative). "Three distinct last-ULP
  results" holds for chDB only; read it as three distinct results in the low-order bits.
- **Arm B, "locks out every other engine".** Arm B tested readers without the key only. Given the key
  (`RESULTS-PME-WITH-KEYS-2026-11-16.md`), a pyarrow-written uniform PME file opens in DuckDB 1.5.3 and 2.0.0 and in
  Polars 2.1.0, while a DuckDB-written file opens only in DuckDB among the five, because DuckDB writes no
  `aad_file_unique` and encrypts with an empty AAD (`RESULTS-FOOTER-AAD-2026-11-16.md`). DataFusion's Python wheel is
  built with Parquet encryption disabled, and chDB exposes no decryption setting. So the lock-out depends on the writer
  and the reader's build, not on encryption as such.

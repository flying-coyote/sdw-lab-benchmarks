# Compute determinism + Parquet encryption interop (lower-level bake-off #5)

**Tier B · single machine · bit-pattern compare.** Two properties under "verify the answer" that bite a
regulated, multi-engine lakehouse: whether a floating-point aggregate is deterministic (across SIMD width and
across engines), and whether an encrypted Parquet file is portable across engines at all. Engines: pyarrow `23.0.1`, duckdb `1.5.3`, polars `1.41.2`, datafusion `53.0.0`, chdb `4.1.8`.

## Arm A(a) — SIMD-dispatch determinism (same engine, forced vector width)

Arrow forced to each level via `ARROW_USER_SIMD_LEVEL`; the sum of 2,000,000 doubles compared bit-for-bit.
AVX-512 is absent on this CPU, so the rung tested is none → SSE4.2 → AVX2.

| forced level | runtime simd | sum (float64 bits) |
|---|---|---|
| none | `none` | `bc4dd3cb950d0143` |
| sse4_2 | `sse4_2` | `bc4dd3cb950d0143` |
| avx2 | `avx2` | `bc4dd3cb950d0143` |

**Byte-identical across SIMD levels: True** — Arrow's reduction does not
change with vector width here, so the SIMD layer is not a determinism risk on its own.

## Arm A(b) — cross-engine float aggregate determinism

The same float column summed/averaged by every engine, compared by exact float64 bit-pattern. Floating-point
addition isn't associative, so a different reduction order or algorithm shows up in the last ULPs.

**sum**: **3 distinct results**
  - `1d30d3cb950d0143` ← duckdb
  - `bc4dd3cb950d0143` ← datafusion, polars, pyarrow
  - `ba4dd3cb950d0143` ← chdb

**mean**: **3 distinct results**
  - `f1c08fd6a5e1b141` ← duckdb
  - `01e08fd6a5e1b141` ← datafusion, polars, pyarrow
  - `fedf8fd6a5e1b141` ← chdb

Exact controls (must agree everywhere, and do): `min`/`max` bit-identical across engines; `count` all equal =
True ([2000000]); integer `sum` all equal = True
([1999999000000]). The integer sum and the min/max agreeing while the float sum splits is the proof
that the divergence is the floating-point *reduction*, not a read bug.

## Arm B — Parquet Modular Encryption interop

pyarrow wrote a PME-encrypted file (1314 bytes) via an in-memory KMS. **pyarrow with the key:**
✅ read [1.0, 2.0, 3.0].

Every other reader, without the key:

| reader | result |
|---|---|
| pyarrow (no key) | ⛔ OSError: Error creating dataset. Could not read  |
| duckdb | ⛔ InvalidInputException: Invalid Input Error: File |
| polars | ⛔ ComputeError: parquet: File out of specification |
| datafusion | ⛔ Exception: DataFusion error: Parquet error: Parq |
| chdb | ⛔ RuntimeError: Code: 636. DB::Exception: The tabl |

## Reading

The two arms cut opposite ways, which is the useful part. SIMD dispatch is *not* a determinism problem here —
Arrow returns the same bytes whether it runs scalar or AVX2 — so the vector-width worry can be set aside. But
the cross-engine float aggregate genuinely diverges: the same column summed by different engines lands on
different last-ULP values, because each engine reduces in its own order with its own algorithm, and that is a
real wrinkle for the answer-equivalence thesis. The integer sum, count, min, and max agree to the bit across
every engine, so exact-typed answers are safe to compare for equality and to hash for chain-of-custody, while
a float-derived metric needs a stated tolerance and can't be hashed across engines. Encryption is the harder
edge: a Parquet-Modular-Encryption file is readable only by the implementer holding the key — every other
engine here is locked out entirely — so turning on at-rest encryption silently revokes the open read contract
the whole swap story depends on. For regulated data that *must* be encrypted, that means either standardizing
on one PME-capable engine + KMS or keeping encryption at the storage layer (encrypted volume / SSE) rather
than inside the Parquet file, so the file stays engine-portable. Tier B, single machine; re-check per version.

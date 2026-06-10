# Parquet float-aggregate determinism + PME encryption lock-out

*Two properties under "verify the answer" that bite a regulated, multi-engine lakehouse: whether a floating-point aggregate is deterministic across SIMD width and across engines, and whether an encrypted Parquet file is portable across engines at all. Bit-pattern compare throughout.*

*Tier B · single machine · bit-pattern compare · version-bound: pyarrow 23.0.1, duckdb 1.5.3, polars 1.41.2, datafusion 53.0.0, chdb 4.1.8. Re-check per version.*

## SIMD-dispatch determinism (same engine, forced vector width)

Arrow forced via `ARROW_USER_SIMD_LEVEL`; the sum of 2,000,000 doubles compared bit-for-bit. AVX-512 is absent on this CPU, so the rung tested is none → SSE4.2 → AVX2.

| forced level | runtime simd | sum (float64 bits) |
|---|---|---|
| none | `none` | `bc4dd3cb950d0143` |
| sse4_2 | `sse4_2` | `bc4dd3cb950d0143` |
| avx2 | `avx2` | `bc4dd3cb950d0143` |

*Byte-identical across SIMD levels — Arrow's reduction does not change with vector width here, so the SIMD layer is not a determinism risk on its own.*

## Cross-engine float aggregate — exact float64 bit-pattern

Floating-point addition isn't associative, so a different reduction order or algorithm shows up in the last ULPs.

| operation | duckdb | datafusion / polars / pyarrow | chdb | distinct results |
|---|---|---|---|:---:|
| `sum` | `1d30d3cb950d0143` | `bc4dd3cb950d0143` | `ba4dd3cb950d0143` | **3** |
| `mean` | `f1c08fd6a5e1b141` | `01e08fd6a5e1b141` | `fedf8fd6a5e1b141` | **3** |

*Exact controls that must agree everywhere, and do: `min`/`max` bit-identical across engines; `count` all equal (2,000,000); integer `sum` all equal (1,999,999,000,000). Integer sum and min/max agreeing while the float sum splits is the proof that the divergence is the floating-point reduction, not a read bug.*

## Parquet Modular Encryption (PME) interop

pyarrow wrote a PME-encrypted file (1,314 bytes) via an in-memory KMS. **pyarrow with the key:** ✅ read `[1.0, 2.0, 3.0]`. Every other reader, without the key:

| reader | result |
|---|:---|
| pyarrow (no key) | ⛔ `OSError: Error creating dataset. Could not read` |
| duckdb | ⛔ `InvalidInputException: Invalid Input Error: File` |
| polars | ⛔ `ComputeError: parquet: File out of specification` |
| datafusion | ⛔ `Exception: DataFusion error: Parquet error: Parq` |
| chdb | ⛔ `RuntimeError: Code: 636. DB::Exception: The tabl` |

**Security-relevant cell: the PME file is readable only by the key-holding implementer — every other engine is locked out entirely.** Turning on at-rest encryption inside the Parquet file silently revokes the open read contract the whole engine-swap story depends on. The float-aggregate split is the quieter hazard: the same column summed by different engines lands on different last-ULP values, so a float-derived metric needs a stated tolerance and can't be hashed across engines for chain-of-custody — while integer sum, count, min, and max agree to the bit and are safe to compare and hash. For regulated data that must be encrypted, either standardize on one PME-capable engine + KMS or keep encryption at the storage layer (encrypted volume / SSE) so the file stays engine-portable.

# Compute determinism + Parquet encryption interop

## What it measures

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

Which result is current: for Arm A the June run stands, with the "last-ULP" wording corrected below. For
Arm B the two 2026-11-16 follow-ups are current, because the June arm tested only readers without the key,
and with the key the outcome depends on which engine wrote the file and how the reader was built (see
Corrections). All three are measured outcomes, since each engine either returned the three written values
or failed.

## What would have made it fail

Arm A(a) would have failed if any forced SIMD level produced a different bit pattern, and Arm A(b) if the
engines agreed on the float sum; the exact controls (integer sum, count, min, max) are the negative
control that shows the read path is identical. Arm B as run in June could only show that readers without
the key fail, which is what encryption is for, so it could not test portability; the 2026-11-16 with-keys
run is the arm that could have shown every engine reading the file, and it found that, given the key,
pyarrow, DuckDB and Polars 2.1.0 read a pyarrow-written file, only DuckDB reads a DuckDB-written one, and the
DataFusion Python wheel and chDB read neither (no decryption setting was found in either).

## Pre-registration

None. No pre-registration file exists in this folder; both 2026-11-16 files are labelled post hoc in
their headers.

## Reproduce

```bash
pip install -r parquet-determinism-encryption/requirements.txt
python parquet-determinism-encryption/run.py
# 2026-11-16 follow-ups, one venv per build set (see the requirements-rerun files):
python parquet-determinism-encryption/rerun_pme_with_keys_2026_11_16.py current
python parquet-determinism-encryption/datafusion_pme_probe_2026_11_16.py current
python parquet-determinism-encryption/footer_aad_check_2026_11_16.py write current   # stage 2 runs under /usr/bin/python3
```

The SIMD arm spawns one subprocess per vector level (env set before pyarrow imports). Determinism and interop
are the transferable findings and are version-bound — re-check on any engine upgrade. Tier B, single machine.
The footer-AAD check also needs the `cryptography` package (its RESULTS file records 41.0.7 under the
system Python), which no requirements file pins. `run.py` rewrites `results/RESULTS.md`, so dated
corrections also live in this README.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json`, the 2026-06-06 run (Arm A current).
- [RESULTS-PME-WITH-KEYS-2026-11-16.md](RESULTS-PME-WITH-KEYS-2026-11-16.md), with
  `results/rerun-pme-with-keys-2026-11-16-*.json` and `results/datafusion-pme-probe-2026-11-16-*.json`.
- [RESULTS-FOOTER-AAD-2026-11-16.md](RESULTS-FOOTER-AAD-2026-11-16.md), with
  `results/footer-aad-check-2026-11-16-*.json`, which explains the DuckDB-written direction.

## Versions and pins

`requirements.txt` pins the June set (pyarrow 23.0.1, DuckDB 1.5.3, Polars 1.41.2, DataFusion 53.0.0,
chDB 4.1.8). The 2026-11-16 venvs are frozen in `requirements-rerun-2026-11-16-*.txt`; their chDB rows run
`chdb-core` 26.11.1 under both wrapper versions, so a chDB result there is bound to that core.

## Evidence tier and limits

Tier B, single machine. Arm B writes three values in one float column, a capability probe rather than a
scale test, and readers outside the five (parquet-java, Spark, arrow-rs built with encryption) were not
tested. AVX-512 was absent on the host, so the SIMD ladder stops at AVX2.

## Hypothesis mapping

Advances **H-ENGINE-ANSWER-EQUIVALENCE-01**: the float-divergence arm establishes which answer
types are safe to compare bit-for-bit across engines and which need a stated tolerance. The
Arm-B PME lockout additionally feeds **H-ICEBERG-METADATA-INTEGRITY-01** — in-file encryption
silently revokes the open multi-engine read contract. *(IDs recorded 2026-06-10 per the
benchmark-alignment audit.)*

## Corrections

*(2026-11-17: sections re-ordered to the lab's README layout and the current-result statement added; the
2026-11-16 corrections below are unchanged, and the ULP figures re-derive from the bit patterns in
`results/RESULTS.md`.)*

### 2026-11-16

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

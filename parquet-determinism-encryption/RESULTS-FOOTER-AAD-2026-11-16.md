---
type: benchmark-results
title: "Why a DuckDB-written PME file fails elsewhere with the correct key: footer AAD check (2026-11-16)"
created: 2026-11-16
evidence_tier: B (first-party, single host, agent-run; post-hoc follow-up to RESULTS-PME-WITH-KEYS-2026-11-16.md)
---

# Footer AAD check (run 2026-11-16)

**What this is.** `RESULTS-PME-WITH-KEYS-2026-11-16.md` direction 2 found that a DuckDB-written uniform PME file opens
in DuckDB but fails in pyarrow 26.0.1 and Polars 2.1.0 with the correct key. An adversarial review (Fable,
2026-11-16) reproduced that and found the cause in the footer bytes; this script reproduces the cause independently.
`footer_aad_check_2026_11_16.py` is new; no tracked file was modified.

**Method.** Write a three-value uniform-PME file from DuckDB and (current builds only) from pyarrow's explicit-key API,
both with the 16-byte key `0123456789012345`. Read each with every reader that has a key path, plus DuckDB with a
wrong key as a control. Then parse the file tail and decrypt the footer by hand with AES-GCM (`cryptography` 41.0.7,
system Python) under an empty AAD and, where the file carries one, under `aad_file_unique || 0x00` (the footer module
AAD the Parquet encryption spec builds for module type Footer = 0 with no AAD prefix).

**Run.** 2026-11-16T13:45:37Z (current: DuckDB 2.0.0, pyarrow 26.0.1, Polars 2.1.0) and the June-pin venv (DuckDB
1.5.3, pyarrow 23.0.1, Polars 1.41.2), same host and venvs as the with-keys run. Raw:
`results/footer-aad-check-2026-11-16-{current,june-pins}.json`. Agent-run, not independently re-run.

## Result

| file | `FileCryptoMetaData` | footer, key + empty AAD | footer, key + `aad_file_unique‖0x00` | wrong key |
|---|---|---|---|---|
| DuckDB 2.0.0 | `1c1c000000` (AesGcmV1, no `aad_file_unique`) | decrypts (182 bytes) | n/a, no identifier | fails |
| DuckDB 1.5.3 | `1c1c000000` | decrypts (171 bytes) | n/a | fails |
| pyarrow 26.0.1 explicit key | carries an 8-byte `aad_file_unique` | fails (InvalidTag) | decrypts (369 bytes) | fails |

Reads (current): the DuckDB file opens in DuckDB, fails in DuckDB with the wrong key ("Computed AES tag differs"),
fails in pyarrow 26.0.1 ("Failed decryption finalization") and in Polars 2.1.0 ("AAD unique file identifier is not
set"). The pyarrow file opens in DuckDB, pyarrow and Polars with the same key bytes.

## Reading

The key is right and the ciphertext is sound: DuckDB writes encryption metadata with no file identifier and encrypts
the footer with an empty AAD, while pyarrow and Polars build the module AAD the Parquet spec describes, which needs
that identifier. DuckDB's reader honors an identifier when one is present, which is why the other direction works.
So this is a writer-format divergence on DuckDB's default (and, per its 2.0 docs, only) encryption writer, not a
one-file accident. Pages were not checked, only the footer. Readers outside the five (parquet-java, Spark, arrow-rs
built with encryption) were not tested.

**Scope note on the with-keys table.** In `RESULTS-PME-WITH-KEYS-2026-11-16.md` direction 2, the pyarrow 23.0.1
cells are not correct-key tests: 23.0.1 has no explicit-key API, and its KMS path never asks for a key on a DuckDB
file, because DuckDB writes no key metadata. Read those cells as "no raw-key API", not as a failure with the key.

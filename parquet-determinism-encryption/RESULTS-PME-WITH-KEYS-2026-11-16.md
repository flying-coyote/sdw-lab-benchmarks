---
type: benchmark-results
title: "Parquet Modular Encryption across engines, WITH the key (post-hoc Arm B extension, 2026-11-16)"
created: 2026-11-16
evidence_tier: B (first-party, single host, agent-run; post-hoc extension, not pre-registered)
---

# PME interop when each engine is given the key (run 2026-11-16)

**What this is.** The 2026-06-06 Arm B (`results/RESULTS.md`) showed that readers *without* the key fail on a
pyarrow PME file, which is what encryption is for. It did not test whether the other engines can read the file when
they are given the key, which is the question that decides whether in-file encryption keeps a multi-engine read
contract. This post-hoc extension asks that, in three directions, on two build sets.
`rerun_pme_with_keys_2026_11_16.py` is new; `run.py` and its tracked `results/` files are untouched.

**Harness traps handled (and one found).**
- pyarrow's KMS path generates a random data key (DEK) and stores it wrapped, so handing another engine the KMS
  master key would fail for a harness reason. Direction 1 therefore writes with uniform encryption,
  `double_wrapping=False` and a 256-bit DEK, and the in-memory KMS records the DEK it is asked to wrap; that DEK is the
  AES key on the footer and the column, and it is what each engine is given.
- DuckDB's `add_parquet_key` takes a VARCHAR that may be a raw 16/24/32-character key or base64 (DuckDB 2.0 docs,
  read 2026-11-16). Probed here: base64 of a 16-byte key is 24 characters, and DuckDB appears to take it as a literal AES-192
  key (a file written under base64 of `0123456789012345` does not open with the raw string). A first attempt with a
  128-bit DEK failed in DuckDB for that reason ("Computed AES tag differs"); with a 256-bit DEK the base64 is 44
  characters and decodes unambiguously. The first attempt's result is superseded and not reported as a finding.
- Directions 2 and 3 use a printable 16-byte key (`0123456789012345`) passed raw, so every engine gets identical
  key bytes.

**Run.** 2026-11-16T13:17:47Z (current) and 13:17:48Z (June pins), Beelink (AMD Ryzen 7 5800H, WSL2), Python
3.12.3, two venvs built earlier on 2026-11-16 for the session's other re-runs and reused here, not modified
(`requirements-rerun-2026-11-16-*.txt`). Agent-run, not independently re-run. Values written:
`[1.0, 2.0, 3.0]`; "reads" below means the engine returned exactly those values.

| build set | pyarrow | DuckDB | Polars | DataFusion (Python) | chDB |
|---|---|---|---|---|---|
| june-pins | 23.0.1 | 1.5.3 | 1.41.2 | 53.0.0 | 4.1.8 |
| current | 26.0.1 | 2.0.0 | 2.1.0 | 55.0.0 | 4.4.0 |

## Results

**Direction 1: pyarrow writes (KMS path, uniform, 256-bit DEK); each reader given the DEK.**

| reader | june-pins | current |
|---|---|---|
| pyarrow (KMS, control) | reads | reads |
| DuckDB (`add_parquet_key` + `encryption_config`) | reads | reads |
| Polars (`ParquetDecryptionProperties`) | no decryption API in 1.41.2 | reads |
| DataFusion (Python) | no decryption setting exposed | no decryption setting exposed |
| chDB | no decryption setting exposed | no decryption setting exposed |

**Direction 3: pyarrow writes through its explicit-key API (`create_encryption_properties`, current set only;
pyarrow 23.0.1 has no such API).** pyarrow, DuckDB 2.0.0 and Polars 2.1.0 read it; DataFusion and chDB as above.

**Direction 2: DuckDB writes (`ENCRYPTION_CONFIG {footer_key}`), each reader given the same key.**

| reader | june-pins | current |
|---|---|---|
| DuckDB (control) | reads | reads |
| pyarrow, KMS whose unwrap returns the key | fails (cannot read schema) | fails: "No footer key or key metadata" |
| pyarrow, explicit-key API | API absent | fails: "Failed decryption finalization" |
| Polars | no decryption API | fails: "AAD unique file identifier is not set" |
| DataFusion (Python), chDB | no decryption setting exposed | no decryption setting exposed |

"No decryption setting exposed" means the probe found none. For DataFusion the script only searched the session
config (`SHOW ALL`), and DataFusion takes Parquet decryption keys as per-table format options, so a follow-up
probe (`datafusion_pme_probe_2026_11_16.py`, `results/datafusion-pme-probe-2026-11-16-*.json`, 13:25:59Z/13:26:00Z)
handed the key through `CREATE EXTERNAL TABLE ... OPTIONS ('format.crypto.file_decryption.footer_key_as_hex' ...)`
on a pyarrow-written and a DuckDB-written file: on both build sets both fail with "Parquet file has an encrypted
footer but the encryption feature is disabled", so the published Python wheel is built without Parquet encryption.
chDB's `system.settings` lists no Parquet `encrypt`/`decrypt` setting. Raw: 
`results/rerun-pme-with-keys-2026-11-16-{current,june-pins}.json`.

## Reading

In-file Parquet encryption is portable in one direction only on these builds. A pyarrow-written, uniformly encrypted
file opens with the key in pyarrow, DuckDB and Polars 2.1.0 (1.41.2 has no decryption API), which matches DuckDB's own documented
interoperability claim (uniform Arrow C++ files). A DuckDB-written file opens only in DuckDB, because pyarrow and
Polars both fail on it with the correct key, Polars naming a missing AAD file identifier. DataFusion's Python wheel
is built with Parquet encryption disabled and chDB exposes no decryption setting, so on this host neither read a PME
file whoever wrote it. The June
README's "locks out every other engine" is too strong for pyarrow-written files on current builds and roughly right
for DuckDB-written ones. The writer you standardize on decides which engines stay in the read contract, so this has
to be tested per writer, per engine and per version before in-file encryption is adopted, and storage-layer
encryption stays the option that keeps every engine able to read the file. Three values in one float column is a
capability probe, not a performance or scale test.

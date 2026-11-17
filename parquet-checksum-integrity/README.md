# Do Parquet readers verify page checksums?

## What it measures

A lower-level correctness bake-off, one layer below the engine. Parquet pages can carry a CRC32 over the
page bytes, but writing that checksum and verifying it on read are independent code paths, and most readers
leave verification off by default — so a single-bit flip inside a checksummed page comes back as a confident
wrong number rather than an error. This is the deepest extension of the cross-engine answer-equivalence
thesis: the earlier silent-wrong-answer findings (chDB's Bloom-pushdown undercount, fastparquet's
`PLAIN_DICTIONARY` mis-decode) both lived in the Parquet *library* layer, and this is the integrity backstop
sitting under all of them.

## Result (Tier B)

It is a **three-way split**, not pass/fail — capability, default, and behavior are three different things.
An int64 column (100,000 rows, PLAIN, uncompressed) is written with page checksums plus a unique sentinel,
one byte of the sentinel is flipped inside the data page (the value moves by +1 and the page CRC no longer
matches), and each reader computes `sum(v)`:

| reader | page-CRC support | stock config | with verification on |
|---|---|---|---|
| chDB `4.1.8` | verifies by default | ✅ caught it (`Page CRC checksum verification failed`) | — |
| pyarrow `23.0.1` | off by default | ❌ silent wrong (+1) | ✅ caught it |
| Polars `1.41.2` | off by default (via pyarrow only) | ❌ silent wrong (+1) | ✅ caught it |
| DuckDB `1.5.3` | no read-side verification | ❌ silent wrong (+1) | n/a |
| DataFusion `53.0.0` | no read-side verification | ❌ silent wrong (+1) | n/a |

The no-checksum control confirms the asymmetry — with no CRC there is nothing to catch the flip, so all five
return truth+1. The richer point for some of them is that this is a configuration default rather than a
missing feature: pyarrow already ships the verifier (`page_checksum_verification=True` on `read_table` /
`ParquetFile`) and just doesn't run it unless asked, and Polars can reach it only through its pyarrow
passthrough (`use_pyarrow=True, pyarrow_options={'page_checksum_verification': True}`). DuckDB and DataFusion
expose no read-side page-checksum knob at all in these versions. The chDB result is the nice irony: the
engine that gave us the Bloom-pushdown silent undercount is the one that catches the bit-flip here, so no
engine is uniformly safe and the only durable discipline is to verify rather than trust. Full table and
reading in [results/RESULTS.md](results/RESULTS.md).

The result is measured: each reader either raised an error or returned a sum, and the
sum is compared with the truth the writer knows. The 2026-11-16 re-check
([RESULTS-RERUN-2026-11-16.md](RESULTS-RERUN-2026-11-16.md)) ran the unmodified
harness on the June pins and on current releases (DuckDB 2.0.0, DataFusion 55.0.0,
Polars 2.1.0, pyarrow 26.0.1, chDB 4.4.0), probed each reader's settings for any new
checksum knob, and found the same split on both build sets, so the June finding still
holds and the re-check is the current result. One qualifier on chDB: the June-pins
venv resolved `chdb-core` 26.11.1 under `chdb==4.1.8`, and the June run did not
record its core, so the chDB row is bound to the wrapper version, not to one engine
build.

## What would have made it fail

A reader that verified the page CRC by default would have errored instead of returning truth+1, and a
reader with no verification would have shown up in the "none" column; both outcomes occurred, so the
split is not fixed by construction. The no-checksum control is the negative control: with no CRC on the
page, every reader returns truth+1, which shows the flipped byte is the only thing the verifying reader
could have caught. The test uses one injected fault, one flipped byte in one uncompressed PLAIN page, so
it reports how each reader behaves on that fault and is not a detection rate over corruptions in
general; a flip inside a compressed page may be caught by the decompressor first.

## Pre-registration

None. No pre-registration file exists in this folder, and the 2026-11-16 re-check is labelled post hoc
in its own header.

## Reproduce

```bash
pip install -r parquet-checksum-integrity/requirements.txt
python parquet-checksum-integrity/run.py
# the 2026-11-16 re-check, one venv per build set:
pip install -r parquet-checksum-integrity/requirements-rerun-2026-11-16-current.txt
python parquet-checksum-integrity/rerun_2026_11_16.py current
```

Deterministic byte-flip, ground-truth-verified sum, single machine. The per-reader class (default / opt-in /
none) is the transferable finding and should be re-checked per version — checksum verification is actively
being added across implementations, so a reader in the "none" column today can move to "opt-in" on an
upgrade. Tier B. `run.py` rewrites `results/RESULTS.md`, so dated corrections live in this README.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json`, the 2026-06-06 run.
- [RESULTS-RERUN-2026-11-16.md](RESULTS-RERUN-2026-11-16.md), with
  `results/rerun-2026-11-16-june-pins.json` and `results/rerun-2026-11-16-current.json`, the current result.

## Versions and pins

`requirements.txt` pins the June versions (pyarrow 23.0.1, DuckDB 1.5.3, Polars 1.41.2, DataFusion 53.0.0,
chDB 4.1.8). The two `requirements-rerun-2026-11-16-*.txt` files are the full frozen sets of the re-check
venvs, including `chdb-core` 26.11.1 in both.

## Evidence tier and limits

Tier B: first-party, single host, one corruption pattern on one column type. No timings are reported, so
no rig stamp is needed.

## Corrections

- *(corrected 2026-11-17: added the 2026-11-16 re-check as the current result and the chDB core caveat;
  no number changed.)*

## Hypothesis mapping

Advances **H-ENGINE-ANSWER-EQUIVALENCE-01**: the page-checksum verification split is the
integrity layer under the cross-engine answer-equivalence question — the same corrupted
bytes return different answers depending on the reader's verification default. *(ID
recorded 2026-06-10 per the benchmark-alignment audit.)*

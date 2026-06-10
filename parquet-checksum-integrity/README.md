# Do Parquet readers verify page checksums?

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

## Run it

```bash
pip install -r parquet-checksum-integrity/requirements.txt
python parquet-checksum-integrity/run.py
```

Deterministic byte-flip, ground-truth-verified sum, single machine. The per-reader class (default / opt-in /
none) is the transferable finding and should be re-checked per version — checksum verification is actively
being added across implementations, so a reader in the "none" column today can move to "opt-in" on an
upgrade. Tier B.

## Hypothesis mapping

Advances **H-ENGINE-ANSWER-EQUIVALENCE-01**: the page-checksum verification split is the
integrity layer under the cross-engine answer-equivalence question — the same corrupted
bytes return different answers depending on the reader's verification default. *(ID
recorded 2026-06-10 per the benchmark-alignment audit.)*

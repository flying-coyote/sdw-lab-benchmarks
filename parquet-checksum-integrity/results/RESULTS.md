# Do Parquet readers verify page checksums? (lower-level correctness bake-off)

**Tier B · single machine · deterministic byte-flip.** An int64 column (100,000 rows, PLAIN,
uncompressed, statistics off) is written **with** Parquet page checksums and a unique sentinel; one byte of
the sentinel is flipped inside the data page (the value changes by +1 and the page CRC no longer matches).
Each reader then computes `sum(v)`. A reader that **verifies** the CRC raises an error (catches it); one that
**ignores** it returns a silently-wrong sum (truth+1). The no-checksum control shows the CRC is the only
signal that could catch the flip. Readers: DuckDB `1.5.3`, pyarrow `23.0.1`, Polars
`1.41.2`, DataFusion `53.0.0`, chDB `4.1.8`.

It is a **three-way split**, not pass/fail — capability, default, and behavior are three different things:

| reader | page-CRC support | stock config (checksummed file) | no-checksum control |
|---|---|---|---|
| duckdb | no read-side verification | ❌ silent wrong (+1) | silent wrong (+1) |
| pyarrow | off by default | ❌ silent wrong (+1) | silent wrong (+1) |
| polars | off by default | ❌ silent wrong (+1) | silent wrong (+1) |
| datafusion | no read-side verification | ❌ silent wrong (+1) | silent wrong (+1) |
| chdb | verifies by default | ✅ caught it | silent wrong (+1) |

**Verifies by default: chdb.**
**Silently wrong with stock config despite the checksum: datafusion, duckdb, polars, pyarrow.**

### Opt-in probe — the SAME corrupted file, verification turned on where the reader has a knob

| reader (verification ON) | result |
|---|---|
| pyarrow | ✅ caught it |
| polars(via pyarrow) | ✅ caught it |

pyarrow's knob is `page_checksum_verification=True` on `read_table` / `ParquetFile` (default `False`); Polars'
native reader has no such parameter, so verification is only reachable through its pyarrow passthrough
(`use_pyarrow=True, pyarrow_options={'page_checksum_verification': True}`). DuckDB and DataFusion expose no
read-side page-checksum verification at all in these versions.

## Reading

Writing a page checksum and verifying it on read are independent code paths, and most readers leave
verification off, so they decode the corrupted bytes and hand back a confident wrong number — the same
silent-wrong-answer failure mode as the chDB Bloom-pushdown undercount and the fastparquet dictionary
mis-decode, one layer deeper. The richer point is that this is a configuration default rather than a missing
feature for some of them: pyarrow already ships the verifier and just doesn't run it unless you ask, which
means the integrity backstop for evidence-grade telemetry is one keyword argument away yet off in the stock
path almost everyone uses. The chDB result is the nice irony — the engine that gave us the Bloom-pushdown
silent undercount is the one that catches the bit-flip here, so no engine is uniformly safe and the only
durable discipline is to verify rather than trust. The no-checksum control confirms the asymmetry: with no
CRC there is nothing to catch the flip, so a writer that emits checksums only helps if the reader on the
other end actually checks them. That is why "verify the answer" has to include verifying the bytes, not just
cross-checking engines — and why the per-reader class here (default / opt-in / none) is the transferable
finding, to be re-checked per version as checksum verification is actively added across implementations.

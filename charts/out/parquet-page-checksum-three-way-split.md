# Do Parquet readers verify page checksums?

*Capability vs default vs behavior are three different things. An int64 column (100,000 rows, PLAIN, uncompressed) is written with Parquet page checksums; one byte of a sentinel value is flipped inside the data page (value changes by +1, page CRC no longer matches). Each reader then computes `sum(v)` — a verifying reader raises, an ignoring reader returns a silently-wrong sum (truth + 1).*

*Tier B · single machine · deterministic byte-flip · version-bound: duckdb 1.5.3, pyarrow 23.0.1, polars 1.41.2, datafusion 53.0.0, chdb 4.1.8. The per-reader class (default / opt-in / none) is the transferable finding; re-check per version as checksum verification is added across implementations.*

## Three-way split — stock config on the checksummed file

| reader | page-CRC support | stock config (checksummed file) | no-checksum control |
|---|---|:---|:---|
| duckdb | no read-side verification | ❌ silent wrong (+1) | silent wrong (+1) |
| pyarrow | off by default | ❌ silent wrong (+1) | silent wrong (+1) |
| polars | off by default | ❌ silent wrong (+1) | silent wrong (+1) |
| datafusion | no read-side verification | ❌ silent wrong (+1) | silent wrong (+1) |
| chdb | verifies by default | ✅ caught it | silent wrong (+1) |

*✅ = the bit-flip is caught (error raised) · ❌ = silently-wrong sum returned. The no-checksum control confirms the CRC is the only signal that could catch the flip.*

## Opt-in probe — same corrupted file, verification turned on where there's a knob

| reader (verification ON) | result |
|---|:---|
| pyarrow | ✅ caught it |
| polars (via pyarrow) | ✅ caught it |

*pyarrow's knob is `page_checksum_verification=True` on `read_table` / `ParquetFile` (default `False`); Polars reaches it only through its pyarrow passthrough. DuckDB and DataFusion expose no read-side page-checksum verification at all in these versions.*

**Security-relevant cell: chDB caught the bit-flip while the other four returned a confident wrong number.** Writing a page checksum and verifying it on read are independent code paths, and most readers leave verification off, so they decode the corrupted bytes and hand back a wrong sum with no error. For some this is a configuration default, not a missing feature — pyarrow already ships the verifier and just doesn't run it unless asked, so the integrity backstop for evidence-grade telemetry is one keyword argument away yet off in the stock path almost everyone uses. The irony is that chDB — the engine that produced the Bloom-pushdown silent undercount elsewhere in the lab — is the one that catches the flip here, so no engine is uniformly safe and the only durable discipline is to verify the bytes rather than trust them.

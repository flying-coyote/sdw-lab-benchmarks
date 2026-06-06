# The Parquet writer as a read lever (T2.6) — size AND read latency across writers

**Tier B, single machine, hot/warm.** One logical OCSF table (20,000,000 rows) written by each writer
at a **matched** codec (zstd-3), row-group (122,880), then read by the **same** engine
(DuckDB `read_parquet`). The only variable is the writer's encoding; reader and logical data are constant.

| metric | duckdb | pyarrow_default | pyarrow_dict | pyiceberg |
|---|---|---|---|---|
| size (MB) | 228.3 | 365.1 | 365.1 | 212.4 |
| src_ip encoding | PLAIN | PLAIN+RLE+RLE_DICTIONARY | PLAIN+RLE+RLE_DICTIONARY | PLAIN+RLE+RLE_DICTIONARY |
| read: filter_count (ms) | 10 | 12 | 12 | 7 |
| read: topn_src (ms) | 629 | 708 | 669 | 381 |
| read: scan_sum (ms) | 37 | 53 | 55 | 31 |

## Reading

"Same codec" is not "same file": the writers choose different dictionary/encoding strategies, so file size
differs — and the read-latency rows show whether that encoding choice is also a *read* lever, with the
reader held constant. Where a writer's output is both smaller and reads faster, the encoding is doing the
work the codec name gets credit for; where size and read latency diverge (smaller file, slower read, or
vice-versa), the two effects are separable. This generalizes the earlier DuckDB-vs-pyiceberg size finding
to read latency across DuckDB, PyArrow (default and dictionary-forced), and pyiceberg, so "pick the writer,
not just the codec" is grounded on read performance, not only bytes. Tier B, single machine; the relative
shape across writers is the transferable finding, the ms are this host's.

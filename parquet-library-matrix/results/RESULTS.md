# Parquet encoding x library correctness matrix (lower-level bake-off #2)

**Tier B · single machine · exact ground truth.** Both silent-wrong-answer findings the Lab turned up this
year (chDB's Bloom-pushdown undercount, fastparquet's dictionary mis-decode) lived in the Parquet *library*
layer. This is the home for that bug-class: for each physical encoding, does each library decode the bytes
back to the right values, or error / silently return wrong ones? It's the empirical companion to the Apache
implementation-status matrix — *claimed* support and a *correct answer* are different things. 20,000 rows per
column; order-independent value compare against exact ground truth. Libraries: pyarrow `23.0.1`, duckdb `1.5.3`, polars `1.41.2`, datafusion `53.0.0`, chdb `4.1.8`, fastparquet `2026.5.0`, pandas `3.0.3`.

## Arm 1 — reader × forced encoding

pyarrow writes one column at each forced encoding (emitted encoding confirmed from file metadata before any
reader is judged); every reader decodes and is compared to ground truth. ✅ correct · ❌ silent-wrong · ⚠️
errored (caught it). An italic cell means pyarrow wouldn't emit that encoding for that type, so there was
nothing to read.

### int64

| encoding | duckdb | pyarrow | polars | datafusion | chdb | fastparquet |
|---|---|---|---|---|---|---|
| `PLAIN` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `RLE_DICTIONARY` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `DELTA_BINARY_PACKED` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `BYTE_STREAM_SPLIT` | ⚠️ Error: BYTE_STREAM_S | ✅ | ✅ | ✅ | ✅ | ⚠️ NotImplementedError: |
### string

| encoding | duckdb | pyarrow | polars | datafusion | chdb | fastparquet |
|---|---|---|---|---|---|---|
| `PLAIN` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `RLE_DICTIONARY` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `DELTA_BYTE_ARRAY` | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ NotImplementedError: |
| `DELTA_LENGTH_BYTE_ARRAY` | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ NotImplementedError: |
### double

| encoding | duckdb | pyarrow | polars | datafusion | chdb | fastparquet |
|---|---|---|---|---|---|---|
| `PLAIN` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `RLE_DICTIONARY` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `BYTE_STREAM_SPLIT` | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ NotImplementedError: |

## Arm 2 — what each writer emits by default

Each writer writes the same three-column table at its defaults; the data-page encoding it chose per type,
from the file metadata.

| writer | int64 | string | double |
|---|---|---|---|
| pyarrow | RLE_DICTIONARY | RLE_DICTIONARY | RLE_DICTIONARY |
| duckdb | PLAIN | PLAIN_DICTIONARY | PLAIN |
| polars | PLAIN | RLE_DICTIONARY | PLAIN |
| fastparquet | PLAIN | PLAIN | PLAIN |

## Arm 3 — writer × reader real-world round-trip

Every reader reads every writer's *default* file, all three columns checked against ground truth. ✅ = all
three correct. This is the matrix that hits DuckDB's `PLAIN_DICTIONARY` string column — the deprecated v1
dictionary encoding the historical fastparquet bug lived on.

| writer ↓ / reader → | duckdb | pyarrow | polars | datafusion | chdb | fastparquet |
|---|---|---|---|---|---|---|
| pyarrow | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| duckdb | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| polars | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| fastparquet | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## Reading

The matrix makes the bug-class legible: a reader can claim an encoding and still decode it wrong, and the only
thing that catches it is comparing the decoded values to a known answer — the same verify-the-answer discipline
as the cross-engine and page-checksum benches, pushed down to the encoding. On these pinned versions the
exotic encodings fail *safe* — fastparquet raises `NotImplementedError` on the DELTA byte-array family and on
BYTE_STREAM_SPLIT, and DuckDB errors on BYTE_STREAM_SPLIT-for-int (a Parquet-2.10-era edge) rather than
returning a wrong number — which is the good failure mode, unlike the page-checksum bench where the same
libraries decoded corruption silently. The writers cluster on dictionary-by-default with PLAIN fallbacks, so
those exotic encodings are the ones a security pipeline only hits when someone tunes for size — exactly when
the least-exercised decode paths get loaded. Note DuckDB still emits the deprecated `PLAIN_DICTIONARY` for
strings; every reader here handles it, but it is the encoding the earlier fastparquet mis-decode lived on, so
it stays on the re-check list. The per-cell result is the transferable finding and is version-bound: re-run on
any library upgrade, because encoding support is actively moving (BYTE_STREAM_SPLIT for integers and the DELTA
family are the active edges).

# Parquet encoding × library correctness matrix

Lower-level bake-off #2, the home for the bug-class. Both silent-wrong-answer findings the Lab turned up this
year — chDB's Bloom-pushdown undercount and fastparquet's dictionary mis-decode — lived in the Parquet
*library* layer, not the engine. So the question here is direct: for each physical encoding, does each library
decode the bytes back to the right values, or does it error / silently return wrong ones? It's the empirical
companion to the Apache Parquet implementation-status matrix, which records *claimed* read/write support —
claimed support and a correct answer are not the same thing, and the gap between them is where a detection
query silently under-counts.

## Result (Tier B)

Three arms, six libraries (pyarrow, DuckDB, Polars, DataFusion, chDB, fastparquet), exact order-independent
ground truth (int sum exact; doubles `i*0.5` so summation order can't confound; clean-ASCII strings):

- **Arm 1 — reader × forced encoding.** pyarrow writes a single column at each forced encoding (emitted
  encoding confirmed from file metadata before any reader is judged), all six readers decode. **No silent-wrong
  cells** on these versions — the gaps are *errors*, the safe mode: fastparquet raises `NotImplementedError`
  on the DELTA byte-array family and on BYTE_STREAM_SPLIT, and DuckDB errors on BYTE_STREAM_SPLIT-for-int (a
  Parquet-2.10-era edge). PLAIN, RLE_DICTIONARY, and DELTA_BINARY_PACKED round-trip correctly everywhere.
- **Arm 2 — writer defaults.** pyarrow dictionary-encodes everything; DuckDB writes PLAIN for int/double and
  the deprecated **`PLAIN_DICTIONARY`** for strings; Polars and fastparquet lean on PLAIN.
- **Arm 3 — writer × reader real-world round-trip.** Every reader reads every writer's *default* file
  correctly — including DuckDB's `PLAIN_DICTIONARY` strings read by fastparquet, the exact deprecated encoding
  the historical fastparquet mis-decode lived on. At defaults, everything interoperates.

The honest headline: at default settings the libraries interoperate cleanly, and the failures show up only
when you force the exotic encodings a pipeline hits when tuning for size — and on these versions they fail
safe rather than silently. That contrast with the page-checksum bench (where the same libraries decoded
corruption *silently*) is the point: which failure mode you get is per-layer and per-version, so you measure
it rather than assume it. Full matrix in [results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
pip install -r parquet-library-matrix/requirements.txt
python parquet-library-matrix/run.py
```

The per-cell result is version-bound and is the transferable finding — re-run on any library upgrade, because
encoding support is actively moving (BYTE_STREAM_SPLIT for integers and the DELTA family are the active edges,
and a reader in the "errors" column today can move to "decodes correctly" — or, the case to watch for,
"silently wrong" — on an upgrade). Tier B, single machine.

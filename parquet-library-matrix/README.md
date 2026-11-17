# Parquet encoding × library correctness matrix

## What it measures

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

Each cell is measured, a decode compared with a known answer, and the result is bound to the corpus as
well as to the versions: the matrix uses 20,000 rows of clean-ASCII values, and on the same fastparquet
2026.5.0 a high-cardinality corpus written with small row groups is mis-decoded (see Corrections), so
"no silent-wrong cells" holds for this corpus and not for every file a security pipeline writes.

## What would have made it fail

Any cell whose decoded values differed from the ground truth without an error would have been marked
silent-wrong, and Arm 1 reads the emitted encoding from the file metadata before any reader is judged, so
a writer that ignored the forced encoding could not pass as a covered cell. What the matrix lacks is a
known-positive control: no cell reproduces the fastparquet `PLAIN_DICTIONARY` mis-decode that the
answer-equality work found on the same version, so a clean matrix cannot be read as evidence that defect
is absent.

## Pre-registration

None. No pre-registration file exists in this folder.

## Reproduce

```bash
pip install -r parquet-library-matrix/requirements.txt
python parquet-library-matrix/run.py
```

`run.py` rewrites `results/RESULTS.md`, so dated corrections live in this README.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json`, the 2026-06-06 run, the only one.

## Versions and pins

`requirements.txt` pins pyarrow 23.0.1, DuckDB 1.5.3, Polars 1.41.2, DataFusion 53.0.0, chDB 4.1.8,
fastparquet 2026.5.0 and pandas 3.0.3, the versions the results file records.

## Evidence tier and limits

Tier B, single machine, one synthetic corpus per type, exact ground truth. No timings are reported.

The per-cell result is version-bound and is the transferable finding — re-run on any library upgrade, because
encoding support is actively moving (BYTE_STREAM_SPLIT for integers and the DELTA family are the active edges,
and a reader in the "errors" column today can move to "decodes correctly" — or, the case to watch for,
"silently wrong" — on an upgrade).

## Corrections

- *(corrected 2026-11-17: Arm 3's "every reader reads every writer's default file correctly, including
  DuckDB's `PLAIN_DICTIONARY` strings read by fastparquet" holds on this bench's 20,000-row clean-ASCII
  corpus only. On the same fastparquet 2026.5.0, a DuckDB-written high-cardinality file with small row
  groups mis-decodes 4,672 of 1,000,000 rows with no error
  (`../clickhouse-vs-duckdb/results/RECONFIRMATION-2026-06-14.md`) and returns a wrong count on all 24
  cells of the 10M multi-engine scorecard (`../clickhouse-vs-duckdb/results/MULTI-ENGINE-CORRECTNESS.md`).
  Read the headline as "at default settings, on a small clean corpus, the libraries interoperate".)*

## Hypothesis mapping

Advances **H-ENGINE-ANSWER-EQUIVALENCE-01**: the encoding × library matrix tests whether the
same Parquet bytes decode to the same values across implementations — the library layer of the
answer-equivalence question, where both historical silent-wrong findings lived. *(ID recorded
2026-06-10 per the benchmark-alignment audit.)*

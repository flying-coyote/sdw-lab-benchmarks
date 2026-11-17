# When a schema-trained ZSTD dictionary helps OCSF data (R4)

## What it measures

How much a ZSTD dictionary trained on OCSF events improves compression, and how that depends on how the
bytes are framed. 100,000 synthetic OCSF events (about 221 bytes of JSON each, from the deterministic
generator in `../clickhouse-vs-duckdb/corpus.py`) are compressed at 1, 10, 100 and 1,000 events per block
with zlib-6, zstd-3, zstd-19 and the two zstd levels with a 110 KB trained dictionary, and the same events
are written to Parquet as a columnar reference. The dictionary is trained on a held-out 50,000-event range
of the same generator, so no test record is in the training set.

## Result (Tier B)

The dictionary's value depends on the block size. At one event per block, the per-record regime of
queue messages and streaming ingest, zstd-3 reaches 1.33× against raw JSON and zstd-3 with the dictionary
3.57×; at 100 events per block the dictionary no longer helps zstd-3 (5.89× with it, 6.30× without), though at
1,000 it gives a small gain again (6.11× with it, 5.88× without), and at 1,000 events per block the best payload codec, zstd-19 with the dictionary, reaches 8.13×, while
Parquet with zstd-3 and no column dictionary reaches 9.45× ([results/RESULTS.md](results/RESULTS.md)).
Sizes are exact and measured; every ratio re-derives from the byte counts in `results/results.json`
against 22,095,837 raw JSON bytes. The latencies beside them are medians with CV from one machine.

## What would have made it fail

The claim that the dictionary pays at small blocks and fades at large ones would have failed if the
dictionary ratio had stayed well above the plain codec at every block size, or had not helped at one
event per block. Holding the training set out guards against the dictionary memorizing the test records.
Training and test rows come from one synthetic generator, though, so the held-out split tests
generalization within one distribution and not to real telemetry, whose field mix and value repetition
differ.

## Pre-registration

None. No pre-registration file exists in this folder.

## Reproduce

```bash
pip install duckdb==1.5.3 pyarrow==23.0.1 zstandard   # pyarrow pin is the likeliest run version, see below
python ocsf-zstd-dictionary/run.py      # 100k test events, 50k held-out training events
```

`run.py` imports the corpus generator from `../clickhouse-vs-duckdb/` and `lib/common.py`, and rewrites
`results/RESULTS.md` and `results/results.json`.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json` (2026-06-05), the only run.

## Versions and pins

No requirements file, and `results/results.json` records no library versions, so the `zstandard`,
pyarrow and DuckDB versions the result ran on are not known from the repo. `zstandard` is pinned nowhere
in the lab; the root `requirements.txt` pins DuckDB 1.5.3 and pyarrow 23.0.1, which is the likeliest
environment and is not confirmed by the results file.

## Evidence tier and limits

Tier B, single machine, synthetic flattened events. The crossover shape is the transferable finding and
the magnitudes are this corpus's. Compress and decompress times have no rig stamp (methodology §7b), so
read their absolute values under §7a.

## Corrections

- *(2026-11-17: README written; no number changed.)*

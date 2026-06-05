# When a schema-trained ZSTD dictionary helps OCSF data (R4)

**Tier B · single machine.** 100,000 OCSF events (~221
bytes of JSON each) compressed under a sweep of codecs and block sizes. The ZSTD dictionary is trained on
a **held-out** 50,000-event sample (a disjoint row range, same schema and
distribution, never the test records), so the ratios are honest generalization. Sizes are exact; latencies
are medians with CV.

## Payload regimes — per-event to batched

### 1 event(s) per block (100000 blocks)

| codec | ratio vs raw JSON | compress ms (cv) | decompress ms (cv) |
|---|--:|--:|--:|
| zlib-6 | 1.4× | 772 (1%) | 235 (0%) |
| zstd-3 | 1.33× | 385 (1%) | 187 (1%) |
| zstd-3+dict | 3.57× | 158 (1%) | 72 (1%) |
| zstd-19 | 1.36× | 1880 (1%) | 188 (2%) |
| zstd-19+dict | 3.72× | 5682 (5%) | 71 (2%) |

### 10 event(s) per block (10000 blocks)

| codec | ratio vs raw JSON | compress ms (cv) | decompress ms (cv) |
|---|--:|--:|--:|
| zlib-6 | 4.26× | 254 (1%) | 61 (1%) |
| zstd-3 | 4.24× | 101 (1%) | 57 (1%) |
| zstd-3+dict | 5.26× | 86 (5%) | 44 (2%) |
| zstd-19 | 4.51× | 4426 (1%) | 55 (1%) |
| zstd-19+dict | 6.41× | 5269 (2%) | 43 (2%) |

### 100 event(s) per block (1000 blocks)

| codec | ratio vs raw JSON | compress ms (cv) | decompress ms (cv) |
|---|--:|--:|--:|
| zlib-6 | 5.9× | 254 (1%) | 38 (1%) |
| zstd-3 | 6.3× | 46 (8%) | 17 (10%) |
| zstd-3+dict | 5.89× | 75 (1%) | 18 (16%) |
| zstd-19 | 7.33× | 6352 (1%) | 31 (3%) |
| zstd-19+dict | 7.69× | 4347 (1%) | 32 (2%) |

### 1000 event(s) per block (100 blocks)

| codec | ratio vs raw JSON | compress ms (cv) | decompress ms (cv) |
|---|--:|--:|--:|
| zlib-6 | 6.23× | 333 (0%) | 33 (1%) |
| zstd-3 | 5.88× | 51 (1%) | 31 (2%) |
| zstd-3+dict | 6.11× | 64 (1%) | 33 (2%) |
| zstd-19 | 7.95× | 6899 (1%) | 28 (1%) |
| zstd-19+dict | 8.13× | 4382 (2%) | 28 (2%) |

## Columnar reference (one large Parquet row group, PyArrow)

The same events written columnar, where the format dictionary-encodes each column then block-compresses —
capturing cross-record redundancy structurally rather than via a trained payload dictionary:

| layout | size | ratio vs raw JSON |
|---|--:|--:|
| parquet snappy + dict | 4.16 MB | 5.32× |
| parquet zstd-3 + dict | 2.95 MB | 7.5× |
| parquet zstd-19 + dict | 2.77 MB | 7.99× |
| parquet zstd-3 no-dict | 2.34 MB | 9.45× |

## Reading

The dictionary's value is a function of how the bytes are framed. At one event per block — the streaming
ingest / queue-message / per-record archival regime security pipelines actually run — a generic codec has
almost no redundancy to exploit inside a ~200-byte payload, so the trained dictionary is the difference
between a poor ratio and a good one. As events are batched into larger blocks, a generic codec finds the
same cross-record redundancy on its own and the dictionary's edge narrows. By the time the data is a large
Parquet row group, the format has already dictionary-encoded each column and block-compressed it, reaching
a ratio the per-record payload codecs can't, and the trained-dictionary trick no longer transfers.

So "use zstd" is an incomplete answer: the right move is set by where in the pipeline the bytes sit. The
per-event hot path that dominates security ingestion is exactly where a schema-trained dictionary pays,
and exactly where a generic codec underperforms — while the analytical lake, which is columnar by
construction, gets its compression from the format and doesn't need the dictionary. The regime is the
lever, not the codec name. Tier B, single machine; the crossover shape is the transferable finding, the
magnitudes are this corpus's.

# Same data, different file: Parquet reproducibility is a configuration choice

> **METHODOLOGY INFRASTRUCTURE** — this probe is not a hypothesis test. It underpins the lab's
> determinism discipline: the logical-fingerprinting approach (sorted-set SHA over row content, not
> file bytes) and the `pin_artifact` convention used across all benchmarks were validated here.
> Results do not map to a hypothesis ID; they establish why the lab hashes logical content rather than
> raw files, and when a reproducible physical file is needed, what settings to ask for.

**Tier B · single machine · synthetic corpus.** This one surfaced as a nuisance and turned out to
be worth writing down. While building the two stores for the context-collapse benchmark, the
normalized store's file size moved between runs — a few tenths of a percent — even though the
corpus feeding it was byte-identical (the testbed fingerprints its raw content and that number
never changed). The first guess was that DuckDB's Parquet writer is non-deterministic. That guess
was wrong, and the real cause is more useful to know.

## What actually happens

The probe builds a small coalesced event store — a network rollup via `GROUP BY`, unioned with two
other sources, which is the shape of a real normalized SIEM table — and writes it to Parquet three
times under each of three settings, comparing the logical row set against the physical file:

| setting | rows | logical content (sorted-set SHA) | file bytes across 3 runs | bytes stable | file SHA stable |
|---|---|---|---|---|---|
| default (multi-threaded) | 500,000 | `857a280427ea7f55` | 2,788,104 / 2,788,326 / 2,869,621 | no | no |
| `SET threads=1` | 500,000 | `857a280427ea7f55` | 2,333,151 | yes | yes |
| `ORDER BY` before `COPY` | 500,000 | `857a280427ea7f55` | 2,303,625 | yes | yes |
| straight `SELECT` (no aggregation) | 400,000 | `0eb53daadb3674dd` | 3,998,714 | yes | yes |

The logical content is identical every single run — same rows, same order-independent hash. The
data is deterministic. What moves is only the physical encoding, and it moves in exactly the
condition you would predict once you stop blaming the writer: the multi-threaded path that runs an
aggregation. Single-threaded execution is byte-stable. Multi-threaded execution with an explicit
`ORDER BY` before the write is byte-stable. The plain scan with no aggregation is byte-stable even
multi-threaded, because nothing reorders its rows. So the writer is deterministic given a fixed row
order; what isn't deterministic is the row order itself.

## Root cause

DuckDB's parallel hash aggregation and `UNION ALL` emit rows in whatever order the worker threads
finish, and SQL never promised an order without an `ORDER BY` in the first place. Parquet's encoding
is order-sensitive — dictionary and run-length encoding and the compression blocks all depend on how
similar adjacent rows are — so two different row orders over the same data compress to different byte
counts and different file hashes. The non-determinism lives in the query's scheduling, surfaced
through an encoding that turns row order into bytes. Nothing is broken; the default just optimizes
for throughput, not for a reproducible file.

There's a second thing in the table worth noticing: the reproducible layouts are also the smaller
ones, around 2.3 MB against 2.79–2.87 MB for the parallel runs, because clustered rows compress
better than interleaved ones. Which order is *smallest* depends on the data and the key you sort on
(here the explicit sort edged out the single-threaded natural order; in the benchmark's real store
the natural ingest order won), so this isn't "always sort." But the default parallel path was both
the least reproducible and the largest, which is a combination worth knowing before you accept it.

## Why a security-data benchmark cares

The mental model that breaks here — same query plus same data equals the same file, so the same
hash — is the model underneath a lot of security and compliance plumbing. Content-addressed storage
and dedup key on byte-identity. Chain-of-custody and integrity-monitoring workflows hash an artifact
to prove it hasn't changed. WORM and "immutable" object claims often reduce to a byte comparison.
Re-derive "the same" evidence table through a parallel engine and you can get a different file and a
different SHA-256 while every row is identical, so a naive file-hash integrity check reports a change
that didn't happen to the data.

The fix is the one the lakehouse formats already chose: hash and compare *logical* content, not raw
file bytes. It is why Iceberg tracks identity at the manifest and snapshot level rather than asking
you to diff Parquet files, and it is why this Lab fingerprints the logical corpus and asserts results
identical on the row set, never on file size. If you do need a reproducible physical file — for a
signed artifact, a cached build, a deterministic test — reproducibility is available, it's just a
setting you have to ask for: pin the order (`ORDER BY` on a stable key) or pin the parallelism
(`SET threads=1`), and accept the throughput trade that comes with it.

## Reproduce

```bash
python determinism_probe.py
```

Deterministic synthetic corpus (seeded off fixed integers, no clocks or randomness), so the only
thing that can move between runs is the write path. Tier B, single machine; the magnitudes are
specific to this corpus and the mechanism is the transferable claim.

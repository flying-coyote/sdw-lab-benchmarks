# Streaming write cadence — throughput, commit latency, inlining inversion (R7)

**Tier B · single machine.** 200 commits per cadence, swept across
[5, 50, 500] rows/commit, on three write contracts (Iceberg file-write, DuckLake inlining off,
DuckLake inlining on at row-limit 10,000). Throughput is rows/sec over the whole
stream; commit latency is p50/p95 of per-commit time; file counts and storage are exact. The inline arm
also runs a read **during** the stream after every commit (the "immediately queryable" claim).

| cadence (rows/commit) | throughput ice/inline (rows/s) | data files ice/inline | commit p95 ice/inline (ms) | inline/ice throughput | files avoided | read-while-write coherent |
|---|--:|--:|--:|--:|--:|:--:|
| 5 | 70 / 273 | 200 / 0 | 133 / 11.9 | 3.93× | 200 | True |
| 50 | 729 / 2427 | 200 / 0 | 132 / 13.7 | 3.33× | 200 | True |
| 500 | 7144 / 15238 | 200 / 0 | 136 / 26.4 | 2.13× | 200 | True |

- Inline's edge over Iceberg is **largest at cadence 5** rows/commit
  and **smallest at cadence 500** — the inversion direction.

## Reading

At the tiniest cadence the inlining contract is at its strongest: Iceberg pays a data file plus a fresh
manifest and metadata.json on every small commit, while DuckLake holds the rows in its catalog and writes
no data file, so both its throughput edge and its file-avoidance are at a maximum. As the batch grows, the
per-commit file Iceberg writes stops being a tiny file and the fixed per-commit overhead (a roughly
constant commit p95 here, independent of batch size) is amortised over more rows, so the file-write
contract is penalised less and the inline arm's relative advantage narrows monotonically. That narrowing
is the inversion *direction*; inline still leads at the largest cadence swept (500 rows/commit), so the
actual crossover where file-write catches up sits beyond this range on this host — the finding is the
trend and that the small-files penalty is a tiny-batch phenomenon, not a located crossover cadence. The read-while-write column is the coherence
check: the inlined rows are queryable and the running count stays exact throughout the stream, so inlining
doesn't trade coherence for its file avoidance. Tier B, single machine; the cadence *shape* and the
coherence result are the transferable findings, the absolute throughput is this host's. Complements
BENCH-D (`ocsf-write-contract`) and `ocsf-write-inlining`.

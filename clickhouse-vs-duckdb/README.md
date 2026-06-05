# ClickHouse vs DuckDB on OCSF-shaped event data

A reproducible benchmark for one question the site's `economics/cost-paradox`
essay raises but does not measure: over an open format, *is* the query engine
interchangeable, and what does swapping cost? It runs the same OCSF-shaped
analytical workload on DuckDB and on embedded ClickHouse (chDB), checks that the
two engines return identical answers, and times them.

## What it measures

A deterministic synthetic corpus of OCSF Network Activity + Authentication events
(one UTC day, hot-IP heavy hitters, ~8% auth failures), written once to a single
Parquet file so both engines read identical bytes. Five SOC-shaped queries — a
full-scan rollup, a high-cardinality top-N, a selective time-window lookup, a
5-minute rate, and a failed-auth burst — run on each engine, two ways: querying
the Parquet file in place, and querying each engine's native store. Every query's
answer is asserted identical across engines before any latency is reported.

## Results (DuckDB 1.5.3, chDB 4.1.8, WSL2)

Every cross-engine answer matched, in both configs, at 1M and 10M events, and the
latencies traded by workload, modestly. At 10M events, native store:

| query | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|--:|:--:|--:|
| Full-scan rollup (count + bytes by class/activity) | 47.3 | 61.6 | duckdb | 1.30 |
| Top-20 talkers (high-cardinality group-by) | 290.9 | 588.5 | duckdb | 2.02 |
| Selective lookup (one user, 6-hour window) | 12.6 | 17.2 | duckdb | 1.36 |
| Time-bucketed rate (5-min buckets) | 48.0 | 41.7 | **clickhouse** | 1.15 |
| Failed-auth burst (filter + group + having) | 23.2 | 43.7 | duckdb | 1.88 |

Native-store load of the 10M corpus: DuckDB `CREATE TABLE` **457 ms** vs
ClickHouse MergeTree insert **3.9 s** (~8.6×). Full per-scale, both-config tables
in [`results/RESULTS.md`](results/RESULTS.md); machine-readable in
[`results/results.json`](results/results.json).

Two things showed up when the run was extended to 100M events. The first is a
measurement-discipline point: coefficient of variation collapses with scale (mean
CV ~19% at 1M, ~5% at 10M, ~4% at 100M), so the sub-100ms micro-queries that read as
wins or ties at 1M are mostly noise, and only at 10M and above does the per-query
ranking hold still — scale the corpus until the signal clears the noise floor before
trusting a ratio.

The second is sharper, and it is the headline. At 100M the answer-equality gate
*failed*: on the selective-lookup query chDB returned a count 49 rows short of
DuckDB's over the same Parquet file, with no error raised. The cause, isolated and
reproduced in [`correctness_divergence.py`](correctness_divergence.py), is a silent
defect in chDB 4.1.8's Parquet reader on an exact string-equality filter — it drops a
handful of genuinely-matching rows in the tail row groups of a many-group file, while
the same predicate via `LIKE`, the same data in chDB's own MergeTree store, and
DuckDB's read of the same bytes all match the generator's ground truth exactly. It is
a narrow, real bug in one read path, not a general indictment of ClickHouse, but it is
exactly the kind of thing a timing-only benchmark publishes as a "win" without ever
noticing the number was wrong.

So the honest reading of "is the engine interchangeable" has two layers. The SQL and
the answers port cleanly up to 10M (four of five queries byte-identical, one needs
`//` → `intDiv`), the swap costs a modest workload-dependent latency delta (≤ ~3×
here), and DuckDB was generally ahead. But interchangeability carries a correctness
asterisk at scale, because the cross-engine answer-equality gate is the only reason
the chDB miscount surfaced at all, and for security data — where `count(*)` under a
filter is a detection threshold or a compliance figure — a fast engine that is
silently wrong is worse than a slow engine that is right. Full divergence detail in
[`results/CORRECTNESS-DIVERGENCE.md`](results/CORRECTNESS-DIVERGENCE.md).

## Honesty boundary

This is **Tier B**, and the result is bounded — read
[`METHODOLOGY.md`](METHODOLOGY.md) before quoting any number:

- **chDB is embedded ClickHouse, not a tuned server or cluster.** This is the
  embedded-vs-embedded, single-node case; a clustered, primary-key-tuned
  ClickHouse at scale is a different system.
- **1–10M rows is below where MergeTree's storage/index design and ClickHouse's
  distributed scale-out pay off.** Neither engine was hand-tuned (defaults, no
  skip indexes, no pragmas).
- **This does not contradict the 145× ClickHouse-vs-Splunk result** (a real
  ClickHouse *server* against a schema-on-read SIEM on Zeek data, at a different
  scale) or the matrix's ClickHouse archetype score. Different comparison,
  different scale; they sit beside each other.
- Latencies are wall-clock medians on one machine — the *shape* of the win, not
  the milliseconds.

## Reproduce

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r ../requirements.txt
python run.py            # scales 1M and 10M
```

`run.py` regenerates each corpus twice and asserts the fingerprint matches, and
asserts every query's answer is identical on both engines, before writing
results. Same corpus, same answers, every run; the latencies are the only thing
that moves.

## Layout

```
corpus.py     deterministic OCSF-shaped corpus generator (-> one Parquet file)
bench.py      the five queries, both engines, both configs, answer-equality + timing
run.py        determinism + answer-equality gates, writes results/
results/      RESULTS.md + results.json (generated)
_work/        generated Parquet corpora (git-ignored)
```

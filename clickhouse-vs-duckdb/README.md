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

## Results (DuckDB 1.5.3, chDB 4.1.8, 12 vCPU WSL2)

Every cross-engine answer matched, in both configs, at 1M and 10M events. The
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

The honest reading: for single-node, in-process OCSF analytics at this scale, the
SQL and the answers port cleanly (four of five queries are byte-identical SQL;
one needs `//` → `intDiv`), the swap costs a modest, workload-dependent latency
delta (≤ ~2.6× here), and DuckDB was generally ahead. That is the cost-paradox
"engines are interchangeable" claim with a measurement under it.

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

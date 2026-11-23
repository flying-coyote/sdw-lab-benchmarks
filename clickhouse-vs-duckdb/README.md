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

## Result (DuckDB 1.5.3, chDB 4.1.8, WSL2)

The answers are measured against each other and, in the correctness follow-ups, against a ground truth
the generator computes without any engine, so a wrong count is a real outcome the harness can and did
produce. Every cross-engine answer matched, in both configs, at 1M and 10M events, and the latencies
traded by workload, modestly. At 10M events, native store, from the current `results/results.json`
(the 2026-11-17 correction below records the earlier table this replaced):

| query | DuckDB ms | ClickHouse ms | faster | × |
|---|--:|--:|:--:|--:|
| Full-scan rollup (count + bytes by class/activity) | 44.9 | 54.5 | duckdb | 1.21 |
| Top-20 talkers (high-cardinality group-by) | 274.6 | 508.2 | duckdb | 1.85 |
| Selective lookup (one user, 6-hour window) | 11.0 | 17.3 | duckdb | 1.57 |
| Time-bucketed rate (5-min buckets) | 44.2 | 35.9 | **clickhouse** | 1.23 |
| Failed-auth burst (filter + group + having) | 17.4 | 42.6 | duckdb | 2.44 |

Native-store load of the 10M corpus: DuckDB `CREATE TABLE` **437 ms** vs
ClickHouse MergeTree insert **4.2 s** (~9.6×). Full per-scale, both-config tables
in [`results/RESULTS.md`](results/RESULTS.md); machine-readable in
[`results/results.json`](results/results.json).

Two things showed up when the run was extended to 100M events. The first is a
measurement-discipline point: coefficient of variation collapses with scale (mean
CV across both engines and both configs ~23% at 1M, ~6% at 10M, ~3% at 100M, recomputed from
`results/results.json`), so the sub-100ms micro-queries that read as
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

### Which chDB the undercount holds for

The undercount was observed on chDB 4.1.8, whose embedded ClickHouse reported 26.3.9.1 according to
the bug report (`CHDB-UPSTREAM-BUG-REPORT.md`; `results/results.json` records the wrapper version only), and it is filed upstream as chdb-io/chdb#587. On 2026-06-14 the
four-probe mechanism script ran clean on chDB 4.1.9, whose engine moved to the 26.5 line
([`results/RECONFIRMATION-2026-06-14.md`](results/RECONFIRMATION-2026-06-14.md); no results JSON was
kept for that run), so the finding is bound to 4.1.8. The defect sits in `chdb-core`, the package that carries the engine:
`chdb` 4.1.8 (PyPI upload 2026-05-22) requires `chdb-core>=26.1.0`, `chdb-core` 26.3.0 (uploaded
2026-05-11) was the newest core until 26.5.0 on 2026-06-08, and `chdb` 4.1.9 (2026-06-09) requires
`chdb-core>=26.5.0`, so "fixed in 4.1.9" holds because 4.1.9 forces a 26.5 or later core. The root
`requirements.txt` now pins `chdb==4.1.8` together with `chdb-core==26.3.0`, and a fresh venv with
those two pins reports engine 26.3.9.1 and reproduces the undercount in `mechanism_chdb_bloom.py`
(re-run 2026-11-22: default reader returns 5,092 against a truth of 5,099 for `user42`, and the older
reader and `bloom_filter_push_down=0` are correct; that run kept no output, so the same run repeated on 2026-11-23 is kept with its `pip freeze` in [`results/RECONFIRMATION-PIN-2026-11-23.md`](results/RECONFIRMATION-PIN-2026-11-23.md), with the same counts). The twelve-engine scorecard in
[`results/MULTI-ENGINE-CORRECTNESS.md`](results/MULTI-ENGINE-CORRECTNESS.md) was run once, on the June
versions, and found ten of twelve engines correct on every cell, chDB's v3 reader and fastparquet
wrong; it was not re-run on 4.1.9, so a count of one wrong reader on current versions rests on the
four-probe re-check alone. Pinning the wrapper alone does not pin the engine the bug lived in: any
`pip install chdb==4.1.8` after 2026-06-08 without the core pin resolves a fixed core (the 2026-11-16
re-runs elsewhere in the lab got chdb-core 26.11.1), which is why the core pin was added on 2026-11-22.
The 2026-11-16 "june-pins" venvs predate that pin, so their chDB legs ran a later core
(`../parquet-checksum-integrity/results/rerun-2026-11-16-june-pins.json` records chdb-core 26.11.1) and
keep their "wrapper only" caveats.

## What would have made it fail

Two things could have failed, and one did. The answer-equality gate fails whenever the engines disagree
on any query, which it did at 100M; the correctness scripts compare each engine with a count the
generator computes directly, which no engine can bias. The latency comparison has no pass or fail and is
reported as a distribution per engine.

## Pre-registration

None. No pre-registration file exists in this folder, and the scale extension and correctness scripts
were added after the first run, as the dated result files show.

## Reproduce

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r ../requirements.txt
python run.py 1000000 10000000 100000000   # the published three scales; writes results/
python correctness_divergence.py    # the 10M ground-truth probe of the chDB undercount
python mechanism_chdb_bloom.py      # per-setting toggle table for the Bloom-pushdown path
python scale_pin_repro.py           # one-column generator, scale sweep (pass 100000000 for the trigger scale)
```

Run bare, `run.py` defaults to 1M and 10M only and overwrites `results/results.json` with a two-scale file
that drops the 100M rows, so pass all three scales to reproduce the entry-point JSON. `run.py` regenerates each corpus twice and asserts the fingerprint matches, and
asserts every query's answer is identical on both engines, before writing
results. Same corpus, same answers, every run; the latencies are the only thing
that moves. `multi_engine_correctness.py` needs the containerized engines (Trino, ClickHouse server,
StarRocks, Postgres) described at the top of that script.

## Results

- [`results/RESULTS.md`](results/RESULTS.md) and [`results/results.json`](results/results.json), the
  entry point: three scales (1M, 10M, 100M), both configs, regenerated by `run.py`.
- [`results/CORRECTNESS-DIVERGENCE.md`](results/CORRECTNESS-DIVERGENCE.md) (2026-06-05), the isolated
  10M reproduction of the undercount.
- [`CHDB-UPSTREAM-BUG-REPORT.md`](CHDB-UPSTREAM-BUG-REPORT.md) (2026-06-06), the filed report.
- [`results/MULTI-ENGINE-CORRECTNESS.md`](results/MULTI-ENGINE-CORRECTNESS.md) (2026-06-06), twelve
  engines plus a MergeTree control against ground truth.
- [`results/RECONFIRMATION-2026-06-14.md`](results/RECONFIRMATION-2026-06-14.md), the version-currency
  re-check (chDB 4.1.9 clean, fastparquet 2026.5.0 still wrong).
- [`results/scale_pin_repro.json`](results/scale_pin_repro.json), the one-column scale sweep.
- [`FASTPARQUET-DECODE-NOTE.md`](FASTPARQUET-DECODE-NOTE.md) and
  [`ENGINE-LANDSCAPE-SURVEY.md`](ENGINE-LANDSCAPE-SURVEY.md), supporting notes.

## Versions and pins

The results ran on DuckDB 1.5.3 and chDB 4.1.8 (`results/results.json`, `environment`). This folder has
no requirements file of its own and relies on the root `requirements.txt`, which pins `duckdb==1.5.3`
and `chdb==4.1.8` plus the readers and clients the multi-engine probe uses. Server engine versions are
recorded per engine in `results/MULTI-ENGINE-CORRECTNESS.md`.

## Evidence tier and limits

This is **Tier B**, and the result is bounded — read
[`METHODOLOGY.md`](METHODOLOGY.md) before quoting any number:

- **chDB is embedded ClickHouse, not a tuned server or cluster.** This is the
  embedded-vs-embedded, single-node case; a clustered, primary-key-tuned
  ClickHouse at scale is a different system.
- **1–10M rows is below where MergeTree's storage/index design and ClickHouse's
  distributed scale-out pay off.** Neither engine was hand-tuned (defaults, no
  skip indexes, no pragmas).
- **This does not contradict the lab's ClickHouse-server result on Zeek data**
  (`../zeek-flagship-rerun/`: a ClickHouse server against an OpenSearch 2.18.0
  schema-on-read baseline on 10M Zeek records, native 46.8× and Iceberg 10.1× on the
  five-query average, which one query dominates; that run supersedes the legacy 145×
  figure) or the matrix's ClickHouse archetype score. Different comparison,
  different scale; they sit beside each other. *(Reworded 2026-11-22: this bullet
  cited the superseded legacy figure and named the commercial SIEM behind it.)*
- Latencies are wall-clock medians on one machine — the *shape* of the win, not
  the milliseconds. The results record 14 vCPU on WSL2; no rig stamp (power plan and clock state,
  methodology §7b) was recorded for these runs, so absolute durations fall under §7a.

## Layout

```text
corpus.py     deterministic OCSF-shaped corpus generator (-> one Parquet file)
bench.py      the five queries, both engines, both configs, answer-equality + timing
run.py        determinism + answer-equality gates, writes results/
results/      RESULTS.md + results.json (generated) and the dated correctness files
_work/        generated Parquet corpora (git-ignored)
```

## Corrections

- *(corrected 2026-11-17: the 10M native-store table, the load times and the mean-CV figures above were
  replaced because they did not re-derive from the current `results/results.json`, which a later
  three-scale run overwrote. The superseded table read DuckDB/ClickHouse 47.3/61.6 ms (1.30×),
  290.9/588.5 (2.02×), 12.6/17.2 (1.36×), 48.0/41.7 (ClickHouse 1.15×) and 23.2/43.7 (1.88×), with
  loads of 457 ms against 3.9 s (~8.6×) and mean CV ~19%, ~5% and ~4% at 1M, 10M and 100M. The table
  and load times are the first run's `results/RESULTS.md` (commit 29fb815, 2026-06-01), which the later
  re-runs overwrote, and the mean-CV figures were stated in this README when the three-scale run landed
  (commit ca0ca04).)*
- *(corrected 2026-11-17: the undercount's reproduction at 10M depends on the file as well as the
  row-group count. The full twelve-column corpus at 10M rows and 814 row groups undercounted on 6 of 8
  probes (`results/correctness-divergence.json`), on 13 of 24 cells in the multi-engine run and on 4 of 4
  probes on 2026-06-14, while the bug report's one-column generator at the same 814 row groups gave 0 of
  2,000 values and 0 of 64 in `results/scale_pin_repro.json`, and reproduced only at 100M. Why the two
  files differ is not established. Read "scale-dependent" in the bug report as "depends on the file
  layout as well as the scale".)*
- *(corrected 2026-11-17: on reader counts. The scorecard covers twelve engines plus a MergeTree control,
  and one of the twelve, Postgres, reads a loaded copy rather than the Parquet file, so eleven of the
  twelve engines read the Parquet file itself. "11 of 13 agree" in the reconfirmation file counts the MergeTree
  control as a reader. The recorded result is ten of twelve engines correct on the June versions.)*
- *(corrected 2026-11-17: `METHODOLOGY.md` records the host as 12 vCPU and the latency gaps as at most
  ~2.6×; the results files record 14 vCPU, and the current 10M Parquet-in-place selective lookup is
  2.85×, 3.06× at 100M. That file is left as written and this note supersedes those two figures.)*

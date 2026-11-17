# Cross-engine NULL / type-coercion / timezone correctness

## What it measures

The answer-equivalence work so far tested `count(*)`/`sum` on equality point-lookups. But the shapes where
security answers silently diverge across engines aren't clean counts — they're NULL three-valued logic, type
coercion, and timezone handling, the parts of SQL that real detections lean on. This bench probes those, over
byte-identical Parquet, against a SQL-standard (or known-UTC) ground truth, with the session timezone forced
to a non-UTC zone so timezone effects are visible.

## Result (Tier B)

SQL engines: DuckDB `1.5.3`, DataFusion `53.0.0`, chDB `4.1.8`. Two patterns:

**Portable traps (identical across all three engines — silent the same way everywhere):** `<>`, `NOT IN`, and
`IN` all silently drop NULL rows; `count(col)` excludes NULLs while `count(*)` doesn't; `''` is not NULL; and
`i = '5'` coerces the string to the int (→ 60) uniformly. These are footguns you carry to every engine.

**Divergences (the same rule gives different answers per engine):**
- **The allowlist footgun, `col NOT IN ('a','b', NULL)`** — by SQL three-valued logic this is **empty**, so a
  detection phrased "flag everything not in the allowlist" matches *nothing* the instant the allowlist picks up
  a NULL. DuckDB and DataFusion return 0 (standard); **chDB returns 80** (it doesn't apply the emptying). Same
  rule, same data, different answer — and on two of three engines it's a silent total-bypass.
- **Time-window counts under a non-UTC session** — the same `WHERE ts >= TIMESTAMP '…12:00' AND ts < '…13:00'`
  over 1,200 instants (UTC-correct window = 600) returns **DuckDB 0 / DataFusion 600 / chDB 0** on a
  UTC-adjusted column and **600 / 600 / 0** on a naive column. No engine is buggy in isolation, though they don't all follow the standard, since SQL-92 (§4.5, §6.1 rule 5)
  gives a zone-less timestamp the session's zone, which is what DuckDB does (corrected 2026-11-16: this line
  previously said the standard leaves naive-timestamp + naive-literal tz-resolution to the engine, and it does not), but a time-bucketed detection is **not
  answer-equivalent** across engines when the session zone isn't UTC.

The safe defaults fall straight out: pin sessions to UTC, store tz-aware (UTC) timestamps, and never let an
allowlist carry a NULL. Full tables in [results/RESULTS.md](results/RESULTS.md).

Which result is current: the 2026-11-16 re-run
([results/RESULTS-RERUN-2026-11-16.md](results/RESULTS-RERUN-2026-11-16.md)) set and read back every
engine's session zone, ran on the June pins and on current builds (DuckDB 2.0.0, DataFusion 55.0.0, chDB
4.4.0), and returned the same answers on both, so the June findings hold and the re-run is the current
record. Re-derived from its two JSON files, the only Arm B divergence on either build is `NOT IN (...,
NULL)` (chDB 80, DuckDB and DataFusion 0), Arm A matches the June table in `results/RESULTS.md` row for row, and the added case
probe gives `LIKE` 20 and `ILIKE` or `lower()` 21 on all three engines. Every count is measured.

## What would have made it fail

Each cell compares an engine's count with a truth fixed by the data, so any engine could have diverged,
and the divergences reported are measured. Two kinds of truth are in play and are labelled: Arm B uses
the SQL-standard answer, and Arm A's 600 is the detection author's intended UTC window, which the
standard does not require (see the 2026-11-16 corrections).

## Pre-registration

None. No pre-registration file exists in this folder; the side probes are labelled post hoc.

## Reproduce

```bash
pip install -r ocsf-temporal-null-coercion/requirements.txt
python ocsf-temporal-null-coercion/run.py
python ocsf-temporal-null-coercion/run_rerun_2026_11_16.py <out_dir> <label>   # verified session zones
```

(Corrected 2026-11-16: in the June run `run.py` set only the process `TZ`, which DataFusion does not read, so
DataFusion ran in a UTC session; the re-run with every session zone set and read back, `run_rerun_2026_11_16.py`,
returns the same 600/600 for DataFusion under a verified New York session. See
[results/RESULTS-RERUN-2026-11-16.md](results/RESULTS-RERUN-2026-11-16.md).)

Deterministic; the bench forces `TZ=America/New_York` (and each engine's session timezone) so the timezone
divergence is reproducible rather than dependent on the host clock. The per-engine behavior table is the
transferable finding and is version-bound — re-check on upgrades. Tier B, single machine. Extends
H-ENGINE-ANSWER-EQUIVALENCE-01 from reader bugs into query semantics. `run.py` rewrites
`results/RESULTS.md`, so dated corrections also live in this README.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json` (2026-06-06), the June record.
- [results/RESULTS-RERUN-2026-11-16.md](results/RESULTS-RERUN-2026-11-16.md), with
  `results/rerun-2026-11-16-{june-pins,current}.json` and `results/side-probes-2026-11-16-*.json`, the
  current result.

## Versions and pins

`requirements.txt` pins the June set (pyarrow 23.0.1, DuckDB 1.5.3, DataFusion 53.0.0, chDB 4.1.8). The
re-run's builds are listed in its RESULTS file, which does not record the `chdb-core`. The session's other
2026-11-16 re-run venvs resolved `chdb-core` 26.11.1 under both wrappers
(`../parquet-checksum-integrity/requirements-rerun-2026-11-16-*.txt`), so the June-pins chDB row is most
likely bound to that core rather than to whatever core the June run used, which was not recorded either.
*(corrected 2026-11-17: this sentence earlier stated the 26.11.1 core as recorded for this folder's run.)*

## Evidence tier and limits

Tier B, single machine, a 370-row NULL file and 1,200 timestamp instants. No timings are reported.

## Corrections

- *(2026-11-16: two corrections inline above, on the SQL standard and on DataFusion's session zone.)*
- *(corrected 2026-11-17: added the current-result statement and the layout sections; no number changed.)*

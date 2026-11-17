# delegation-chain-query (R7)

## What it measures

What it costs to walk an agent delegation chain at query time to detect scope escalation. Records are
synthetic and *delegation-shaped*: they are modeled on the OCSF 1.9.0 IAM `delegation` object, but the
field names haven't been checked against the schema. There are four arms: a recursive CTE walk (A), a one-hop
parent self-join (B), a filter on an authority column materialized at write time (C), and a root-only filter (D).
Each runs in DuckDB 1.5.3 and chDB 4.4.0, at depths 2 to 12 and volumes of 1e5 to 1e7 rows. A deterministic arm
has no LLM in the loop, so methodology §10 does not apply.

## Result

At 1e7 rows and depth 12 the recursive walk ran in a median 1.56 to 1.70 s in DuckDB and 0.87 to 0.99 s in chDB across
two runs, the one-join check in 0.28 to 0.41 s and the write-time column filter in 20 to 27 ms, and the within-cell
walk-to-join ratio rose with depth in both engines (`RESULTS.md`, Headline). The latencies are measured, under a
shared host, and the within-cell ratios are the defensible output because absolute medians moved with load between
runs. The correctness result is different in kind: arms A, B and C returning exactly the planted escalation set in
18 of 18 cells checks that the SQL implements the generator's own definition, and arm D's per-cell recall of 0.398 to 0.67
is set by the generator's plant mix, which `RESULTS.md` says, so it shows the blind spot exists and not how common
it is in real logs.

## What would have made it fail

H1 to H3 in `PREREGISTRATION.md` carry numeric thresholds, and H1 was falsified for DuckDB, H2 as stated, and H3 for
chDB. H5 would have failed on any cell where A, B or C differed from ground truth or D caught a `reacquire` plant.
A, B and C returning exactly the planted set shows each query implements the same escalation definition the
generator used (H5, "correctness"); it is a consistency check that a query bug, in CTE depth or chDB semantics for
instance, could have failed, not a detection rate, because plants and arms share one definition.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before the run and not owner-reviewed, at 2026-11-09T23:00:13Z
(`results/freeze.txt`), with two dated amendments appended in the same file: a launch fix before any data was
collected (23:01:01Z) and a replication pass added after run 1 and before run 2 (23:13:25Z). All three hashes in
`results/freeze.txt` verify against the matching prefix of the current file (lines 1 to 135 for the freeze, 1 to 142
after amendment 1, the whole file after amendment 2). Hypotheses are judged on run 1 as pre-registered, with run 2
beside it as a replication. The amendment text and two other lines in the frozen file name private working paths
outside this repo; the file is frozen and is left as it is.

## Reproduce

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run_all.py                       # run 1 (results then moved to results/raw_run1/)
.venv/bin/python run_all.py                       # run 2 -> results/raw/
.venv/bin/python summarize.py raw_run1 > results/tables_run1.md
.venv/bin/python summarize.py raw      > results/tables_run2.md
```

`gen.py` generates the data, `run_cell.py` runs one cell and `run_all.py` drives the grid. The Parquet is deleted
after each cell and regenerates from seed 20261109; the planted ground truth `data/*.truth.json` is gitignored with
the rest of `data/`.

## Results

- `RESULTS.md` is the entry point: headline, hypothesis verdicts, key cells, limits, commands.
- `results/raw_run1/` (run 1) and `results/raw/` (run 2) hold per-cell raw JSON and artefact pins;
  `results/tables_run1.md` and `results/tables_run2.md` the tables; `results/summary.json` and
  `results/summary_raw*.json` the summaries; `results/freeze.txt` the hashes and clock readings.
- `VERIFICATION.md` is the independent check (VERIFIED-WITH-FIXES); the fixes are wording on H1, H3's chDB margin,
  D's recall and some range statements.

## Versions and pins

`requirements.txt` pins duckdb 1.5.3, chdb 4.4.0, chdb-core 26.9.0, pyarrow 23.0.1, numpy 2.5.4 and pandas 3.1.1.
chDB 4.4.0 is not the lab-wide 4.1.8 pin in the root `requirements.txt`, which `RESULTS.md` also says.

## Evidence tier and limits

`RESULTS.md` describes this as a first-party lab measurement on a single host under shared load, synthetic and
deterministic, with no tier letter. Linear chains only, integer keys where OCSF uses strings, an unmeasured ingest
cost for arm C, engine defaults with no ClickHouse server, and depth trends confounded with load. See Limits in
`RESULTS.md`.

## Corrections

- 2026-11-09: verifier wording fixes in `RESULTS.md`.
- 2026-11-17: the correctness bullet in the `RESULTS.md` headline now carries a dated note that A, B and C matching the
  planted set is a consistency check against the generator's definition, not a detection rate. One first-person
  phrase in `RESULTS.md` (the attribute names) was recast in neutral voice. This README was restructured to the lab layout and now records the prefix-hash checks on the amended pre-registration.

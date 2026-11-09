# delegation-chain-query (R7)

What it costs to walk an agent delegation chain at query time to detect scope escalation. Records are
synthetic and *delegation-shaped*: they are modeled on the OCSF 1.9.0 IAM `delegation` object, but the
field names haven't been checked against the schema. There are four arms: a recursive CTE walk, a one-hop
parent self-join, a filter on an authority column materialized at write time, and a root-only filter. Each
runs in DuckDB 1.5.3 and chDB 4.4.0, at depths 2 to 12 and volumes of 1e5 to 1e7 rows. A deterministic arm
has no LLM in the loop, so methodology §10 does not apply.

- `PREREGISTRATION.md`: question, hypotheses, stop rule. Frozen before the run, with two dated amendments.
- `RESULTS.md`: headline, hypothesis verdicts, limits.
- `gen.py` generates the data; `run_cell.py` runs one cell; `run_all.py` drives the grid; `summarize.py` builds the tables.
- `results/raw_run1/`, `results/raw/`: per-cell raw JSON and artifact pins. `results/tables_run*.md` are the tables, and `results/freeze.txt` holds the hashes and clock reading.
- `data/*.truth.json`: planted ground truth. The Parquet is deleted after each cell; seed 20261109 regenerates it.

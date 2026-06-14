# DuckLake catalog failure modes (BENCH-E)

Built 2026-06-14, pre-registered in project1 `BENCHMARK-BACKLOG.md` as BENCH-E. It tests a
narrow, falsifiable question raised by the Iceberg-V4-vs-DuckLake metadata work: the DuckLake
vendor pitch leads with planning speed and a 105× streaming claim, but the catalog layer that
makes that speed possible carries its own correctness and operability bugs. This bench does not
re-run the 105× marketing number (it is an unequal-workload comparison — see the V4/DuckLake
reconciliation). It reproduces three *verified-real, OPEN* catalog bugs and reports whether each
still fires on the most-current stack.

## Discipline (why this is a benchmark and not a bug-report rehash)

Every issue number was verified at the primary (`duckdb/ducklake` GitHub) as real and OPEN
*before* a single line of repro was written — the three came in via a Gemini Deep Research
intake, which is corroboration, not proof. Each arm records the DuckDB + DuckLake extension
versions it ran under, so every verdict is a version-bound statement, not a timeless one. This is
the same version-currency method the chDB answer-equivalence bench used: a bug that "should be
fixed" is only fixed when you run it on the current version and watch it not fire — and, for the
one that doesn't fire, you confirm it *does* fire on the version it was filed against, so
"fixed" is distinguished from "my repro under-triggers."

## The three arms

| arm | issue | what it is | needs |
|---|---|---|---|
| E1 | [#1215](https://github.com/duckdb/ducklake/issues/1215) | cross-store delete-conflict gap (correctness) | DuckDB-native catalog |
| E2 | [#1184](https://github.com/duckdb/ducklake/issues/1184) | >1600-column CREATE TABLE wall (operability) | Postgres catalog |
| E3 | [#1031](https://github.com/duckdb/ducklake/issues/1031) | connection-pool timeout (operability) | Postgres catalog |

### E1 — cross-store delete-conflict gap (#1215)

Two concurrent transactions delete the *same row* of the same data file. One delete is
≤ `DATA_INLINING_ROW_LIMIT` so its tombstone is written as an inlined file delete; the other is
> the limit so its tombstone is a parquet delete file. DuckLake's commit-conflict check compares
parquet-vs-parquet and inlined-vs-inlined but not the cross-store (inlined+parquet) pair, so both
commit and the row's position lands in *both* delete stores — after which the read path makes the
deleted rows reappear. The repro is the issue's own minimal case (100-row table, a 1-row inlined
delete racing a 30-row parquet delete on the same position), run in both commit orders. It needs
no Postgres: a DuckDB-native catalog lets both transactions reach commit (a SQLite catalog blocks
the second writer with `database is locked` first). This is a correctness result, so there is no
timing — the evidence is the surviving-row count.

### E2 — >1600-column CREATE TABLE wall on Postgres (#1184)

`CREATE TABLE` in DuckLake unconditionally emits a backing
`CREATE TABLE ducklake_inlined_data_<id>_0 (<every user column> BYTEA, ...)` against the Postgres
catalog, in the same transaction as the metadata writes. That backing CREATE hits Postgres's hard
per-table 1600-column limit, so a wide table cannot be created — and disabling row inlining does
not help, because the backing-table *schema* is still created with all user columns. The arm
probes 1500 / 1600 / 1700 columns plus a 1700-column-with-inlining-disabled case, against a fresh
Postgres catalog database per probe (each catalog pins its own `DATA_PATH`).

### E3 — connection-pool timeout on Postgres (#1031)

`DuckLakeTransaction::GetConnection()` opens a fresh connection per transaction; with
`pg_pool_enable_thread_local_cache=true` and `pg_pool_max_connections` defaulted, each DuckDB
worker thread caches one Postgres connection in thread-local storage and never releases it, so
after enough catalog operations every pooled connection is "in use" and the next catalog read
hangs ~30s then fails. This issue is labeled **PR submitted** upstream, and the reporter notes it
does *not* reproduce on the older DuckDB 1.4.4 + DuckLake v0.3 — so it is a genuine
version-currency question. This arm runs the issue's minimal repro (create 60 tables, then an
`information_schema.tables` query) under **both** the reported-reproducing DuckDB 1.5.2 and the
current 1.5.3, against a fresh `postgres:17` catalog each time.

## Result (Tier B · single host · 2026-06-14)

Run on DuckDB **1.5.3** + DuckLake extension **e6a3bd0a** (the issues were filed against DuckDB
1.5.2 + DuckLake **415a9ebd**). Postgres arms on the `postgres:17` image. Single host (Beelink
5800H, WSL2 48 GB / 14 threads).

| arm | issue | verdict on current stack | evidence |
|---|---|---|---|
| E1 | #1215 | **PERSISTS** | both commit orders: 29 rows survive a delete that should leave 0; second commit raises no conflict |
| E2 | #1184 | **PERSISTS** | 1500 cols creates fine; 1600/1700 fail with `ERROR: tables can have at most 1600 columns`; **still fails with inlining disabled** |
| E3 | #1031 | **FIXED between 1.5.2 and 1.5.3** | 1.5.2 (DuckLake 415a9ebd): `information_schema` probe hangs 60 s then `all 14 connections in use`. 1.5.3 (e6a3bd0a): same workload returns in 0.036 s, no timeout |

The E3 result is the headline of the version-currency angle: the exact version the bug was filed
against (1.5.2 auto-resolves the DuckLake extension to **415a9ebd**, the same commit named in the
issue) reproduces it precisely — including the pool exhausting at **14** connections, one per
worker thread on this 14-thread host, which is the thread-local mechanism the issue's root-cause
analysis described — and the next point release no longer does. The other two are open
correctness/operability gaps that a security lakehouse standing up DuckLake on a Postgres catalog
would hit today.

## Reproduce

```bash
# E1 (no Postgres needed)
.venv/bin/python3 ducklake-catalog-failuremodes/e1_crossstore_delete.py

# E2 (#1184): brings up one postgres:17 container, runs the wide-table probes
bash ducklake-catalog-failuremodes/run_postgres_arms.sh

# E3 (#1031): the 1.5.2-vs-1.5.3 controlled comparison (builds a throwaway 1.5.2 venv)
bash ducklake-catalog-failuremodes/run_e3_version_compare.sh

# consolidate the per-arm JSONs into results/summary.json
.venv/bin/python3 ducklake-catalog-failuremodes/consolidate.py
```

Results: `results/e1.json`, `results/e2.json`, `results/e3_v1.5.2.json`, `results/e3_v1.5.3.json`,
`results/summary.json`. Findings narrative in `FINDINGS-2026-06-14.md`.

## Scope, honestly

Single host, the issues' own minimal repros, pinned versions recorded per arm. What travels is the
boolean (does the bug fire on this version) and, for E3, the controlled 1.5.2→1.5.3 delta. These
are catalog-layer findings — they say nothing about DuckLake's read/scan performance, only about
correctness and operability of the metadata catalog under the conditions each issue describes. The
105× streaming claim is deliberately not reproduced here; it is an unequal-workload vendor number
(see the Iceberg-V4-vs-DuckLake reconciliation), and this bench targets the failure modes instead.

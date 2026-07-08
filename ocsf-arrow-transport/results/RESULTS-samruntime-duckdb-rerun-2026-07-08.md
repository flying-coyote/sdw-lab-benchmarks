---
type: benchmark-result
title: "RESULTS — A2 same-runtime transport isolation on DuckDB, bare-window re-run"
created: 2026-07-08
tags: [arrow, adbc, transport, duckdb, pre-registration, final]
status: FINAL — adversarially verified 2026-07-08; all pre-registered gates PASS (any-arm CV gate max 2.5% vs the ≤5% line; 1M gap 7.8× inside the [2×, 15×] survives-band); SUPERSEDES run 1's PROVISIONAL-DISCARDED result (transport_same_runtime_duckdb.json, kept as the discarded record). RESULTS.md same-runtime section + prereg erratum-lift note still owed.
---

# RESULTS — A2 same-runtime transport isolation, DuckDB, bare-window re-run (2026-07-08)

Tier B (lab measurement, single host: Beelink 5800H, WSL2 48GB, 14 vCPU). Scope is same-runtime
transport on DuckDB 1.5.3 only — one Python 3 process family, one in-process engine; nothing here
generalizes to cross-runtime or client-server transports.

Re-run of the leg pre-registered in `PRE-REG-samruntime-duckdb-2026-07-04.md`. Run 1 (2026-07-04)
was scored under amended conditions (moar-* containers up-idle, not stopped — permission-held that
session) and was **discarded** by the pre-committed CV gate: the reference arm (`native_arrow`)
breached the any-arm ≤5% line at 1M rows (5.1%). This re-run executes in the genuinely bare window
the erratum called for: the owner explicitly authorized stopping `moar-lab-1`, `moar-minio-1`, and
`moar-iceberg-rest-1` for this run only, and they were stopped, confirmed via an empty `docker ps`,
and restarted immediately after the timed trials completed.

**Verification record.** An independent adversarial verify pass (2026-07-08) recomputed every
derived figure from the raw JSON medians (both gaps, both ADBC-vs-native ratios, all six spread
ratios — all reproduce exactly), bounds-checked each reported CV against its min/max range for
feasibility, confirmed the empty-`docker ps` bare window brackets the timed trials in the
scratchpad logs, and diffed the re-run harness against the canonical script (verbatim except the
pre-registered `to_arrow_table()` swap). All pre-registered gates PASS; this result supersedes
run 1's PROVISIONAL-DISCARDED status. The RESULTS.md same-runtime section and the prereg
erratum-lift note remain owed to the main session; nothing in `results/RESULTS.md` has been
touched by this pass.

## Container restore status

All three containers were restarted and verified healthy before this note was written:
`moar-lab-1` Up, `moar-minio-1` Up (healthy), `moar-iceberg-rest-1` Up (healthy). See
`post-restart-docker-ps.txt` in the scratchpad bundle (path below).

## One pre-registered deviation from run 1

The prereg's erratum text (appended before this re-run) states: "the native arm used the
deprecated `fetch_arrow_table()` wrapper, which the re-run should switch to `to_arrow_table()`."
That single swap is applied in `native_arrow()` in the re-run script; every other line — arms,
7 trials / 2 warmups, corpus (`_work/rs_100000.parquet`, `_work/rs_1000000.parquet`), query
(`SELECT * FROM read_parquet(...)`) — is unchanged from `transport_same_runtime_duckdb.py`. No
other methodology change was made. The re-run script itself lives in the scratchpad bundle (not
committed to the repo) since it only differs from the canonical harness by that one documented
line plus hardcoded absolute paths (it runs from outside the repo's script directory).

## Per-arm results

### rs_100000 (100k rows)

| arm | median ms | min ms | max ms | CV % | spread ratio |
|---|---|---|---|---|---|
| adbc_arrow | 43.712 | 43.241 | 45.296 | 1.5 | 1.05 |
| dbapi_rows | 159.704 | 156.953 | 161.928 | 0.9 | 1.03 |
| native_arrow | 52.169 | 51.265 | 53.242 | 1.3 | 1.04 |

- Gap (dbapi_rows / adbc_arrow): **3.7×**
- ADBC vs native_arrow: **0.84×** (adbc_arrow faster than native_arrow at this size; no ADBC tax)

### rs_1000000 (1M rows)

| arm | median ms | min ms | max ms | CV % | spread ratio |
|---|---|---|---|---|---|
| adbc_arrow | 176.643 | 169.317 | 181.311 | 2.4 | 1.07 |
| dbapi_rows | 1373.778 | 1366.358 | 1386.192 | 0.4 | 1.01 |
| native_arrow | 199.259 | 197.202 | 212.963 | 2.5 | 1.08 |

- Gap (dbapi_rows / adbc_arrow): **7.8×**
- ADBC vs native_arrow: **0.89×** (adbc_arrow faster than native_arrow; no ADBC tax)

## CV gate — PASS (adjudicated 2026-07-08)

The prereg amendment pre-committed: "if any arm's CV exceeds 5%, the run is discarded"; its
erratum restates the re-run condition as "require every arm CV < 5%". Every one of the six
arm×size CVs is comfortably under that line: 1.5%, 0.9%, 1.3% (100k) and 2.4%, 0.4%, 2.5% (1M) —
worst arm 2.5%, passing under both the ≤5% and the strict <5% phrasing. The reference arm that
breached the gate in run 1 (native_arrow, 4.9%/5.1%) came in at 1.3%/2.5% here. The bare window
(no other process, docker ps confirmed empty for the duration) appears to be what run 1's amended
up-idle-containers condition was missing.

## Gap multiples vs. the pre-committed survives-band — SURVIVES (adjudicated 2026-07-08)

Pre-reg band: "Same-runtime gap (dbapi_rows / adbc_arrow) in [2x, 15x] at 1M rows → the
cross-runtime table's single-digit framing SURVIVES runtime isolation; report the measured
factor."

- 100k: **3.7×** (identical to run 1's provisional 3.7×)
- 1M: **7.8×** (run 1's provisional/discarded reading was 8.3×; both are inside [2×, 15×])

The 1M gap of 7.8× sits inside the pre-committed survives-band, consistent with run 1's
provisional direction, so the cross-runtime table's single-digit framing survives runtime
isolation and 7.8× is the measured factor to report. The prereg's gap-above-spread rule is also
met: both gaps (3.7×, 7.8×) exceed the worst per-arm run-to-run spread ratio (1.08×) by a wide
margin.

## Environment during trials

Nothing else was running. Pre-stop `docker ps` showed only the three moar-* containers Up (plus a
long tail of already-Exited containers from other projects — zfr-*, ejs-*, ocsf-attack-coverage
moar-*, etc. — none active). After `docker stop`, `docker ps` returned zero rows for the full
duration of the timed trials; load average dropped from 1.50 (1-min, pre-stop) to 0.68 (post-stop,
after a 30s settle) on a 14-vCPU host. Full docker ps / free -h / uptime captures are in the
scratchpad bundle.

## Raw files (all in the scratchpad bundle unless noted)

Scratchpad dir: `/tmp/claude-1000/-home-jerem-project1/3d08ac08-8431-4db7-afde-e1078486fc9a/scratchpad/bench/a2-duckdb/`

- `pre-stop-docker-ps.txt` — docker ps + docker ps -a before stopping the moar-* containers
- `pre-stop-system.txt` — free -h + uptime before stopping
- `post-stop-docker-ps-immediate.txt` — docker ps immediately after `docker stop` (empty)
- `post-stop-docker-ps.txt` — docker ps after the 30s settle (empty)
- `post-stop-system.txt` — free -h + uptime after the 30s settle
- `transport_same_runtime_duckdb_rerun.py` — the re-run harness (one documented deviation, see above)
- `rerun-stdout.log` — full teed stdout of the timed run
- `transport_same_runtime_duckdb-rerun-2026-07-08.json` — raw results JSON (same file also copied
  into the repo at `results/transport_same_runtime_duckdb-rerun-2026-07-08.json`, alongside this note)
- `post-restart-docker-ps.txt` — final docker ps after restart, both health-checked containers (healthy)

The original run-1 artifact, `results/transport_same_runtime_duckdb.json`
(PROVISIONAL-DISCARDED), is untouched by this re-run.

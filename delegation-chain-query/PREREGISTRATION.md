---
type: benchmark-prereg
title: "R7: cost of walking an agent delegation chain at query time (pre-registration)"
created: 2026-11-09
review_ref: project1/02-projects/securitydataworks/SITE-REVIEW-2026-11-09.md section 5, row R7 (feeds new-article #3, "Delegation is the new logon event")
status: frozen by agent before run; not owner-reviewed
---

# R7 pre-registration: delegation-chain walk cost

## Question

When agent activity is logged as one record per delegation hop (human principal delegates to agent A,
A to agent B, and so on, each hop carrying its own authority), detecting *scope escalation* (a hop that
grants authority its delegator did not hold) looks like it needs a recursive walk of the chain at query
time. How much does that walk cost, by chain depth (2 to 12) and table volume (1e5 to 1e7 rows), in
DuckDB and in chDB (embedded ClickHouse), and how does it compare with the two ways of not walking: a
single child-to-parent self-join, and a filter on an authority column materialized at write time?

## Records (what "delegation-shaped" means here)

Modeled on the OCSF 1.9.0 IAM `delegation` object (per-hop authorization context, added 2026-08-03 per
`project1/01-knowledge-base/evidence/ocsf-v1-9-release-20260803.md`). The attribute names are this
bench's own and were not checked against the 1.9.0 schema JSON, which was not on disk. Columns:
`event_uid`, `chain_uid`, `parent_uid` (NULL at the human root), `hop`, `actor_uid` (delegator),
`agent_uid` (delegatee), `time` (ms epoch), `scope_mask` (16-bit authority bitmask, INT32),
`parent_eff_scope` (effective authority of the delegator, written by the generator to stand in for
write-time materialization; NULL at root), `root_scope`.

Generator `gen.py` (seed 20261109, numpy `default_rng([seed, rows, depth])`): linear chains, so depth is
exact and a cell of N rows at depth d holds round(N/d) chains; fixed-N cells therefore hold total rows
constant while chain count falls with depth. Root authority: bits 0 to 14 each held with p = 0.6, bit 15
never. Each normal hop keeps each bit of its parent's grant with p = 0.85, so a normal chain never
escalates. In 1% of chains exactly one hop (uniform over hops 1..d-1) escalates, in one of two classes:
`new` (grants bit 15, which no root holds) or `reacquire` (re-grants a bit the root held but an earlier
hop dropped; needs hop >= 2, so at depth 2 every plant is `new`; chosen with p = 0.5 when possible).
Identifiers are random non-sequential int64; rows are sorted by `time`, which interleaves chains the way
log arrival does. Integer ids (not string UUIDs) are a fixed choice, declared as a limit.

## Arms (exact predicates)

Escalation at a hop = `scope_mask` is not a subset of the authority it was delegated from, tested as
`(scope_mask | X) <> X` (`bitOr(...) != X` in ClickHouse). Each arm returns the DISTINCT set of flagged
`chain_uid`.
- **A_recursive**: `WITH RECURSIVE` from roots (`parent_uid IS NULL`), `UNION ALL`, joining
  `delegation.parent_uid = walk.event_uid`, carrying `eff = eff & scope_mask`; X = parent's effective
  authority.
- **B_selfjoin**: one non-recursive join child to parent on `parent_uid = event_uid`; X = parent's
  `scope_mask`. At chain level this is equivalent to A (the first escalating hop is flagged by both;
  every hop before it is a subset, so parent grant equals parent effective authority).
- **C_materialized**: filter only; X = `parent_eff_scope`.
- **D_rootonly**: filter only; X = `root_scope`. Cheapest flattening, and blind to `reacquire` by
  construction; included to measure what that shortcut misses.

Exact SQL for both engines is in `run_cell.py` (sha256 below).

## Hypotheses, and what would prove each wrong

- **H1 (recursive cost grows with depth).** At fixed N >= 1e6, A_recursive median latency at depth 12 is
  at least 2x its depth-2 median, in each engine. Wrong if the ratio is below 2 in an engine (then the
  walk's cost is dominated by total rows, not iterations).
- **H2 (self-join is depth-flat).** At fixed N, B_selfjoin median varies by no more than 25% across
  depths 2 to 12 (max/min <= 1.25), per engine. Wrong if max/min > 1.25 beyond the cells' CV.
- **H3 (walking costs a multiple).** At N = 1e7, depth 12, A_recursive / B_selfjoin median ratio > 3 in
  each engine. Wrong if <= 3 (then query-time walking is not the cost problem the article assumes).
- **H4 (engines, exploratory, two-sided).** No directional prediction for DuckDB vs chDB. A difference is
  reported as real only where it exceeds both cells' CV.
- **H5 (correctness).** A, B and C return exactly the planted chain set (recall 1.0, zero false
  positives) in every completed cell in both engines; D misses every `reacquire` plant and nothing else.
  Wrong if any A/B/C cell differs from ground truth, or D catches a `reacquire` plant (generator bug).

## Instrument and environment

- Host: the Beelink (AMD Ryzen 7 5800H), WSL2 kernel 6.6.87.2-microsoft-standard-WSL2, 14 vCPU and
  47 GB visible to the guest. Windows power plan is not verifiable from the guest; recorded as unknown.
- Engines: DuckDB 1.5.3 (lab pin); chDB 4.4.0 on ClickHouse 26.9.2.1. The lab-wide `requirements.txt`
  pins chdb 4.1.8; this bench uses 4.4.0 (current at install, recursive CTE confirmed working) and
  records the served `version()` string. pyarrow 23.0.1, numpy 2.5.4, Python 3.12.3. Pinned in
  `requirements.txt`; venv at `delegation-chain-query/.venv`.
- Tables: each cell's one Parquet artifact (zstd, 1M-row groups) is loaded into both engines in one
  process: DuckDB in-memory table (default config), chDB `ENGINE = Memory` (no ORDER BY, no index;
  MergeTree ordering would be a tuning knob and is out of scope). Default thread counts (recorded).
  Memory caps: DuckDB `memory_limit = 16GB`, chDB `max_memory_usage = 16 GiB`.
- Timing: `time.perf_counter_ns` (monotonic) around query execution plus fetch of the result. The WSL
  guest clock was found `0.277 s slow of NTP` under chrony shortly before the run (target is milliseconds);
  monotonic timers make that offset irrelevant to latencies, and wall-clock stamps in logs carry it.
  `chronyc tracking` is re-recorded verbatim immediately before the run.
- Per cell: one untimed warmup per engine-arm that fetches the full flagged set and checks it against
  `*.truth.json`; then 5 timed rounds of `SELECT count(*), sum(chain_uid) FROM (<arm>)`, round-robin
  over arm x engine (duckdb-A, chdb-A, duckdb-B, ...), each checked against the warmup checksum. An
  engine-arm whose warmup exceeded 60 s gets 3 timed trials instead of 5. Hot/warm only (in memory,
  unprivileged): no cold numbers are claimed.
- Isolation is NOT met: other workflow agents share the host (1-minute load average 6.24 at venv
  creation). `os.getloadavg()` is recorded before every timed query. Within-cell ratios are the
  defensible output; absolute latencies are reported but flagged as taken under shared load.
- Artifact pinned per cell with `lib.common.pin_artifact()` (logical fingerprint, manifest, byte hash);
  the Parquet is then deleted (seed + generator reproduce it).

## Metrics

Per (engine, arm, N, depth): median, min, max, CV (stdev/mean) of timed trials; warmup ms; load ms;
load-average range; status (OK / DNF / SKIPPED); flagged, true positives, false positives, recall,
missed `reacquire`, exact match. Derived: A/B, A/C ratios per cell; A depth-12/depth-2 ratio per N;
B max/min across depth per N.

## Grid, stop rule, cost

- Grid: N in {1e5, 1e6, 1e7} x depth in {2, 4, 6, 8, 10, 12} = 18 cells x 2 engines x 4 arms.
- Per-query timeout 300 s (DuckDB `interrupt()` timer; chDB `max_execution_time`); any exception
  (timeout, memory cap, error) marks the engine-arm DNF in that cell. Per-cell subprocess timeout 3600 s.
- Skip rule: a DNF engine-arm at (N, d) reports every cell with N' >= N and d' >= d for that engine-arm
  as SKIPPED (run but not trusted), so DNFs are published as rows, not dropped.
- Wall-time budget 3 h. If exceeded, the remaining 1e7 cells are cut to depths {2, 6, 12} and labelled.
- Cost: local CPU only; no paid API calls; $0.

## Pre-run instrument development (declared)

`gen.py` and `run_cell.py` were smoke-tested on two 3,000-row fixtures (depth 2 and 6) before freezing,
to check the SQL ran in both engines and matched ground truth; no latency from the smoke test was
recorded or used, and the fixtures were deleted.

## Harness hashes at freeze

```
0880eac5025e0deab7e70f32c1542a6f3f418ce812ee0fe9281f25e33526c6fe  gen.py
829b7dd48f4e6f9ba0c9e58e0d55484db4ad8495f9f853de1d6f7802416ae870  run_cell.py
94d30b84af03fc1cacbe629bbf5089019a04c36aba3b99c978da8d949c537c62  run_all.py
4099918be7885aa33fbcc9e7cff83edc64809693f9d29e9cb4af816a4bc7c42e  requirements.txt
```

Any later change is a dated amendment section below, never an in-place edit.

## Amendments

(none at freeze)

- **2026-11-09, amendment 1 (launch fix, no data collected).** The first launch of `run_all.py` failed at
  import before generating or timing anything: a `lib` package on the session's `PYTHONPATH`
  (`/home/jerem/project1/automation/lib`) shadowed the lab's `lib/common.py`. The import now loads
  `lib/common.py` by file path; no other line changed. New `run_all.py` sha256:
  `a2d0b59eab287d86d784d4c88db2701e0e6c8dff9b8b3cd32fb147c93fc4feba`. The frozen hash in
  `results/freeze.txt` is of the pre-amendment file; the post-amendment hash is recorded there too.
- **2026-11-09, amendment 2 (replication pass, added after run 1, before run 2).** Run 1 finished the
  whole grid in about 5 minutes with no DNF, but under a 1-minute load average of 10 to 17 from other
  workflow agents, and within-cell CVs at 1e5 and 1e6 rows ran 20 to 60% (filter arms higher). Because
  the cost is negligible, the unchanged harness is run a second time over the same grid (run 2;
  `results/raw_run1/` holds run 1, `results/raw/` run 2). The hypotheses are judged on run 1 as
  pre-registered; run 2 is reported beside it as a run-to-run replication, and a verdict that flips
  between runs is reported as unstable rather than as either outcome. No hypothesis, threshold or
  harness line changed.

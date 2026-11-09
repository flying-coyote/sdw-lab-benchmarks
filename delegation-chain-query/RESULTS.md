# R7 results: cost of walking an agent delegation chain at query time

Pre-registration `PREREGISTRATION.md`, sha256 `18c6124ccb4703f27abaf447ac2b9a7ffe15523731cfe3a7a6d6e7e398cd166a`,
frozen 2026-11-09T23:00:13Z, **frozen by agent before run; not owner-reviewed**. Two dated amendments
followed: a launch fix before any data (sha256 after amendment 1 `fb4b9890…e056`), and a replication pass added
after run 1 and before run 2 (sha256 after amendment 2 `15bebb41…0dbe`). The hashes and timestamps are in
`results/freeze.txt`.

**Rig stamp.** The Beelink (AMD Ryzen 7 5800H), WSL2 kernel 6.6.87.2-microsoft-standard-WSL2, with 14 vCPU and
47 GB visible to the guest. The Windows power plan can't be read from the guest, so it's recorded as unknown. Run 1
started 2026-11-09T23:01Z and run 2 at 23:13Z. Engines: DuckDB 1.5.3, and chDB 4.4.0 serving ClickHouse 26.9.2.1
(the lab-wide pin is chdb 4.1.8). Both used their default 14 threads. Clock: chrony was running, and `chronyc
tracking` read `0.2997 s slow of NTP` before run 1. That is above the methodology's milliseconds target. Every
duration here comes from `time.perf_counter_ns` (monotonic), so the offset doesn't affect any latency; only the
wall-clock stamps in logs carry it. **Isolation was not met.** Other workflow agents shared the host, and the
1-minute load average sat between 7.5 and 26 during the timed queries. Load was recorded before every query and is
shown per cell in `results/tables_run*.md`. Every number is hot/warm only, because the tables are in memory and
the harness ran unprivileged.

**Tier:** this is a first-party lab measurement on a single host under shared load. It is synthetic and
deterministic, with no LLM arm.

Records are *delegation-shaped*. They are modeled on the OCSF 1.9.0 IAM `delegation` object, but the attribute
names are mine and were not checked against the 1.9.0 schema JSON.

## Headline

Independent verification on 2026-11-09 (`VERIFICATION.md`): VERIFIED-WITH-FIXES. Data, correctness and the headline
numbers reproduced; the fixes are wording on H1, H3's chDB margin, D's recall and a few range statements.

- **Correctness held completely, with one pre-registered exception.** The recursive walk (A), the parent
  self-join (B) and the write-time materialized filter (C) all returned exactly the planted escalation set. That
  held in 18 of 18 cells, in both engines and both runs: recall 1.000 and zero false positives. The root-only
  shortcut (D) missed every `reacquire` plant and nothing else. That is 31,758 planted chains missed per run
  across the grid. Per-cell recall was 0.55 to 0.67 in the 1e6 and 1e7 cells at depth 4 and deeper, and 0.398 in the smallest
  cell (1e5 rows, depth 12, 83 plants). That recall level is set by the generator's plant mix (about half of plants at
  hop 2 or later are `reacquire` by design), so it shows the blind spot exists, not how common it is in real logs. A hop that re-grants authority an
  intermediate agent had already dropped stays inside the human root's authority, so a check against only the
  root's authority can't see it.
- **The walk works at this scale.** At 1e7 rows and depth 12 (833,333 chains), the recursive CTE ran in a median
  1.56 to 1.70 s in DuckDB and 0.87 to 0.99 s in chDB across the two runs. The within-run trial CV was 8% or
  less. Between the two runs the medians moved further: A by −8% in DuckDB (1702 to 1560 ms) and −13% in chDB
  (995 to 865), and B by −15% (332 to 281) and −25% (406 to 303). The within-cell A/B ratio moved much less (5.13
  to 5.55 and 2.45 to 2.86), and that stability is the evidence for treating within-cell ratios as the defensible
  output.
  Nothing hit the 300 s timeout or the 16 GiB memory cap, so the grid has no DNF cells.
- **Not walking is much cheaper.** In the same cell, the one-join check (B) ran in 0.28 to 0.41 s. The
  materialized-column filter (C) ran in 20 to 27 ms, which is 34 to 80 times faster than the walk. C is answer-
  identical to A, so the walk can move to write time without losing anything, provided the ingest path can
  look up the delegator's effective authority. That write-time cost was **not** measured here.
- **The walk's premium grows with depth.** This is the defensible depth result, and it was not pre-registered.
  At 1e7 rows the within-cell A/B ratio rose from depth 2 to depth 12 in both runs: from 2.21 to 5.13 and from
  1.97 to 5.55 in DuckDB, and from 1.37 to 2.45 and from 1.30 to 2.86 in chDB. A within-cell ratio is the number
  that survives the shared load, because both arms in a cell ran interleaved under the same load.
- **Engines.** At 1e7 rows chDB ran the recursive walk 1.3 to 1.8 times faster than DuckDB at every depth, in
  both runs, with every cell's CV under 11%. On B, C and D there was no consistent direction between the engines across depths and runs.

## Hypotheses (judged on run 1 as pre-registered; run 2 beside it)

| Hypothesis | Threshold | Run 1 | Run 2 | Verdict |
|---|---|---|---|---|
| H1: walk cost grows with depth, N ≥ 1e6 | A d12/d2 ≥ 2 per engine | DuckDB 1.95 (1e6), 2.59 (1e7); chDB 2.54 (1e6), 2.59 (1e7) | DuckDB 1.50, 1.93; chDB 2.06, 1.61 | **Falsified for DuckDB as pre-registered** (run 1, 1e6: 1.95 < 2; below 2 at both N in run 2). **Unstable for chDB** (passed run 1, 1.61 at 1e7 in run 2). A verification re-run at lower load gave 2.57 (DuckDB) and 2.39 (chDB) at 1e7, so the outcome tracks host load. Cross-cell comparisons are confounded by load drift; see below. |
| H2: self-join is depth-flat | B max/min ≤ 1.25 per N | 1.31 to 2.84 | 1.42 to 3.62 | **Falsified as stated.** At 1e7 there was no monotonic depth trend: DuckDB run 2 *fell* from 410 to 281 ms as load dropped. Under this load the bench can't confirm flatness either. |
| H3: walking costs a multiple | A/B > 3 at 1e7, d12 | DuckDB 5.13, chDB 2.45 | DuckDB 5.55, chDB 2.86 | **Supported for DuckDB, falsified for chDB**, stable across both runs. The chDB margin is thin: across the two runs and three verification re-runs chDB A/B ran 2.45 to 2.99, just under the threshold of 3. |
| H4: engines (exploratory) | difference > CV | chDB A faster at 1e7 by 1.3 to 1.8× | same | chDB is faster on the recursive arm at 1e7. There is no consistent difference on the other arms. |
| H5: correctness | A/B/C exact; D misses only `reacquire` | 18/18 exact; D missed exactly the reacquire class in every cell | same (re-checked on run 2: 18 of 18 cells) | **Supported.** |

**Why the depth hypotheses are weak.** In run 2 the load fell from about 18 to about 8 while the 1e7 cells went
from depth 2 to depth 12. So any latency trend from one cell to the next mixes depth with load. H1 and H2 compare
absolute medians across cells, and this run can't separate the two effects. A/B within a cell is the comparison
that holds up. A quiet-host rerun is the fix (see Limits).

## Key cells: 1e7 rows, median ms (CV) over 5 timed trials

| depth | chains | DuckDB A | DuckDB B | DuckDB C | chDB A | chDB B | chDB C | load (r1 / r2) |
|---|---|---|---|---|---|---|---|---|
| 2 | 5,000,000 | 656 (7%) / 809 (7%) | 297 / 410 | 19 / 31 | 384 (5%) / 538 (7%) | 279 / 412 | 27 / 43 | 13 / 17 to 19 |
| 6 | 1,666,667 | 932 (7%) / 886 (3%) | 284 / 257 | 28 / 16 | 657 (4%) / 588 (8%) | 333 / 314 | 25 / 24 | 10 to 12 / 13 |
| 12 | 833,333 | 1702 (8%) / 1560 (3%) | 332 / 281 | 24 / 20 | 995 (8%) / 865 (4%) | 406 / 303 | 27 / 25 | 11 to 14 / 8 |

The full per-cell tables for both runs are in `results/tables_run1.md` and `results/tables_run2.md`. They cover
every arm and every N, with CV, A/B and A/C ratios, and the load range.

Below 1e7 the runs are mostly noise. At 1e5 and 1e6 the medians are 3 to 870 ms, and CVs on A and B ran up to 58% (often 20% or more, a few cells under 10%)
under load averages of 12 to 26. The filter arms (C, D) sat at the noise floor of about 3 to 40 ms, with CVs up to
164% in chDB. Read those cells as "fast", and don't use them for engine or depth claims. One cell, 1e6 at depth 8
in run 1, spiked on every arm in both engines at the same moment, which points to host load and not the query. It
did not repeat in run 2.

## Held constant and varied

- **Held constant:** one Parquet artifact per cell, loaded into both engines in the same process (DuckDB
  in-memory table, chDB `ENGINE = Memory` with no ORDER BY); default threads; the same predicate in both
  dialects; `UNION ALL` in both recursive CTEs; int64 ids. Generator output was logically identical across runs:
  all 18 `pin_artifact` logical fingerprints matched, and all 18 byte hashes matched too. The pins are in
  `results/raw*/rows*_d*.pin.json`. Load into the engines took about 0.4 to 0.8 s at 1e7 for both.
- **Varied:** engine, arm, N in {1e5, 1e6, 1e7}, depth in {2, 4, 6, 8, 10, 12}. Load drifted uncontrolled.

## Limits

- **Shared host.** Absolute latencies were taken under 1-minute load averages of 7.5 to 26 from other agents.
  Within-cell ratios are the defensible output, and depth trends across cells are confounded. A quiet-host rerun
  should come first, and costs about 10 minutes.
- **Linear chains only.** Real delegation forms trees (fan-out) and sometimes cycles. A recursive CTE over a
  graph with cycles needs cycle guards, and this bench didn't test them.
- **Synthetic, integer-keyed records.** OCSF uids are strings, and string join keys would raise the cost of A and
  B. The field names are not verified against OCSF 1.9.0.
- **Part of arm C's cost is unmeasured.** The generator wrote `parent_eff_scope` for free. A real ingest path
  pays one lookup per hop against recent chain state, and that cost and its freshness aren't measured here.
- **Defaults only.** There is no MergeTree ORDER BY, no index and no ClickHouse server. chDB 4.4.0 is not the
  lab's 4.1.8 pin. The run is hot only, with no cold numbers.
- **One escalation per planted chain, 1% plant rate.** Detection volume doesn't stress the DISTINCT step.

## Commands

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run_all.py                       # run 1 (results then moved to results/raw_run1/)
.venv/bin/python run_all.py                       # run 2 -> results/raw/
.venv/bin/python summarize.py raw_run1 > results/tables_run1.md
.venv/bin/python summarize.py raw      > results/tables_run2.md
```

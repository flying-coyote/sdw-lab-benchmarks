---
type: benchmark-results
title: "R2 post-hoc: timing the AOS example-2 shape beside R2's layouts"
created: 2026-11-16
area: R2-toolcall-three-schemas
status: post-hoc, not pre-registered, not independently verified
---

# R2 post-hoc: timing the AOS example-2 shape

**Post-hoc rerun, not pre-registered.** Added on 2026-11-16 after an external review of the draft essay that cites R2. The review found that R2's query-time layout L3 follows AOS example 1, while R2's loss-table primary column and its validator run use AOS example 2 (deviation 4 in `RESULTS.md` says so, but the essay did not). This run adds an example-2-shaped layout, L3b, so both AOS examples can be priced on the same corpus. It is a single-agent run, and no second agent has re-run it yet.

## What ran

- `posthoc_ex2_timing.py gen 1000000` regenerated R2's 1M corpus from `gen_corpus.generate` (same seed, sub-seed 9202) and wrote R2's three layouts (`L1_SQL`, `L2_SQL`, `L3_SQL`, unchanged) plus L3b. The codec and row groups are the same as R2's: zstd, `ROW_GROUP_SIZE 122880`.
- `posthoc_ex2_timing.py time 1000000 {0,1,2,3}` ran R2's five hunt queries (`run_queries.Q`, unchanged) on all four layouts, plus the L3b version of each hunt.
  - Each process ran 2 warmups and 7 timed trials (`lib/common.time_trials`).
  - Four processes rotated the layout order, so each layout ran first once, giving 28 samples per cell.
- `posthoc_ex2_pool.py` pooled the samples into `results/timing_ex2posthoc_summary.json`.
  - Raw passes: `results/timing_ex2posthoc_n1000000_pass{0..3}.json`.
  - Console log: `results/ex2posthoc_run_log.txt`.
  - Corpus pins: `results/corpus_meta_ex2posthoc_n1000000.json`.

**Versions.** These are the resolved versions recorded in every pass file: DuckDB 1.5.3, pyarrow 23.0.1 and Python 3.12.3, the same as R2. They ran from a fresh venv, because R2's `.venv` is no longer on disk. The host was the Beelink (Ryzen 7 5800H, WSL2), with DuckDB's default thread count.

**Corpus identity with R2.** This was checked two ways:

- The regenerated layouts match R2's 1M sizes: L1 27,439,196 bytes, L2 58,221,187 and L3 30,860,739, which round to the 27.4, 58.2 and 30.9 MB in `RESULTS.md:124`.
- The answers reproduce R2's formal answers on every query: 75; 566; agent-0000 and agent-0001 at 18; 5571; 138987 (`VERIFICATION.md:39`).

**L3b shape.** L3b follows `extend_ocsf.md` example 2, as `map_schemas.AOS` does:

- Typed fields:
  - `actor.user` carries the agent, with type_id 99.
  - `actor.session.uid` carries the session.
  - `api.operation` carries the tool name.
  - `api.service.name` carries the server.
  - `status_id` carries the outcome.
- Inside `unmapped.aos`:
  - `step.operation.tool.inputs` carries the arguments.
  - `step.operation.tool.outputs` carries the result.
  - `context.agent` and `context.model` carry the agent and model context.

One simplification favours example 2. It keeps the arguments as an object under `inputs`, so Q2 runs the same regex on the same JSON path shape as the other layouts. `map_schemas.py` renders example-2 inputs as a list of `{name, value}`, which a real producer following the page would emit, and which would make Q2 harder to write.

**Isolation.** Not isolated. The 1-minute load average was 3.3 at the start and 8.3 at the end, rising with each pass, and some of that load was this run itself. As in R2, the within-pass ratios are the claim and the absolute milliseconds are not.

## Result (1M calls, pooled over 28 samples per cell)

| query | L1 typed ms (CV) | L2 OTel map ms | L3 AOS ex. 1 ms | L3b AOS ex. 2 ms | L3 / L1 | L3b / L1 (floor) | L2 / L1 | answers equal |
|---|---|---|---|---|---|---|---|---|
| Q1 tool by agent | 6.5 (46%) | 217.3 | 58.1 | 6.8 | 9.0x | 1.04x (0.23) | 33.5x | yes (75) |
| Q2 argument hunt | 34.8 (22%) | 241.5 | 188.3 | 105.1 | 5.4x | 3.02x (1.44) | 6.9x | yes (566) |
| Q3 tool breadth on errors | 7.6 (81%) | 229.8 | 123.6 | 8.2 | 16.3x | 1.09x (0.16) | 30.3x | yes |
| Q4 failure bursts | 5.3 (80%) | 211.8 | 99.2 | 20.2 | 18.6x | 3.78x (0.16) | 39.7x | yes (5571) |
| Q5 off-allowlist anti-join | 7.9 (68%) | 242.2 | 182.7 | 7.9 | 23.1x | 1.00x (0.19) | 30.6x | yes (138987) |

The floor is the fastest L3b trial over the slowest L1 trial; below 1 means the two are not separated at this noise level. On disk, L3b is 40.6 MB against L1's 27.4 MB, because it carries the arguments and results document beside its typed columns.

## Reading

- **Example 1 reproduces R2.** The L3/L1 ratios (5.4x to 23.1x) and L2/L1 ratios (6.9x to 39.7x) are inside or just past the three-pass ranges in `RESULTS.md` and `VERIFICATION.md`. L2 is again the slowest layout on every query.
- **Example 2 erases most of the gap.** It types every column that Q1, Q3, Q4 and Q5 filter or group on, and on Q1, Q3 and Q5 it runs level with typed OCSF (1.00x to 1.09x, floors below 1).
- **Q2 still pays.** It filters on the typed tool name, but it still parses the `unmapped` document for the `run_query` rows, so example 2 is 3.0x slower than L1 there, and the floor (1.44x) separates the two.
- **Q4 is unexplained.** Example 2 ran 3.8x slower than L1 on Q4 in all four passes (19 to 22 ms against 5 to 6 ms). Both group typed `actor.session.uid` under a typed `status_id` filter, and the floor (0.16) does not separate them. The cause has not been found, and Q4 should not be quoted for example 2 as anything stronger than "slower in this run".
- **What this changes.** R2's query-time result is a property of AOS example 1. It is not a property of the AOS record that R2 counts (22 of 33 unmapped) and validates. Under example 2, the agent-context facts in `unmapped` (model, arguments, results, step) cost query time only when a hunt reaches into them.

## Limits

- Post-hoc and single-agent, with no second-agent re-run yet.
- One host under load that rose during the run.
- One engine (DuckDB 1.5.3 over Parquet), warm cache, synthetic corpus.
- L3b's `inputs` simplification favours example 2 on Q2, as stated above.

## Validator, same day (post-hoc)

`validate_posthoc_2026_11_16.py` re-sent R2's records to schema.ocsf.io and wrote `results/validator_posthoc_2026-11-16.json`:

- The ten OCSF-main records pass the server's 1.10.0-dev schema with 0 errors and 0 warnings. R2 sent them to 1.9.0, where they failed on `ai_capability` and the version string.
- The ten AOS example-1 records pass 1.9.0 with 0 errors and 2 warnings, the same result as example 2, which was the only AOS example R2 validated.

So both AOS examples are validator-clean on the released schema. The 1.9.0 failure of the main-branch records is a version effect, and they pass once checked against the schema version they were built for.

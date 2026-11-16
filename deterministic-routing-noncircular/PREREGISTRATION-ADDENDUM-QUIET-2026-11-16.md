---
type: benchmark-preregistration
title: "deterministic-routing-noncircular: quiet-host replication addendum (2026-11-16)"
created: 2026-11-16
status: frozen by agent, not owner-reviewed
parent: PREREGISTRATION.md (sha256 1d07f6de...d9074c, frozen 2026-11-15T20:06:31Z), unchanged
---

# Replication addendum: quiet-host rerun (2026-11-16)

Written and frozen before any timed execution on 2026-11-16. The 2026-11-15 run shared the host with sibling
benches (1-minute load 3.3 to 23.7 during timed executions) and its LLM legs ran concurrently with each other and
with another session's Ollama work, so every latency there is indicative. The owner declared the host quiet at about
03:00Z 2026-11-16. This rerun repeats the same queries, oracle and scoring with nothing else timed on the host. The
parent pre-registration's hypotheses H1 to H9, thresholds, truth model, cliff definition and scorings apply unchanged;
this file adds only what "replicated" and "changed" mean and the run-hygiene rules. Every 2026-11-15 file stays
untouched; all new output goes to `results/quiet-2026-11-16/`, `logs/quiet-2026-11-16/` and `_work_quiet_2026-11-16/`.

## What I knew before freezing

The full 2026-11-15 results, verification and ledger row (I read them), so this is not blind. A smoke test of
`gemma4:e4b` on a non-corpus prompt (Ollama 0.20.6, `/api/chat`, top-level `"think": false`, `num_predict 16`)
returned reasoning text in the visible reply ("The user wants me to pick a color..."), the same failure as 11-15.

## Data identity (done before freezing; a precondition, not a timed cell)

Nessie runs IN_MEMORY, so its catalog was empty after restart; the Iceberg files survive in `drn-minio-data`.
Instead of re-appending the parquet with `load.py` (which would write new data files at new locations), I registered
each of the 13 tables in Nessie from the exact metadata file the 11-15 run recorded (`register_quiet.py`,
`_work_quiet_2026-11-16/register_report.json`). Result: every table's metadata location and table location equal
11-15's, and every row count equals both the 11-15 record and the pinned parquet. This is a declared departure from
the brief's "reload via load.py": it restores the identical snapshots rather than a reload.

**Gates that stop this bench** (any one, before the scored passes count as a replication):
1. Once ClickHouse is up: `count()` through `icebergS3` (the pinned metadata) and through native `bench.*` must equal
   the 11-15 row counts for all 13 tables (`load.py` documents a 54.0M-of-59.99M lineitem misread when the pin fails).
2. After the passes: per arm, the number of corpus queries that complete and match the oracle, and the number of
   anchors that match ground truth, must each be within 1 of 11-15's count for that arm, apart from the queries that
   failed on 11-15 by DNF (those may now complete or fail; that is a result, not a data mismatch). A larger gap means
   the data or the stack differs, and the bench is reported as not replicated.
The oracle is the 11-15 `results/oracle.json`, byte-copied (sha256 `72bc0b48...186a`); it is not recomputed.

## Protocol (unchanged except as listed)

Same rig and engines as 11-15 (StarRocks `allin1-ubuntu:4.1-latest` image already on disk, ClickHouse 26.5.1.882,
Trino 481, same compose file, same 24g limits), same order (ClickHouse-Iceberg, ClickHouse-native, StarRocks, Trino),
one engine at a time, 1 warmup + 5 timed trials, 300 s timeout, two strikes, `run_engines.py` unchanged and imported by
`run_engines_quiet.py`, which changes only the work/results paths and appends a Unix timestamp as a fourth element to
each execution's load list. `score.py` unchanged, run via `score_quiet.py` (paths only). Everything runs with
`python -B`. The ClickHouse containers are restarted (stopped, not removed, on 11-15) and StarRocks and Trino are
re-created from the same images by compose; StarRocks on 11-15 was a newly created container for the main pass. If the
StarRocks container is a restart rather than a fresh create, carried-over state is a rival explanation for any change
in its failure rate, and RESULTS says which it was.

**Load and clock hygiene.** A gate before each *cell*, where a cell is one arm pass, one LLM leg, or the StarRocks
attempt probe: record 1-minute load and `chronyc tracking` "System time" offset; wait while 1-minute load > 1.0, up to
300 s, then start regardless and record that the gate expired. Inside an engine pass, load comes from the engine's own
work (a 14-vCPU engine drives it well above 1); that is self-generated and is recorded per execution, not gated.
Nothing else timed runs on the host. Ollama models are unloaded (`keep_alive 0`) and `ollama ps` confirmed empty before
the engine passes, between LLM legs and at the end.

**Cron window.** Hub cron jobs fire 06:00 to 07:30Z, 08:00 to 08:30Z and 09:30Z. An engine pass is not started
if it cannot plausibly finish before 06:00Z; it waits until 07:30Z instead. If an engine pass is already running at
06:00Z it continues, and every execution stamped 06:00 to 07:30Z is tagged `cron-overlap` in RESULTS. LLM legs run
through the window, and calls stamped inside it are tagged `cron-overlap`; their verdicts rest on margins of an order
of magnitude, which cron jobs cannot plausibly close, and RESULTS reports the median with and without those calls.

## StarRocks failure count (fixed now)

An *attempt* is one execution of corpus `join_3to4_04` on StarRocks. Attempts counted: every execution in the main
pass (warmup + up to 5 trials, stopping at two strikes, so 2 to 6 attempts) plus exactly **5** probe executions
(`sr_probe_quiet.py`, each on a fresh client, no retries) run immediately after the main pass on the same running
engine, before any LLM leg. Output: `results/quiet-2026-11-16/sr_attempts_probe.json`. 11-15 tally for comparison:
3 failures in 5 attempts (2 main-pass strikes, 1 of 3 post-hoc executions). "StarRocks fails again" = one or more
failures among the quiet attempts.

## What counts as changed (vs 11-15)

Scored against the quiet run's own measured truth (primary), with the 11-15 numbers as comparison:
- **Winner flips.** Per decision (84 corpus queries x {hot, cold}), any change of the strict winner is reported, and
  separately any decision where the 11-15 strict winner falls outside the quiet tie-tolerant acceptable set. A quieter
  host shrinks CVs, so tie-tolerant accuracy can fall without any winner flip; strict-winner flips are the primary
  flip measure. Any flip counts as "changed" at the decision level; hypothesis verdicts change only if a verdict flips.
- **Catastrophic picks.** S2 count as scored (11-15: 3) and as registered with `join_3to4_09` excluded (11-15: 2).
  Changed if either count differs.
- **Always-StarRocks cold tie-tolerant accuracy** (11-15: 0.905). Changed if it differs by more than 0.02 (two decisions).
- **H1 to H6 verdicts** as defined in the parent file. Changed if any verdict differs. H6 also reports whether native
  q5's warmup completes again (11-15: 176.6 s).
- **Hot-cell decisions settled by tens of ms.** RESULTS lists every hot-cell decision whose 11-15 margin between the top
  two valid engines was under 100 ms and says which winner the quiet run gives.

## LLM-router arm (registered legs, serial, $0)

Run only after every engine pass, the StarRocks probe and the stop of the engine containers, one leg at a time:
1. **gemma4:e4b (registered)**: 48 decisions (`_01` and `_02` of every family, hot and cold) x 5 trials, request
   body as `llm_router_quiet.py` (prompt and parse imported from the unchanged `llm_router.py`), top-level
   `"think": false`, temperature 0.7, seed 1000+trial, `num_thread 8`, `num_predict 16`. **Stop rule:** if the first 3
   scored calls are all `invalid`, the leg stops and is reported as not runnable on this runtime (the smoke test
   predicts this). No prompt, parse or template change is allowed to rescue it.
2. **phi4:latest** (the 11-15 substitute): 24 decisions (`_01`) x 5 trials, request body identical to 11-15's
   `call_local`.
3. **agy 1.5.9** `--model gemini-4-hydrogen-high`, `-p` last, plan quota, 24 decisions (`_01`) x 5 trials.
No paid API at any point. Every call records 1-minute load and UTC start. Scoring by the unchanged
`analyze_llm.py` logic against the quiet truth (primary) and the 11-15 truth (comparison).

**H9 uncontended margins** are reported two ways: median latency over the registered threshold (11-15: phi4
31.3 s / 1 s = 31x, agy 28.1 s / 2 s = 14x, as in VERIFICATION fix 13), and median latency over the rule stack's
median per-decision latency, with the rule stack timed under its own load stamp on the same decisions. H7 and H8 are
reported on whatever legs ran, with the n stated in the verdict line.

## Outputs

`RESULTS-QUIET-2026-11-16.md`, `LEDGER-ROW-QUIET-2026-11-16.md`, then, after every timed run, an independent
`VERIFICATION-QUIET-2026-11-16.md` with a Gemini (`agy -p`) adversarial leg. Evidence tier: lab measurement, single
host. Anything not specified here and done after seeing data is labelled post-hoc.

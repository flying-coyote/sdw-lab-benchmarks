# agent-toolcall-schemas (R2)

## What it measures

One real MCP `tools/call` exchange, recorded in four schemas (OCSF main with the `ai_operation` profile, the OCSF
#1754 draft class, OpenTelemetry GenAI and MCP semantic conventions, and OWASP AOS on OCSF), scored on what each
schema keeps typed, keeps as an untyped blob, pushes to `unmapped` or custom attributes, or drops; then the query-time
cost of the unmapped shape, measured with five pre-registered hunts over a million synthetic calls written in three
layouts (typed OCSF, an OTel attributes map, AOS `unmapped` JSON) in DuckDB.

## Result

Over a 33-fact inventory per call, OCSF main typed 24 facts against AOS's 11 (8 under AOS example 1), and AOS put 9 of
the 12 agent- and tool-specific facts in `unmapped` under example 2; no schema typed individual argument values
(`RESULTS.md`, H1 to H3). At a million calls the AOS `unmapped` layout ran several times slower than typed OCSF on four
hunts: Q1 about 8.4x and Q5 about 22x in both the formal run and a lower-load rerun, and Q3 and Q4 roughly 5x to 16x
across the two, a spread `RESULTS.md` attributes to contention on single-digit-millisecond baselines. The OTel map
layout ran 10.6x to 32.4x in the formal run and swings the same way (27.6x and 33.2x on Q3 and Q4 in the rerun), while on disk the unmapped layout was only 1.13x larger, so the cost of
the unmapped shape lands at query time (`RESULTS.md`, Part 2 and H4 to H5). The loss table is a mapping judgment
made by the run agent against pinned upstream schema files, including one call it names as its own (OCSF main's
`api.version` for the MCP protocol version), while the timings are measured, and the within-pass ratios are the
claim because the host was shared. The query-time layout follows AOS example 1, not the example-2 record the loss
table counts, and a post-hoc run found an example-2 layout level with typed OCSF on three of the five hunts.

## What would have made it fail

H1 to H5 in `PREREGISTRATION.md` carry thresholds (H4 predicted L3 at least 3x L1 on four hunts, H5 predicted at
least 1.3x on disk), and H4b and H5 were refuted while the OTel-map half of H4 failed. Answers were checked identical
across the three layouts for every query in every pass, and Q2, the argument hunt, was pre-registered as a null
control because arguments are JSON in every layout.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before the run and not owner-reviewed. Its sha256 in `PREREGISTRATION.sha256`
(`eddf6816…0183`) still matches, with freeze time 2026-11-09T22:58:56Z. The committed capture and timing files carry
monotonic clocks but no wall-clock stamp, so freeze-before-run rests on the verifier's check in `VERIFICATION.md`
(section 1). Six deviations are listed in `RESULTS.md`; the sixth collects four items (a to d) that the verifier logged and
the run had not.

## Reproduce

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python capture.py
.venv/bin/python map_schemas.py && .venv/bin/python validate_ocsf.py
for p in 0 1 2; do .venv/bin/python run_queries.py 100000 $p; done
.venv/bin/python gen_corpus.py 1000000      # (gen_corpus.py 100000 ran first)
for p in 0 1 2; do .venv/bin/python run_queries.py 1000000 $p; done
.venv/bin/python analyze.py
for p in 0 1 2; do R2_TAG=_rerun .venv/bin/python run_queries.py 1000000 $p; done
.venv/bin/python explore_l2_nopayload.py     # exploratory
```

The generated corpora under `data/` are gitignored and regenerate from one seeded RNG; `data/n*/corpus_meta.json`,
which the RESULTS file names as the pinned fingerprints, is therefore not committed either. The post-hoc example-2
timing runs as `posthoc_ex2_timing.py gen 1000000`, `posthoc_ex2_timing.py time 1000000 {0,1,2,3}` and
`posthoc_ex2_pool.py`, and `validate_posthoc_2026_11_16.py` re-runs the validator post hoc.

Files: `server.py` (SDK `MCPServer` backed by DuckDB), `proxy.py` (stdio tee), `capture.py`, `capture/wire.jsonl`
(25 wire messages), `map_schemas.py`, `validate_ocsf.py`, `gen_corpus.py`, `run_queries.py`, `analyze.py`, and
`ref/` with the pinned upstream schema files (OCSF main at d1cbd61, PR #1754 at 08d6f53, OTel GenAI at e6658f1 and
semconv v1.45.0, AOS at 9a9bc37).

## Results

- `RESULTS.md` is the entry point: capture and the loss table, query-time cost, the lower-load rerun, exploratory
  work, deviations, limits, commands.
- `results/loss_table.md` and `results/loss_table.json` are the loss table; `results/records_*.jsonl` the records in
  each schema; `results/ocsf_validator_1.9.0.json` the validator output; `results/timing_*.json`,
  `results/timing_summary.md` and `results/timing_rerun_summary.json` the timings; `results/run_log.txt` and
  `results/rerun_log.txt` the console logs.
- `RESULTS-EX2-POSTHOC-2026-11-16.md` (post-hoc, not pre-registered, not independently verified) times an AOS
  example-2 layout beside the original three, with its passes in `results/timing_ex2posthoc_*.json` and
  `results/validator_posthoc_2026-11-16.json`.
- `VERIFICATION.md` is the independent check (VERIFIED-WITH-FIXES). Under `verify/`, `backup/RESULTS.md.pre-verify`
  and the rest of `backup/` are superseded copies from before the verifier's fixes, and `rerun/` with `pool.py` is
  the verifier's own re-run; none of them is the current result.

## Versions and pins

`requirements.txt` pins every line with `==`. The rig stamp in `RESULTS.md` names DuckDB 1.5.3, pyarrow 23.0.1,
Python 3.12.3 and MCP Python SDK 2.3.0, and the post-hoc file records the same versions from a fresh venv.

## Evidence tier and limits

Tier B for method (`RESULTS.md`): first-party, one machine, a synthetic corpus for the timing part and a real wire
capture for the mapping part, with schema facts Tier B from the pinned upstream files. stdio only, harness-supplied
agent and model identity, AOS scored on its published examples, one engine, warm cache and a contended host. See
Limits in `RESULTS.md`.

## Corrections

- 2026-11-09: three verifier wording fixes and four verifier-logged deviations in `RESULTS.md`.
- 2026-11-16: dated corrections in `RESULTS.md` on protocol negotiation and OTel attribute stability, and a dated note
  pointing to the example-2 post-hoc run.
- 2026-11-17: first-person narration in `RESULTS.md` and `RESULTS-EX2-POSTHOC-2026-11-16.md` was recast in neutral
  voice; this README was added.

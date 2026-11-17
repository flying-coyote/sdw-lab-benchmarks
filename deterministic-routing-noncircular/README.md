# deterministic-routing-noncircular: the June routing rules, scored off their own training shapes

## What it measures

Whether the unchanged June rule stack from `../deterministic-routing-sim/route_sim.py` still sends queries to the engine that is actually fastest when the queries are not the shapes it was built from. `gen_queries.py` generates 84 queries in 12 families (seed 20261115, `queries/corpus.json`), every query runs on four engine arms (StarRocks 4.1.7, ClickHouse 26.5.1.882 over Iceberg and over native MergeTree, Trino 481), a DuckDB oracle supplies the answer key, and `score.py` compares the rules' picks with the measured winners. A $0 LLM-router arm (a local phi4 and a hosted Gemini model) is scored on a 24-decision subsample against the same truth.

## Result, and whether it is measured

Measured, and the headline went against the rules. Off its training shapes the rule stack is not a reliable cliff guard: it sent two 4-table joins carrying a non-key nation equality to native MergeTree, where they took 110.9 s and 200.9 s against about 2.0 s and 1.0 s on the best engine on the contended 2026-11-15 run, and 92.6 s and 159.8 s against about 0.7 s on the quiet 2026-11-16 run (`RESULTS.md`, `RESULTS-QUIET-2026-11-16.md`). Per hypothesis, from the two ledger rows and the RESULTS files:

| hypothesis | 2026-11-15 (contended host) | 2026-11-16 (quiet host) |
|---|---|---|
| H1 placement accuracy at least 0.90 | falsified, 0.643 hot / 0.738 cold | falsified, 0.643 / 0.679 |
| H2 no catastrophic picks | falsified, 3 as scored, 2 as registered | falsified, 2 as scored, 1 as registered |
| H3 always-StarRocks has no cold cliff | falsified (shares one memory-limit DNF) | held as run on a restarted engine (0.940, 0.016 s regret), but a fresh container failed 5 of 5, so not established under the frozen protocol |
| H4 UEBA two-level aggregations replicate the June inversion | held, 8 of 8 | held |
| H5 hot-cell winners stable inside shape classes | falsified | falsified, hot cell only |
| H6 native q5 times out again; anchors match June | held (6 of 7 anchors), with the discarded warmup completing in 176.6 s | held (7 of 7), warmup completed in 140.1 s |
| H7 to H9 LLM arm | split by leg (phi4 0.625, agy 0.750, rules 0.750) | agy 0.708 and phi4 0.583 against the rules' 0.792; H7 now holds for agy too |

A post-hoc ClickHouse check confirms June's mechanism on both new cliff queries: with `query_plan_optimize_join_order_limit = 0` they answer in 5.8 s and 7.1 s (`results/posthoc_ch_order.json`).

## What would have made it fail

The hypotheses carried numeric falsifiers frozen before any corpus query ran, and the measured winners come from engine timings the rule author did not choose. Always-StarRocks and always-native are scored as baselines beside the rules, and the oracle answer gate rejects any engine answer that disagrees.

## Pre-registration

- `PREREGISTRATION.md`, sha256 `1d07f6de...d9074c`, verified 2026-11-17 against `PREREGISTRATION.sha256`; stamped 2026-11-15T20:06:31Z.
- `PREREGISTRATION-ADDENDUM-QUIET-2026-11-16.md`, sha256 `c19b9cf1...561d`, verified with all five scripts its hash file lists (`run_engines_quiet.py`, `sr_probe_quiet.py`, `score_quiet.py`, `llm_router_quiet.py`, `register_quiet.py`); stamped 2026-11-16T03:12:43Z.
- Both were frozen by the agent that ran the bench, and the files record that neither was reviewed by the repository owner before the runs. The rule stack under test, `../deterministic-routing-sim/route_sim.py`, matches the hash in `PREREGISTRATION.md:37`.
- Freeze-before-run rests on file modification times recorded in `VERIFICATION.md`, which show every scored output after the freeze and cannot show when the first oracle pass began. The raw result files carry no per-trial timestamps.
- Deviations, all declared in the RESULTS files: the oracle retried one query at 24 GB rather than excluding it, Dremio excluded, a Chainguard MinIO image, StarRocks 4.1.7 drift, the local model swapped, the LLM subsample cut, a contended host on 11-15, and on 11-16 the catalog re-registered rather than reloaded, containers restarted rather than re-created, orchestration scripts written after the freeze and some calls inside a cron window. `llm_router.py` was saved after the scored LLM legs started, and its frozen version is not preserved (`RESULTS.md:258`).

## Reproduce

The pipeline, as `RESULTS.md` lists it under "Files": `gen_queries.py` writes `queries/corpus.json`; `oracle.py` writes `results/oracle.json`; `compose.yml` with `Dockerfile.lab` brings up MinIO, Nessie and the `drn-lab` container, with each engine behind its own compose profile; `load.py` loads the tables; `run_all.sh` runs the 2026-11-15 protocol, one engine at a time through `run_engines.py`; `score.py` writes `results/scores.json`; `llm_router.py` and `analyze_llm.py` produce the LLM arm. The quiet replication uses `register_quiet.py`, then `run_quiet.sh` (load-gated per cell) and `score_quiet.py`, `analyze_llm_quiet.py` and `compare_quiet.py`.

```bash
cd deterministic-routing-noncircular
bash run_all.sh      # 2026-11-15 engine passes (expects the stack, tables and oracle in place)
bash run_quiet.sh    # 2026-11-16 quiet replication
```

The engine passes take hours (03:13Z to 07:04Z on 2026-11-16). The LLM arm needs a local Ollama with phi4 and the agy CLI.

## Results

- Entry point: `RESULTS-QUIET-2026-11-16.md` (the quiet-host run, which the essays now cite for timings), then `RESULTS.md` (the contended 2026-11-15 run, which carries the hypothesis text and the full deviations list).
- Verification: `VERIFICATION.md` (11-15), `VERIFICATION-QUIET-2026-11-16.md` and `VERIFICATION-INDEPENDENT-2026-11-16.md`, all VERIFIED-WITH-FIXES with no verdict change. These are verifier reports and keep their first-person voice.
- Ledger text: `LEDGER-ROW.md`, `LEDGER-ROW-QUIET-2026-11-16.md`.
- Data: `results/` (11-15), `results/quiet-2026-11-16/` (11-16); post-hoc files are named `*posthoc*`.

## Versions and pins

ClickHouse `26.5.1.882` and Trino `481` are pinned in `compose.yml`. StarRocks runs from `starrocks/allin1-ubuntu:4.1-latest` (recorded as 4.1.7-b81ff9c), Nessie from `ghcr.io/projectnessie/nessie:latest`, and MinIO from `cgr.dev/chainguard/minio:latest` (digest recorded in `RESULTS.md`). The oracle is DuckDB 1.5.3 and the router sqlglot 30.11.0; sqlglot is not pinned in any requirements file in the repository, and pyiceberg is not pinned in the root `requirements.txt` and this folder has no requirements file of its own (other benches pin 0.11.1, for example `ocsf-iceberg-metadata/requirements.txt`).

## Evidence tier and limits

Tier B for the mechanism: one host, generated queries over TPC-H-derived SF10 and synthetic Zeek-shaped tables. The TPC-H-derived queries are not audited and are not comparable to published TPC-H results. On 11-15 a sibling bench shared the host and the arms saw uneven load, so hot-cell decisions settled by tens of milliseconds are tilted toward native on that date.

## Corrections

None.

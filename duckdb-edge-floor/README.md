# duckdb-edge-floor: how little memory a DuckDB hunting detection needs, under an enforced cap

## What it measures

The memory floor of three H-EDGE-01 detection shapes in DuckDB 1.5.3, and how each fails below it: S, a streaming UEBA two-level aggregation; H, a heavy group-by; J, a same-minute self-join; plus a client-only baseline. The November runs put every trial in its own Docker container with cgroup v2 memory equal to memory-plus-swap, so the kernel enforces the cap, and they record live spill, peak cgroup anon, `VmHWM`, the buffer-manager peak and `memory.peak` per trial, across caps of 4096, 256, 128, 64, 32 and 16 MiB at 1 and 4 threads, five trials per cell.

## Result, and whether it is measured

Measured. Under the pre-registered rule that `memory_limit` is 7/8 of the cap, S and H need 256 MiB and fail below it by kernel OOM kill, and J has no capped floor (it fails at every capped point). Post hoc, with `memory_limit` at about half the cap, S completes at 64 MiB and H at 128 MiB; those are lower bounds on device memory, probably by something like 13 to 40 MiB, because file-backed pages already in the host cache were not charged to the container (that range comes from a one-off check with no committed artifact, `RESULTS-2026-11-15.md:203,272`). The quiet-host replication on 2026-11-16 reproduced every discrete result: outcome counts are identical (main arm 105 completed, 114 kernel kills, 0 DuckDB OOM errors; arm B 50 / 48 / 40; arm C 50 / 4 / 6, re-derived from `run-2026-11-15/results/trials*.jsonl` and `run-2026-11-16-quiet/results/trials*.jsonl`), every floor is the same, and answer hashes match. Its timings are the ones to cite, since the 2026-11-15 main arm and arm B ran under heavy host load.

## What would have made it fail

Each hypothesis carried a floor and a failure mode that would make it wrong, frozen before corpus generation, and five of the ten main-arm hypotheses were falsified (H1, H2, H3, H5a, H5b). The 4096 MiB reference cell is the baseline for every answer hash and latency ratio.

## Pre-registration

- `PREREGISTRATION-2026-11-15.md`, whole-file sha256 `d5ede44b...dc01b6` and body sha256 `eef135a4...4512a`, both verified 2026-11-17; frozen 2026-11-15T19:59:59Z, and the first main-arm trial is stamped 20:00:24Z.
- `PREREGISTRATION-2026-11-15-ADDENDUM-A.md` (`6aa30729...bf912`, frozen 20:13:01Z, first arm-B trial 23:29:05Z) and `PREREGISTRATION-2026-11-15-ADDENDUM-B.md` (`a94dab7d...432378`, frozen 2026-11-16T00:24:28Z, first arm-C trial 00:24:40Z), both post-hoc arms frozen before their first trial; whole-file and body hashes verified.
- `PREREGISTRATION-2026-11-16-ADDENDUM-QUIET.md` (`c4e9bc30...c108`, frozen 03:12:43Z, first trial 07:30:33Z). Its hash file lists seven scripts by bare name; all seven are in `run-2026-11-16-quiet/` and match. The 11-15 harness hashes in the parent file and the addenda (`trial.py`, `driver.py`, `driver_armB.py`, `driver_armC.py`, `gen_corpus.py`, `gen_corpus_z2.py`, `image/Dockerfile`) match the copies in `run-2026-11-15/`.
- All four were frozen by the agent that ran the bench, and the files record that none was reviewed by the repository owner before the runs. The freeze times above come from the files themselves; confirming them against commit history is left to a session that reads git.
- Deviations are declared in both ledger rows: two post-hoc arms, the corpus Z generator's key dependence found afterwards, analysis scripts written after the freeze, stop rules that cut killed cells to two trials, decimal-MB `memory_limit` against MiB caps, contended timings on 11-15, and chrony offsets up to about 1.4 s (timings are monotonic).

## Reproduce

```bash
cd duckdb-edge-floor
docker build -t sdw-edge-floor:duckdb-1.5.3 run-2026-11-15/image/
docker run --rm --user 1000:1000 -v $PWD/run-2026-11-15:/work sdw-edge-floor:duckdb-1.5.3 python /work/gen_corpus.py
python3 run-2026-11-15/driver.py                 # main arm; driver_armB.py and driver_armC.py for the addenda
bash run-2026-11-16-quiet/run_quiet.sh           # quiet replication: arm C, main, arm B, load-gated
```

The quiet replication ran 417 of 735 scheduled trials in about 34 minutes (07:30Z to 08:04Z); the stop rules skip the rest.

## Results

- Entry point: `RESULTS-QUIET-2026-11-16.md` for timings and the replication verdict, then `RESULTS-2026-11-15.md` for the hypotheses, mechanism and memory accounting.
- `RESULTS-2026-06-15.md` is the earlier run that set only `memory_limit`, with no OS-enforced cap, and found no cliff down to 64 MB. The November runs supersede its floor; it is kept as the record of why the enforced-cap design was needed.
- Verification: `VERIFICATION-2026-11-15.md`, `VERIFICATION-QUIET-2026-11-16.md`, `VERIFICATION-INDEPENDENT-2026-11-16.md`, all VERIFIED-WITH-FIXES with no verdict change; they keep the verifiers' first-person voice.
- Ledger text: `LEDGER-ROW-2026-11-15.md`, `LEDGER-ROW-QUIET-2026-11-16.md`.
- Data: `run-2026-11-15/results/`, `run-2026-11-16-quiet/results/`; the June files are `results/edge_floor.json` and `results/heavy_cliff.json`.

## Versions and pins

DuckDB 1.5.3 on Python 3.12.3 in image `sdw-edge-floor:duckdb-1.5.3`, built from `python:3.12.3-slim` (image ID `sha256:ead733f4...558943`, recorded in the pre-registration). The host's system Python carries DuckDB 1.5.4, which is not used.

## Evidence tier and limits

Tier B, one x86 desk host under WSL2; the 4-thread cells use a cpuset to stand in for a small quad-core, not a specific device, and real edge hardware is out of scope. The self-join is one join shape. Synthetic corpora.

## Corrections

- 2026-11-17: dated note added to `RESULTS-2026-06-15.md` pointing to the November enforced-cap runs, which supersede its floor.

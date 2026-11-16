---
type: benchmark-preregistration
title: "duckdb-edge-floor enforced-cap re-run: peak memory and OOM under a cgroup v2 cap, live spill, a self-join, a Zipf corpus, five trials per cell"
created: 2026-11-15
status: frozen-by-agent-before-run (not owner-reviewed)
review_ref: project1/02-projects/securitydataworks/content/drafts-2026-11/18-hunting-at-the-edge-duckdb.md, "What's missing before this can publish", items 1 to 5
---

# Pre-registration: duckdb-edge-floor, enforced-cap run (2026-11-15)

Requested by the owner on 2026-11-15 (relayed by the main session), run by an agent, frozen by the agent before any timed or hypothesis-bearing run, not owner-reviewed. Spend $0, local only.

## What I knew before writing this

- The June run (`RESULTS-2026-06-15.md`, `run.log`, `results/edge_floor.json`, `results/heavy_cliff.json`): DuckDB 1.5.3, `memory_limit` only (no OS cap), one run per cell. The streaming shape completed at every `memory_limit` from 4 GB to 128 MB at 4, 2 and 1 threads, and the heavy group-by completed down to 64 MB at 1 thread. The temp directory was empty after every query.
- The draft's gate (2026-11-09) counted 9,999,996 heavy-shape groups, 1,346,361 host-hours and 8,000 hosts on the June generator, and found that `ts` and `host` both derive from `hash(i)`.
- Mechanism checks run before this file was written. None ran a bench shape or a corpus.
  - systemd user scope: `systemd-run --user --scope -p MemoryMax=64M true` fails with "Failed to connect to bus", and `sudo -n` needs a password, so cgroup v2 via systemd is unavailable. The run uses Docker 29.5.3 (server 29.8.0, cgroup v2, systemd driver).
  - Image `sdw-edge-floor:duckdb-1.5.3`, built from `python:3.12.3-slim` plus `duckdb==1.5.3` (`run-2026-11-15/image/Dockerfile`), image ID `sha256:ead733f45f4b9f0ad0c9fa91f9e427d888ee7174e6f43c6f19afef0726558943`. DuckDB 1.5.3 matches June and the lab venv. The host's system `python3` carries 1.5.4, which is not used.
  - In a container run with `--memory=64m --memory-swap=64m --user 1000:1000`, `/sys/fs/cgroup/memory.max` read 67108864, `memory.peak` and `memory.events` were readable, and a bind-mounted write from the bench folder landed owned by uid 1000.
  - Kill detection: a Python process touching 200 MB in a 64 MB container was killed (`rc=137`, `memory.events` `oom 1`, `oom_kill 1`), and the `sh` parent survived to report it.
  - Polling during execution: a non-bench query (`SELECT count(*) FROM range(400000000) ... hash(i) % 7 = 0`, 1.89 s, 1 thread) collected 36 poll samples from a second cursor while it ran, so the Python client releases the GIL during `execute` and live polling works. That probe's client baseline was `VmHWM` 63.4 MB, of which `RssAnon` was 20.3 MB (the rest is file-backed pages of the DuckDB library and Python). This is the only memory number I knew before freezing, and it bears directly on H0.
- `chronyc tracking` read `System time` 0.95 s slow at 14:51 local, then 0.00015 s fast at 14:52 after an update. Timings use `time.perf_counter` (monotonic), so the offset matters less than the rate.

I computed no group count, no corpus statistic, no latency and no capped outcome on either new corpus before freezing.

## Question

When the operating system enforces the memory cap, the way a small edge box does, at what cap do three hunting-detection shapes stop completing in DuckDB 1.5.3, how do they fail when they do, and does DuckDB spill while they run?

## Instrument

### Mechanism and memory accounting

- One fresh container per trial: `docker run --rm --user 1000:1000 --memory=<cap>m --memory-swap=<cap>m --cpuset-cpus=<2 | 2-5>`. Setting `--memory-swap` equal to `--memory` gives the cgroup no swap, so going over the cap triggers a kernel OOM kill. Trials never share a process or a cgroup, because `memory.peak` is cumulative over a cgroup's life.
- PID 1 is `sh`. It runs `python /work/trial.py ...`, then prints the child's return code, `memory.peak` and `memory.events`.
- DuckDB settings per trial: `memory_limit` = 7/8 of the cap, `threads` = the cell's thread count, `temp_directory` on a bind-mounted directory on the WSL2 ext4 disk (`run-2026-11-15/spill/<tag>/`, never tmpfs, since tmpfs pages are charged to the cgroup) and `preserve_insertion_order=false`, as in June.
- Memory read four ways, because `memory.peak` also counts page cache, and reading a 100+ MB Parquet file can be expected to drive it to the cap even when the query's own memory is small:
  1. `memory.peak`, the cgroup high-water mark including page cache.
  2. Peak cgroup `anon`, the maximum of `memory.stat` `anon` sampled every 50 ms. This is the headline "process memory" figure, because it is what the kernel cannot reclaim without killing.
  3. `VmHWM`, the process's peak RSS including file-backed library pages, read at the end of a completed trial.
  4. The DuckDB buffer-manager peak, the maximum of `sum(memory_usage_bytes)` over `duckdb_memory()`, sampled every 50 ms.
- Samples are written one line at a time, with a flush per line, to `results/raw/<tag>.samples.jsonl`, so the last sample before a kill survives.

### Spill observed during execution

A poller thread on a second cursor (`con.cursor()`, same database instance) samples every 50 ms, recording:

- `sum(size)` over `duckdb_temporary_files()`;
- `sum(temporary_storage_bytes)` over `duckdb_memory()`;
- a directory walk of the temp directory, as a fallback.

Peak spill is the maximum of the first and third over the trial. The driver also records the bytes left in the temp directory after the trial, which is the June measurement, so the two can be compared. Poll errors are counted, not fatal. The poller costs one extra cursor and a query every 50 ms, applied the same way in every cell.

### Corpora

Both have 10,000,000 rows with columns `ts, host, usr, process, bytes`, are generated once (uncapped, single-threaded write) by `run-2026-11-15/gen_corpus.py` inside the same image, and are mounted read-only.

- **U** is the June `heavy_cliff.py` generator unchanged, plus June's `bytes` column: 8,000 hosts, 20,000 users and 200 processes, hash-uniform, with `ts` and `host` both derived from `hash(i)`. Its expected heavy-shape group count is 9,999,996, and reproducing that number is the identity check against June.
- **Z** is a Zipf corpus with s = 1, using the continuous inverse-CDF approximation `k = floor((n+1)^u) - 1` on host (n = 8,000), usr (n = 20,000) and process (n = 200). Each of `ts`, host, usr, process and bytes is drawn from its own hash, `hash(i, '<column>')`, so the keys are independent. The exponent is frozen at 1 and there is no other seed, so the generator is deterministic for DuckDB 1.5.3's `hash`.
- Recorded per corpus in `results/corpus_stats.json`: file sha256, the logical fingerprint `bit_xor(hash(all columns))`, distinct key counts, the heavy-shape group count, host-hours, host-minutes, the self-join's upper bound on pair rows, the head-host and top-10-host share, the head-process share, and corr(ts, host number).

### Shapes (exact SQL in `trial.py`, sha256 below)

- **null**, the client baseline: `import duckdb`, connect, apply settings, `SELECT 1`. It runs at every cap at 1 thread, so a cap that the Python + DuckDB client cannot fit is never reported as a query-shape floor.
- **S**, streaming two-level aggregation (June's UEBA volume z-score): per-host hourly counts, then each host's mean and stddev, with a flag where z > 3. A tie-break `ORDER BY z DESC, host` is added and float outputs are rounded to 6 places, so answers compare exactly.
- **H**, high-cardinality group-by (June's heavy shape) on `(host, usr, process, ts // 60)`, with the tie-break `ORDER BY c DESC, host, usr, process, m LIMIT 50` added. On U almost every group has c = 1, so the top 50 is decided by the tie-break.
- **J**, a self-join. Process pairs co-occurring on one host in the same minute: `e a JOIN e b ON a.host = b.host AND a.m = b.m AND a.process < b.process`, aggregated to per-(host, p1, p2) counts. It returns one row: pair count, total co-occurrences, rare pairs (c = 1) and a `bit_xor` checksum of the rare pairs.
  - This is a same-minute-bucket approximation of the draft's "within a 60-second window". It is an equi-join on purpose, because a range join keyed only on host goes quadratic on Zipf head hosts.
  - My arithmetic bound before freezing, not measured: on U each host-minute holds about 0.12 events, so roughly 0.6 M join rows. On Z the head host holds about 7.7% of rows (about 770 k, or 76 a minute), and the sum over hosts of n_k² / (2 × 10,080 minutes) comes to roughly 30 to 60 M join rows. That is heavy but bounded.

### Matrix

- Caps: 4096 MB (the uncapped reference), 256, 128, 64, 32 and 16 MB. `memory_limit` is 3584, 224, 112, 56, 28 and 14 MB.
- Shapes S, H and J, each on corpora U and Z, each at threads 1 (cpuset `2`) and 4 (cpuset `2-5`). Null runs at threads 1 only.
- 5 trials per cell, each one a fresh container: 6 caps × (12 shape cells + 1 null) × 5 trials = 390 trials before stop rules.
- Order: the null cells first, then corpus U, then Z; within a corpus S, H, J, threads 1 then 4, caps from loosest to tightest, with trials back to back.

### Outcome classes (per trial)

- `completed`: the query returned. It counts as *correct* only if `answer_sha256` equals the 4096 MB reference for the same shape, corpus and thread count.
- `duckdb_oom_error`: DuckDB raised an out-of-memory exception, which is graceful refusal.
- `error`: any other DuckDB or Python exception.
- `kernel_oom_kill`: the child died with no final record and `memory.events` `oom_kill` > 0, which is abrupt process death.
- `timeout`: container wall time over **300 s**, then `docker kill`, which is thrash or a hang.
- `no_record_rc<N>`: anything else. Reported as is.

### Stop rules (frozen, to bound cost)

- Once two trials of a cell have failed with the same outcome class, the cell's remaining trials are recorded as `skipped_by_stop_rule`.
- After a timeout in a (shape, corpus, threads) chain, the timed-out cell and every tighter cap in that chain run one trial only.

### Load and clock

Other benches may run on this host.

- Before each cell, the driver reads the 1-minute load. If it is above 4.0, it waits in 30 s steps, up to 600 s, then runs regardless.
- The 1-minute load and the `chronyc` `System time` offset are recorded on every trial.
- Timings are hot/warm: the host page cache is warm after the first trial, and the methodology §3 cold path needs root. They are indicative, Tier B, single host.

## Definitions used in the verdicts

- **Floor** for a (shape, corpus, threads) chain: the tightest cap at which every run trial completed correctly, *provided* every looser cap also did. If completion is non-monotone, so that a tighter cap completes after a looser one failed, the floor is the cap just above the loosest failure, and the non-monotonicity is reported.
- **First failing cap**: the loosest cap with any trial not completed correctly. **Failure mode**: the modal outcome class at the first failing cap.
- A cap where null fails is *client-bound*. A shape failing at a client-bound cap is reported as "below the client floor", and that cap does not count as a shape floor.
- **Spill observed**: peak polled spill (`duckdb_temporary_files` or the directory walk) > 0 in a trial.

## Hypotheses (each a floor plus a failure mode, with what would make it wrong)

- **H0 (client floor).** The client baseline completes at 32 MB and above and fails at 16 MB, by kernel OOM kill or timeout.
  - Basis: anon was about 20 MB in the probe, and file pages are reclaimable.
  - Wrong if null completes all trials at 16 MB, or fails any trial at 32 MB or above.
- **H1 (streaming floor).** S has a floor of 64 MB at threads 1 on both corpora, failing first at 32 MB by kernel OOM kill.
  - Wrong on the floor if S completes at 32 MB, or fails at 64 MB or above, on either corpus.
  - Wrong on the mode if the modal failure at the first failing cap is a DuckDB OOM exception or a timeout.
- **H2 (spill exists and the June check missed it).** On U at threads 1, H shows live spill > 0 in at least one completed trial at a cap of 128 MB or below, while the temp directory is empty after every trial. This would settle the draft's first explanation, that DuckDB deletes temp files on release.
  - Wrong if no completed H-U trial at 128 MB or below shows live spill.
  - The second clause is wrong if any trial leaves spill bytes behind.
- **H3 (the heavy shape's floor is higher under an OS cap).** H on U at threads 1 has a floor of 128 MB, meaning it fails at 64 MB, where June completed with only `memory_limit` set.
  - Wrong if H-U-t1 completes all trials at 64 MB, or fails at 128 MB or above.
- **H4 (`memory_limit` is not the process bound).** In every completed trial at a cap of 64 MB or below, `VmHWM` exceeds the trial's `memory_limit`, and peak cgroup anon exceeds the peak DuckDB buffer-manager bytes by 15 MB or more. This tests the draft's second explanation.
  - Wrong if any completed trial at 64 MB or below has `VmHWM` ≤ `memory_limit`, or an anon minus buffer-manager gap under 15 MB.
- **H5 (skew grows the join floor and shrinks the group-by).**
  - (a) Z's heavy-shape group count is at least 30% below U's.
  - (b) J's floor on Z is strictly higher than on U at threads 1.
  - (c) H's floor on Z is at or below H's floor on U at threads 1.
  - Each clause is wrong independently if its inequality fails.
- **H6 (threads cost memory).** For every shape and corpus, the floor at threads 4 is at or above the floor at threads 1.
  - Wrong if any chain completes at a tighter cap with 4 threads than with 1.
- **H7 (an enforced cap cliffs rather than refuses).** Across all shape chains, the modal failure mode at the first failing cap is a kernel OOM kill, and DuckDB's own OOM exception is the mode in fewer than half of the chains that fail at all.
  - Wrong if `duckdb_oom_error` is the mode in half or more of the failing chains.

### Variance and reporting

- Per cell: median latency, min, max and coefficient of variation (population stddev over mean) over the completed trials, and the per-trial load.
- A latency difference between cells is described as real only where it exceeds both cells' CV.
- Cells with CV above 10% are flagged.
- Raw per-trial records go to `results/trials.jsonl` and per-trial samples to `results/raw/`.

### Predicted confidence delta

None on hub hypotheses from this bench alone. For draft 18, if a floor is located with a known failure mode, the "What the numbers don't show yet" section can name it. If H4 holds, the draft's 64 MB and 128 MB figures must be restated as `memory_limit` settings, not device memory.

## Scope and what is out

- Item 6 of the draft list (real edge hardware: ARM SBC or industrial PC, cold cache) is out of scope. Everything runs on the Beelink (Ryzen 7 5800H, WSL2 6.6.87.2, 14 vCPU, about 47 GB) under Docker.
- The 4-thread cells use cpuset 2-5 on an x86 desk host, so they stand in for a small quad-core, not a specific device.
- The self-join is one join shape. It is not a claim about joins in general.

## Harness hashes at freeze

| File | sha256 |
|---|---|
| `run-2026-11-15/trial.py` | `c7c822a52f75d58cef3f58b39473b3b8c33fc033fbf051f6d95fbbf7ea85a029` |
| `run-2026-11-15/driver.py` | `c05d29096f403964c9181dd43a71381db043278cfa7f1ea9c87b85cfcf484007` |
| `run-2026-11-15/gen_corpus.py` | `2e0d4fc5e56927ce88fe2db82484114f2d4682400505b71acda94b4b90f4f0f2` |
| `run-2026-11-15/image/Dockerfile` | `405ac0a313e361da50dd29c7461bb9ad736de10b1b91dd1aaffc9090b6973c64` |

Reproduce: `docker build -t sdw-edge-floor:duckdb-1.5.3 run-2026-11-15/image/`, then generate the corpora with `docker run --rm --user 1000:1000 -v $PWD/run-2026-11-15:/work sdw-edge-floor:duckdb-1.5.3 python /work/gen_corpus.py`, then run `python3 run-2026-11-15/driver.py`.

## Freeze

Frozen by agent at 2026-11-15T19:59:59Z, before corpus generation and before any timed or hypothesis-bearing run. Not owner-reviewed.

- Body sha256: `eef135a43f0768e51b47b2ab9d73ebe0a1e32ff512883080b6a439ff2c04512a`. This is sha256 of every byte of this file before the `## Freeze` line, including the newline that ends the line above it. Check with `python3 -c "import hashlib;d=open('PREREGISTRATION-2026-11-15.md','rb').read();print(hashlib.sha256(d[:d.index(b'\n## Freeze\n')+1]).hexdigest())"`.
- Whole-file sha256, footer included, is in `run-2026-11-15/results/PREREG.sha256` and `run-2026-11-15/.frozen`.
- DuckDB pinned at 1.5.3, Python 3.12.3, image `sha256:ead733f45f4b...558943`.

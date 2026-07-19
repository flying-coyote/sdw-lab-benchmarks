# stream-complexity — batch vs streaming operational complexity

Pre-registration (frozen, read first): `PRE-REG-stream-complexity-2026-07-19.md`. This
README is the "how to run it" companion; it does not restate the hypotheses,
predictions, or honesty boundaries the pre-reg already states — read that file for
the *why*, this one for the *how*.

## What's being compared

Same detection outcome, same seeded corpus, two arms:

- **Batch**: `gen_corpus.py` → `batch/land_microbatches.py` (Parquet files, one per
  60s of event time) → `batch/batch_job.py` (a bare Python process on a poll loop,
  DuckDB query, appends to `results/alerts-batch.jsonl`). Zero containers, by design.
- **Streaming**: `gen_corpus.py` → `streaming/producer.py` (Kafka topic `smx-auth`) →
  Flink SQL job (`streaming/flink_job.sql`, tumbling 60s event-time windows +
  watermarks, checkpointing enabled) → Kafka topic `smx-alerts` →
  `streaming/consume_alerts.py` (the sink) → `results/alerts-stream.jsonl`.

Both implement: alert when a `(user, src_ip)` pair has ≥5 failed logins inside one
epoch-aligned 60-second tumbling window. `compare_answers.py` is the answer-equality
gate — the pre-reg means it literally: a divergent run is not a scoreable run.

## Image pins (verified 2026-07-19)

| Image | Tag | Why this one |
|---|---|---|
| `apache/kafka` | `4.3.1` | Latest stable; Kafka 4.x is KRaft-only (no ZooKeeper mode to accidentally pick) |
| `flink` | `2.2.1-scala_2.12-java11` | Latest Flink version whose `flink-sql-connector-kafka` build (`5.0.0-2.2`) is published on Maven Central — checked against the connector's own POM (`<flink.version>2.2.1</flink.version>`), not assumed |
| `busybox` | `latest` | Two one-shot volume-ownership fixups only (see Gotchas) |

`streaming/Dockerfile.flink` builds a local `smx-flink-kafka:2.2.1` image (base Flink
image + the Kafka SQL connector jar, fetched from Maven Central at build time — not
checked into the repo as a binary).

## `smx-` naming

Every container, network, and volume is prefixed `smx-` (declared quiet-box rule —
this host also runs a `moar-*` stack that must never collide with this bench):
`smx-kafka`, `smx-jobmanager`, `smx-taskmanager`, `smx-topic-init`,
`smx-kafka-data-init`, `smx-flink-checkpoints-init`; network `smx-stream-net`;
volumes `smx-kafka-data`, `smx-flink-checkpoints`. Compose project name `smx-stream`.

## Running a trial

```bash
cd stream-complexity
source ../.venv/bin/activate   # duckdb, pyarrow, confluent-kafka — see requirements.txt
bash run_clean_trial.sh 1      # "1" is an optional trial number for latency-trial-N.json
```

`run_clean_trial.sh` does everything: generates the corpus if `data/events.jsonl` is
absent, brings the streaming stack up, submits the Flink job, replays both arms at an
identical paced wall-clock (env `SMX_REPLAY_FACTOR`, default 20x), takes a mid-run
moving-parts/config-LOC snapshot, waits for both arms to drain, runs
`compare_answers.py`, and records `results/latency-trial-N.json`. It exits with
`compare_answers.py`'s exit code — nonzero means the run's complexity numbers are not
scoreable (pre-reg P5), full stop.

Env overrides: `SMX_SEED` (default 20260719), `SMX_LIMIT` (default unset = full
500k-event corpus), `SMX_REPLAY_FACTOR` (default 20).

**Before a real scored trial**, wipe any smoke/dev leftovers so stale Kafka consumer-
group offsets or Flink checkpoint state from an earlier run can't contaminate it:

```bash
( cd streaming && docker compose down -v )
rm -f data/events.jsonl data/ground_truth.json   # force a fresh corpus at full scale
rm -rf data/batch_in results/*.jsonl results/*.json
```

### Individual pieces (for debugging, or a from-scratch full-scale run)

```bash
python3 gen_corpus.py --seed 20260719 --out-dir data          # full 500k events, ~2h span
cd streaming && docker compose up -d && bash submit_flink_job.sh && cd ..
python3 batch/land_microbatches.py --replay-factor 20 &
python3 batch/batch_job.py --poll-interval 5 --max-idle-ticks 6 &
python3 streaming/producer.py --replay-factor 20 &
python3 streaming/consume_alerts.py --idle-timeout 30 &
wait
python3 compare_answers.py
python3 measure_complexity.py       # run WHILE both arms are up, for a live snapshot
python3 measure_latency.py --replay-start-epoch <the shared epoch you used above> --replay-factor 20
```

`land_microbatches.py` and `producer.py` both accept `--replay-start-epoch`: pass the
**same** value to both so their pacing shares one wall-clock origin (see their
docstrings — independent per-script `time.time()` anchors would introduce clock skew
of the same order as streaming's whole predicted freshness advantage).

### Fault injections

```bash
python3 faults/run_faults.py --only all             # all three, sequentially
python3 faults/run_faults.py --only broker          # or one at a time
python3 faults/run_faults.py --only taskmanager
python3 faults/run_faults.py --only batch
```

Each fault runs against its own small dedicated corpus under `faults/_work/`
(`--limit 5000`, isolated from the main `data/`+`results/` a clean trial uses), tears
down/rebuilds the streaming stack fresh for the Kafka/Flink faults (they share one
stack, so they run sequentially, not concurrently), and writes all three results into
`results/faults.json`: recovery step count (parsed straight from each
`recover_*.sh`'s own `# Step N:` comment markers, so the count can't silently drift
from the script it describes), wall-clock-to-recovered, and a post-recovery
`compare_answers.py` check restricted to the affected arm.

`--replay-factor` for fault tests defaults to 5 (slower than a clean trial's 20) —
comfortable wall-clock runway to land a kill mid-flight without racing the replay's
own natural completion; `--warmup-s` (default 12) is how long each arm runs before
the fault is injected.

## Cleanup

```bash
( cd streaming && docker compose down -v )      # wipes containers, network, AND volumes
docker rmi smx-flink-kafka:2.2.1                # optional — only if reclaiming disk
rm -rf data/batch_in/*.parquet data/batch_in/.batch_state.json
rm -f results/*.jsonl results/.stream_consumer_state.json
```

## Gotchas hit building this (left in as comments at the point they bite)

- **Named-volume ownership.** `apache/kafka` runs as uid 1000, the Flink image as uid
  9999; a freshly-created Docker named volume is root-owned, so KRaft's
  format-on-first-boot and Flink's first checkpoint both fail with
  `AccessDeniedException`/`IOException` until something chowns the volume first.
  Fixed with two one-shot `busybox` init services (`smx-kafka-data-init`,
  `smx-flink-checkpoints-init`) that exit immediately and never appear in a "running
  containers" snapshot.
- **`docker logs --since <plain integer>` — use epoch seconds, not a bare
  `date +%Y-%m-%dT%H:%M:%S`.** A no-offset ISO string is ambiguous about which
  timezone the Docker daemon should read it in; epoch seconds sidesteps the question.
- **The `var="$(cmd | grep ... | tail -1)"` trap under `set -e -o pipefail`.** A
  command-substitution assignment is NOT exempted from `errexit` the way an
  `if cmd; then` conditional is — if the piped command fails (e.g. `grep` finding no
  match), the whole script aborts on that line, silently, with no error message
  unless something downstream checks the exit code. This bit `faults/
  recover_taskmanager.sh` for real during development: an early version reported
  taskmanager recovery in ~0.6s, which was actually the script dying on the first
  no-match poll iteration, not a fast recovery — the jobmanager's own log showed the
  real `RESTARTING`→`RUNNING` transition happening about 21–23s later (heartbeat/RPC
  failure detection, then the configured 5s `restart-strategy.fixed-delay.delay`).
  Fixed with `|| true` on the assignment so an empty `$hit` falls through to the
  explicit `[ -n "$hit" ]` check where "did we find it yet" is actually supposed to
  be decided. Worth remembering for any future `recover_*.sh`.
- **Flink's per-task vertex status can read as `RUNNING` before recovery has even
  started.** The default `region` failover strategy can keep the *job-level* state at
  `RUNNING` throughout a task failure/restart, so polling `/jobs/overview` alone is
  not proof recovery completed — `recover_taskmanager.sh` instead greps the
  jobmanager's own log for the `RESTARTING`→`RUNNING` transition (or a
  checkpoint-recovery line), anchored to a timestamp captured before the fix, so a
  stale pre-fault read can't false-positive.
- **Kafka `USER` is a reserved word in Flink SQL (Calcite).** Every identifier in
  `flink_job.sql` is backtick-quoted for this reason, not stylistic preference.
- **Watermark closing needs a trailing buffer, not just a leading one.** A brute-force
  burst planted in the corpus's last usable tumbling window would depend on the
  *following* window containing an event within the 2s bounded-out-of-orderness
  margin to ever push the watermark past its boundary and fire — true in expectation
  at this corpus's density but not guaranteed. `gen_corpus.py` excludes the first
  window AND the last two (not just the last one) from burst/near-miss placement.

## Deviations from the literal task brief (declared, not silent)

1. **Flink SQL via the SQL Client, not PyFlink.** The brief named both as acceptable
   ("your call, pick what you can make WORK"). PyFlink's Python-Java bridge needs a
   Python interpreter version matched to the Flink image's bundled UDF runner — a
   second moving part to pin and debug for a single-host smoke pass. SQL via
   `sql-client.sh -f flink_job.sql` needs nothing beyond the connector jar already
   baked into the image. `streaming/flink_job.sql` + `streaming/submit_flink_job.sh`
   stand in for the named `streaming/flink_job.py`.
2. **`--limit` scales the corpus's SPAN, not just its event count.** The brief named
   `--limit` for the ~20k-event smoke corpus without fixing its semantics. Replay
   wall-clock time is governed by the corpus's event-TIME SPAN divided by the replay
   factor, not by event count — shrinking count alone over the full 7200s span
   wouldn't speed up a smoke replay at all. `--limit` scales span, burst/near-miss
   counts, and background population together by the same factor (floored at sane
   minimums), preserving event density. See `gen_corpus.py`'s docstring.
3. **`measure_latency.py`'s baseline is the window-close instant, not either arm's own
   `ingest_wall_ts` field.** batch's `ingest_wall_ts` is a whole FILE's landing time;
   streaming's is an individual event's production time — comparing them directly
   would compare two different reference semantics and unfairly flatter streaming.
   Both arms are instead measured against the wall-clock instant their window could
   first possibly have closed (see the module docstring for the full argument). This
   is an implementation decision in service of the pre-reg's own P4 language, not a
   deviation from it.

Nothing else diverges: the detection semantics (≥5 failures, 60s tumbling,
`(user, src_ip)` key), the answer-equality gate, and the three fault injections are
implemented exactly as specified.

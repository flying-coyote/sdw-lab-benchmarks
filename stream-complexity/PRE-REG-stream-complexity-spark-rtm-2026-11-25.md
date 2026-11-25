---
type: benchmark-spec
title: "PRE-REG: STREAM-COMPLEXITY v4, a Spark 4.3.0 Real-Time Mode arm on the v2 detection (batch vs Kafka+Flink vs Kafka+Spark RTM)"
status: pre-registered
created: 2026-11-25
frozen-at: "owed: the main session's commit of this file is the freeze; no frozen-at stamp, commit hash or .sha256 exists yet"
frozen-by: "agent-drafted on owner ruling 2026-11-25; NOT owner-reviewed line by line"
hypotheses: [H-STREAMING-02, H-IMPL-01]
evidence-tier: B
depends_on:
  - "[[PRE-REG-stream-complexity-risingwave-2026-11-07]]"
  - "[[RESULTS-v3-risingwave-2026-11-07]]"
  - "[[PRE-REG-stream-freshness-2026-11-06]]"
  - "[[PRE-REGISTRATION-LEDGER]]"
tags: [h-streaming-02, h-impl-01, stream-complexity, spark, real-time-mode, pre-registration, m6, pre-registered]
---

# PRE-REG: STREAM-COMPLEXITY v4, a Spark 4.3.0 Real-Time Mode arm (2026-11-25)

**Status: PRE-REGISTERED, not frozen-run, not run.** Written on the owner ruling of 2026-11-25 ("pre-register a Spark 4.3 Real-Time Mode arm of the STREAM-COMPLEXITY bench"). No container has been pulled, no harness file written and nothing run. Under methodology §12 the freeze is the commit that adds this file, before any scored run; that commit, a `frozen-at` stamp and a `PRE-REG-stream-complexity-spark-rtm-2026-11-25.sha256` beside it are owed by the main session, and the hash file gains the harness files once they exist and before the first scored run. The design was drafted by an agent and has not been reviewed line by line by the owner, which affects how much weight this pre-registration carries. Every number under Frozen predictions and every decision rule is fixed at that commit; a change afterwards is a dated amendment appended below the original text, recorded before the scored run it affects.

## Blocker (as of 2026-11-25, subject to change)

As of 2026-11-25 Maven Central has no Iceberg Spark runtime for Spark 4.3. The `org/apache/iceberg/` metadata on `repo1.maven.org` lists `iceberg-spark-runtime-4.0_2.13` and `iceberg-spark-runtime-4.1_2.13` at 1.12.0 (lastUpdated 2026-09-30), and the `iceberg-spark-runtime-4.2_2.13` and `iceberg-spark-runtime-4.3_2.13` metadata paths return 404; the Iceberg source tree carries a `spark/v4.2` module but no published jar, and nothing targets Spark 4.3.0. So a Spark 4.3.0 Real-Time Mode job can't write to an Iceberg table through a released runtime today, and this may change any week. Re-check before the build session with `curl -s https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-4.3_2.13/maven-metadata.xml`.

**The design does not wait for the runtime, and the choice is made for comparability.** None of the existing arms writes to Iceberg: B lands Parquet files and appends JSONL, S writes alerts to the Kafka topic `smx-alerts` and a drain consumer writes JSONL, and R served a subscription cursor. A Kafka alert sink drained to JSONL is therefore the like-for-like design, and an Iceberg sink would add a write path no other arm pays for. There is a second reason the blocker does not bind: the Spark 4.3.0 Real-Time Mode documentation allows only the Kafka, Foreach (`ForeachWriter`), Console and memory sinks, says `foreachBatch` is not supported, and fails other sinks with `STREAMING_REAL_TIME_MODE.SINK_NOT_SUPPORTED`. A 4.3 Iceberg runtime would not by itself give an RTM query an Iceberg sink. An Iceberg leg, RTM to Kafka followed by a separate micro-batch Iceberg writer, would test a different question (end-to-end freshness into the lake) and gets its own pre-registration once a runtime ships. If a runtime ships before this arm runs, nothing in this design changes.

## Why this bench, and why now

Spark 4.3.0 (release page sidebar dates it 2026-10-30) says "Real-Time Mode now supports stateful queries: streaming aggregation, `dropDuplicates`, and `transformWithState` run with end-to-end latency on the order of 100 milliseconds" (SPARK-58508, SPARK-58635, SPARK-57228), and removes the `@Experimental` annotation (SPARK-57281). That puts an aggregation-shaped detection on open-source Spark into the same latency class as Flink and the incremental engines, with no Databricks dependency, and the streaming-decision page and H-STREAMING-02's rewritten text both treat the choice as "Kafka + Flink or a single-system engine". A team already running Spark has a third option that the bench has never measured. The "~100 ms" figure is the project's own claim (Tier B for what the feature does, C for how well it works), and the lab harness already has the detection, the corpus, the answer-equality gate, the fault battery and the counting rules, so adding the arm is the cheapest honest test.

## Question

For the v2 detection outcome on the v2 events ("≥5 failed logins per (user, src_ip) within a 60-second epoch-aligned event-time tumbling window → alert" over the seed-20260719, 500,000-event synthetic OCSF-shaped auth corpus, 30 ground-truth alerts), what does a Kafka 4.3.1 + Spark 4.3.0 Real-Time Mode arm cost in moving parts, config surface, recovery effort and correctness, and platform dependence, against the freshness it buys, measured with the v2/v3 harness against freshly re-run batch and Kafka+Flink arms? A separately labelled dedup leg asks whether RTM's `dropDuplicates` suppresses injected duplicate deliveries.

## Arms

- **B, batch (unchanged from v2/v3)**: `batch/land_microbatches.py` + `batch/batch_job.py`, bare host Python, DuckDB 1.5.3. Re-run in every v4 trial.
- **S, streaming (unchanged from v2/v3)**: `apache/kafka:4.3.1` + `smx-flink-kafka:2.2.1` (Flink 2.2.1, connector 5.0.0-2.2), the v2 compose, SQL job and sink consumer; Flink checkpoint interval 10,000 ms (`streaming/docker-compose.yml:28`). Re-run in every v4 trial. The B and S code, compose and SQL are not edited, and RESULTS must confirm B 131 and S 197 LOC reproduce.
- **P, Kafka + Spark RTM (new)**:
  - **Image**: one container `smx-spark` built from `apache/spark:4.3.0-scala2.13-java21-python3-ubuntu` (Docker Hub, pushed 2026-11-05, compressed 808,736,627 bytes, amd64 digest prefix `sha256:19e80b60d4f4`, read 2026-11-25; the full index digest is recorded at pull and pinned in `spark/Dockerfile`, never a floating tag) plus `org.apache.spark:spark-sql-kafka-0-10_2.13:4.3.0` (confirmed on Maven Central 2026-11-25) and its transitive jars, fetched at build time and baked into a local image `smx-spark-kafka:4.3.0` exactly as S bakes its connector. Java 21, PySpark.
  - **Deploy**: Spark local mode (`--master local[4]`) in the one container, which is the smallest Spark there is, the same way R ran standalone. The RTM docs require cores equal to source reader tasks (one per Kafka partition; `smx-auth` has 1 partition, `streaming/init-topics.sh`) plus `spark.sql.shuffle.partitions` for a stateful query, and the default of 200 shuffle partitions cannot be scheduled here, so P sets `spark.sql.shuffle.partitions=2`; that line is counted in P's config LOC. AQE is off (the docs say RTM does not support it).
  - **Input**: P reads the S arm's broker and topic `smx-auth` with its own Spark-managed offsets (no shared consumer group), so B, S and P share one replay clock and one producer, which keeps the freshness comparison clean. Because the broker is shared at runtime, P's moving parts and config LOC count the Kafka service as P's own (below).
  - **Detection**: `withWatermark("event_time", "2 seconds")` (matching Flink's 2 s bounded out-of-orderness), `groupBy(window("event_time", "60 seconds"), "user", "src_ip").agg(count("*"))`, filter `count >= 5`, `outputMode("update")` (the only output mode RTM accepts), `.trigger(realTime="10 seconds")` so the RTM checkpoint interval matches Flink's 10 s, `checkpointLocation` on the named volume `smx-spark-checkpoints`. RocksDB state store and checkpoint format v2 are RTM's automatic defaults and are recorded, not set.
  - **Output**: the Kafka sink to topic `smx-alerts-spark`, created by P's own `spark/init-topics.sh` (counted in P's LOC; S's `init-topics.sh` is not edited), drained by `spark/consume_alerts_spark.py`, a copy of S's drain with the topic and output file (`alerts-spark.jsonl`) changed. The drain dedups on `(user, src_ip, window_start)` like S's, and is an adapter: counted in engine + sink units and excluded from config LOC under July's frozen rule.
- **R (RisingWave v3.1.1) and F (Feldera 0.375.0) are not re-run.** Their numbers are cited from `RESULTS-v3-risingwave-2026-11-07.md` and `RESULTS-v2-2026-11-03.md` with their dates, never pooled with v4 trials. They ran before chrony (methodology §7a), so their absolute durations carry a clock error of unknown sign, and any freshness comparison with them says so.

**What `update` mode changes, frozen before any prediction.** In update mode a windowed count emits a row when the count first reaches 5 and again on each later qualifying event in the same window, before the window closes. Three consequences are fixed here:
1. P's alert is *non-final* at emission. Because the input is append-only and a count can only grow, an early emission cannot be a false positive, but a late event dropped by the watermark could leave a window short; answer equality decides.
2. **Update re-emissions** (rows for a key the engine has already emitted, during the same run) are counted and reported separately and are not duplicates. **Raw engine duplicates** are rows the Kafka sink re-delivers after a recovery (the docs say the Kafka sink is at-least-once), identified as a re-emitted row whose count value is not greater than one already seen for that key.
3. Freshness from window close can be negative for P, so a second baseline is added for every arm (Measures, item 6).

**Answer-equality gate (three arms, unchanged in kind):** on every clean scored trial B, S and P each produce 30/30 distinct alerts matching the independent ground truth (missing 0, extra 0, duplicates 0 in the file) and are pairwise identical. No number is quoted from a trial whose answers diverge, until the divergence is explained and fixed.

## Dedup leg D (separately labelled, P only, a demonstration)

The harness has no dedup-shaped *detection*; dedup exists only in the drain adapters and the batch job. Rather than invent one silently, this leg is scoped as a separate, labelled demonstration of RTM's `dropDuplicates`, and it is never pooled with the W results.

- **Corpus**: the IOC-planted corpus from the freshness bench (`freshness/plant_ioc.py`, 30 successful logons from 30 TEST-NET-3 addresses, `ioc_ground_truth.json`). Gate before any D run: `plant_ioc.py`'s self-checks pass and the W ground truth on the planted corpus equals the base 30 alerts.
- **Injected duplicates**: a P-only replayer flag re-sends each of the 30 IOC events a second time with the same `event_uid` and event time, at a seeded wall offset of 0.5 to 3.0 s after the original. IOC events are successes from dedicated addresses, so the duplicates can't create or break a failure window. They are written to a separate topic `smx-auth-dup` so that S and B never see them.
- **Query**: a second Spark application (the RTM docs say to run one RTM query per cluster) in its own container `smx-spark-ioc`, run in its own trials and not counted in W's moving parts: `src_ip.isin(<30 literals>)` (stateless filter; the freshness bench's Flink side used a 30-row table join, and an `isin` list avoids a broadcast join), then `withWatermark("event_time", "10 seconds").dropDuplicates(["event_uid", "event_time"])` (`dropDuplicatesWithinWatermark` is not supported in RTM), Kafka sink to `smx-ioc-spark`.
- **Reported as "N of 30 injected duplicates suppressed"** under methodology §11 question 3, since the injected duplicates are the only duplicates, never as a dedup rate. Also reported: 30/30 IOC alerts (missing, extra), and event-to-alert p50 at 1×.

## What was verified on 2026-11-25, and what wasn't

Verified (ASF release notes and docs, Tier B for what the feature does, never for how well it works):

| Item | Finding | Source |
|---|---|---|
| Stateful RTM | streaming aggregation (including `window(...)`), `dropDuplicates` and Scala/Java `transformWithState` supported in RTM from 4.3.0; `@Experimental` removed (SPARK-57281) | spark.apache.org/releases/spark-release-4-3-0.html |
| Not supported in RTM | stream-stream joins, `flatMapGroupsWithState`, `dropDuplicatesWithinWatermark`, session windows, distinct aggregates, PySpark `transformWithState`, AQE | spark.apache.org/docs/4.3.0/streaming/real-time-mode.html |
| Sources and sinks | Kafka source; Kafka, Foreach, Console and memory sinks; `foreachBatch` not supported | same |
| Requirements | `update` output mode only; `checkpointLocation` required; trigger duration is the checkpoint interval, minimum 5 s (`spark.sql.streaming.realTimeMode.minBatchDuration` 5000 ms); cores = Kafka partitions + shuffle partitions; one RTM query per cluster; Kafka sink at-least-once | same |
| Connector | `spark-sql-kafka-0-10_2.13:4.3.0` on Maven Central | repo1.maven.org metadata, 2026-11-25 |
| Image | `apache/spark:4.3.0-scala2.13-java21-python3-ubuntu`, pushed 2026-11-05 | Docker Hub API, 2026-11-25 |

Not verified, carried as open items (each settled at smoke, and a change to the design is a dated amendment before scoring):
- that RTM runs under `--master local[N]`; the docs speak of clusters and cores. If it does not, the fallback is a single-node standalone master and worker in the same container, which changes P1's process count and needs an amendment before any scored run;
- that a filter after the aggregation (`count >= 5`) passes RTM's allowlist check (`spark.sql.streaming.realTimeMode.allowlistCheck`);
- that the connector's bundled `kafka-clients` reads from the Kafka 4.3.1 broker (stop rule 4);
- that a PySpark entrypoint resubmitting the query after `docker start` restores from the checkpoint with no operator step (P1's predicted 1 step).

## Hardware and clock

The Beelink (Ryzen 7 5800H, Docker Desktop on WSL2), the same host as July, v2, v3 and the freshness sweep. The WSL2 memory and thread allocation, Docker Desktop version and Windows power plan are recorded at run time by `../env_characterize.py`, not restated from memory. RESULTS carries a §7b rig stamp. Clock gate: chrony running, `chronyc tracking` `System time` offset under 10 ms before every scored trial, and `v3/clock_watch.py` running for the whole trial.

## Versions

| Component | Version | Pin |
|---|---|---|
| Spark | 4.3.0, Scala 2.13, Java 21, Python 3 | `apache/spark:4.3.0-scala2.13-java21-python3-ubuntu`, digest recorded at pull |
| Spark Kafka connector | `spark-sql-kafka-0-10_2.13:4.3.0` | baked at build |
| Kafka | 4.3.1 (shared with S) | as v2 |
| Flink | 2.2.1, connector 5.0.0-2.2 | as v2 |
| DuckDB | 1.5.3 | `requirements.txt` |
| Host Python deps | as `requirements.txt` | pinned 2026-07-19 |

## Harness

The v3 harness, with only additions for P: a v4 trial runner (B, S, P on the shared replay clock, from `v3/run_trial_v3.sh`), P's container and process patterns in `v2/sampler.py`, P's file list in `v2/measure_complexity_v2.py`, P1 in `v2/faults_v2.py`, and a scorer `v4/score_v4.py`. Moving-parts inclusion rule unchanged: generator, replayers and ground-truth checker are harness; **engine-only** and **engine + sink adapter** units are both reported, as median and max of the 10 s mid-run samples. **P's config LOC** counts `spark/Dockerfile`, `spark/docker-compose.yml` (the Spark service), `spark/init-topics.sh`, the PySpark job, and the Kafka share of S's deployment, sliced by a frozen rule: in `streaming/docker-compose.yml`, the `name`, `networks` and `smx-kafka-data` volume declarations (lines 10 to 18), the `services:` key, and the `smx-kafka-data-init`, `smx-kafka` and `smx-topic-init` service blocks (lines 42 to 101), plus S's `streaming/init-topics.sh` in full, because a P-only deployment needs the broker, its volume fixup and the `smx-auth` topic. Counted on 2026-11-25 with July's `count_loc` rule (non-blank, non-comment): 7 + 1 + 8 + 34 + 11 = **61 compose LOC**, plus **7** for `init-topics.sh`, so the **Kafka slice is 68 LOC**, fixed here as a constant. The scorer recomputes it and prints it beside P's total; if the recount differs from 68, that is a deviation to explain.

## Fault battery

Full 500,000-event corpus at 20×, kill at event-time minute 45 (replay start + 135 s), 30 wall-seconds held, then the recover script and a post-recovery answer-equality check over the full corpus, as in v2/v3. B and S faults are not re-run; their v2 rows are cited.

| ID | Arm | Fault | Frozen operator rule after recovery |
|---|---|---|---|
| P1 | P | `docker kill smx-spark` | Step 1: `docker start smx-spark`; the container's entrypoint resubmits the job, which restores state and Kafka offsets from `checkpointLocation`. Kafka retained the input, so there is no rewind step. The drain consumer reconnects through its own retry code (adapter, not an operator step). |

Scored as in v2/v3: operator steps (from `# Step N:` markers in `faults/recover_p1.sh`), recover-script wall, kill to infrastructure restored, kill to first new correct alert, post-recovery missing / extra / duplicates in the file, raw engine duplicates (definition above), update re-emissions, and whether the output file exists and grew after recovery. n=1; step counts are deterministic and wall-clock figures single observations.

## Measures

The v2/v3 measures applied to P: (1) moving parts; (2) config surface under July's frozen LOC rule plus the Kafka slice above; (3) recovery per the battery; (4) answer equality; (5) platform dependence under v2's frozen rubric (a single-vendor-controlled components, b paid-gated features needed for recovery parity with S2, c engine-specific detection lines as a share of detection LOC, d image source, e a plain lock-in note); and (6) freshness, with two baselines for every arm:
- **window close to alert**, the v2/v3 baseline (continuity; negative allowed for P);
- **knowable to alert**, from the scheduled replay time of the event that first makes the window qualify (the 5th failure for that key in that window) to the alert landing in the arm's output file. This is the baseline that tests the RTM latency claim, and it is computable for every arm from the corpus and the output files.

Freshness is scored at **1× only**, three trials (median and CV of trial medians), because poll intervals and replay pacing are wall-clock and the claim is sub-second; three 20× trials are run for the complexity axes and their freshness is reported for continuity, never scored. Freshness is reported with the cost, never alone.

## Frozen predictions

Baselines from `results/RESULTS-v3-risingwave-2026-11-07.md` (pre-chrony): engine + sink units B 1, S 4, R 2; containers B 0, S 3, R 1; config LOC B 131, S 197, R 76; recovery steps S1 2, S2 2 (S total 4), R1 3; S2 kill to first new correct alert 39.05 s; window-close p50 at 1× S 2.167 s, R 5.441 s. From the freshness sweep (2026-11-06, also pre-chrony): S IOC event-to-alert p50 0.01 s.

- **P1 moving parts.** P runs **2 containers** (Kafka, Spark), **2 engine-only units** and **3 engine + sink units**, with **2 to 3 processes** inside `smx-spark` (the JVM and the Python driver). The Spark image's `.Size` is **1.3 to 2.5 GB**.
- **P2 config surface.** P lands at **115 to 150 LOC**: the fixed 68-LOC Kafka slice plus 47 to 82 LOC of P's own files (Spark compose service 12 to 18, Dockerfile 5 to 8, P's `init-topics.sh` about 6, PySpark job 25 to 50). Below S's 197, above R's 76.
- **P3 recovery.** P1 takes **1 step**, kill to first new correct alert **under 75 s** (30 s hold, JVM and Python start, state restore), post-recovery **30/30 with 0 missing, 0 extra and 0 duplicates in the file**, raw engine duplicates **0 to 5**, output file exists and grows after recovery. Structural: P1 needs **fewer steps than R1 (3) and no more than S2 (2)**, because Kafka retains the un-checkpointed input, as it does for Flink, and the restart resubmits the query.
- **P4 freshness at 1×.**
  - P knowable-to-alert p50 **0.05 to 0.5 s**.
  - S knowable-to-alert p50 **12 to 35 s**, and every S alert at least 7 s. Derivation: `gen_corpus.py` (lines 162 to 179) plants each true burst as 5 to 8 failures at distinct offsets drawn from 2 to 55 s into the window, so the 5th failure lands at offset 6 to 55 s (around 25 to 48 s at the median across burst sizes), and S alerts about 2.2 s after the close, giving (60 − offset) + 2.2. B is larger than S by its poll wait.
  - P window-close-to-alert p50 **between −35 and −10 s** on every trial (P emits at the 5th failure, so the mirror of the same offsets).
  - S window-close-to-alert p50 **1.8 to 2.6 s** (v3 2.167 s, freshness sweep 2.16 to 2.18 s).
- **P5 equality.** 30/30, pairwise identical across B, S and P, on all three 20× and all three 1× trials.
- **P6 platform dependence.** P scores **0**: no single-vendor-controlled component (Spark and Kafka are ASF projects) and no paid-gated feature needed for recovery parity (RTM and RocksDB state are in open-source Spark 4.3.0). Engine-specific detection lines **at least 3** (`trigger(realTime=…)`, `withWatermark`, `outputMode("update")`).
- **Leg D.** **30 of 30** injected duplicates suppressed (0 duplicate IOC alerts out of the engine), 30/30 IOC alerts, event-to-alert p50 at 1× **0.05 to 0.5 s**.
- **Update re-emissions** on W are reported, not predicted.

## Predicted confidence delta (frozen; the v3 block froze none and the ledger requires one)

**H-STREAMING-02: predicted 0, HOLD at 3.5/5.** This arm does not re-measure RisingWave, so it cannot raise a RisingWave-specific claim under any outcome; what it can do is show that the reduction the hypothesis credits to "a single streaming database" is available to a broker-plus-engine shape a Spark team already runs. On the predictions above, P lands within 1.25× of R on one complexity axis at most (units 3 vs 2 = 1.5×; LOC 115 to 150 vs 76 = 1.5× to 2.0×; steps 1 vs 3, which is the one axis where P is at or below R), so the downgrade rule below should not fire and the expected outcome is HOLD with a context block.

**H-IMPL-01: context only, no move under any outcome**, as in v3. If P lands within 1.5× of B on two or more complexity axes, that is a third streaming arm narrowing the infrastructure premium and is recorded as context.

## What each result would mean (frozen decision rules)

"Complexity axes" means the three v2 axes: engine + sink units, config LOC, and recovery steps summed over the arm's faults (P: P1; S: 4 from v2; R: 3 from v3).

- **H-STREAMING-02, downgrade candidate (−0.5, to 3.0/5, at the gate).** All of these hold:
  - P is at or below 1.25× R on at least two of the three complexity axes;
  - P's 1× knowable-to-alert p50 is at or below R's 1× window-close p50 (5.441 s, pre-chrony, which is the only R freshness figure there is, and the comparison says so);
  - P1 reaches 30/30 with 0 missing and 0 extra.

  That would mean the simplification is not specific to RisingWave or to single-system design, and the hypothesis text gets rescoped to "against Kafka + Flink". The move happens only after the karen → hypothesis-validator → contradiction-detector gate and the owner's ruling.
- **HOLD (predicted).** Anything else in which P1 reaches 30/30. A context block records P's per-axis numbers against S and R.
- **Spark RTM does not simplify against Flink (context, HOLD).** P at or above S on two or more complexity axes: the hypothesis's Kafka + Flink baseline stands as the relevant comparison for a broker-plus-engine shop, and the streaming-decision page's Spark branch gets that number.
- **RTM fails the claim (context, HOLD, reported as a finding).** P's 1× knowable-to-alert p50 above 1.0 s on every trial, or P1 cannot reach 30/30 under the frozen rule.
- **Answer-equality failure** on any arm voids that arm's numbers for that trial, with no partial quoting.

## Stop rules

1. **Clock.** A `chronyc tracking` offset of 10 ms or more before a trial, or any wall-clock step over 100 ms logged by `clock_watch.py` during it, voids that trial. Two voided re-runs in a row stop the run until the clock is fixed.
2. **RTM refuses the query.** If Spark rejects the detection with any `STREAMING_REAL_TIME_MODE.*` error, the run stops and the error is recorded verbatim. Fixes inside the documented RTM surface (shuffle partitions, trigger duration at or above 5 s, checkpoint settings) are allowed with a dated amendment. There is no silent fallback to a micro-batch trigger; a micro-batch Spark arm is a new pre-registration.
3. **Equality in smoke.** If smoke trials fail answer equality, at most three harness-fix iterations, each a dated note, then stop and report.
4. **Client and broker compatibility.** If the connector's bundled `kafka-clients` cannot read from Kafka 4.3.1, stop; no broker change, because S's broker is fixed.
5. **Host contention.** If the 10 s sampler shows host CPU above 90% at the median during a 20× trial with B, S and P concurrent, the remaining trials run P and S in alternating trials on the same replay schedule, declared as a deviation, and freshness comparisons are then labelled cross-trial.
6. **Budget.** If the build exceeds four sessions, stop and report what is blocking.

## Run budget and cost

Cloud cost **$0** (one host, open images). Disk: about 0.8 GB compressed Spark pull (797 GB was free on 2026-11-07; recheck).

| Phase | What | Estimate |
|---|---|---|
| Freeze | commit this file, `frozen-at`, `.sha256` (main session) | under 1 session |
| Build P | Dockerfile with baked connector, compose service, init-topics, PySpark job, drain copy, `recover_p1.sh`, the D-leg replayer flag and second app | 2 to 3 sessions |
| Harness additions | v4 trial runner, sampler patterns, LOC file list plus Kafka slice, P1 in `faults_v2.py`, knowable-to-alert in the scorer | 1 session |
| Smoke | one throwaway 100× trial, one P1 smoke confirming the output file exists and grows after recovery, one D smoke | 1 session |
| Scored runs | three 20× trials at about 8 min each, P1 at about 10 min, three 1× trials at about 2 h 15 min each unattended, two D trials at 1× | about 1.5 h attended + about 11 h unattended |
| Score and write | RESULTS with rig stamp, ledger row, gate pass, then site and book wording only after the gate | 1 to 2 sessions |

## Threats to validity

- **Single host, single node, everything.** Spark local mode is the smallest Spark there is and flatters P on moving parts the way standalone mode flattered R and the containerless design flatters B; RESULTS says so beside the P1 table. A production Spark cluster (driver, executors, a cluster manager) is not what runs here.
- **Shared broker.** P and S read one Kafka broker at runtime. That keeps the input clock identical but means a broker fault would hit both, so no broker fault is run for P, and P's broker LOC is the slice of S's compose, not an independent deployment.
- **Update versus emit-on-close semantics.** P alerts before the window closes; S and R alert at close. That is a real behavioural difference a SOC would care about (an alert that can still grow), and the knowable-to-alert baseline is there so it isn't scored as raw speed alone.
- **Synthetic seeded corpus, one detection shape plus one demonstration leg.** No joins (RTM in 4.3.0 does not support stream-stream joins), no sessionization, no Python `transformWithState` (Scala/Java only in 4.3.0).
- **Mixed-date and mixed-clock comparison.** R and F are pre-chrony and are cited, not re-run; every cross-run comparison names its source run.
- **Edition and vendor framing.** This arm tests the Apache Spark 4.3.0 release only and says nothing about any vendor's managed Spark.
- **Author runs and scores the bench**, on a page (streaming-decision) whose recommendation branch is being rewritten in the same week. The pre-registration is the main protection.
- **Out of scope:** dollars, headcount, on-call load, multi-host, Databricks, an Iceberg sink (see Blocker), serving-query latency, the Python state API.

## Honesty boundaries (carried into any RESULTS.md verbatim)

Single host, Docker Desktop/WSL2, synthetic seeded corpus (injection-surface boundary: no real telemetry), ONE detection shape plus one labelled dedup demonstration, single-node every arm. Kafka 4.3.1 + Flink 2.2.1 as the canonical streaming stack and Kafka 4.3.1 + Apache Spark 4.3.0 Real-Time Mode in local mode as the Spark arm, which is the smallest Spark deployment and not a production cluster. No arm writes to Iceberg, and no Iceberg Spark runtime for 4.3 existed when this was written. Complexity and dependence proxies are not dollars, headcount, or on-call burden. Assumption under test: open-source Spark's stateful Real-Time Mode gives a Spark team aggregation-shaped detection at Flink-class latency with less configuration than Kafka + Flink and without a paid-gated feature.

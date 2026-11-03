---
type: benchmark-spec
title: "PRE-REG DRAFT: STREAM-COMPLEXITY v2, batch vs Kafka+Flink vs Feldera (OSS) on the July detection"
status: frozen
created: 2026-11-03
hypotheses: [H-IMPL-01, H-STREAMING-02]
evidence-tier: B
depends_on:
  - "[[H-IMPL-01-stream-complexity-verdict-DRAFT-2026-11-03]]"
  - "[[feldera-medallion-architecture-2026-11-03]]"
  - "[[PRE-REGISTRATION-LEDGER]]"
tags: [h-impl-01, stream-complexity, feldera, dbsp, incremental-view-maintenance, pre-registration, m6, edition-bound, draft]
---

# PRE-REG DRAFT: STREAM-COMPLEXITY v2 (batch vs Kafka+Flink vs Feldera), 2026-11-03

**Status: DRAFT, not frozen.** Nothing has run, no container has started, and the lab repo was only read. This block becomes a frozen pre-registration only when the owner un-parks `~/sdw-lab-benchmarks` and it is copied, unchanged except for the version pin and freeze date, into `~/sdw-lab-benchmarks/stream-complexity/PRE-REG-stream-complexity-feldera-<freeze-date>.md` before any scored run. Under M6 a smoke test to make the harness work is not a scored run, but every number in the Predictions section is frozen at that copy and does not change afterwards; a design change after freeze needs a new dated block that says why.

## Why this is a new block and not a re-run of 07-19

The 2026-07-19 pre-registration is exhausted, and I want that on the record before anything else so this does not read as a quiet reinterpretation of it. Its move condition needed P1 through P3 to hold, P2 (config surface) was frozen at ≥3× and came in at 1.50× (197 vs 131 LOC), and a frozen threshold that already failed cannot be rescued by fixing the fault harness and re-running P3 (`02-projects/H-IMPL-01-stream-complexity-verdict-DRAFT-2026-11-03.md`, section (a)). The owner kept H-IMPL-01 in rotation on 2026-11-03 with the next step named as "the same detection on Feldera against the July batch arm," so this block does three things the old one could not: it adds a third arm, it fixes the five harness flaws the adjudication found, and it adds a fifth axis (platform dependence) to test a specific refinement of the hypothesis.

The refinement under test, stated so it can fail: *managed or incremental-view-maintenance engines do not remove the streaming complexity premium so much as move it out of the running infrastructure and into platform dependence*, meaning licence gating, single-vendor control and non-portable dialect. If Feldera shrinks the premium on the infrastructure axes and the parity features it needs turn out to be open, the refinement is wrong and the premium is genuinely reduced.

Target hypotheses: H-IMPL-01 (Streaming Architecture Hidden Costs, 1/5, evidence level magnitude D / direction B per the 11-03 adjudication) and, adjacently, H-STREAMING-02 (RisingWave cuts streaming complexity), which is the same claim class and gets Feldera as a second data point rather than a score change.

## Question

For the same detection outcome on the same events ("≥5 failed logins per (user, src_ip) within a 60-second epoch-aligned event-time tumbling window → alert" over the seed-20260719, 500,000-event synthetic OCSF-shaped auth corpus), what does each of three arms cost in moving parts, config surface, recovery effort and correctness, and platform dependence, against the freshness it buys, when recovery correctness and freshness are measured properly this time?

## Arms

- **B, batch (July arm, unchanged)**: `batch/land_microbatches.py` lands one Parquet file per 60 event-seconds; `batch/batch_job.py` (bare Python process, DuckDB, poll loop) appends to `alerts-batch.jsonl`. Zero containers by design.
- **S, streaming (July arm, unchanged)**: `apache/kafka:4.3.1` (single KRaft broker) + `smx-flink-kafka:2.2.1` (Flink 2.2.1 jobmanager + one taskmanager, checkpointing on, `flink-sql-connector-kafka` 5.0.0-2.2), Flink SQL TUMBLE job with `WATERMARK ... - INTERVAL '2' SECOND`, alerts to topic `smx-alerts`, drained by `consume_alerts.py`.
- **F, Feldera (new arm)**: one `pipeline-manager` container from the Feldera open-source edition, version pinned at freeze (current release v0.375.0, published 2026-11-02; releases are near-daily, so `FELDERA_VERSION` must be an exact tag, never `latest`). One SQL program: an `append_only` table `auth_events` with `LATENESS INTERVAL '2' SECONDS` on the event-time column (matching Flink's 2 s watermark), and a view that groups by `(user, src_ip, TUMBLE window)` with `HAVING COUNT(*) >= 5`. Input arrives by the pipeline's **HTTP ingress** endpoint, fed by a replayer that shares the July pacing code and `--replay-start-epoch`. Output is read from the view's HTTP egress stream by a drain consumer into `alerts-feldera.jsonl`.

- **BC, containerised batch (new arm, added at freeze by owner ruling 2026-11-03)**: the same
  `batch/land_microbatches.py` + `batch/batch_job.py` code as B, packaged in one container
  (`python:3.12-slim` base, DuckDB pinned to the July version, restart policy `on-failure`) with a
  compose file. It answers the objection that B wins moving parts by being containerless. B stays
  exactly as in July for comparability; BC is a robustness check, not a replacement.

Three design decisions for F, each fixed here with its reason:

1. **No broker in the F arm.** HTTP ingress keeps the arm what the Feldera capture describes, SQL-only incremental compute with no broker or cluster in the path. This removes Kafka's durable buffer, so F's recovery depends on the source being able to re-send, and that trade is part of what is under test rather than a harness shortcut. A Feldera-reads-Kafka sub-arm would mix the engine swap with the broker question, so it is out of scope here and can be its own pre-registration later.
2. **Output semantics.** Feldera views emit insert/delete updates by default, so a `HAVING COUNT(*) >= 5` view would emit at 5 and then retract and re-emit at 6 and 7, which the July gate would score as duplicates. **Primary:** mark the view `emit_final` on the window-start column, so a row is only emitted once the waterline passes it. The docs call `emit_final` experimental, and say compilation fails if a waterline cannot be inferred for that column, which the time-series page does not confirm for TUMBLE's window column. **Fallback, only with a dated note in RESULTS:** consume the insert/delete change stream and score the final state per key at drain time, and report that the F arm needed the fallback (that need is itself a config-surface and dialect finding).
3. **Edition.** The bench runs the **open-source edition** (MIT). The F arm is labelled **EDITION-BOUND** in every table that carries its recovery numbers, per the repo's edition-bound benchmarking rule, because the feature that would make its recovery comparable to Flink's checkpoint restore is gated (next section).

**Answer-equality gate (unchanged from July, extended to three arms):** on every clean scored trial, B, S and F must each produce 30/30 distinct alerts matching the independent ground truth (missing 0, extra 0, duplicates 0) and be pairwise identical. No complexity, recovery or dependence number is quoted from a trial whose answers diverge, until the divergence is explained and fixed.

## Feldera edition: what was verified on 2026-11-03, and what the OSS edition cannot do

Verified (sources read 2026-11-03; vendor-authored, Tier C as claims, used here only for what the product ships):

| Item | Finding | Source |
|---|---|---|
| Licence | "OPEN-SOURCE EDITION - MIT LICENSE ... applies to all parts of the Feldera project except for Feldera Enterprise code"; Enterprise code is "gated behind the `feldera-enterprise` feature flag or documented as Enterprise-only" and needs a valid licence under the Feldera Terms of Service | `github.com/feldera/feldera` LICENSE (GitHub API reports `NOASSERTION` because the file is dual-section) |
| Checkpoint and fault tolerance | "Checkpoints & fault tolerance features are only available in Feldera Enterprise Edition." Enterprise offers `at_least_once` and `exactly_once` modes; default checkpoint interval 60 s; HTTP and Kafka inputs support both modes | docs.feldera.com/pipelines/fault-tolerance |
| Other Enterprise-only features | multi-node clusters, pipeline and control-plane fault tolerance, pipeline resource isolation, scale-out ("coming soon"), dedicated support; one-pipeline-per-pod on Kubernetes, resource limits, Kubernetes secrets / IAM / OIDC auth, checkpoint-resume-resize, sidecars, Prometheus metrics and logs | docs.feldera.com/get-started/enterprise, /architecture/enterprise |
| Licence key | "Using Feldera Enterprise requires a license key," obtained through sales | docs.feldera.com/get-started/enterprise |
| Docker image | `images.feldera.com/feldera/pipeline-manager:${FELDERA_VERSION:-latest}`, port 8080, described as "suitable for demos, development, and testing" | deploy/docker-compose.yml, docs.feldera.com/get-started/docker |
| Image weight | amd64 manifest of `ghcr.io/feldera/pipeline-manager:0.375.0`: 27 layers, **2,559,051,848 bytes compressed**. This is a lower bound on footprint, not the footprint; July's figures are uncompressed `docker image` sizes, so F's uncompressed size is measured at run time and only that number goes in the moving-parts table | ghcr.io registry manifest, read 2026-11-03 |

So the OSS F arm, as run here, **cannot** checkpoint, resume from a checkpoint, restart itself automatically, give at-least-once or exactly-once recovery, run multi-node, or isolate pipeline resources. A killed OSS pipeline loses its in-memory window state and comes back empty, and correct output after a crash depends on the operator re-sending input. That is the edition boundary this bench measures inside, and no F recovery number may be generalised to "Feldera" without the edition label.

Not verified, carried as open items:
- whether the Feldera Terms of Service carry a benchmark-publication (DeWitt-class) clause for Enterprise use; the MIT OSS edition carries none, so publishing OSS numbers seems clear, but an Enterprise eval licence would need publication rights negotiated alongside it;
- whether Prometheus metrics are actually gated in the OSS image, since the architecture page lists them as Enterprise while the OSS compose file ships a `prometheus` service;
- the uncompressed image size, and whether `images.feldera.com` and `ghcr.io` serve the same digest for a given tag (check at pin time).

**Edition probe (pre-registered, cheap, first-party):** after the F pipeline compiles, attempt to enable fault tolerance on the OSS image (`fda set-config <pipeline> fault_tolerance at_least_once`, or the equivalent REST config), start the pipeline, and record the response or refusal verbatim into `results/edition-probe.json`. This turns "the docs say it is gated" into an observed fact. If the OSS image accepts and honours the setting, that is a surprise that changes the dependence score and gets reported as such.

## Harness fixes (the five flaws the 11-03 adjudication found)

1. **Recovery correctness by replaying the lost window.** Every fault now ends with a post-recovery answer-equality check over the full corpus, after a per-arm rewind rule that is frozen below. The July fault runs came back with the output file absent on all three injections (`exists: False`, 0 rows); the adjudication did not verify the mechanism and I have not either, so this block does not assert a cause. The smoke run must confirm, for each fault, that the arm's output file exists and grows after recovery before any scored fault run.
2. **Freshness on a real-time clock.** In addition to the three 20× trials, one full-corpus trial runs at replay factor 1 (event time = wall time), all three arms concurrently, n=1, labelled as such. July's latency files note that only batch's latency is replay-factor dependent, but F's behaviour at 1× vs 20× event rate is unmeasured, so neither direction is extrapolated.
3. **Moving parts sampled mid-run.** A sampler runs every 10 s through each scored trial and records per arm: running containers (`docker ps`), processes inside each container (`docker top`), and host processes matched by a frozen per-arm pattern list. Reported as median and max across samples, never from an end-of-run snapshot. Inclusion rule, applied identically to all three arms: the corpus generator, the paced replayers/producers and the ground-truth checker are harness and excluded; two counts are reported, **engine-only** (broker, engine, scheduler, job process) and **engine + sink adapter** (adds the drain consumer that moves alerts to a file, which S and F both need and B does not).
4. **At least one batch-side fault.** B gets two new batch-specific faults on top of July's process kill (below), so the recovery comparison no longer only tests the faults where streaming is expected to look worse.
5. **Redundancy limits stated.** Kafka runs as one KRaft broker, Flink as one jobmanager and one taskmanager, Feldera as one OSS pipeline-manager, batch as one process. No arm has a peer to fail over to, so nothing here measures replication, leader election, ISR catch-up, HA jobmanager or multi-host recovery, and the hypothesis's "higher infrastructure redundancy" clause gets no evidence from this bench in either direction.

## Fault battery and per-arm rewind rules

Every fault runs on the **full 500,000-event corpus** at 20× (not July's 5,000-event / 3-alert fault corpus), with the kill landing at **event-time minute 45** (base_epoch + 2,700 s) and a held outage of **30 wall-seconds** (600 event-seconds at 20×) before recovery starts. Minutes 20 to 60 are the densest alert range in the ground truth (7 + 7 alerts in the 20–40 and 40–60 minute blocks), so the outage window spans planted bursts. Each fault runs once (n=1); step counts are deterministic, wall-clock figures are single observations and are reported that way.

| ID | Arm | Fault | Frozen operator rewind rule after recovery |
|---|---|---|---|
| S1 | S | `docker kill smx-kafka` | producer pauses on send failure and resumes from the first event not acknowledged by the broker; nothing else re-driven |
| S2 | S | `docker kill smx-taskmanager` | nothing re-driven by the operator; Flink restores from the last checkpoint and re-reads the topic from the checkpointed offsets |
| B1 | B | SIGKILL `batch_job.py` mid-tick (July fault) | nothing re-driven; files persist and the job's state file plus rebuild-from-output fallback reprocess the interrupted tick |
| B2 | B | **late file**: the micro-batch file for the minute-45 window is held back and lands only after the job has processed the next two ticks | nothing re-driven; the question is whether the job picks up the late file and emits that window's alert at all |
| B3 | B | **truncated file**: the minute-45 file is written half-length (non-atomic write), then replaced with the complete file 30 wall-seconds later | operator steps are whatever it takes for the job to process the complete file (zero if it retries, otherwise the documented manual steps, counted) |
| F1 | F | `docker kill` the pipeline-manager container | restart the container; restart the pipeline (recording whether it recompiles); compute the rewind point from the **replayer's** last event time that Feldera's ingress acknowledged (`last_acked`), not from the drain consumer, because windows below threshold emit nothing and the last alert can sit many windows behind the waterline. Rewind point = start of the epoch-aligned 60 s window containing (`last_acked` − 2 s lateness), i.e. the oldest window still open; re-send from there to the current replay position, then resume live pacing. Computing the rewind point counts as an operator step |
| F2 | F | SIGKILL the pipeline process inside the container, leaving the manager up | same rewind rule as F1, minus the container restart |

Scored per fault: operator steps (counted from `# Step N:` markers in each `recover_*.sh`, as July did), wall-clock from kill to the arm emitting a new correct alert, wall-clock to infrastructure restored (July's measure, kept for comparison), and post-recovery correctness against the 30-alert ground truth as **missing**, **extra** and **duplicates** separately. Flink's Kafka sink in the July job is non-transactional, so duplicates after S2 are a legitimate expected finding about the arm, not a harness bug, and the July compare script already counts them. If F2 cannot isolate the pipeline process inside the OSS container, F2 is dropped with a dated note rather than substituted.

## Measures (five axes plus the benefit side)

1. **Moving parts**: containers, processes (engine-only and engine + sink adapter, median and max of mid-run samples), distinct images, and uncompressed image bytes per arm.
2. **Config surface**: LOC under July's frozen inclusion rule in `measure_complexity.py` (non-blank, non-comment, docstrings stripped; buckets compose_orchestration, engine_config, job_and_scheduler; harness excluded). For F: the compose service, the SQL program, the pipeline/connector config, and the deploy script.
3. **Recovery**: steps, time and correctness per the battery above.
4. **Answer equality**: 30/30 on every clean trial, all three arms, pairwise identical.
5. **Platform dependence (new)**, scored per arm with this frozen rubric:
   - **(a)** components that are single-vendor controlled vs foundation-governed (DuckDB is MIT with IP held by the DuckDB Foundation; Kafka and Flink are Apache-2.0 under the ASF; Feldera's MIT core and Enterprise code are both controlled by Feldera, Inc.);
   - **(b)** features required for *recovery parity with S2* (automatic restore of window state without operator re-send) that sit behind a paid licence;
   - **(c)** engine-specific SQL constructs in the detection (Flink's `WATERMARK FOR` and TUMBLE TVF; Feldera's `LATENESS`, `emit_final`, `append_only`; DuckDB's floor-division windowing), counted as lines that would need rewriting to move the detection to another engine, scored the same way for every arm;
   - **(d)** image source (vendor registry vs Docker Hub / ASF-published images);
   - **(e)** a plain-language lock-in note: what an operator would have to change to leave this arm.
   - The dependence score is the count (a) + (b), with (c) reported alongside as a percentage of detection LOC. It is a count, not a price.
6. **Freshness (benefit side, reported with the cost, never separately)**: alert latency from the alert's own window closing to emit (July's `measure_latency.py` baseline, same for all arms), median and CV over the three 20× trials, plus the single 1× trial. Batch figures are given on both clocks; S and F as measured.

## Frozen predictions (numbers carried from source files; freeze unchanged)

July baselines used below come from `~/sdw-lab-benchmarks/stream-complexity/results/`: S images 238,880,881 + 674,189,499 = 913,070,380 bytes; config S 197 / B 131 LOC; recovery S1 2 steps 18.14 s, S2 2 steps 21.46 s, B1 1 step 0.02 s; pooled p50 S 0.260 s, B 2.271 s at 20× (real-time equivalent 41.07 / 47.78 / 40.44 s per trial).

- **P1 moving parts.**
  - S reproduces July within one unit: 3 containers, 4 engine + sink units; B 1 host process, 0 containers.
  - F runs **1 container**, with **2 to 6 processes** inside it (manager, SQL compiler, pipeline, and possibly an embedded database), so F is between B and S on container count.
  - F's uncompressed image bytes are **≥ 2.8× S's 913,070,380 bytes** (that is, ≥ 2.56 GB), because the compressed amd64 image alone is 2,559,051,848 bytes. I expect F to be the lightest streaming option on containers and the heaviest arm on footprint.
- **P2 config surface.** F lands at **50 to 110 LOC**, at or below B's 131 and well below S's 197. S and B reproduce July exactly (the files have not changed).
- **P3 recovery.**
  - B1: 1 step, under 1 s, 30/30 post-recovery with 0 duplicates.
  - B2 (late file): 0 operator steps and 30/30, with the late window's alert emitted late but present.
  - B3 (truncated file): at least 1 operator step **or** at least 1 missing alert; I'm unsure which, and either outcome counts as "batch has a real failure class."
  - S1: 2 steps (July), 0 missing; S2: 2 steps, 0 missing, duplicates between 0 and 3.
  - F1 (OSS): **≥ 3 steps** (container restart, pipeline restart, rewind compute and re-send), **≥ 20 s** kill-to-correct-alert, and 30/30 with 0 duplicates if the rewind rule is followed.
  - F2 (OSS): ≥ 2 steps, 30/30.
  - The structural prediction: on OSS, F needs **more** recovery steps than S on its comparable fault (F1 vs S2), because the edition has no checkpoint restore.
- **P4 freshness.** At 20×: S p50 < 1 s, F p50 < 2 s, B p50 2 to 4 s. At 1×: S p50 < 1 s, F p50 < 2 s, B p50 25 to 60 s. If `emit_final` adds a waterline delay larger than this, that is a freshness cost of F's correct-output mode and gets reported as one.
- **P5 equality.** 30/30, pairwise identical across B, S and F, on all three 20× trials and the 1× trial.
- **P6 platform dependence.**
  - B scores 0 (0 single-vendor engine components, 0 gated features).
  - S scores 0 (Kafka and Flink ASF-governed, no Confluent or Ververica features used).
  - F scores **≥ 2**: 1 single-vendor component, plus ≥ 1 paid-gated feature (checkpoint / fault tolerance) needed for recovery parity with S2.
  - Edition probe: the OSS image refuses or ignores fault tolerance.
  - Engine-specific SQL lines: S ≥ 2 and F ≥ 2, so both streaming arms are dialect-bound; this sub-measure is not expected to separate them.

## What each result would mean (frozen decision rules)

"Complexity axes" below means the three July axes: moving parts (engine + sink units), config LOC, and recovery steps summed over the arm's faults.

- **MOVE H-IMPL-01 toward 2/5 (direction only, magnitude stays D).** Under the fixed harness:
  - S ≥ 2× B on moving parts;
  - S needs more recovery steps than B, with B's total taken across all three batch faults (B1 + B2 + B3) and S's across S1 + S2;
  - post-recovery correctness was actually measured on both arms, with output files present.
  The move is to 2/5 at most, and only after the karen → hypothesis-validator → contradiction-detector gate.
- **HOLD and rescope H-IMPL-01 to broker-plus-cluster stacks.** The S-vs-B direction replicates, but F lands within 1.5× of B on two or more complexity axes. That would say the hidden cost belongs to the Kafka+Flink shape rather than to streaming freshness as such, so the hypothesis text gets narrowed and does not move.
- **FALSIFIER (frozen).** Either of these means the hidden-costs direction loses its first-party leg, and H-IMPL-01 leaves the needs-validation rotation as directional-only. That is a real result and ships the same way.
  - B needs as many recovery steps as S or more, counting the batch-side faults;
  - S lands within 1.5× of B on two or more complexity axes.
- **REFINEMENT SUPPORTED** ("the premium moves into platform dependence"). Both of these hold:
  - F within 1.5× of B on at least two complexity axes, so the infrastructure premium shrinks;
  - F's dependence score exceeds both B's and S's, through a paid-gated feature needed for recovery parity or an OSS recovery that costs more steps than S2.
- **REFINEMENT NOT SUPPORTED, premium genuinely reduced.** F shrinks the premium as above, and the OSS edition also reaches S2-level recovery (steps ≤ S2, 30/30, no paid feature). In that case the edition gate does not matter for this workload, and the honest reading is that incremental view maintenance cut the premium rather than moving it.
- **REFINEMENT NOT SUPPORTED, premium not reduced.** F at or above S on two or more complexity axes. Then incremental view maintenance does not help on this detection, and H-STREAMING-02's claim class weakens for Feldera.
- **Answer-equality failure on any arm** voids that arm's numbers for the trial, with no partial quoting.

## Run budget at the owner's ~1 hr/day cadence

**Running this means un-parking `~/sdw-lab-benchmarks`, which is the owner's call.** None of the time below is committed until that ruling.

| Phase | What | Estimate |
|---|---|---|
| Freeze | copy this block into the lab repo, pin `FELDERA_VERSION`, record the image digest | 1 session (under 1 hr) |
| Build F arm | compose service, SQL program, HTTP-ingress replayer adapter, egress drain consumer, F1/F2 scripts, rewind helper, edition probe | 3 to 4 sessions |
| Harness fixes | 10 s mid-run sampler, B2/B3 faults, replay-lost-window path for S1/S2/B1, 1× trial mode, full-corpus fault runs | 2 to 3 sessions |
| Smoke | first F compile (Feldera compiles SQL to Rust, which may take minutes on first build; measured and recorded, since a restart that forces a recompile changes F1 wall-clock), output-file-exists checks per fault, one throwaway trial | 1 to 2 sessions |
| Scored runs | three 20× trials, about 8 min each including teardown (July's full scored pass was about 50 min); seven faults on the full corpus, about 8 to 10 min each; 1× trial, 2 h of event time plus drain, about 2 h 15 min **unattended** | about 2 hr attended + 2 h 15 min unattended |
| Score and write | RESULTS.md, gate pass, ledger row | 1 to 2 sessions |

Total is roughly **9 to 13 one-hour sessions plus one unattended 2 h 15 min window**, so about two to three calendar weeks at the current cadence. The image pull is at least 2.56 GB, and host disk should be checked before pulling.

## Threats to validity

- **Single host, single node, everything.** Ryzen 5800H under Docker Desktop on WSL2; no arm has redundancy, so the redundancy and staffing clauses of H-IMPL-01 are untouched, and recovery numbers are single-node numbers.
- **Synthetic seeded corpus, one detection shape.** Seed 20260719, 500,000 events, 30 alerts; time-ordered input with no real late data. One tumbling-window count over two keys does not stand for joins, sessionization or the medallion workloads Feldera's guide uses.
- **Edition-bound F arm.** Feldera OSS lacks checkpointing, so its recovery numbers describe the free edition, not the engine. An Enterprise eval licence with publication rights is the only way to measure the other half, and the Terms of Service are unread.
- **"Managed" is only half tested.** The refinement talks about managed incremental engines; this bench tests a self-hosted OSS engine and counts gated features, and does not price or run a managed service (Feldera Enterprise, Databricks Lakeflow / Enzyme, RisingWave Cloud).
- **Batch arm is containerless by construction**, which favours B on moving parts. A containerised batch arm (scheduler container + object store) would narrow the gap; that is named as a later pre-registration rather than added here, to keep the July comparison intact.
- **F's input path differs from S's.** HTTP ingress with no broker is a real design choice that removes the durable buffer; the recovery comparison is partly a comparison of "broker retains, engine restores" against "source re-sends."
- **The rewind rules are written by the bench author**, and operator step counts depend on them. They are frozen here, and any deviation in a run is a dated note, but a different operator could choose a cheaper or costlier procedure.
- **`emit_final` is experimental**, and the waterline inference for the TUMBLE window column is unconfirmed, so the F arm may need the fallback output mode.
- **End-of-corpus flush.** `emit_final`, like Flink's watermark, only finalizes a window once a later event moves the waterline past window end + lateness. The last ground-truth alert window starts at base + 7,020 s and the corpus runs to base + 7,199 s, so trailing events should flush it, and July's S arm got 30/30 under the same property. F's replayer reuses the July producer's end-of-replay behaviour, and a last-window non-flush found in smoke is a harness failure to fix, not an F result.
- **Version churn.** Feldera ships near-daily; a result is pinned to one tag and may not hold a month later.
- **Image bytes.** The only F figure in hand is compressed; July's are uncompressed. Only same-basis numbers go in the table.
- **Each fault runs once**, so recovery wall-clock has no variance estimate; step counts are deterministic.
- **Replay acceleration.** The three CV-qualifying trials are at 20×; the 1× trial is n=1.
- **Author runs and scores the bench**, on a hypothesis the loop wants restored; the pre-registration is the main protection, as it was in July.
- **Relationship conflict.** The owner has a personal contact at Feldera, and the capture came from that conversation. The fair-broker posture means reporting F's weak results as plainly as its strong ones, and not sharing results with Feldera before they are gated.
- **Out of scope:** dollars, headcount, on-call load, multi-host, other streaming stacks (Redpanda, RisingWave), and a Kafka-input Feldera sub-arm.

## Honesty boundaries (carried into any RESULTS.md verbatim)

Single host, Docker Desktop/WSL2, synthetic seeded corpus (injection-surface boundary: no real telemetry), ONE detection shape, single-node every arm. Kafka 4.3.1 + Flink 2.2.1 as the canonical streaming stack and Feldera open-source edition (pinned tag) as the incremental-view-maintenance arm; EDITION-BOUND, since checkpointing and fault tolerance are Enterprise-only and were not tested. Complexity and dependence proxies are not dollars, headcount, or on-call burden, so this measures the operational-surface direction of H-IMPL-01 and the gated-feature half of the platform-dependence refinement, not cost. Assumptions under test: the canonical streaming stack carries structurally more operational surface than an equivalent-outcome batch path, and an incremental engine that removes that surface does so partly by relying on vendor-gated features.

## Paste-ready ledger bullet (for `PRE-REGISTRATION-LEDGER.md` "Next pre-registrations"; not applied)

```markdown
- **STREAM-COMPLEXITY v2: batch vs Kafka+Flink vs Feldera OSS** (drafted 2026-11-03 in
  `02-projects/PRE-REG-DRAFT-stream-complexity-feldera-2026-11-03.md`; freezes into the lab repo on un-park)
  — supersedes the exhausted 07-19 block. Adds the Feldera arm, fixes the five harness flaws (replay lost
  window, 1× clock, mid-run sampling, batch-side faults, redundancy stated), adds a platform-dependence axis.
  Falsifier = batch needs ≥ as many recovery steps as streaming, incl. batch-side faults, OR streaming within
  1.5× of batch on ≥2 complexity axes. Refinement test = Feldera within 1.5× of batch on ≥2 axes AND a
  dependence score above both other arms.
```

## Frozen at owner ruling 2026-11-03 (answers to the open questions)

Jeremy, hub tab, 2026-11-03: "Agree get tests done as well". He took every hub recommendation:

1. **Lab un-parked** for this bench (`.claude/cross-repo-progress.json` moves sdw-lab-benchmarks
   back to active).
2. **No Enterprise licence request before this run.** Run the OSS edition first and share the gated
   result. Any Enterprise arm is its own later pre-registration. Before publishing anything that names
   Feldera, read Feldera's terms for a benchmark-publication clause.
3. **Both batch faults kept** (B2 late file, B3 truncated file).
4. **One unattended 1× trial** over the full corpus (2 h 15 min).
5. **Containerised batch arm BC added** as a fourth arm (see Arms). Its frozen predictions:
   - **P1-BC**: 1 container, 1–2 processes, image ≤ 600 MB uncompressed.
   - **P2-BC**: config 131–175 LOC (B's 131 plus Dockerfile and compose).
   - **P3-BC**: container kill recovers in ≤ 1 step (0 if the restart policy brings it back unaided),
     30/30 correct.
   - **P5-BC**: 30/30 on every clean trial, identical to the other arms.
   - **P6-BC**: dependence 0.

   **BC decision rule:** the frozen H-IMPL-01 rules above are scored against B as written. They are
   also reported against BC. If S-vs-B separates on moving parts but S-vs-BC is within 1.5×, the
   moving-parts direction is narrowed to "against a containerless batch job" and quoted only that way.
6. **Disclosure:** the owner's Feldera contact may see this pre-registration only after it is
   frozen, and only to correct facts about how to configure Feldera. The predictions don't change. Any
   correction he offers is recorded with its date in RESULTS. Contact with him stays listed under
   threats to validity.

**Pinned at freeze:** Feldera OSS `v0.375.0`, the release current on 2026-11-03. The freeze commit in
`~/sdw-lab-benchmarks` is the binding copy.

## Open questions for the owner

1. **Un-park the lab?** Running this needs `~/sdw-lab-benchmarks` un-parked for roughly 9 to 13 sessions plus one unattended 2 h 15 min window.
2. **Enterprise eval licence?** The OSS edition has no checkpoint or fault tolerance. Ask the Feldera contact for an Enterprise eval licence **with benchmark-publication rights**, so a later arm can measure the gated half? It would be its own pre-registration, and asking creates a vendor dependency that has to be handled through the fair-broker posture.
3. **Batch faults.** Keep both B2 (late file) and B3 (truncated file), or only one to save a session?
4. **1× trial.** Accept a single 2 h 15 min unattended run, or prefer three 1× trials over a 20-minute slice (about 1 h 15 min total, with fewer alerts per trial)?
5. **Containerised batch arm.** Add it now, which costs about two more sessions and answers the main karen objection, or keep the July B arm exactly as is for comparability, as drafted?
6. **Disclosure.** Should the Feldera contact see the pre-registration before the run (useful for catching config mistakes, though it invites tuning pressure), or only the gated result?

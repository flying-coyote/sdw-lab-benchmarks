---
type: benchmark-spec
title: "PRE-REG: STREAM-COMPLEXITY v3, a RisingWave arm on the v2 detection (batch vs Kafka+Flink vs RisingWave Community Edition)"
status: frozen
created: 2026-11-07
hypotheses: [H-STREAMING-02, H-IMPL-01]
evidence-tier: B
depends_on:
  - "[[PRE-REG-stream-complexity-v2-2026-11-03]]"
  - "[[RESULTS-v2-2026-11-03]]"
  - "[[PRE-REGISTRATION-LEDGER]]"
tags: [h-streaming-02, h-impl-01, stream-complexity, risingwave, pre-registration, m6, frozen]
---

# PRE-REG: STREAM-COMPLEXITY v3, a RisingWave arm (2026-11-07)

**Status: FROZEN at the commit that adds this file, before any RisingWave container has been pulled or started and before any harness change.** The owner un-parked the lab for this on 2026-11-07. Under M6 a smoke test to make the harness work is not a scored run, but every number under Predictions and every decision rule is fixed here; a design change after this commit needs a new dated Deviations note that says why, recorded before the scored run it affects.

## Why this bench, and why now

The book (ch06) and the site both say RisingWave "hasn't been measured in the SDW lab", while H-STREAMING-02 carries a 3.5/5 score for the claim that RisingWave "reduces streaming architecture complexity by 60-80% compared to Kafka + Flink + database stack". That score rests on vendor and adopter reports (Tier C) and has no first-party leg. The v2 harness already measures exactly the axes the claim is about (moving parts, config surface, recovery, answer equality, platform dependence, freshness) on one detection with four arms, so adding a RisingWave arm is the cheapest honest test of the claim that exists, and it gives the v2 Feldera arm a second incremental-engine comparison point with a different edition boundary: RisingWave's checkpointing is in its free Community Edition, while Feldera's is Enterprise-only.

## Question

For the v2 detection outcome on the v2 events ("≥5 failed logins per (user, src_ip) within a 60-second epoch-aligned event-time tumbling window → alert" over the seed-20260719, 500,000-event synthetic OCSF-shaped auth corpus, 30 ground-truth alerts), what does a single-process RisingWave arm cost in moving parts, config surface, recovery effort and correctness, and platform dependence, against the freshness it buys, measured with the v2 harness against the same batch and Kafka+Flink arms?

## Arms

- **B, batch (unchanged from v2)**: `batch/land_microbatches.py` + `batch/batch_job.py`, bare host Python process, DuckDB 1.5.3.
- **S, streaming (unchanged from v2)**: `apache/kafka:4.3.1` + `smx-flink-kafka:2.2.1` (Flink 2.2.1, connector 5.0.0-2.2), the v2 compose, SQL job and sink consumer.
- **R, RisingWave (new)**: one container from `risingwavelabs/risingwave:v3.1.1` (latest stable release, published 2026-11-05; Docker Hub amd64 digest prefix `sha256:127bfb6418cc`, compressed `full_size` 2,521,997,536 bytes, read 2026-11-07; the full digest is recorded at pull time and pinned in the compose file, never `latest` or a nightly). It runs in **standalone mode** (`single_node`), which the docs describe as the whole cluster in one process with the embedded `LocalFs` object store and an embedded SQLite meta store, with its state directory on a named Docker volume so that state survives a container kill.
  - **Detection SQL**: an `APPEND ONLY` table `auth_events` with `WATERMARK FOR event_time AS event_time - INTERVAL '2' SECOND` (matching Flink's 2 s watermark and Feldera's 2 s lateness), and a materialized view over `TUMBLE(auth_events, event_time, INTERVAL '1' MINUTE)` grouped by `(user, src_ip, window_start)` with `HAVING COUNT(*) >= 5` and `EMIT ON WINDOW CLOSE`, so a window is emitted once, final, when the watermark passes its end.
  - **Input path, no broker**: a replayer that shares the July pacing code and `--replay-start-epoch` writes events by batched `INSERT` over the PostgreSQL wire protocol (port 4566). This tests the claim as stated ("single-system design"); a RisingWave-reads-Kafka sub-arm would mix the engine swap with the broker question, so it is out of scope and can be its own pre-registration.
  - **Output path**: a drain consumer reads the view through `CREATE SUBSCRIPTION` and a subscription cursor into `alerts-risingwave.jsonl`. This adapter, like S's and F's drain consumers, is counted in the engine + sink units and excluded from config LOC under July's frozen rule. If the subscription path cannot deliver the 30 alerts, the **fallback**, used only with a dated note, is polling `SELECT` on the view with client-side dedup, and needing it is itself reported as a finding.
  - **Edition**: Community Edition (Apache-2.0). The docs say a fresh deployment automatically includes a free trial of premium features for clusters of up to 4 RWUs (4 CPU cores and 16 GiB). To keep the arm Community-only, the deploy script records the license state verbatim into `results/edition-probe-risingwave.json`, attempts to clear the trial license by the documented system parameter, and records the response. Every SQL feature and connector the arm uses is listed in RESULTS against the documented premium-features table, and if any used feature is on that table the arm is labelled EDITION-BOUND.
- **F (Feldera) and BC (containerised batch) are not re-run.** Their v2 numbers stay in the v2 RESULTS and are cited as v2 results with their date, never pooled with v3 trials.

**Answer-equality gate (unchanged, three arms):** on every clean scored trial B, S and R must each produce 30/30 distinct alerts matching the independent ground truth (missing 0, extra 0, duplicates 0) and be pairwise identical. No complexity, recovery, dependence or freshness number is quoted from a trial whose answers diverge, until the divergence is explained and fixed.

## What was verified on 2026-11-07, and what wasn't

Verified (vendor-authored docs, Tier B for what the product ships, never for how well it works):

| Item | Finding | Source |
|---|---|---|
| Licence | Apache-2.0 | GitHub API, `risingwavelabs/risingwave` |
| Release | v3.1.1 latest stable, 2026-11-05; nightlies and `v3.2.0-alpha` tags exist and are excluded | GitHub releases API, Docker Hub tags |
| Checkpointing | Chandy-Lamport checkpoints persisted to the state store, default interval 1 s; "only the states that are not saved to the upcoming checkpoint are lost" on failure; not listed as a premium feature | docs.risingwave.com/reference/fault-tolerance, /get-started/premium-features |
| Premium features | Console, elastic disk cache, state-table preload, locality backfill, time travel, secret management, database isolation, resource groups, auto schema change, Glue registry, several sinks and sources; none needed by this detection as designed | docs.risingwave.com/get-started/premium-features |
| Standalone mode | single process, embedded LocalFs object store, embedded SQLite meta store, data under `~/.risingwave` by default | docs.risingwave.com/operate/rw-standalone-mode |
| EMIT ON WINDOW CLOSE | needs a watermark on the source; emits a final immutable result once the watermark passes the window end | docs.risingwave.com/processing/emit-on-window-close |

Not verified, carried as open items:
- whether DML `INSERT` acknowledgements are durable before the next checkpoint (the docs imply not, which is why the rewind rule below exists);
- whether a subscription cursor can re-emit a row the drain had already read once the engine recovers from a checkpoint, which is what the R1 duplicate count measures;
- whether standalone mode runs as one OS process inside the container or forks helpers, which the mid-run sampler measures;
- the unpacked image size, measured at pull time on both of v2's bases (`docker image inspect .Size` and `docker system df -v`);
- whether the 4-RWU trial switches itself off on this host (16 threads), which the edition probe records.

## Harness

The v2 harness as run on 2026-11-03, with only additions for R: `v2/run_trial_v2.sh` gains an R arm on the shared replay clock; `v2/sampler.py` gains R's container and host-process patterns; `v2/measure_complexity_v2.py` gains R's file list; `v2/faults_v2.py` gains R1. The B and S code, compose files and SQL are not edited, and the RESULTS must confirm that B and S reproduce their v2 LOC exactly. Moving-parts inclusion rule unchanged: the generator, replayers and ground-truth checker are harness and excluded; **engine-only** units and **engine + sink adapter** units are both reported, as median and max of the 10 s mid-run samples.

## Fault battery and rewind rule

Every fault runs on the full 500,000-event corpus at 20×, with the kill at event-time minute 45 (replay start + 135 s) and a held outage of 30 wall-seconds, then the recover script and a post-recovery answer-equality check over the full corpus, as in v2. B and S faults are not re-run; their v2 rows are cited as v2 results.

| ID | Arm | Fault | Frozen operator rewind rule after recovery |
|---|---|---|---|
| R1 | R | `docker kill smx-risingwave` (the whole single-process cluster) | Step 1: `docker start` the container (v2's BC1 showed `docker kill` does not trigger a restart policy). Step 2: once the SQL port answers, compute the rewind point as `SELECT max(event_uid) FROM auth_events`, which reads the last committed checkpoint. Step 3: the replayer re-sends every event with a larger `event_uid` up to the current replay position, then resumes live pacing. The drain consumer reconnects through its own retry code (adapter, not an operator step). |
| R2 | R | SIGKILL of the RisingWave process from inside the container (`docker exec … kill -9`), dropped with a dated note if the process is the container's PID 1 and the kill is therefore identical to R1 | the same rule as R1, minus step 1 if the container stays up |

Scored per fault, as in v2: operator steps (from `# Step N:` markers in `faults/recover_r*.sh`), recover-script wall, kill → infrastructure restored, kill → first new correct alert, post-recovery missing / extra / duplicates in the file, raw engine duplicates, and whether the output file exists and grew after recovery. One extra pre-registered count: **checkpoint loss**, the number of events the replayer had acknowledged before the kill whose `event_uid` is above the recovered `max(event_uid)`, which is the data the rewind rule has to re-send. Each fault runs once (n=1); step counts are deterministic and wall-clock figures are single observations.

## Measures

The v2 measures unchanged, applied to R: (1) moving parts, (2) config surface under July's frozen LOC rule (for R: the compose service, `detection.sql`, and the deploy script), (3) recovery per the battery, (4) answer equality, (5) platform dependence under v2's frozen rubric (a single-vendor-controlled components, b paid-gated features needed for recovery parity with S2, c engine-specific SQL lines as a share of detection LOC, d image source, e a plain lock-in note), and (6) freshness from the alert's own window close to emit, median and CV over three 20× trials plus one 1× trial (event time = wall time), reported with the cost and never on its own.

## Frozen predictions

Baselines carried from `results/RESULTS-v2-2026-11-03.md`: engine + sink units B 1, S 4, F 2; containers B 0, S 3, F 1; config LOC B 131, S 197, F 61; recovery steps S1 2, S2 2 (S total 4), B1 1, B2 0, B3 2 (B total 3), F1 4, F2 3; S2 kill → first new correct alert 39.05 s.

- **P1 moving parts.** R runs **1 container**, **1 engine-only unit** and **2 engine + sink units**, with **1 to 4 processes** inside the container. R's image is at least 2.5 GB on the `.Size` basis, so R is, like F, light on containers and heavy on footprint.
- **P2 config surface.** R lands at **35 to 80 LOC**, below B's 131 and S's 197.
- **P3 recovery.**
  - R1: **3 steps**, kill → first new correct alert **under 60 s** (including the 30 s hold), post-recovery **30/30 with 0 missing, 0 extra and 0 duplicates in the file**, and raw engine duplicates **0 to 1**.
  - Checkpoint loss on R1: **at least 1 event and under 2,000** (about 1 s of events at 20× plus in-flight batches), which is what makes step 3 necessary.
  - The structural prediction: R1 needs **more steps than S2 (2) and fewer than F1 (4)**, because R restores window state from its own checkpoint, as Flink does, but has no broker to retain the un-checkpointed input, as Feldera doesn't.
  - R2: dropped as identical to R1, which I expect because standalone mode is one process.
- **P4 freshness.** At 20×: R p50 **0.3 to 2.0 s** (watermark 2 event-seconds = 0.1 wall-s, plus up to one 1 s barrier). At 1×: R p50 **2.0 to 3.5 s**, against v2's S at about 2.2 s. If EMIT ON WINDOW CLOSE adds more delay than this, that is the freshness cost of R's correct-output mode and gets reported as one.
- **P5 equality.** 30/30, pairwise identical across B, S and R, on all three 20× trials and the 1× trial.
- **P6 platform dependence.** R scores **1**: one single-vendor-controlled component (RisingWave Labs; Apache-2.0 but not foundation-governed), and **0** paid-gated features needed for recovery parity, since checkpointing is Community. Engine-specific SQL lines: R ≥ 2 (`WATERMARK FOR`, `EMIT ON WINDOW CLOSE`, `APPEND ONLY`). The edition probe either clears the trial license or records that the trial switched itself off above 4 RWUs; either way no premium feature is used.
- **H-STREAMING-02's own number.** Against S, R cuts config LOC by **59 to 82%** (35 to 80 LOC against 197, which mostly overlaps the claimed 60-80% band) and engine + sink units by **50%** (below the band), so I expect the "60-80%" figure to hold on configuration and to overstate the reduction in running infrastructure.

## What each result would mean (frozen decision rules)

"Complexity axes" means the three v2 axes: engine + sink units, config LOC, and recovery steps summed over the arm's faults (R: R1, plus R2 if run; S: 4 from v2).

- **H-STREAMING-02 SUPPORTED on direction, magnitude partly.** All of these hold:
  - R is at or below half of S on at least two of the three complexity axes;
  - R1 reaches 30/30 with 0 missing and 0 extra;
  - R's dependence (b) is 0.

  The score can move only after the karen → hypothesis-validator → contradiction-detector gate, and the hypothesis text gets the measured per-axis reductions in place of "60-80%" wherever they differ, since one detection on one host does not carry a single headline percentage.
- **H-STREAMING-02 NOT SUPPORTED (frozen falsifier).** Either of these:
  - R is at or above S on two or more complexity axes;
  - R1 cannot reach 30/30 under the frozen rewind rule.

  Either means the claim loses the first-party leg it was expected to gain, and the score comes down at the next gate. That is a real result and ships the same way.
- **Edition-dependent.** If any feature R needed is on the premium table, or the trial license could not be cleared and R's behaviour differs with it on, then R is labelled EDITION-BOUND and the dependence part of the result is reported like F's, not like S's.
- **H-IMPL-01 (context only, no move).** If R lands within 1.5× of B on two or more complexity axes, that joins the v2 Feldera result as a second incremental engine that narrows the premium on infrastructure, and the H-IMPL-01 text's rescope to broker-plus-cluster stacks gets a second data point. H-IMPL-01's 2/5 does not move on this bench under any outcome.
- **Answer-equality failure** on any arm voids that arm's numbers for that trial, with no partial quoting.

## Run budget

| Phase | What | Estimate |
|---|---|---|
| Freeze | this commit; pin the full image digest at pull | under 1 session |
| Build R arm | compose service, `detection.sql`, deploy script with edition probe, INSERT replayer adapter, subscription drain consumer, `recover_r1.sh` | 2 to 3 sessions |
| Harness additions | sampler patterns, LOC file list, R1 in `faults_v2.py`, R in the trial runner | 1 session |
| Smoke | one throwaway trial, R1 smoke confirming the output file exists and grows after recovery | 1 session |
| Scored runs | three 20× trials at about 8 min each, R1 at about 10 min, the 1× trial at about 2 h 15 min unattended | about 1 hr attended + 2 h 15 min unattended |
| Score and write | RESULTS, gate pass, ledger row, then the book and site wording only after the gate | 1 to 2 sessions |

Host disk on 2026-11-07: 797 GB free on `/`, so the roughly 2.5 GB pull is not a constraint.

## Threats to validity

- **Single host, single node, everything.** Ryzen 5800H under Docker Desktop on WSL2, so no arm has redundancy, and the redundancy and staffing parts of both hypotheses are untouched. In particular, RisingWave's distributed shape (separate meta, compute, compactor and frontend nodes over S3) is not what runs here; standalone mode is the smallest RisingWave there is, which flatters R on moving parts exactly the way B's containerless design flatters B, and RESULTS must say so beside the P1 table.
- **Synthetic seeded corpus, one detection shape.** One tumbling-window count over two keys does not stand for joins, sessionization or the serving-layer queries H-STREAMING-02 also claims ("built-in query serving"), which this bench does not test.
- **"Kafka + Flink + database stack."** The hypothesis compares against three systems; S has no serving database, because the v2 detection writes alerts to a topic. So the bench measures RisingWave against Kafka + Flink only, which understates the reduction the claim describes, and I'd read a near-miss on the 60-80% band with that in mind.
- **No broker in R.** INSERT over the Postgres wire removes Kafka's durable buffer, so R's recovery depends on the source re-sending from a rewind point, which the battery measures rather than hides.
- **The rewind rules are written by the bench author**, and step counts depend on them. They are frozen here, and any deviation is a dated note.
- **Version churn.** RisingWave ships often (nightlies daily); the result is pinned to v3.1.1.
- **Mixed-date comparison.** B and S are re-run in v3 trials, but F and BC are cited from v2; any cross-bench comparison says which run each number came from.
- **Author runs and scores the bench**, on a claim the book currently leaves open. The pre-registration is the main protection.
- **Out of scope:** dollars, headcount, on-call load, multi-host, the distributed RisingWave deployment, RisingWave Cloud, a Kafka-source RisingWave sub-arm, and serving-query latency.

## Honesty boundaries (carried into any RESULTS.md verbatim)

Single host, Docker Desktop/WSL2, synthetic seeded corpus (injection-surface boundary: no real telemetry), ONE detection shape, single-node every arm. Kafka 4.3.1 + Flink 2.2.1 as the canonical streaming stack and RisingWave v3.1.1 Community Edition in standalone mode as the single-system arm, which is the smallest RisingWave deployment and not its distributed production shape. Complexity and dependence proxies are not dollars, headcount, or on-call burden, so this measures the operational-surface direction of H-STREAMING-02 against Kafka + Flink without a serving database, not cost. Assumption under test: a single streaming database removes most of the configuration and running infrastructure of a broker-plus-engine stack for an equivalent detection outcome without moving the cost into paid-gated recovery features.

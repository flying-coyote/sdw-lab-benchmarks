# STREAM-COMPLEXITY v3, RisingWave arm: results (2026-11-07)

Batch vs Kafka+Flink vs RisingWave v3.1.1 Community Edition (standalone) for the v2 detection outcome. Binding plan: `../PRE-REG-stream-complexity-risingwave-2026-11-07.md`, frozen at lab commit `dbf7406` before any RisingWave container was started; it was not edited during or after the run, and every place where the run could not follow it as written is a dated note under Deviations. Target hypotheses: H-STREAMING-02 (scored) and H-IMPL-01 (context only, no move). Run and scored by one agent session overnight on 2026-11-07 with the owner asleep, so the pre-registration is the main protection against the author's interest. Tier B. F (Feldera OSS) and BC (containerised batch) were not re-run; wherever they appear below they are the dated v2 results of 2026-11-03 from `RESULTS-v2-2026-11-03.md`, never pooled with v3 trials, and the same goes for the B and S fault rows.

## Honesty boundaries (carried verbatim from the pre-registration)

Single host, Docker Desktop/WSL2, synthetic seeded corpus (injection-surface boundary: no real telemetry), ONE detection shape, single-node every arm. Kafka 4.3.1 + Flink 2.2.1 as the canonical streaming stack and RisingWave v3.1.1 Community Edition in standalone mode as the single-system arm, which is the smallest RisingWave deployment and not its distributed production shape. Complexity and dependence proxies are not dollars, headcount, or on-call burden, so this measures the operational-surface direction of H-STREAMING-02 against Kafka + Flink without a serving database, not cost. Assumption under test: a single streaming database removes most of the configuration and running infrastructure of a broker-plus-engine stack for an equivalent detection outcome without moving the cost into paid-gated recovery features.

## Bottom line first

On the frozen decision rules, H-STREAMING-02 is SUPPORTED on direction, magnitude partly. RisingWave is at or below half of Kafka + Flink on two of the three complexity axes (engine + sink units 2 vs 4, config LOC 76 vs 197), it recovered from a whole-cluster kill to 30/30 under the frozen rewind rule, and it needed no paid-gated feature to do it. The per-axis reductions against S are 50% on running units, 61% on config and 25% on recovery steps, so the claimed "60-80%" holds on configuration only, and I'd write the hypothesis with those three numbers rather than one band. The score change is staged for the karen → hypothesis-validator → contradiction-detector gate, not applied here.

Two things travel with that verdict and should not be dropped from any summary. The first is freshness: R was the slowest arm, with a pooled p50 of 3.25 s at 20× against S's 0.25 s, and 5.44 s at 1× against S's 2.17 s, which misses P4 at both speeds. The second is a durability finding the battery was not designed to produce. RisingWave ran engine-internal recoveries, apparently triggered by this host's wall clock stepping backwards, and each one dropped INSERTs it had already acknowledged, with no error to the client: 387 events in one R1 smoke run, 256 in the other, and 369 in the scored 1× clean trial. That answers the pre-reg's first open item for the configuration tested here, which is RisingWave's default: by default it acknowledges DML before the next checkpoint, and an operator-visible fault is not needed to lose those acknowledged rows. A documented durable mode exists (`DML_WAIT_PERSISTENCE`, `RW_IMPLICIT_FLUSH`, or an explicit `FLUSH`; see the finding below) and was not tested here. The alert answer was 30/30 on every trial only because no lost run happened to cover a ground-truth window, and the mechanism is the price of R having no broker in front of it.

## What ran

- **Detection and corpus**: unchanged from v2. "≥5 failed logins per (user, src_ip) within a 60-second epoch-aligned event-time tumbling window", seed 20260719, 500,000 events, 30 ground-truth alerts.
- **B and S**: the v2 arms, code, compose files and SQL unedited (confirmed by LOC below: B 131, S 197, identical to v2).
- **R (new)**: one container, `risingwavelabs/risingwave:v3.1.1@sha256:b869358fa704250d25045d3575145ca59cfb67a558a08fa4f8fd375874c24d63` (index digest; the image on disk is amd64, created 2026-11-05T06:50:19Z, `version()` = `PostgreSQL 13.14.0-RisingWave-3.1.1 (04db7efd159bfe2941cd0aeaf1a42288d49a70ff)`), command `single_node`, state on the named volume `smx-rw-state`. Files: `risingwave/docker-compose.yml`, `risingwave/detection.sql`, `risingwave/deploy.py`. Input by multi-row `INSERT` over the Postgres wire protocol from `risingwave/replay_pg.py` (July pacing, shared replay clock, one INSERT per event-second bucket); output through `CREATE SUBSCRIPTION alerts_sub` and a subscription cursor read by `risingwave/drain_alerts.py`. The subscription path delivered the 30 alerts on every run, so the polling fallback was not needed.
- **Detection SQL as run**: an `APPEND ONLY` table with `event_time TIMESTAMPTZ AS to_timestamp("time")` as a generated column and `WATERMARK FOR event_time AS event_time - INTERVAL '2' SECOND`, then a materialized view over `TUMBLE(auth_events, event_time, INTERVAL '1' MINUTE)` grouped by `("user", src_ip, window_start, window_end)` with `HAVING COUNT(*) >= 5` and `EMIT ON WINDOW CLOSE`. Every guessed construct (watermark on a TIMESTAMPTZ column, here a generated one; EOWC with HAVING; `CREATE SUBSCRIPTION … WITH (retention = '1D')`; `DECLARE … SUBSCRIPTION CURSOR FOR … SINCE begin()` and `SINCE <unix ms>`; `FETCH n FROM cur WITH (timeout = '1s')`) worked on the running engine, and the cursor's `op` column reads `Insert`. EOWC worked as the primary output mode: 0 non-insert ops across every trial and fault.
- **Clean trials**: three at 20× and one at 1×, B, S and R concurrently on one shared replay clock, 10-second moving-parts sampler throughout (`v3/run_trial_v3.sh`, `v2/sampler.py`), plus a new host clock-step watcher (`v3/clock_watch.py`, harness).
- **Fault**: R1 on the full corpus at 20×, kill at event-time minute 45, 30 s hold, `faults/recover_r1.sh`, post-recovery equality over the full corpus (`v2/faults_v2.py --only R1 --results-dir v3`). R2 dropped (Deviations 1).
- **Smoke before scoring**: one 100× three-arm trial (gate PASS, 30/30 on every arm) (at 100× the R replayer took 138 s against the nominal 72 s, so R's 100× latencies reflect replayer lag and were not used for anything; at 20× it kept pace, 360 s against 360 s) and two R1 smoke runs, both confirming the R output file exists and grows after recovery (12 and 11 rows at recovery done, 30 at the end). The scored chain (`v3/run_scored_v3.sh`) then ran the three 20× trials, R1, and the 1× trial with no re-runs.

## P5, answer equality (the gate)

| Trial | B | S | R | Pairwise identical |
|---|---|---|---|---|
| 20× #1 | 30/30, 0 missing, 0 extra, 0 dup | 30/30 | 30/30 | yes |
| 20× #2 | 30/30 | 30/30 | 30/30 | yes |
| 20× #3 | 30/30 | 30/30 | 30/30 | yes |
| 1× | 30/30, 0 missing, 0 extra, 0 dup | 30/30 | 30/30 (but see the input-completeness note below) | yes |

Raw engine output agreed with the deduplicated files: the S sink topic held exactly 30 records at drain on every trial, and the R subscription delivered exactly 30 `Insert` rows with 0 engine duplicates and 0 non-insert ops. I also checked input completeness on R after every trial, since R has no broker to fall back on. `auth_events` held all 500,000 distinct `event_uid`s at the end of all three 20× trials (`risingwave-input-check.json`), with no internal engine recovery in the engine log (`risingwave-recovery-log.txt`). The 1× trial did not: the table ended at 499,631 rows, missing 369 acknowledged events in three contiguous runs (`event_uid` 1–87, 82,371–82,507 and 169,776–169,920), each lost in an engine-internal recovery the replayer was never told about (see the finding below). The gate still passed, because none of the three runs touched a ground-truth window, and the frozen gate scores alerts, not input rows, so P5 is a HIT as frozen. I would not read that HIT as "R was correct on the 1× trial", though; it was correct on the alerts and lossy on the input, and a different seed could have turned the same loss into a missed detection.

## P1, moving parts (median / max of 49–50 mid-run samples per 20× trial, identical in all three)

| Arm | Running containers | Processes inside containers (`docker top`) | Engine-only units | Engine + sink units | Image bytes, July basis (`docker image inspect .Size`) | Unpacked on disk (`docker system df -v`) |
|---|---|---|---|---|---|---|
| B | 0 / 0 | 0 / 0 | 1 / 1 | 1 / 1 | 0 | 0 |
| S | 3 / 3 | 3 / 4 | 3 / 3 | 4 / 4 | 913,070,380 | 686 MB + 1.58 GB |
| R | 1 / 1 | 1 / 1 (`risingwave`) | 1 / 1 | 2 / 2 | 2,521,484,435 | 11 GB |
| F (v2, 2026-11-03) | 1 / 1 | 12 / 13 | 1 / 1 | 2 / 2 | 2,559,070,153 | 11 GB |

Standalone mode really is one OS process, which closes one of the pre-reg's open items: `/proc/1/cmdline` inside the container is `/risingwave/bin/risingwave single_node`, `docker top` sees one `risingwave` process in every sample, and the engine's log shows its meta, compute, compactor and frontend running as threads (`rw-standalone-meta`, `rw-standalone-compute`, `rw-standalone-compactor`, `rw-standalone-frontend`). So R is lighter than F inside the container (1 process against F's 12) and as heavy on footprint: 2.76× S on July's basis and roughly 5× S unpacked.

The threat the pre-reg asked to have stated beside this table: standalone mode is the smallest RisingWave there is, and it flatters R on moving parts exactly the way B's containerless design flatters B. A production RisingWave runs separate meta, compute, compactor and frontend nodes over S3 and a separate meta store, which this bench did not run, so the 1-container, 2-unit figure is a floor, not RisingWave's distributed shape.

## P2, config surface (July's frozen counter, `v2/measure_complexity_v2.py` → `results/v3/complexity-v3.json`)

| Arm | Files counted | LOC | Ratio to B |
|---|---|---|---|
| B | `batch/batch_job.py` | 131 | 1.00 |
| S | compose 129, Dockerfile 4, init-topics 7, flink_job.sql 52, submit 5 | 197 | 1.504 |
| R | compose 18, detection.sql 24, deploy.py 34 | 76 | 0.58 |
| F (v2) | compose 15, detection.sql 27, deploy_pipeline.sh 19 | 61 | 0.47 |

B and S reproduce v2 exactly. R's deploy script carries the edition probe (version, license parameter before and after, the attempted clear, `rw_features`), which is about a third of its 34 lines; I counted it because the pre-reg puts the deploy script in the count and the probe runs as part of deploying. Excluded under July's rule, as for every arm: the INSERT replayer (`replay_pg.py`, harness) and the drain adapter (`drain_alerts.py`), which is real code an operator would own, just as S's `consume_alerts.py` is.

## P3, recovery (full corpus, 20×, kill at minute 45, 30 s hold, n=1)

| ID | Arm | Operator steps | Recover-script wall | Kill → infra restored (incl. 30 s hold) | Kill → first new correct alert | Post-recovery: missing / extra / dup in file | Raw engine duplicates | Checkpoint loss (events) | Output exists and grew |
|---|---|---|---|---|---|---|---|---|---|
| R1 | R: `docker kill smx-risingwave` | 3 | 1.09 s | 31.88 s | 36.48 s | 0 / 0 / 0 (30/30) | 0 | 979 | yes / yes |
| S1 (v2) | S: `docker kill smx-kafka` | 2 | 17.27 s | 48.37 s | 91.01 s | 0 / 0 / 0 | 0 | n/a | yes / yes |
| S2 (v2) | S: `docker kill smx-taskmanager` | 2 | 6.27 s | 37.47 s | 39.05 s | 0 / 0 / 0 | 1 | n/a | yes / yes |
| F1 (v2, EDITION-BOUND) | F: `docker kill smx-feldera` | 4 | 5.72 s | 36.91 s | 37.42 s | 0 / 0 / 0 | 0 | n/a | yes / yes |

Step totals for the decision rules: R 3 (R1 only, R2 dropped), S 4 and B 3 from v2.

What happened on R1, in order. The kill landed on the replayer as `OperationalError: consuming input failed: server closed the connection unexpectedly` at event time base + 2,443 s, which is minute 40.7 rather than the frozen minute 45, because the fault driver's wait sleeps on a monotonic clock that runs about 9% fast against the wall clock on this host (Deviations 12); that put the kill inside the minute-40 window, which holds a ground-truth alert (`user00405`, `198.51.100.4`, window base + 2,400 s), so R1 was if anything a harder test than the frozen one, and that alert was in the file at the end. The replayer paused. The container stayed `exited` for the whole hold with RestartCount 0 (no restart policy is set, and v2's BC1 had already shown `docker kill` does not fire one). Step 1 started it; step 2 got an answer to `SELECT max(event_uid) FROM auth_events` about a second later, `e-00168941`; step 3 wrote the control file, and the replayer re-sent from `e-00168942` back-to-back to the live replay position, then resumed pacing. The replayer's last acknowledged INSERT before the kill ended at `e-00169920`, so the checkpoint loss was 979 events, which is about 0.7 event-seconds at this corpus's rate, or roughly one 1-second barrier at 20× plus the batch in flight. The drain reconnected on its own (2 connects, 1 disconnect), resumed its cursor `SINCE` the last `rw_timestamp` it had read, re-read that one boundary row (`SINCE` is inclusive; counted as resume overlap, not as an engine duplicate), and wrote the remaining 19 alerts. The table ended with all 500,000 distinct event_uids.

Two observations from the engine log that the frozen rule tolerated but a reader should know. On restart the engine's first recovery attempt failed (`recovery failed error=global recovery failed due to failure of databases [1]`, because the compute thread was not yet listening) and the second succeeded about 0.2 s later, and the SQL frontend answered the step-2 query around that point, so "once the SQL port answers" is slightly earlier than "once streaming has recovered". It made no difference here, because batch reads see the last committed checkpoint either way, which is what the rule needs. And on that restart the engine logged `DatabaseFailureIsolation disabled by license`; that is a premium feature for isolating failures between databases, this deployment has one database, and recovery worked without it.

Smoke runs, for calibration only (not scored): R1 smoke 1 had 3 steps, 31.68 s kill to first new alert, 30/30, loss 543; R1 smoke 2 had 3 steps, 31.98 s, 30/30, loss 1,135. So the loss figure moves by about 2× run to run, and all three sit inside the frozen band.

## P4, freshness (benefit side, reported with the cost)

20×, three trials, B, S and R concurrently, latency from the alert's own window close on the shared replay clock to the alert landing in the arm's file (July's baseline):

| Arm | Trial medians (s) | Pooled p50 (s) | CV of trial medians | Within-trial CV |
|---|---|---|---|---|
| B | 1.862 / 2.382 / 1.494 | 2.049 | 19.0% | 46–114% |
| S | 0.252 / 0.261 / 0.251 | 0.255 | 1.8% | 25–663% |
| R | 3.239 / 3.292 / 3.236 | 3.254 | 0.8% | 40–46% |
| F (v2) | 0.105 / 0.105 / 0.105 | 0.105 | 0.0% | 0.3–12.5% |

v2 pooled p50 was S 0.239 s and B 2.312 s, so S reproduces; B's trial medians spread more than in v2, and the within-trial CVs for B and S are inflated by negative latency samples, which the host clock explains (Deviations 3).

R's 3.25 s decomposes cleanly, because the drain stores the `rw_timestamp` RisingWave stamps on every subscription row:

| Component (20×, per trial p50) | #1 | #2 | #3 |
|---|---|---|---|
| window close → `rw_timestamp` of the emitted row | 2.176 s (range 0.16–4.19) | 2.236 s (0.22–4.25) | 2.168 s (0.17–4.19) |
| `rw_timestamp` → row written by the drain | 1.074 s | 1.054 s | 1.083 s |

The second line is constant at about 1.05–1.08 s on every alert of every trial, and an exploratory probe after the scored chain (`results/v3/exploratory-fetch-probe/probe.txt`, not pre-registered, scores nothing) puts it in the engine rather than the adapter: polling `FETCH` with no timeout every 20 ms saw a closed window's row 1.10–1.17 s after its `rw_timestamp`, the same instant the row became visible to a plain `SELECT` on the view (1.09–1.15 s), and `FETCH 1 … timeout` matched that on the first reading (1.154 s against 1.149 s for the view) but not the second, where it read 2.101 s against the view's 1.087 s, one full 1 s timeout later. So `rw_timestamp` marks the start of the epoch and the row is readable once that epoch's checkpoint commits, about one 1 s barrier later. The probe script errored after its second reading, so this rests on two readings that agree. The first line is the engine's own emit delay for EOWC, and it is far above the 0.1 wall-second the 2 s watermark costs at 20×: the spread is roughly uniform between 0.2 and 4.2 s, and the per-alert values cluster on whole-second offsets (0.17, 1.17, 2.2, 3.17, 4.18 s), so each EOWC row seems to land on a 1 s barrier somewhere between the first and the fifth after its window closes, not reliably on the next one. I checked whether the host clock steps produce that spread: in each 20× trial, the R samples with no clock step inside their latency interval (28, 26 and 24 of 30) still span 0.16–4.25 s on the engine side and have medians of 3.23, 3.29 and 3.24 s, so the spread and the median are the engine's, not the clock's. I did not find the mechanism, and I'm not going to guess at it in a results file. That spread is the freshness cost of R's correct-output mode as this standalone deployment runs it, and the pre-reg asked for exactly that to be reported as a cost.

1× trial (unattended, n=1, 2026-11-07T07:51:24Z to 09:55:42Z, event time = wall time): gate PASS, 30/30 on every arm, pairwise identical; S's topic held exactly 30 records and the R subscription delivered 30 `Insert` rows, 0 duplicates, 0 non-insert ops. Moving parts over 753 samples matched the 20× trials (B 1 unit; S 3 containers, 4 units, 3 median and 5 max processes; R 1 container, 1 process, 2 units).

| Arm | p50 at 1× (s) | min / max (s) | Within-trial CV | p50 at 20× (s) |
|---|---|---|---|---|
| B | −2.887 (not interpretable, below) | −6.717 / 7.016 | n/a | 2.049 |
| S | 2.167 | −0.539 / 2.280 | 33.5% | 0.255 |
| R | 5.441 | 2.458 / 7.764 | 29.0% | 3.254 |
| F (v2, 1× of 2026-11-03) | 2.005 | 2.004 / 3.221 | 10.7% | 0.105 |

- **R at 1×** is the 2 s watermark (now 2 wall-seconds) plus the same roughly 3.4 s the engine spends at 20×: window close to `rw_timestamp` p50 4.375 s (range 1.42–6.67), then 1.065 s to commit visibility. So the engine-side part does not scale with the replay factor, and it costs R about 3.3 s at the median against S on a real clock (5.44 vs 2.17 s), which is the opposite of the sub-S freshness the pre-reg expected from a 1 s barrier.
- **S at 1×** reproduces v2 (2.184 s), the 2 s watermark on a real clock.
- **B at 1×** has a negative median, which no real batch job can have, and I'm not reporting a freshness figure for it. The lander waits for each window's close with one `time.sleep` of about 58 s, which runs on the monotonic clock, and on this host that clock runs about 9% fast against the wall clock the latency baseline uses (Deviations 3), so each file landed roughly 5 s before its window closed in wall terms. At 20× the same sleeps are about 3 s and the error is a few hundred milliseconds, which is why B's 20× medians are usable but noisier than in v2.

## P6, platform dependence (v2's frozen rubric)

| Arm | (a) single-vendor engine components | (b) paid-gated features needed for S2 recovery parity | Score | (c) engine-specific detection lines | (d) image source | (e) what leaving would take |
|---|---|---|---|---|---|---|
| B | 0 | 0 | 0 | 1 of 7 (14.3%) | none (PyPI) | as v2 |
| S | 0 | 0 | 0 | 2 of 52 (3.8%) | Docker Hub `apache/kafka`, Docker Official `flink` + Maven Central jar | as v2 |
| R | 1 (RisingWave Labs; Apache-2.0, not foundation-governed) | 0 (checkpointing is Community; R1 recovered with no licence) | 1 | 4 of 24 (16.7%): `WATERMARK FOR`, `APPEND ONLY`, `TUMBLE(…)`, `EMIT ON WINDOW CLOSE` | Docker Hub `risingwavelabs/risingwave`, vendor-published | rewrite the four dialect lines, replace INSERT-over-pgwire and the subscription cursor with a broker or connector, and re-plan recovery around a source that can re-send; no licence to buy to stay |
| F (v2, EDITION-BOUND) | 1 | 1 | 2 | 4 of 27 (14.8%) | vendor registry | as v2 |

Line rule for (c): v2's uniform rule, with the two constructs this pre-reg names (`APPEND ONLY`, `EMIT ON WINDOW CLOSE`) added to the pattern; the addition changes no B, S or F count (1, 2, 4 as in v2).

Edition probe (`results/edition-probe-risingwave.json`, per-run copies under each `results/v3/*/`), verbatim. Before: `SHOW PARAMETERS` row `('license_key', '<default>', 'The license key to activate enterprise features.', True)`. `ALTER SYSTEM SET license_key TO ''` was accepted on every run. After: the parameter read `''` on three runs and `<default>` on one (trial 3), which looks like a read racing the parameter's propagation, so I'd not lean on the after-value. What settles it is the engine itself. At boot it loads `License { sub: "rw-default-all-4-core", iss: Prod, tier: All, rwu_limit: Some(4), exp: 10000627200 }` and then logs `feature ElasticDiskCache is not available due to license error: a valid license key is set, but it is currently not effective because the CPU core in the cluster (14) exceeds the maximum allowed by the license key (4)`, and `rw_catalog.rw_features` reports all 22 premium features `available = false` on every run. So the 4-RWU trial switched itself off on this 14-thread VM, and the arm ran Community-only in fact as well as by intent. Against the docs' premium table and `rw_features`, the arm uses: a table with `APPEND ONLY` and a watermark, a generated column, `TUMBLE`, a materialized view with `EMIT ON WINDOW CLOSE`, `CREATE SUBSCRIPTION` and subscription cursors, DML `INSERT`, and the built-in checkpoint and recovery. None is on the premium table or in `rw_features`. Not EDITION-BOUND.

## Prediction scorecard (frozen numbers vs measured)

| Prediction | Frozen | Measured | Verdict |
|---|---|---|---|
| P1 containers | 1 | 1 (median and max, all trials) | HIT |
| P1 engine-only units | 1 | 1 | HIT |
| P1 engine + sink units | 2 | 2 | HIT |
| P1 processes in container | 1 to 4 | 1 | HIT |
| P1 image size | ≥ 2.5 GB on `.Size` | 2,521,484,435 bytes (11 GB unpacked) | HIT (by 21 MB on `.Size`) |
| P2 config LOC | 35 to 80, below B 131 and S 197 | 76 | HIT |
| P3 R1 steps | 3 | 3 | HIT |
| P3 R1 kill → first new correct alert | under 60 s | 36.48 s | HIT |
| P3 R1 post-recovery | 30/30, 0 missing, 0 extra, 0 dup in file | 30/30, 0 / 0 / 0 | HIT |
| P3 R1 raw engine duplicates | 0 to 1 | 0 | HIT |
| P3 checkpoint loss | ≥ 1 and < 2,000 events | 979 | HIT |
| P3 structural | R1 steps > S2 (2) and < F1 (4) | 3 | HIT |
| P3 R2 | dropped as identical to R1 (one process) | dropped: PID 1 is `risingwave single_node` | HIT |
| P4 20× R p50 | 0.3 to 2.0 s | 3.254 s pooled (3.236–3.292 per trial) | MISS |
| P4 1× R p50 | 2.0 to 3.5 s | 5.441 s | MISS |
| P5 equality | 30/30 pairwise identical, three 20× and the 1× | 4 of 4 trials pass on alerts; R's 1× input was missing 369 acknowledged events, none in an alert window | HIT (as frozen; see the 1× input note) |
| P6 dependence score | 1 (a=1, b=0) | 1 | HIT |
| P6 engine-specific lines | ≥ 2 | 4 | HIT |
| P6 edition probe | trial cleared, or switched off above 4 RWUs; no premium feature used | switched off (14 cores > 4), 0 of 22 premium features available, none used | HIT |
| H-STREAMING-02, config | 59 to 82% cut vs S | 61.4% (76 vs 197) | HIT |
| H-STREAMING-02, engine + sink units | 50% cut vs S | 50% (2 vs 4) | HIT |

Tally: 19 hits, 2 misses, both on R freshness (P4 at 20× and at 1×), with one cause: on this standalone deployment RisingWave takes about 2–4 s after the watermark passes to emit an EOWC row, plus about 1 s to commit it, and neither part shrinks with the replay factor.

## H-STREAMING-02, per axis

| Axis | S (Kafka + Flink) | R | Reduction | Inside the claimed 60-80%? |
|---|---|---|---|---|
| Engine + sink units (median) | 4 | 2 | 50% | no, below |
| Running containers | 3 | 1 | 67% | yes |
| Config LOC | 197 | 76 | 61.4% | yes, at the bottom |
| Recovery steps (S1+S2 v2 vs R1) | 4 | 3 | 25% | no, well below |
| Kill → first new correct alert, worst fault | 91.01 s (S1, v2) | 36.48 s | 60% | yes, but n=1 and a different fault |
| Image bytes, July basis | 913,070,380 | 2,521,484,435 | −176% (R heavier) | no, the other way |
| Freshness p50, 20× | 0.255 s | 3.254 s | R 12.8× slower | no, the other way |

So I'd read the claim this way on this one detection: RisingWave does remove most of the configuration (61%) and two of three containers, it halves the running units once the sink adapter is counted, it cuts the operator's recovery work by one step out of four, and it pays for that in footprint and, on this deployment, in freshness. The "Kafka + Flink + database" comparison in the hypothesis has a serving database that S doesn't, so these reductions understate what the claim describes, as the pre-reg warned; I'd still not write "60-80%" as a headline, since one axis lands in the band, one at its bottom edge, and two well below it.

## Frozen decision rules

| Arm | Engine + sink units | Config LOC | Recovery steps | Ratio to S (units / LOC / steps) | Ratio to B (units / LOC / steps) |
|---|---|---|---|---|---|
| B | 1 | 131 | 3 (v2) | | 1 / 1 / 1 |
| S | 4 | 197 | 4 (v2) | 1 / 1 / 1 | 4.00 / 1.504 / 1.33 |
| R | 2 | 76 | 3 | 0.50 / 0.386 / 0.75 | 2.00 / 0.58 / 1.00 |

- **H-STREAMING-02 SUPPORTED on direction, magnitude partly: fires.** R is at or below half of S on two axes (units 0.50, exactly at half; LOC 0.386); R1 reached 30/30 with 0 missing and 0 extra; R's dependence (b) is 0. The units leg sits exactly on the boundary ("at or below half"), so it holds on the frozen wording with no margin, and LOC carries the second leg comfortably. Per the rule, the score moves only after the karen → hypothesis-validator → contradiction-detector gate, and the hypothesis text should carry the per-axis reductions above instead of "60-80%". Staged, not applied.
- **NOT SUPPORTED (falsifier): does not fire.** R is below S on all three axes, and R1 reached 30/30 under the frozen rewind rule.
- **Edition-dependent: does not fire.** No premium feature used, and the trial licence was not effective on this host (14 cores > 4 RWU), so there is no "behaviour with the trial on" to differ.
- **H-IMPL-01 (context only, no move): the context condition holds.** R is within 1.5× of B on two axes (LOC 0.58×, steps 1.00×), not on units (2×). So R joins v2's Feldera result as a second incremental engine that narrows the infrastructure premium, and the H-IMPL-01 rescope to broker-plus-cluster stacks gets a second data point; v2's Feldera was within 1.5× of B on config only, so R is the stronger of the two data points. H-IMPL-01's 2/5 does not move on this bench.
- **Answer-equality failure: none** on any clean scored trial (4 of 4), with the 1× input-completeness caveat above.

## Finding outside the battery: acknowledged INSERTs lost on an engine-internal recovery (default DML mode)

This was first seen in the R1 smoke runs, which the pre-registration does not score, and then again in the scored 1× clean trial. I'm reporting it at length because it answers the pre-reg's first open item and because a reader of the R1 row could otherwise assume R's input path is lossless between operator-visible faults.

- **What happened.** About 30 wall-seconds into the replay, roughly two minutes before the scheduled kill, the engine logged `failure_recovery{error=Hummock error: unexpected decreasing now, old=1794034786, new=1794034784}` and ran about fifteen back-to-back internal recoveries over 1.5 s. The replayer saw no error at all, and every INSERT it sent was acknowledged. At the end, `auth_events` was missing exactly one contiguous run, `event_uid` 42,421 to 42,807 (387 events), the events acknowledged in the un-checkpointed epoch before that recovery. The alert answer was still 30/30, because no ground-truth window fell in that run. The first R1 smoke run ended 256 events short (499,744 rows), but I had not yet added the uid-range check or the full recovery-log capture, and the 40 log lines it kept are all boot and post-kill recovery lines, so both its missing range and its trigger are unobserved.
- **Why the clock.** "Unexpected decreasing now" says the engine read its wall clock going backwards. A host clock watcher (`v3/clock_watch.py`, comparing `time.time()` with `time.monotonic()` every 0.5 s) then measured, at idle and in every scored run, the WSL2 wall clock stepping back by 2.02–2.61 s every 27–30 s. A 60 s comparison of the kernel clocks shows `CLOCK_MONOTONIC` and the realtime tick running about 9% fast against `CLOCK_MONOTONIC_RAW`, and something on the host pulling the wall clock back in steps; `systemd-timesyncd` is running and reports the clock synchronized, but whether it or WSL2's own Hyper-V time sync does the stepping was not determined. The 1× trial makes the link close to observed rather than inferred. Across its two hours the engine logged `unexpected decreasing now` about every 25–30 s, the same cadence as the 260 host clock steps the watcher recorded in that trial, mostly as small three-line events with no data loss, and three times as a full burst of recoveries (34 lines at replay start, 234 at replay + 1,175 s, 121 at replay + 2,440 s). Those three bursts line up one-for-one with the three missing uid runs (event time 0–1 s, about 1,186 s and about 2,443 s). None of the three 20× trials or the scored R1 logged a single `decreasing now` recovery despite the same clock steps, so the step alone is not sufficient; something about the slower 1× epoch cadence, or how a step lands relative to an epoch, decides whether the engine only complains or fully recovers, and I did not pin that down.
- **What it means.** In the three 20× trials and the scored R1 nothing was lost (500,000 distinct uids after each), so no 20× or fault number depends on this, and the 1× trial's 369 lost events missed every ground-truth window, so its gate result stands as frozen. The mechanism holds for RisingWave's default DML mode, which is the mode this bench ran (the replayer sets no session variables): with INSERT over pgwire and no broker, anything that makes RisingWave restart its streaming graph discards the acknowledged-but-uncheckpointed epoch, and the producer is not told. It is not RisingWave's only mode. The engine documents `SET DML_WAIT_PERSISTENCE = true`, under which INSERT, UPDATE and DELETE wait until their transaction is included in a successful checkpoint before returning; `SET RW_IMPLICIT_FLUSH = true`, which flushes after each DML statement and makes `DML_WAIT_PERSISTENCE` moot; and an explicit `FLUSH`, which blocks until pending changes are durable. Both variables default to false (docs.risingwave.com/sql/commands/sql-set-dml-wait-persistence, docs.risingwave.com/sql/commands/sql-set-rw-implicit-flush, docs.risingwave.com/sql/commands/sql-flush, read 2026-11-07; the docs pages carry no version marker, so the defaults and the `IMPLICIT_FLUSH` precedence were confirmed in the v3.1.1 tag's `src/common/src/session_config/mod.rs`, lines 103-111). None of these was tested here, so this file makes no claim about their freshness cost or whether they close the loss path under an internal recovery; the supplementary trial in the open items would. The frozen R1 rewind rule handles that for a kill the operator sees; it does nothing for a recovery the operator doesn't see. That's the same structural point the pre-reg made about R having no durable buffer, now with an observed silent case, and it is a reason to put a broker or a replayable source in front of RisingWave in production, which brings back some of the moving parts R saved here. A host whose clock steps every half-minute is not a normal production host, so I'd treat the trigger as this lab's artefact and the loss path as RisingWave's real behaviour.

## Deviations from the pre-registration (dated 2026-11-07)

None changes a frozen prediction or decision rule. Items 1 to 8 were settled before the first scored run; the scored chain then ran without any harness change.

1. **R2 dropped.** As the pre-reg allows: `/proc/1/cmdline` in the container is `/risingwave/bin/risingwave single_node`, and `docker top` shows one process, so a `docker exec … kill -9` of the RisingWave process is a kill of PID 1 and identical to R1.
2. **Generated `event_time` column.** The pre-reg puts the watermark on the table's event-time column without saying where that column comes from. A first build had the replayer compute `event_time` client-side; I moved it into the engine as `event_time TIMESTAMPTZ AS to_timestamp("time")` (a generated column, which RisingWave accepts a watermark on), so the R input carries exactly the corpus fields plus `ingest_wall_ts`, like F's, and the event-time derivation is part of R's counted SQL.
3. **Host clock.** The pre-reg did not anticipate that this host's wall clock steps back about 2.6 s every 27–30 s (see the finding above). Every arm's latency is a difference of `time.time()` readings, so a step between a window's close and its alert's write shifts that one sample by up to −2.6 s, and the realtime clock runs about 9% fast between steps. That is why B and S show negative minimum latencies (B −2.48 s, S −2.27 s in trial 1) and inflated within-trial CVs, and why B's trial medians spread more than in v2. It affects every arm equally in kind; the medians at 20× are robust to it (a step lands inside a 0.25 s S latency about 1% of the time and inside a 3.25 s R latency about 12% of the time, and R's medians on unstepped samples alone match the trial medians, per P4), the 1× latencies are more exposed (a 2–3 s latency overlaps a step about 8–10% of the time), and no correctness or step count depends on it. I did not change the host's time configuration, which is outside this bench and could disturb other jobs on the host.
4. **`deploy.py` comment bug (found in smoke).** It split `detection.sql` on `;` before stripping comments, and a `;` inside a header comment broke the first deploy; fixed by stripping comment lines first. The edition probe gained a `rw_features` read. Line count after both: 34.
5. **Drain `FETCH` batch size (found in smoke).** `FETCH n FROM cur WITH (timeout = '1s')` waits for n rows or the timeout, so the first drain build (n = 100) held every live alert for the full 1 s timeout; it now fetches one row at a time (`--batch 1`). Without this R's freshness would read about 1 s worse from an adapter artefact. The constant 1.05 s that remains between `rw_timestamp` and the drain write is discussed under P4.
6. **Diagnostics added after the R1 smokes.** `fault_r` and the trial runner now record R's input completeness (missing `event_uid` ranges), the engine's recovery log lines, and host clock steps, and their end-of-run waits stop once `auth_events` stops growing instead of waiting only for 500,000 (a lossy run never reaches it). The replayer records the first few acknowledgements after a rewind. None of this touches detection or recovery logic.
7. **Checkpoint-loss arithmetic.** "Events the replayer had acknowledged before the kill whose `event_uid` is above the recovered `max(event_uid)`" is computed as the difference of the uid ordinals (`e-00169920` − `e-00168941` = 979), which is exact because the corpus uids are gap-free and in time order (checked over all 500,000).
8. **Harness edits to v2 files.** `v2/sampler.py` (R arm), `v2/measure_complexity_v2.py` (R files, R image, the two pre-reg-named constructs, an output-path argument so v2's `complexity-v2.json` is not overwritten), `v2/faults_v2.py` (R1, a `--results-dir` argument). B and S code, compose files and SQL were not edited, and B and S reproduce their v2 LOC exactly.
9. **One registry read.** While collecting image facts I ran `docker buildx imagetools inspect` on the pinned digest, which queried Docker Hub for the manifest list. The brief allowed no network calls beyond images already pulled; it changed nothing on disk and no result depends on it, but it was a network call and I'm recording it.
10. **Image digest naming.** The pre-reg quotes the Docker Hub amd64 platform digest prefix `sha256:127bfb6418cc`; the compose pins the multi-arch index digest `sha256:b869358f…24d63`, which is what `docker image inspect` reports as `RepoDigests` on this host, with architecture amd64. Same release; the compose uses the index digest so the pin survives a re-pull.
11. **The 1× trial ran last**, unattended, launched by `v3/run_scored_v3.sh` straight after R1, as the brief ordered.
12. **R1 kill instant.** The frozen battery kills at replay start + 135 wall-s, i.e. event-time minute 45. `v2/faults_v2.py` waits for that instant with one `time.sleep`, which on Linux runs on `CLOCK_MONOTONIC`, and on this host that clock ran about 9% fast against the realtime clock the replayer paces by (Deviations 3), so the kill fired at event time base + 2,443 s (minute 40.7). The two R1 smokes landed at base + 2,495 s and base + 2,444 s for the same reason. In v2 the same code put F1's first failed send at base + 2,770 s, so the clock condition seems to have appeared on this host after 2026-11-03. I left the scored result as run rather than re-run it: the step count, correctness and loss measures do not depend on which minute the kill hits, the minute-40 window carries a ground-truth alert that minute 45 does not, and the pre-reg's no-re-run discipline matters more here than the exact minute. The wall-clock figures in the R1 row are single observations measured with the same skewed clocks, so read them to about ±10%.

## Open items

- The 1 s gap between `rw_timestamp` and the drain write, and the 0.2–4.2 s spread in EOWC emission at 20×, both need a RisingWave-side explanation before the freshness numbers leave the lab; the probe places the 1 s in epoch commit visibility, so the open part is the 2–4 s between the watermark passing and the EOWC emit.
- RisingWave Labs Terms of Service and any benchmark-publication clause: not read. Apache-2.0 carries none, but the same owner ruling that applied to Feldera should be applied before anything naming RisingWave is published.
- The internal-recovery data loss should be reproduced deliberately (on a host with a sane clock, or by forcing an engine-internal recovery) before it is quoted outside the lab; here it is four located runs of lost events (one in R1 smoke 2, three in the scored 1× trial) plus one unlocated smoke case, all on a host whose clock steps every half-minute.
- A durable-DML supplementary (dated, unscored, on a host with a sane clock): one 20× and one 1× R trial with `DML_WAIT_PERSISTENCE = true`, plus a forced engine-internal recovery in the default mode to reproduce the loss on demand, so the cost of the durable mode and the default-mode loss are both measured rather than inferred.
- A Kafka-source RisingWave sub-arm, out of scope here, is the obvious next pre-registration, since it would test whether a broker in front closes the loss path and what it costs in units and LOC.

## Files

- `results/v3/trial-20x-{1,2,3}/`, `results/v3/trial-1x/`, `results/v3/smoke-100x/`: `compare.json`, `latency.json`, `samples.jsonl` + `samples-summary.json`, the three alert files, R drain and replayer state, `risingwave-input-check.json`, `risingwave-recovery-log.txt`, `clock-steps.jsonl`, the edition probe, licence log lines and PID-1 command line; `results/v3/trial-*.log` driver logs; `results/v3/scored-status.txt`.
- `results/v3/faults-scored/R1/result.json` (+ alert file, drain/replayer state, clock steps); `results/v3/faults-smoke/R1/` (smoke 2, with the 387-event loss) and `results/v3/faults-smoke-1/R1/` (smoke 1).
- `results/v3/complexity-v3.json`, `results/v3/scorecard.json`, `results/edition-probe-risingwave.json` (matched by the `results/*.json` ignore pattern, so it needs `git add -f`).
- Removed after use: the regenerable Parquet landing folder `data/v3_b_in/`.
- New code: `risingwave/drain_alerts.py`, `faults/recover_r1.sh`, `v3/run_trial_v3.sh`, `v3/run_scored_v3.sh`, `v3/score_v3.py`, `v3/clock_watch.py`. Changed: `risingwave/deploy.py`, `risingwave/detection.sql`, `risingwave/replay_pg.py`, `v2/sampler.py`, `v2/measure_complexity_v2.py`, `v2/faults_v2.py`.

Reproduce: `bash v3/run_trial_v3.sh <label> 20` per clean trial (`1` for 1×), `../.venv/bin/python3 v2/faults_v2.py --only R1 --tag <tag> --results-dir v3`, `../.venv/bin/python3 v2/measure_complexity_v2.py results/v3/complexity-v3.json`, `../.venv/bin/python3 v3/score_v3.py`.

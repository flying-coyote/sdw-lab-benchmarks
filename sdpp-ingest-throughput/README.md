# SDPP ingest throughput — consolidated OSS-engine matrix

A first-party benchmark for one question the Capability Matrix's route/ingest
component raises but the lab had not yet measured directly: among the open
security-data-pipeline-platform (SDPP) tools, how fast does each one actually
*move* data — read a stream of security logs, apply a light filter, and emit the
survivors — and what does it cost in CPU and memory to do it? This is the
**throughput** leg, not the mapping-fidelity leg.

It now spans the viable no-sudo OSS engines, not just two: **Vector** and **Tenzir**
(stdin-drain CLIs), plus the **OpenTelemetry Collector (contrib)**, **Grafana Alloy**,
and **rsyslog** (tailing daemons, the last in two sub-modes). Cribl Stream and the
Splunk Universal Forwarder are documented-reference rows; the engines that only install
via a privileged package path (syslog-ng, AxoSyslog, Fluentd, Logstash, NXLog CE,
Fluent Bit) are listed under "Pending sudo install" with their install commands so an
operator can fold them into a follow-up run.

## Scope — what this measures, and what it deliberately does not

In scope: generic pipeline **ingest / transform / output throughput**. One seeded
corpus of Zeek `conn.log` NDJSON is handed to each engine; each reads it, drops a
class of low-value records, and writes the survivors to a sink. We report
sustained events/sec and MB/s, wall-clock, peak RSS, and CPU%, over repeated
trials with the spread.

Out of scope: **normalization / mapping accuracy.** This bench does not score how
faithfully any engine maps Zeek into OCSF — each runs its idiomatic config
for the *same logical filter*, and mapping fidelity is a separate question the lab
measures elsewhere (`ocsf-mapping-fidelity`, `flattening-fidelity`). Keeping the
two apart is deliberate: a route-by-value economics argument turns on raw
throughput and the cost of a drop, and folding fidelity into the same number would
confound the two.

## Which hypotheses it serves

This is the throughput evidence for the ingest/route capability:

- **H3-INTEGRATION-04 / Matrix Component 4 (route/ingest)** — the open SDPP layer
  is the component that decouples sources from sinks; this sizes how much an open
  router can push on one host, the precondition for "the engine is interchangeable
  over an open format."
- **H1-COST-02 (route-by-value economics)** — dropping low-value events before they
  hit paid storage only pays if the drop is cheap. The `discard`-vs-`file` split
  and the measured ~38% selectivity put a throughput number under that argument.

## What ran vs what is documented-only

| engine | status | how |
|---|---|---|
| Vector 0.40.0 (OSS, Datadog) | **RAN** (stdin-drain) | static `x86_64-unknown-linux-gnu` tarball to `~/.vector` — no sudo, no docker |
| Tenzir 6.0.0 (OSS) | **RAN** (stdin-drain) | static `x86_64-linux-static` tarball to `~/.tenzir` — no sudo, no docker |
| OpenTelemetry Collector contrib 0.153.0 | **RAN** (tailing daemon) | `otelcol-contrib` linux_amd64 tarball to `~/.otelcol` — no sudo, no docker |
| Grafana Alloy v1.16.3 | **RAN** (tailing daemon) | `alloy-linux-amd64.zip` to `~/.alloy` — no sudo, no docker; OTel filelog/filter/file are below GA, so run with `--stability.level` |
| rsyslog 8.2312.0 | **RAN** (tailing daemon, 2 sub-modes) | the system `/usr/sbin/rsyslogd`, run UNPRIVILEGED with a self-contained `-f <conf> -i <pidfile>` work dir under `_work/` (imfile → omfile), no root |
| Cribl Stream | **documented reference only** | commercial / license-gated; figures from Cribl's published sizing docs, cited in `results/RESULTS.md`, NOT a run on this host |
| Splunk Universal Forwarder | **documented reference only** | a forwarder, not a modes-A–D transform pipeline (output is Splunk S2S, no parse, no generic sink); EULA-gated; see `CAPABILITY-MATRIX.md` §3/§4 |
| Fluent Bit, syslog-ng OSE, AxoSyslog, Fluentd, Logstash, NXLog CE | **pending sudo install** | only install via apt/yum/docker (or, for Fluent Bit, no clean no-sudo static binary + no `cmake` here); install commands in `results/RESULTS.md` |

Every measured engine installed and ran locally with no privilege escalation and no
container runtime. rsyslog needed no root: run with an explicit config and pidfile and a
private `workDirectory`/imfile state under `_work/`, it tails the corpus and writes
survivors as the current user. The two daemon shapes (OTel/Alloy/rsyslog) tail the file
and never exit at EOF, so they are timed by polling to completion rather than by process
exit — see the timing-models note below.

## Two timing models (read before comparing across shapes)

- **stdin-drain** (Vector, Tenzir): `cat FILE | engine`, the process drains stdin and
  exits at EOF, so `/usr/bin/time -v` gives the whole picture — wall-clock is the drain
  time, plus peak RSS and CPU%.
- **tailing daemon** (OTel Collector, Alloy, rsyslog): the engine reads the corpus via
  its native file tailer and does NOT exit at EOF. The harness starts it under
  `/usr/bin/time -v`, polls to completion (file mode → emitted survivor count reaches the
  exact expected; discard mode → the engine's read offset into the corpus reaches EOF via
  `/proc/<pid>/fdinfo`, then its CPU settles as the buffered events drain), records that
  processing wall-clock with `perf_counter`, then SIGTERMs the engine child (leaving the
  `time` wrapper alive to flush its RSS/CPU report). The daemon wall-clock is
  start→completion, NOT the idle tail until terminate.

This is the honest apples-to-oranges line: a native file tailer and a stdin pipe are
different read paths, and the discard sinks differ per engine (Vector blackhole, Tenzir
`discard`, OTel `nop`, Alloy `otelcol.exporter.file`→`/dev/null`, rsyslog
`omfile`→`/dev/null`). Alloy has no nop exporter and its experimental `debug` exporter
back-pressures the filelog receiver into stalling, so Alloy's discard routes through the
file exporter to `/dev/null` — a real pulling sink that drains the whole corpus, at the
cost of a small re-serialize the others' nop sinks skip. Compare within a shape first,
across shapes with care. Both shapes are the real deployment form of each tool, not an
artificial handicap.

## Corpus + method

- **Corpus:** deterministic Zeek `conn.log` NDJSON, default **1,000,000 events
  (~0.40 GB, ~397 bytes/event)**, generated by `corpus.py` as a pure function of the
  row index off the lab master seed — byte-identical on every run, gated by a
  content fingerprint. Realistic field set (`id.orig_h`, `conn_state`, `history`,
  bytes/pkts counters) so a JSON parser does real work per line. 1M is the practical
  consolidated scale: process startup is amortized but the matrix (6 engine-rows × 2
  modes × trials) stays under a bounded runtime. (100k was startup-dominated; 10M is too
  slow across this many engines and crashed Tenzir on this host.)
- **Filter (the transform):** drop `conn_state ∈ {S0, REJ, RSTO}` — the short-lived
  / rejected / scan-shaped connections a route-by-value pipeline sheds before
  storage. The selectivity is a measured property of the corpus (~38% dropped),
  reported, not assumed. The expected survivor count is an **exact** count over the
  full corpus (not a prefix extrapolation), and every engine's emitted survivor count is
  verified equal to it before any throughput is quoted.
- **Identical input path:** both engines read the same bytes via `cat FILE |
  engine` from stdin, so neither gets a native file-tailer advantage and both pay
  the same kernel read path. (Vector's `file` source is a tailer that never EOFs;
  stdin gives a finite, drainable run for a fair wall-clock.)
- **Two sink modes per engine:** `discard` (read + parse + filter to a null sink =
  pure pipeline throughput) and `file` (the full route: + re-serialize + write
  NDJSON), so the cost of the output stage is visible separately.
- **Measurement:** `/usr/bin/time -v` for wall-clock, peak RSS, CPU%; events/sec
  and MB/s derived from the corpus size and wall-clock. Median + min/max + CV over
  3 trials, after a warmup pass. This is a wall-clock *pipeline* measurement (a real
  process draining the whole corpus), not a micro-benchmark; process startup is
  included and amortized over millions of events at the default scale.

## Confounds (controlled / stated)

- Same input bytes (one fingerprinted corpus), same logical filter selectivity,
  single host, one engine at a time (isolation).
- **Warm cache only** — the corpus is pre-read before timing; a true cold run needs
  a root `drop_caches` this unprivileged harness can't issue, so the numbers are
  steady-state warm and labelled as such (lab methodology §3).
- **Default parallelism each, not pinned** — Vector runs its async runtime over the
  host cores; Tenzir runs a single-shot pipeline. The CPU% column shows how much
  each actually used; the comparison is each engine in its idiomatic default, not a
  thread-matched one.
- Tier B, single WSL2 host, run on the Windows High Performance power plan per the
  repo methodology. Read `../BENCHMARKING-METHODOLOGY.md` before quoting a number.

## Reproduce

```bash
# from the sdpp-ingest-throughput dir, with the repo venv
SDW_DUCK_MEMORY_LIMIT=12GB \
  /home/jerem/sdw-lab-benchmarks/.venv/bin/python3 run.py --n 1000000 --trials 3
# quick run:        --n 100000
# pipeline-only:    --modes discard
# subset of engines:--engines "vector,tenzir,otelcol-contrib"
```

`run.py` regenerates the corpus, asserts its fingerprint is stable, computes the exact
survivor count, warms the file cache, then times each engine in each sink mode (the
stdin-drain engines to process exit, the tailing daemons by polling to completion) and
verifies the surviving event count matches the exact expected before writing `results/`.
To add a pending-sudo engine after installing it: drop a config template in `configs/`,
add a `cmd`/`cmd_files` builder and an `ENGINES` registry entry the same way the measured
ones were added, and add its name to `--engines`.

## Layout

```
corpus.py                    deterministic Zeek-conn NDJSON generator + fingerprint + selectivity
configs/
  vector_blackhole.toml      Vector: stdin json -> filter -> blackhole (discard)
  vector_file.toml           Vector: stdin json -> filter -> file (full route)
  otel_discard.yaml.tmpl      OTel: filelog -> json_parser -> filter -> nop
  otel_file.yaml.tmpl         OTel: filelog -> json_parser -> filter -> file
  alloy_discard.alloy.tmpl    Alloy: filelog -> json_parser -> filter -> debug/basic
  alloy_file.alloy.tmpl       Alloy: filelog -> json_parser -> filter -> file
  rsyslog_raw.conf.tmpl       rsyslog: imfile -> raw-line substring match -> omfile
  rsyslog_json.conf.tmpl      rsyslog: imfile -> mmjsonparse -> field filter -> omfile
run.py                       corpus + determinism gate, two timing models, runs every engine x mode, scorer
results/RESULTS.md           human table + documented references + pending-sudo + honesty boundary
results/results.json         machine-readable
_work/                       generated corpus + engine outputs + rendered configs (git-ignored-by-size)
```

The `.tmpl` configs carry `__CORPUS__` / `__OUT__` / `__MODDIR__` / `__WORKDIR__` /
`__STORAGE__` placeholders the harness fills per run into `_work/`.

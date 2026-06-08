# SDPP ingest-throughput — consolidated OSS-engine matrix

_Run 2026-06-08T16:01:11Z · B (single WSL2 host; wall-clock medians; Cribl + Splunk-UF rows are Tier-C docs-only)_

Corpus: **1,000,000 events**, 0.397 GB (396.9 bytes/event), Zeek conn.log NDJSON. Filter drops `conn_state` in `['S0', 'REJ', 'RSTO']` (EXACT selectivity 0.3802, expected survivors 619,777).

Host: 14 vCPU, WSL2, warm cache, 3 trials + 1 warmup, each engine default parallelism. Two timing models — stdin-drain (`cat FILE | engine`, exits at EOF) and tailing daemon (polled to completion, then SIGTERM); see Honesty boundary.


## Measured engines

| engine | version | shape | mode | events/s (median) | MB/s | wall s | wall CV% | peak RSS MB | CPU% | survivors match |
|---|---|---|---|--:|--:|--:|--:|--:|--:|:--:|
| vector | vector 0.40.0 (x86_64-unknown-linux-gnu 1167aa9 2024-07-29 15:08:44.028365803) | stdin | discard | 120,337 | 47.8 | 8.31 | 6.0 | 688 | 166 | yes |
| vector | vector 0.40.0 (x86_64-unknown-linux-gnu 1167aa9 2024-07-29 15:08:44.028365803) | stdin | file | 26,137 | 10.4 | 38.26 | 3.9 | 541 | 156 | yes |
| tenzir † | tenzir 6.0.0 | stdin | discard | 88,339 | 35.1 | 11.32 | 6.0 | 371 | 122 | — |
| tenzir † | tenzir 6.0.0 | stdin | file | 89,606 | 35.6 | 11.16 | 1.7 | 400 | 156 | yes |
| otelcol-contrib | otelcol-contrib 0.153.0 | daemon | discard | 103,824 | 41.2 | 9.63 | 1.0 | 216 | 140 | — |
| otelcol-contrib | otelcol-contrib 0.153.0 | daemon | file | 30,496 | 12.1 | 32.79 | 13.2 | 218 | 48 | yes |
| alloy | alloy v1.16.3 | daemon | discard | 63,919 | 25.4 | 15.64 | 0.6 | 265 | 136 | — |
| alloy | alloy v1.16.3 | daemon | file | 22,096 | 8.8 | 45.26 | 5.1 | 265 | 48 | yes |
| rsyslog (raw-line-match) | rsyslog 8.2312.0 | daemon | discard | 206,970 | 82.1 | 4.83 | 3.5 | 9 | 150 | — |
| rsyslog (raw-line-match) | rsyslog 8.2312.0 | daemon | file | 149,182 | 59.2 | 6.70 | 4.1 | 9 | 119 | yes |
| rsyslog (json-parse) | rsyslog 8.2312.0 | daemon | discard | 110,627 | 43.9 | 9.04 | 6.4 | 232 | 235 | — |
| rsyslog (json-parse) | rsyslog 8.2312.0 | daemon | file | 93,740 | 37.2 | 10.67 | 1.6 | 230 | 201 | yes |

† This engine had a trial crash and was retried (bounded). Tenzir 6.0.0 on this static build has an intermittent thread-pool segfault on shutdown (~1-in-6 at 1M, sink-independent — seen on both `discard` and `to_file`). The reported medians are over the successful trials; the crash count is recorded in `results.json` (`crash_retries`). This is a reliability finding about the build, not a harness fault.


`discard` = read+parse+filter to a null/nop sink (pure pipeline throughput). `file` = the full route: read+parse+filter+re-serialize+write to a file.

`shape`: **stdin** = drains the corpus off a `cat … | engine` pipe and exits at EOF (Vector, Tenzir). **daemon** = tails the corpus file and never exits at EOF, so it is polled to completion then terminated (OTel, Alloy, rsyslog). The two shapes are the real deployment forms of these tools, not an artificial handicap — read the caveats before comparing a stdin number to a daemon number directly.

rsyslog is shown in two sub-modes: **raw-line-match** (substring match on the raw line, no JSON parse — a line matcher, NOT a JSON field filter) and **json-parse** (`mmjsonparse` lifts the NDJSON and the filter keys off the parsed field). Per the capability matrix §4, only the json-parse sub-mode is parse-comparable to the JSON-native engines; the raw sub-mode is a different, lighter operation and is labelled as such.


## Documented references (NOT run here)

**Cribl Stream** — commercial / license-gated; not installed or run in this WSL env. Source tier: C (vendor docs).

- Throughput (published): Cribl sizes a single worker process at ~400 GB/day in / ~200-400 GB/day out as the planning rule of thumb (Cribl 'Sizing and Scaling' / Worker Process guidance). ~400 GB/day ≈ 4.6 MB/s sustained per worker process.
- Scaling model: Cribl's model is horizontal: a Worker Node runs N worker processes (≈ one per vCPU, minus headroom), and you add nodes to scale. So a single-process number is not comparable to a single-process Vector/Tenzir run without normalizing by process count — stated, not asserted as faster/slower.
- Pricing: Cribl Stream is free up to 1 TB/day ingest; above that it is a paid commercial license (Cribl pricing is credit/GB-based, contract-gated — no public per-GB list price to quote, so we do not invent one).
- Caveat: Tier C, vendor-published, per-worker-process. Do NOT compare directly to the measured OSS rows; it documents the commercial reference point only.


**Splunk Universal Forwarder** *(proprietary-but-free agent (installable, ecosystem-gated))* — forwarder, not a transform pipeline — no parse and no generic file/null sink (output is Splunk S2S to an indexer), so the read->filter->sink modes A–D do not apply.

- Natural metric: forwarding throughput (KBps self-reported in metrics.log) file -> S2S -> a Splunk receiver — a different test requiring a Splunk indexer, not run here.
- EULA: Splunk software: any published throughput number is subject to the project's Splunk EULA (1.2(v)/3(f)) and must be genericized ('schema-on-read SIEM forwarder') or cleared.
- Strengths: small footprint, robust at-least-once delivery (persistent queue + useACK), best-in-class Windows Event Log collection.
- Caveat: Documented reference only. Not comparable to the OSS pipeline rows; it solves a different problem (durable forwarding) and is measured by a different test.


## Pending sudo install (operator can fold these into a follow-up run)

These OSS pipelines were NOT installed here: this environment has no passwordless sudo, no `apt`, and docker is out of scope for this run. Each only installs via a privileged package path (or, for Fluent Bit, ships no clean no-sudo static binary and the host has no `cmake` for a source build). Install command provided so the operator can add them and re-run — the harness registry is structured to fold a new engine in the same way the measured ones were added (config template + `cmd`/`cmd_files` builder + an ENGINES entry).

| engine | license | why pending | install command |
|---|---|---|---|
| Fluent Bit | Apache-2.0 | no clean no-sudo static binary on GitHub releases (source-only); host has no cmake for a source build. Official path is apt/yum/container. | `curl -fsSL https://raw.githubusercontent.com/fluent/fluent-bit/master/install.sh | sh   # (apt/yum under the hood; needs root)` |
| syslog-ng OSE | LGPL-2.1 + GPL-2 | distro package; no first-party no-sudo static binary. | `sudo apt-get install -y syslog-ng-core   # Debian/Ubuntu` |
| AxoSyslog (syslog-ng fork) | GPL-3.0-or-later | Axoflow apt/container repo; no no-sudo static binary. | `curl -sSf https://pkg.axoflow.io/axosyslog/deb/install.sh | sudo bash && sudo apt-get install -y axosyslog` |
| Fluentd (td-agent / fluent-package) | Apache-2.0 | Ruby runtime + gems; distro/calyptia package. No no-sudo static binary. | `curl -fsSL https://toolbelt.treasuredata.com/sh/install-ubuntu-noble-fluent-package5.sh | sh   # (apt; needs root)` |
| Logstash | Apache-2.0 (Elastic) | JVM; Elastic apt/yum repo or tarball that expects a JDK. Heavy; needs root for the package path. (A tarball+JDK no-sudo route is possible but out of scope here.) | `sudo apt-get install -y logstash   # after adding the Elastic apt repo + a JDK` |
| NXLog CE | NXLog Public License (source-available, not OSI) | account-gated .deb/.msi download; no open no-sudo static binary. | `sudo dpkg -i nxlog-ce_<ver>_amd64.deb   # download is account-gated at nxlog.co` |

## Honesty boundary

- Tier B, single WSL2 host; wall-clock medians, not universal constants. Read this with the repo `BENCHMARKING-METHODOLOGY.md` and `CAPABILITY-MATRIX.md`.
- **Two timing models, stated.** stdin-drain engines (Vector, Tenzir) are timed by `/usr/bin/time -v` to process exit at EOF. Tailing daemons (OTel, Alloy, rsyslog) never exit at EOF, so they are polled to completion — **file** mode to the exact emitted survivor count, **discard** mode by watching the daemon's read offset into the corpus reach EOF (`/proc/<pid>/fdinfo`) and its CPU then settle as the buffered events drain. The processing wall-clock is taken at that point, then the engine child is SIGTERM'd (leaving the `time` wrapper alive to flush RSS/CPU). The daemon wall-clock is start->completion, NOT the idle tail until terminate. (The read-offset signal replaced an earlier CPU-plateau heuristic that mis-fired for Alloy's near-zero-CPU debug sink.)
- **Apples-to-oranges caveat.** A daemon's native file tailer and a stdin pipe are different read paths; the discard sinks differ (Vector blackhole vs Tenzir `discard` vs OTel `nop` vs Alloy file-exporter→`/dev/null` vs rsyslog `omfile`→`/dev/null` — Alloy has no nop and its experimental debug sink back-pressures the receiver, so it routes through the file exporter to /dev/null, a real pulling sink at the cost of a small re-serialize); and the daemons' CPU% includes idle-thread scheduler overhead. Compare within a shape first, across shapes with care.
- **Tenzir 6.0.0 instability (build, not harness).** This static Tenzir build segfaults intermittently on pipeline shutdown (~1-in-6 at 1M, on both `discard` and `to_file`), so a trial may crash and is retried a bounded number of times; medians are over the successful trials and the crash count is in `results.json`. Treat Tenzir's row as indicative, and the instability itself as a finding.
- **Warm cache only.** The corpus is pre-read before timing; a true cold run needs a root `drop_caches` we don't have, so these are steady-state warm numbers.
- **Exact survivor verification.** The expected survivor count is an EXACT count over the full corpus (not a prefix extrapolation), and every engine's emitted survivor count is checked equal to it before its throughput is quoted (`survivors match` column).
- Process startup is included in wall-clock and amortized over the events at this scale (1,000,000); at small N it would dominate, which is why 100k was retired for 1M.
- Each engine ran its idiomatic config at default parallelism (not pinned). The filter is logically identical across engines and the survivor count is verified equal.
- **Normalization/mapping accuracy is out of scope** — this measures throughput of a light filter/route, not how faithfully any engine maps Zeek to OCSF.

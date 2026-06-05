# Lab benchmarking methodology

A cross-cutting standard for every benchmark in this repo. It exists because of a concrete miss: the
BENCH-E large-scan arm compared Apache Iceberg against DuckLake and found DuckLake read faster while
using more storage — until a diagnostic (`ocsf-read-scan/config_probe.py`) showed the two write paths
used **different Parquet codecs and row-group sizes by default** (Iceberg via pyiceberg = ZSTD, 1M-row
groups; DuckLake via DuckDB = Snappy, 122,880-row groups). The "format comparison" was confounded by
compression and layout. This document is the rule set that prevents that class of error, drawn from the
benchmarks that take methodology seriously — ClickBench, db-benchmarks.com, and benchANT — and scoped
honestly to what a single WSL2 host can and cannot enforce.

## Decision — the standard we commit to

One standard, stuck to: the **db-benchmarks rigor principles** (configuration parity, cold/hot,
coefficient of variation, isolation) as the north star, with **ClickBench's reporting model** (cold +
hot-min, default-config baseline, within-class relative ratios) for how results are presented. Adapted
to a single embedded-engine host, this is fully achievable here — verified, not assumed.

**Environment (decided): the Beelink under WSL2 with the Windows "High Performance" power plan.** We
characterized the host (`env_characterize.py`) under both plans. On the default "AMD Ryzen Balanced"
plan, sustained queries ran at CV 2.9–5.8% and short (~26ms) queries at CV 19.8% — the on-demand
governor's ramp lag. Switching the Windows power plan to High Performance dropped in-memory-heavy CV
from **5.8% → 0.8%**, the short-query CV from **19.8% → 2.7%**, with every query class GREEN (<5%) and
no thermal drift. So the CPU-frequency variance that would otherwise justify a native-Linux boot is
resolved by a Windows-side power-plan setting; **we run benches on High Performance and do not need to
leave WSL2.** Re-run `env_characterize.py` if the host or plan changes; if a future workload shows CV
above its claimed delta there, escalate (native Linux boot, or a cloud fixed-frequency instance).

## Principles

### 1. Configuration parity (the rule the confound taught us) — ENFORCED
When the benchmark's claim is about system/format A vs B, every knob that is *not* the variable under
test must be held equal and **verified**, not assumed. For a Parquet-backed comparison that means:
compression codec, compression level, row-group size (in **both** rows and bytes), page size, Parquet
version (V1/V2), target file size, and sort order. Write the comparison both ways and read the actual
file footers (`pyarrow.parquet` metadata or DuckDB `parquet_metadata()`) to confirm the knob took before
trusting any latency. The residual difference after parity is the real system effect; the difference
before parity is mostly encoding. Report a **default-config** comparison and a **parity-normalized**
comparison as two distinct results — never let a default mismatch masquerade as an architecture finding.

### 2. Same hardware, same engine, same data — ENFORCED
One physical host, one read engine across all arms (so the variable is the system, not the client), and
a seeded corpus that is byte-identical across arms. Corpus identity is fingerprinted; results are scored
twice and asserted identical on **logical content** (not file bytes — see `ocsf-parquet-determinism`).

### 3. Cold and hot, reported separately — PARTIAL (cold needs privilege)
Analytical scans are often cold in production, so a hot-only number overstates. ClickBench's model:
**cold** = clear OS page cache + restart the engine process before the query; **hot** = the fastest of
N warm runs. We adopt the cold/hot split and report both. Caveat on this host: clearing the OS page
cache requires `echo 3 > /proc/sys/vm/drop_caches` as root; the harness runs unprivileged, so a true
cold run needs a privileged pre-step (a `sudo` drop-caches, or a NOPASSWD rule). Where that isn't
available, runs are labelled **hot/warm only** rather than pretending to be cold.

### 4. Stability before claims — coefficient of variation — ENFORCED
Per db-benchmarks: do not claim "A is N% faster than B" if the run-to-run coefficient of variation is
itself ≳ N%. Every latency is reported as a **median over ≥3 trials with its CV**; a format/system
delta is only called real when it exceeds the CV. This replaces single-run medians, and it is also our
honest substitute for the CPU-frequency pin we cannot set (see §7).

### 5. Isolation — ENFORCED by discipline
Nothing else heavy runs during a timing pass (this is also the OOM-serialization rule from the resource
config). Heavy benches are run one at a time; concurrent runs invalidate the timing.

### 6. Defaults vs tuning, declared — ENFORCED
Default-configuration results are the baseline (ClickBench's stance). Any tuning is a separate, labelled
result with the knobs documented. The DuckLake/Iceberg default-codec mismatch is precisely why both a
default and a parity result are required for any format comparison.

### 7. CPU frequency — SOLVED via the Windows power plan (not a WSL caveat after all)
A WSL2 guest can't set the governor, but the Windows host can, and that is sufficient: the High
Performance power plan holds the cores near max and removes the on-demand downclock that was the noise
source (§Decision: CV 5.8%→0.8% on sustained, 19.8%→2.7% on short queries). So run benches on High
Performance and confirm with `env_characterize.py`; CV reporting (§4) catches any residual variance.

### 8. What remains genuinely ACKNOWLEDGED, not faked
- **Non-invasive measurement** (benchANT: don't run the harness on the system under test). DuckDB is an
  embedded engine, so timing is necessarily in-process; we keep harness work out of the timed region and
  accept in-process measurement as inherent to embedded-engine benchmarking.
- **Cold runs** need a root OS-cache purge (`echo 3 > /proc/sys/vm/drop_caches`); unprivileged runs are
  labelled hot/warm only rather than pretending to be cold.

## Reporting checklist (every comparative bench)
- [ ] Per query: cold (if privileged) and hot-min, plus **median + CV over ≥3 trials**.
- [ ] On-disk size, file count, row-group count, **and the footer-verified codec/row-group** per arm.
- [ ] Load/write time, separately from read latency.
- [ ] Relative ratios within a single hardware+tuning class (cross-class comparison is invalid).
- [ ] Tier label, single-machine caveat, and the explicit list of what was held constant vs varied.
- [ ] Logical answer-equality across arms.

## Sources
- ClickBench — github.com/ClickHouse/ClickBench (run protocol, scoring weights, self-acknowledged biases)
- db-benchmarks — github.com/db-benchmarks/db-benchmarks (cache purge, restart-per-query, CV, CPU pin, NVMe)
- benchANT — benchant.com/blog/database-benchmarking (non-invasive measurement, statistical rigor)
- ClickHouse benchmark dashboard — benchmark.clickhouse.com (within-class relative normalization)

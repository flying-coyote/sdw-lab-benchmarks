---
type: benchmark-spec
title: "Lab Benchmarking Methodology — Cross-Cutting Standard"
created: 2026-06-05
tags: [methodology, benchmarking, config-parity, coefficient-of-variation, parquet, wsl2]
---

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

## Confidentiality: what never lands in this repo

This repo is public, and a private, NDA-gated catalog benchmark exists alongside it, so the line between
them is written here rather than left to memory (owner ruling 2026-11-08, from the 2026-07 grill bank 3B
Q5). Three classes are never committed to this repo, in a results file, a README, a commit message, a
fixture or a code comment:
- **Client names**, and any detail specific enough to identify a client engagement (environment sizes,
  vendor stacks, incident dates). Anonymize to a role or sector, or leave it out.
- **NDA-sourced numbers**: any figure obtained under a non-disclosure agreement, a vendor evaluation
  licence or a private briefing, even when the number looks generic.
- **Content from the private catalog benchmark**: its workloads, results,
  configurations, vendor names in that context, and anything derived from them.

There is no scanner for this, by decision. The control is the author checking each of the three classes
before a commit, and a reviewer checking again before a push. When it is unclear whether something falls
in a class, it stays out until Jeremy rules. The DeWitt-clause restriction (no public results for an
engine whose licence forbids them) is a separate rule and binds as well.

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

### 7a. Guest clock rate: chrony since 2026-11-07 (dated note)
On the Beelink (Ryzen 7 5800H, WSL2), the guest clock ran about 4% slow against Windows until chrony
replaced systemd-timesyncd on 2026-11-07. Timesyncd was correcting the drift by stepping the realtime
clock forward roughly 1.2 s every 32 s, and containers under Docker Desktop share the WSL2 kernel, so
they inherited the same slow clock and the same steps. Three consequences for results produced on this
host before that date:
- Absolute durations read about 4% short.
- Ratios between arms measured in the same run are unaffected, because every arm saw the same clock.
- Comparisons between event time and wall-clock time may contain steps. The stream-complexity RisingWave
  v3 results (`stream-complexity/results/RESULTS-v3-risingwave-2026-11-07.md`) already carry this caveat.

The in-container picture did not match the host one exactly: the v3 run logged the container wall clock
stepping backwards about 2.6 s every 27 to 30 s, with a larger gap between monotonic and wall time than
the host's 4%. I have not reconciled the two, and the likeliest reading is that more than one time
correction was acting on the shared kernel. After chrony, a 40 s check inside a container showed
`/proc/uptime` and `date` advancing together (40 s each, at one-second resolution), and the host matched
Windows to within a millisecond over 40 s, so treat the pre-2026-11-07 numbers as carrying a clock error
of unknown sign in the container case, not a clean 4%.

Pre-run check from now on: `chronyc tracking` should report a small `System time` offset (milliseconds or
less, not seconds) before a timed run starts. If chrony is not running, or the offset is large, fix the
clock first and treat any absolute timing from that run as suspect.

### 7b. Rig stamp on latency-bearing RESULTS files — ADOPTED 2026-11-08; back-stamping of existing files pending
Every RESULTS file that reports an absolute duration (latency, throughput, wall time, load time) carries a
rig stamp near the top: host (for example the Beelink, Ryzen 7 5800H, WSL2), Windows power plan, the date
of the run, engine versions, and the clock state at the time, meaning either "chrony, `chronyc tracking`
offset checked" or "pre-2026-11-07, timesyncd: absolute durations read about 4% short, container clock
error of unknown sign (§7a)". Results that report only correctness, answer equality, sizes, counts or
within-run ratios do not need one. The stamp exists because the §7a clock error is invisible in a number
once it leaves the run, and a stamp is the only way a reader can tell a pre-chrony timing from a corrected
one (owner ruling 2026-11-08, from grill bank 3B Q4). Back-stamping applies to the existing latency-bearing
RESULTS files, with `ocsf-read-scan/` and the other pre-chrony timings done in the same pass; until a file
is stamped, treat its absolute durations under §7a.

### 8. What remains genuinely ACKNOWLEDGED, not faked
- **Non-invasive measurement** (benchANT: don't run the harness on the system under test). DuckDB is an
  embedded engine, so timing is necessarily in-process; we keep harness work out of the timed region and
  accept in-process measurement as inherent to embedded-engine benchmarking.
- **Cold runs** need a root OS-cache purge (`echo 3 > /proc/sys/vm/drop_caches`); unprivileged runs are
  labelled hot/warm only rather than pretending to be cold.

### 9. Pin the artifact, sweep the scale (the chDB lesson) — ENFORCED for correctness findings
The chDB Bloom-pushdown undercount made both halves of this concrete, after a near-miss in each direction.
- **Pin the artifact, not the generator.** Parquet from a parallel writer is not byte-reproducible (the
  row-group composition shuffles run to run — see `ocsf-parquet-determinism/`), so "regenerate with the
  generator + pinned versions" does *not* pin a finding that depends on the file's layout. A
  reproducibility-critical result records `lib.common.pin_artifact()`: a layout-independent **logical
  fingerprint** (hash the rows, not the bytes), the **structural manifest** (row count, row-group count,
  per-column encodings, bloom-filter presence — i.e. the finding's *preconditions*, made explicit instead of
  left implicit in "the generator"), and the byte hash (exact, when the write was forced deterministic).
- **Sweep the scale; don't trust one "cheap" point.** The undercount reproduced at 100M rows / ~8k row groups
  and *not* at 10M / ~800 — a smaller scale chosen to make the bug cheap to study reported clean. Correctness
  findings run through `lib.common.scale_sweep()` across at least two scales, and the isolation scale is
  validated against the scale the bug was first seen at rather than assumed to shrink. Worked example:
  `clickhouse-vs-duckdb/scale_pin_repro.py`.

### 10. LLM arms: stability, contamination, harness, strata — ENFORCED for any bench with a generation step
Added 2026-11-07 from production evaluation practice reported at [un]prompted II (October 2026). The
engine principles above assume a deterministic system under test; an LLM arm is not one, and four
failure modes follow from that which CV over latency does not catch.
- **Verdict stability (run-to-run flip rate).** Report, per (arm, query, model), the share of repeated
  trials whose scored verdict differs from the modal verdict, beside the per-trial mean. Wiz re-ran its
  production SOC agent on identical threats and found "on around 6% of the time, the verdict flips";
  a shadow model with "98% of verdict agreement" on ~11,000 production threats still "generated 44% more
  false alarms", and one threat "investigated 33 times in the same day" was wrong in 32 of the 33 at high
  self-reported confidence, so self-reported confidence is not a substitute measure (Waitzenberg/Harush,
  "Same Threat, Two Verdicts"; vendor describing its own agent, Tier B for method, C for efficacy). BENCH-C v2 and
  v2.1 already collect 8 trials per cell, so the flip rate is derivable from data on disk; the frozen
  pre-registrations are not amended, and the metric applies to new runs. Agreement between two arms or
  two models is reported as agreement, never as accuracy.
- **Contamination exposure, and a no-data arm where the corpus is public.** Public security datasets are
  memorized: run the same questions with the evidence withheld and report that score as the floor. Louie.ai
  ran the BOTSv3 CTF "with Splunk disabled" and scored "Opus 5.5 29% Opus 4.6 17% Sonnet 4.6 10%"
  (Meyerovich, "Three Years of Evals Later", deck; vendor, Tier C), and Kovalsky/Arshad got "207 right again"
  after withdrawing the documentation the agent had read ("Your AI Analyst Is Confidently Wrong"; Tier B). The mapping oracle's
  `none` condition is this lab's existing precedent and generalizes. Deterministic arms with no model in
  the loop (pySigma-compiled rules, curated SQL) are exempt and say so in their README.
- **Harness, prompt format and tuning disclosed; a tuned lift is re-run on a second model before it is
  claimed.** Prompt and skill optimizations overfit: Dan Dye saw operational loss drop 99% after
  evolving his skills, and "when I test those changes in a different model, or a different harness, the
  improvements disappear"; rubrics embedded in the skills were "basically giving the LLM the answer to the
  test" ("Engineering Context for SOC Agents"; Tier B). Scoring rubrics and gold answers never enter a prompt, skill or
  grounding note. `RESULTS-headtohead-2026-06-16.md` already notes that no prompt ablation was run; this
  names the rule.
- **Per-stratum reporting, never pooled.** Report every dataset, source and query class separately before
  any pooled number. Intuit's activation-probe guardrail held 98.1% recall on 11,086 held-out attack
  prompts and 85.4% on a disjoint 996-prompt red-team set, and "one backbone missed 140 of 140 injections
  rendered as text inside an unfamiliar image layout", which a pooled score hid (Shtar/Elad,
  "Reading the Residual Stream", deck; Tier B). BENCH-A's routine/adversary-tail split is the existing instance.
- **Seeded gold subset as a cheap oracle.** Where a full answer key is too costly, a hand-verified subset
  of about 100 items dispersed inside the larger task can stand in for whole-run precision and recall;
  Kovalsky/Arshad report it "turned out to be a pretty good proxy for overall model performance" across a
  4,000-plus question run, and that recall collapse, not hallucination, dominated as evidence volume grew
  ("Hallucination is a tiny, tiny percentage of the overall problem"; Tier B, one team's
  experience). Score false negatives as a first-class outcome, not only invented answers.
- **Synthetic-data recognition.** Frontier models can tell simulator output from real attacks: Torq
  reports that with Caldera or Kali environments "frontiers tell that they're synthetic data and not real
  attacks very early on", and that well-known public SOC datasets are saturated (Cohen/Herzog,
  "When Humans Can't Make It Hard Enough"; vendor, Tier C). A synthetic corpus fed to an LLM arm declares this as a validity
  limit, and a run can probe it by asking the model directly whether the evidence looks synthetic.

Every quote above was re-checked on 2026-11-07 against the talk transcripts and decks, which are held
locally rather than in this repo.

## Reporting checklist (every comparative bench)
- [ ] Per query: cold (if privileged) and hot-min, plus **median + CV over ≥3 trials**.
- [ ] On-disk size, file count, row-group count, **and the footer-verified codec/row-group** per arm.
- [ ] Load/write time, separately from read latency.
- [ ] Guest clock checked before the run (`chronyc tracking`, small `System time` offset; §7a).
- [ ] Rig stamp at the top of any RESULTS file that reports an absolute duration (§7b).
- [ ] Nothing from the three never-commit classes (client names, NDA-sourced numbers, private catalog-benchmark content).
- [ ] Relative ratios within a single hardware+tuning class (cross-class comparison is invalid).
- [ ] Tier label, single-machine caveat, and the explicit list of what was held constant vs varied.
- [ ] Logical answer-equality across arms.
- [ ] For a correctness finding: the **pinned artifact** (logical fingerprint + manifest) and the **scales swept**.
- [ ] For an LLM arm (§10): **verdict flip rate** over repeated trials beside the mean; **contamination exposure
  declared**, with a **no-data arm** run where the corpus is public (or the deterministic-arm exemption stated);
  **harness, prompt format and any tuning disclosed**, with a tuned lift re-run on a second model; results
  **per stratum** before any pooled figure; synthetic-corpus recognition named as a limit.

## Sources
- ClickBench — github.com/ClickHouse/ClickBench (run protocol, scoring weights, self-acknowledged biases)
- db-benchmarks — github.com/db-benchmarks/db-benchmarks (cache purge, restart-per-query, CV, CPU pin, NVMe)
- benchANT — benchant.com/blog/database-benchmarking (non-invasive measurement, statistical rigor)
- ClickHouse benchmark dashboard — benchmark.clickhouse.com (within-class relative normalization)
- [un]prompted II, October 2026 (transcripts and decks held locally, not in this repo): Tal Waitzenberg and
  Erez Harush (Wiz), "Same Threat, Two Verdicts: Shadow Testing Our SOC Agent"; Leo Meyerovich (Louie.ai),
  "Three Years of Evals Later: What's Changing in Model and Harness IR/SOC Scores"; Maxim Kovalsky and Ali
  Arshad, "Your AI Analyst Is Confidently Wrong: Adversarial QC for Agentic Security Analysis"; Dan Dye,
  "Engineering Context for SOC Agents: Lessons, Failures and Open Questions"; Shtar/Elad (Intuit),
  "Reading the Residual Stream: Productizing Activation-Probe Security at Intuit"; Noam Cohen and Jeremy
  Herzog (Torq), "When Humans Can't Make It Hard Enough: Self-Hardening Environments for Frontier AI
  Investigators". Practitioner talks, Tier B for method; vendor efficacy figures Tier C.

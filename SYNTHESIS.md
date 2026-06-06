# Campaign synthesis — what the benchmarks actually argue

This is the through-line across the extended benchmark campaign (R0–R6), written after the runs rather
than before, so it reflects what the measurements forced me to change my mind about. The per-run results
and the nine corrected assumptions live in [`CAMPAIGN.md`](CAMPAIGN.md); the methodology spine — CV on
every comparative run, config-parity or same-files registration when writers differ, isolation, the
single-machine caveat — lives in [`BENCHMARKING-METHODOLOGY.md`](BENCHMARKING-METHODOLOGY.md). What
follows is the argument the campaign makes when you read the runs together.

## The strongest result wasn't a speed number

The single most important thing the campaign produced is the chDB correctness divergence (R3): at 100
million rows, embedded ClickHouse returned a selective-lookup `count(*)` forty-nine rows short of DuckDB
over the *same Parquet bytes*, with no error raised, and it only surfaced because the benchmark refuses
to report a latency until both engines return identical answers. The defect is narrow and real — chDB
4.1.8's Parquet equality filter drops matching rows in the tail row groups of a many-group file, while
`LIKE`, chDB's own MergeTree store, and DuckDB all match the generator's ground truth — and I reproduced
it deterministically down to a cheap 10M-row case. A benchmark that only timed the two engines would have
published chDB as competitive on that query and never noticed the number was wrong. For security data
this is the whole game: a `count(*)` under a filter is a detection threshold or a compliance figure, so a
fast engine that is silently wrong is worse than a slow engine that is right. The cross-engine
answer-equality gate is not ceremony, it is the product — and that is the empirical core of the
fair-broker position, that the value is in the verification, not the speed.

## The thing people argue about is rarely the lever

The format runs kept dissolving the headline question into a different, more specific one. "DuckLake reads
faster than Iceberg" looked true under defaults (~1.1–1.7×), but matched codec narrowed it and
byte-identical data collapsed it to roughly parity, because the read-speed lever is the Parquet
writer/encoder, not the table format, and the storage gap people quote was Iceberg defaulting to ZSTD
against DuckLake's Snappy rather than anything intrinsic. The compression question turned out not to be
"which codec" but "which regime": a schema-trained ZSTD dictionary roughly triples the ratio on per-event
payloads (the streaming, queue-message, per-record-retention hot path security ingestion actually runs)
and then fades to nothing as you batch toward a columnar row group, where the format captures the
redundancy structurally and beats every per-record approach. And the planning question (R6) was never
"which format plans faster" but "where does the metadata live" — Iceberg enumerates files by reading
manifests, so its end-to-end query and especially its planning climb with file count (6.5× and 17.6×
across a 10→200-file ladder here), while DuckLake resolves the same question with an indexed SQL-catalog
lookup that stays flat (~3 ms regardless), which is the architectural answer to exactly what the Iceberg
V4 metadata work targets. In every one of these, naming the real variable and controlling for it changed
the answer, which is the applied-bridge thesis in miniature: data-engineering discipline (config-parity,
same-files registration, regime-awareness) carried into a security-data decision that was otherwise being
made on a vendor's default.

## Scale, and then trust the number

The coefficient of variation collapsed from roughly 19% at one million rows to about 4% at a hundred
million, and below ten million the micro-query rankings were noise — several apparent wins at small scale
were ties inside the noise floor. The practical rule the campaign earns is that a comparison which
doesn't report its CV and scale past the noise floor is decoration, and it is why the audit pass (R0 and
the re-runs that opened the campaign) was worth doing before any new measurement: it put a stability
number on every comparative bench so a later delta can be believed or discounted on evidence rather than
hope.

## Normalization has a SOC-facing cost, and it isn't one number

The detection runs (R1, with R2's dose-response and second-chain behind them) show that OCSF
context-collapse does not impose a uniform fidelity tax. The same portable Sigma rules that fire cleanly
on the fidelity store split two ways on the coarse store, and which way depends on which coarsening knob
touched the field the rule keys on: a generic rare-DNS sampling default drops the single C2 resolution
and the rule goes *blind* (recall 1→0, and silently — no alert is raised at all), while coercing
MFA-absence to false makes the priv-esc rule *cry wolf* (precision 1.0→0.004 as 267 routine MFA failures
join the one real needle). The dose-response curve is flat-then-step rather than smooth, and a second,
independent attack chain reproduced the headline within 0.01, so the effect is a property of what coarse
normalization discards, not an artifact of one planted chain. The transferable claim is that fidelity has
to be evaluated against the detections you actually run, because the worst failure is the silent one.

## Materialization is a bet you can price

The materialized-view run (R5) is the cleanest example of the campaign refusing a one-number answer. The
read speedup is real and large (45–77× to serve a SOC-dashboard panel from a few hundred pre-aggregated
rows instead of scanning twenty million), but the honest accounting is three numbers, not one:
incremental maintenance is only cheaper than full recompute when the base is large relative to the
arriving batch (2.9× for a low-cardinality panel here, break-even for a high-cardinality one), storage
overhead scales with the aggregate's cardinality rather than the table's, and an MV answers only the
questions you pre-decided — an ad-hoc hunt still pays the base scan. An MV is a bet that a fixed question
set is worth paying storage and per-batch maintenance to answer fast, which is exactly right for an
always-on dashboard and wrong for exploration.

## Where this leaves the thesis, and what's still open

Read together, the campaign is evidence for the program's actual claim, which is not that any one engine
or format wins but that the open stack is decidable on its merits *when you measure correctly* — and that
"correctly" is a higher bar than the vendor benchmarks clear, because it includes a correctness gate, a
noise floor, and control of the real variable. The chDB finding is the sharp end of why an accountable
party who verifies belongs in the picture at all: the open components are good, and they are also capable
of being silently wrong at the scale where you would trust them, so independence without verification is
not enough. That is the fair-broker / capability-matrix method demonstrated on its own benches rather than
asserted, and it keeps the per-vendor scores honest because every one of them rests on a run that reports
its CV and checks its answers.

Validated this campaign: the audit foundation (CV across every comparative bench), the format
decomposition (read-neutral on identical bytes; the encoder is the lever), the compression regime
crossover, the MV cost structure, the planning-vs-fragmentation scaling, the detection blindness/noise
split, and the chDB correctness divergence with a deterministic reproduction.

Still open, and honestly labelled: R7 (streaming write-contract — micro-batch cadence, commit-latency
percentiles, read-while-write coherence, and where DuckLake's inlining inverts) is the next run; R8
(same-files at one billion rows, the format-neutrality result at scale rather than at 100M) follows, with
the caveat that routing its data to the E: SSD over drvfs inflates absolute latencies and the relative
comparison is the part that survives; R9 (device-measured DWPD under sustained ingest) likely stays
non-viable on this box because WSL2 can't read the host NVMe's SMART data through `smartctl`, and I'd
rather say so than fake it. The frontier leg of BENCH-B (needs an API key), the OBDA arm of BENCH-C
(needs an Ontop + R2RML setup), and the named-practitioner realism sign-off on BENCH-A all need a
dependency or a human and sit outside the single-box autonomous run. The essay slate in `CAMPAIGN.md`
maps each finding to a `/writing` pillar; all of it goes through the voice and publication gates before
anything reaches the site, and the per-vendor magnitudes stay paid IP — only the method and the
relative shapes are public.

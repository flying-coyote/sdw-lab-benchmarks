# engine-join-specialization — SR / CH / Trino / Dremio joins on shared Iceberg

**PRE-REGISTRATION (2026-06-10, committed before any scored run).** The lab has no
first-party measurement of multi-table JOIN latency on any engine — every prior join result
is a correctness or demonstration result, and the only quantitative engine-vs-engine join
anchor in the public assets is a Tier-C vendor-published number ("ClickHouse 30–120 s vs.
StarRocks 5–30 s on TB-scale multi-table joins", cited with its caveat in the
starrocks-clickhouse-pair reference). Meanwhile the deck, MATRIX.md, and the references
assign engine roles *by join capability* (StarRocks = ad-hoc/CBO joins, Trino = federation
joins, ClickHouse = scheduled single-table, Dremio = accelerated mixed workloads), and deck
slide 16 concedes "broader joins untested." This bench is the first-party replication those
assignments are waiting on.

**Provenance note:** `splunk-db-connect-benchmark/results/starrocks_vs_clickhouse_20251207_023341.json`
is **simulated** (`np.random.uniform` latencies in `simulate_query_execution()`); it is
superseded by this bench and must never be cited as a measurement.

## Scope boundary (read before citing)

Two different capabilities travel under the word "joins" in the assets:

1. **Single-store multi-table join execution** — joining tables that live in the same
   (Iceberg) store. **This bench measures that.** It is the axis on which StarRocks claims
   superiority over ClickHouse.
2. **Cross-source federation joins** — joining Iceberg to MySQL/Postgres/Snowflake in one
   query. **This bench does NOT measure that.** MATRIX.md's "Trino > Dremio > ClickHouse >
   StarRocks for cross-source JOINs" ordering is a federation claim (connector-count proxy)
   and is neither confirmed nor refuted here. A federation bench is the named follow-up.

## Why TPC-H and not ClickBench (the benchmark-politics layer)

ClickBench is 42 queries against one denormalized flat table — zero joins — which is why
ClickHouse dominates it: it measures exactly the workload ClickHouse was designed for.
TPC-H is join-heavy (multi-way joins, correlated subqueries), which is why StarRocks states
its claims in TPC terms. The choice of instrument *is* the marketing position, and an
honest engine-assignment story has to measure on both grounds plus the ground that actually
matters here (SOC-shaped correlation). So: ClickBench is **cited, not re-run** (public
results at benchmark.clickhouse.com; its joinlessness is the relevant fact); a TPC-H-derived
join subset is **run** for comparability with the vendor claims; and a SOC join suite is
**run** because no published benchmark covers security-shaped joins across engines (verified
gap, 2024–2026 sweep).

**TPC disclaimer (required language):** the F1 workload is *derived from* TPC-H (DuckDB
`tpch` extension dbgen, SF10). It is not an audited TPC result and is **not comparable** to
published TPC-H results. Public assets must say "TPC-H-derived join workload."

## Hypotheses

- **H-ARCH-06** (engines hyper-specialize by workload; VALIDATED on industry evidence only)
  — this is its first first-party lab evidence, extending specialization to the join axis.
- **H-ARCH-02** (multi-engine inevitable; graduated 0.97) — extends the measured
  workload-shape matrix with the missing join shapes.
- Matrix Component 3 (Archetype A/B engine scores), deck slides 10/15/16, and the
  starrocks-clickhouse-pair reference consume the result (task #13 realignment).

Expected outcome, stated before the run: see Predictions. The number we publish is whatever
survives the CV gate.

## Arms

| Arm | Engine + version | Read path | Notes |
|---|---|---|---|
| `starrocks` | StarRocks 4.1 allin1 | external Iceberg catalog (REST) | CBO + runtime filters; the claimed join leader |
| `clickhouse_iceberg` | ClickHouse latest (26.5+) | `DataLakeCatalog` REST db (catalog-mediated) | tests whether the 24.12→26.4 join-optimization run survives the Iceberg read path (undocumented publicly) |
| `clickhouse_native` | same server | MergeTree copies of the same tables | extends the flagship rerun's native-vs-Iceberg split to joins |
| `trino` | Trino 481 | Iceberg REST catalog | mature CBO + dynamic filtering; single-node so no cluster-shuffle advantage |
| `dremio` | Dremio 26.0 OSS | Nessie source | **Reflections OFF** (declared: the 20× TPC-DS marketing number measures materialization, not joins) |

Config parity: each heavy engine gets `mem_limit: 24g` (one engine runs at a time on the
48 GB host; parity is by equal limit, not by tuning). Engine defaults otherwise — no hints,
no manual join reordering, no statistics priming beyond what the engine does automatically
(automatic stats are part of what's being measured, esp. ClickHouse 25.10+).

**Catalog plan:** primary = a single Nessie catalog for everything — pyiceberg writes via
Nessie's Iceberg-REST endpoint (`http://nessie:19120/iceberg/`), Trino + StarRocks point
their REST catalogs at the same endpoint, Dremio reads the native Nessie API, ClickHouse
reads the raw S3 paths — so every arm reads **byte-identical files**
(`reference_format_compare_writer_confound`). Declared decision rule: if StarRocks or Trino
fail the smoke test against Nessie's REST endpoint, fall back to the MOAR-proven split
(iceberg-rest fixture for SR/Trino + a second Nessie-written copy for Dremio) and report the
two-catalog confound explicitly.

**Declared deviation (build phase, before any scored run):** the `clickhouse_iceberg` arm
reads `icebergS3()` against a **planted metadata pin**. Reasons, both measured during
build: (1) Nessie names every metadata file `00000-<uuid>.metadata.json` with no sequence
numbers, so icebergS3's "latest metadata" resolution silently picked an intermediate
commit — 54.0M of 59.99M lineitem rows, no error; the write-once-is-safe assumption does
not hold under Nessie naming (`reference_clickhouse_icebergs3_stale_snapshot`). (2) The
catalog-mediated fix (`DataLakeCatalog` REST database, experimental) read correctly live
but crash-loops the server at boot once persisted (pthread mutex assertion on database
load), so it cannot survive an engine restart. Final mechanism: after load, a byte-copy of
the catalog's current metadata pointer is planted per table under a sort-last name
(`99999-….metadata.json`), making catalog-less resolution deterministic and correct;
verified count-exact per table. Tables are write-once; any reseed purges the table's S3
prefix first. ClickHouse arms also carry `max_memory_usage = 18e9` (below the 24g cgroup)
so an oversized join fails as a loud per-query resource DNF instead of killing the server
(observed: TPC-H Q21 took the server down with SIGSEGV in smoke).

## Corpora (pinned by sha256)

- **TPC-H SF10** via DuckDB `tpch` extension (deterministic dbgen): 8 tables, lineitem
  ≈60M rows, exported to Parquet and written to Iceberg via pyiceberg (2M-row appends).
- **Zeek conn 10M** — the same pinned corpus as `zeek-flagship-rerun`
  (sha256 `c6ed5e3c05f311a6…`), reloaded here through the shared catalog.
- **Companion tables** (new, seeded generators, derived from the conn corpus's measured
  host population — 14,788 distinct `orig_h`, 264,778 distinct `resp_h`, 1.05 h span):
  - `dns` 1,000,000 rows: `orig_h` sampled from conn's source population, `ts` within the
    conn span, zipf-distributed query names, answers drawn from the `resp_h` population.
  - `assets` 14,788 rows: one per distinct conn `orig_h` (ip, site, dept, criticality, owner).
  - `ioc` 5,000 rows: 2,500 indicators sampled from `resp_h` (hit set) + 2,500 synthetic
    non-matching (miss set).
  - `conn_enriched` 10M rows: conn pre-joined to assets at build time (the denormalized
    twin for the join-tax pair).

## Query families

**F1 — TPC-H-derived join subset (5 queries):** Q3 (3-table), Q5 (6-table), Q9 (6-table,
the heavy one), Q18 (large agg-join), Q21 (4-table + correlated EXISTS/NOT EXISTS — the
classic DNF query; independent 2026 runs still show CH 26.1 failing 4–5 of 22 TPC-H
queries). **Completion rate is itself a scored metric.**

**F2 — SOC join suite (4 queries).** Implements the join shapes already pre-registered in
`workloads/edr-sysmon` (Family 3, LATERAL/dim asset-enrichment) and `workloads/cloud-vpcflow`
(Family 3, cross-plane time-window correlation) on the Zeek corpus — same taxonomy, not a
new one; those workload-specific corpora remain spec-phase.
- **J1 dim enrichment:** conn JOIN assets on `orig_h`, GROUP BY criticality (fact × small dim).
- **J2 large-large correlation:** conn JOIN dns on `orig_h` + same 5-min bucket
  (`floor(ts/300)`), aggregate over ~50M pre-aggregation pairs (measured multiplicity ~5.4×).
- **J3 two-streams aggregate join** (the deck's own demo shape, `correlate.py`'s big sibling):
  per-host aggregate of conn (RDP-ish, `resp_p=3389`) joined to per-host aggregate of dns,
  thresholded.
- **J4 IOC semi-join:** conn WHERE `resp_h` IN (SELECT indicator FROM ioc).

**F3 — join-tax pair (2 queries, same answer):** T-flat reads `conn_enriched` directly;
T-join computes the identical answer via conn JOIN assets. The per-engine tax (T-join /
T-flat) measures the *flattening pressure* that engine exerts — the engine-side cousin of
OCSF flattening: the join tax is what forces denormalization, so an engine that removes the
tax removes the pressure. ClickHouse's own SSB guidance denormalizes before benchmarking;
this measures whether that instinct is still load-justified per engine, on Iceberg.

**SQL discipline:** one canonical ANSI text per query; per-engine substitution of table
references only. Minimal surface-syntax accommodation allowed (identifier quoting, date
literal form), recorded per query in `queries.py`; **no structural rewrites** (no manual
reorder, no subquery flattening, no hints). A parse failure after surface accommodation is a
DNF recorded as `dialect`, distinct from `resource` (OOM/timeout). Per-query timeout 300 s,
two strikes = DNF. Gated answers avoid `COUNT(DISTINCT)` (approximate on some engines);
exact aggregates only (count, sum, min/max).

## Protocol (per BENCHMARKING-METHODOLOGY.md)

- Per arm × query: **1 discarded warmup + 7 timed trials**; report all durations, median,
  mean, CV.
- **Claims gate:** a pairwise delta is claimable only when gap % > max(CV_a, CV_b).
- **Answer equality first:** every query's extracted answer must be identical across all
  arms before any latency is trusted — join answers have never been equality-gated in this
  lab; that gate is new and required. A mismatch invalidates that query's comparison.
- **Isolation:** one engine timed at a time; all other engine containers stopped. Heavy
  engines started one at a time (~12 s gaps; simultaneous JVM/MPP cold starts OOM —
  exit 137 lesson from the MOAR stack). Windows High Performance power plan verified.
- **Timing client:** client-side wall time from one Python process over each engine's
  persistent protocol (CH HTTP, SR MySQL, Trino statement API, Dremio v3 job API — Dremio's
  job-orchestration overhead is part of its serving path and is reported as such).
- **Conditions:** hot/warm only (no passwordless sudo for an OS-cache drop; labelled per
  methodology §3).
- Storage footprints are not re-measured (cost-to-serve-retention owns that axis).

## What this bench does NOT re-measure (cite instead)

Single-table workload×engine latency at 1M/10M/100M (`workload_matrix.py`,
H-ARCH-02-evidence) · single-table answer-equality across 13 readers
(`MULTI-ENGINE-CORRECTNESS.md`) · contested-key entity-resolution tax (data-health EXT-2,
−10.1 pp; this bench's clean-key joins price the join EXT-2's oracle assumes free) ·
cross-source correlation correctness (`correlate.py` demo) · scan-aggregate concurrency
(`concurrency_sweep.py`).

## Predictions (pre-registered; priors from the 2024–26 external-evidence sweep, Tier C/B)

1. **Overall SOC-suite ordering: StarRocks > ClickHouse ≈ Trino > Dremio** (~55% SR first;
   ~50/50 on the CH/Trino middle; ~65% Dremio last with reflections off).
2. **Per shape:** J1 SR first, CH-iceberg close second (~60%); J2 SR first, Trino second,
   CH-iceberg third — highest-variance cell (~45%); J3 low confidence (~40%); J4 CH first
   (degenerate hash join + runtime filters, ~55%).
3. **F1 completion:** SR and Trino complete 5/5; CH at risk on Q21 (correlated
   EXISTS/NOT EXISTS) despite 26.x decorrelation; Dremio completes but slowly (~60%).
4. **CH native > CH Iceberg on every join** (~70%): the 2025–26 join-optimization run was
   measured on MergeTree; whether automatic statistics and runtime-filter pushdown apply
   over `icebergS3()` is publicly undocumented — this delta is the answer.
5. **Cross-cutting (~75%): the engine spread at this scale is low single-digit ×**, not the
   3–26× of the marketing literature (StarRocks 3–5×, ClickHouse "26× faster than v22.4",
   Dremio 20× all come from 100 GB–1 TB+ scale or materializations; at 10–60M rows fixed
   overheads compress differences). If this holds it is itself the publishable finding:
   *at SOC-single-node scale, engine choice on joins matters less than the marketing war
   implies — the assignment criteria should be catalog maturity, concurrency, and ops.*
6. **F3 join tax: SR smallest, CH-iceberg largest among Iceberg arms** (~55%). A tax near
   1.0× on any engine is the "you no longer need to flatten for this engine" headline.

## Run order

```bash
docker compose up -d minio nessie          # core
.venv/bin/python generate_data.py          # TPC-H SF10 + dns/assets/ioc/conn_enriched, sha256-pinned
.venv/bin/python load_tables.py            # pyiceberg → Nessie REST; CH-native copies; per-table fingerprints
.venv/bin/python run_bench.py --smoke      # answer-equality across all arms, all queries (gate)
# timed passes — one engine at a time, others stopped
.venv/bin/python run_bench.py --arm starrocks
.venv/bin/python run_bench.py --arm clickhouse_iceberg
.venv/bin/python run_bench.py --arm clickhouse_native
.venv/bin/python run_bench.py --arm trino
.venv/bin/python run_bench.py --arm dremio
.venv/bin/python run_bench.py --compare    # CV-gated pairwise + completion matrix
```

## Outputs

`results/raw_<arm>.json` (every trial + answers + DNF reasons), `results/comparison.json`
(equality gate + CV-gated pairwise + completion matrix), `results/RESULTS.md` (written after
the run; every claim CV-gated). Consumers: H-ARCH-06 first lab evidence, H-ARCH-02
extension, Matrix Component 3 re-scoring, deck slides 10/15/16, the
starrocks-clickhouse-pair reference (replaces the Tier-C anchor), task #13 asset
realignment.

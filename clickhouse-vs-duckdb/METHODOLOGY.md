# Methodology

This benchmark exists to put a number under one claim the site makes in
`economics/cost-paradox`: that over an open format the query engine is
interchangeable — "ClickHouse or DuckDB or Trino or Spark, but not locked to
one," and swapping is "a Python-library change rather than a data-migration
change." That is a testable claim, so this measures two halves of it: do the
engines actually return the *same answers* to the same SQL over the same data
(the part that has to be true for "interchangeable" to mean anything), and what
does swapping cost you in latency (the part the claim is quiet about).

## Evidence tier

**Tier B** — a reproducible corpus and cross-engine-verified answers, on one
machine. The corpus is synthetic but deterministic; the answers are checked
engine-against-engine; the latencies are wall-clock medians and are *not* a
production claim and *not* a universal constant. Read the latency numbers as the
*shape* of which engine wins which query, not as milliseconds you should expect
on other hardware or at other scale.

## What is deterministic, and is asserted

- **The corpus.** Every column is a pure function of the row index, computed with
  DuckDB's `hash()` over a string-salted key — no `random()` (whose row
  assignment is thread-order-dependent under a parallel engine) and no
  `datetime.now()`. `run.py` generates each scale's fingerprint twice and asserts
  they match; the fingerprint is a set of order-independent sums, so it is
  independent of thread count and row order.
- **The answers.** Every query runs on both engines and the result rows are
  asserted identical before any timing is reported. Each query is written to
  return a small, deterministically-ordered, integer-valued result so the
  comparison is exact (no float-format divergence). This is the real
  determinism guarantee of a perf benchmark: the timings vary, the answers do not.

## What is not deterministic, and is reported as a distribution

The latencies. `time_trials` discards warmup calls, then times N calls with
`time.perf_counter` and reports median, min, and max. Re-run it and the numbers
move; run it on other hardware and they move more. The host is named on every
results page (12 vCPU, WSL2), and the honest unit of the finding is "DuckDB won
query X by roughly k× here," not "X takes Y ms."

## The corpus

A flattened slice of OCSF Network Activity (`class_uid` 4001) and Authentication
(3002) — the columns a SOC filters and aggregates on: `time` (epoch ms over one
UTC day), `activity_id`, `severity_id`, `src_ip`, `dst_ip`, `dst_port`,
`user_name`, `bytes_in`, `bytes_out`, `status_id`. A small set of hot source IPs
(~0.3% of rows concentrated on ten addresses) gives "top talkers" real heavy
hitters; an ~8% failure rate gives the failed-auth-burst query something to find.
Written once to a single Parquet file so both engines read identical bytes.

## The two configs, both warm

- **Config A — query the same Parquet file in place.** DuckDB
  `read_parquet(...)`, ClickHouse `file(..., Parquet)`. Identical input bytes.
- **Config B — native store.** DuckDB `CREATE TABLE AS SELECT`; ClickHouse a
  `MergeTree` ordered by `time`. Ingest time is measured separately (and includes
  table (re)creation/truncate).

Both engines run **warm**: one persistent DuckDB connection and one persistent
chDB session, created once and reused across both configs. This matters for
fairness — chDB's stateless `chdb.query()` re-initialises the engine on every
call (a ~40 ms floor that warmup cannot amortise), which would turn Config A into
a startup benchmark. Using a session removes that artifact, so the only thing
that differs between A and B is the storage.

## The queries

Five shapes a SOC actually runs: a full-scan rollup, a high-cardinality top-N, a
selective single-user time-window lookup, a 5-minute time-bucket rate, and a
failed-auth burst (filter + group + having). Four of the five are byte-identical
SQL across both engines. The fifth, the time bucket, differs by exactly one
token — DuckDB's integer-division `//` versus ClickHouse's `intDiv(...)` — which
is itself a small, honest data point about how interchangeable the SQL really is.

## The caveats that bound the finding

These are the lines you must not let the result cross:

- **chDB is *embedded* ClickHouse, not a tuned server or cluster.** This measures
  the single-node, in-process case against embedded DuckDB — the genuine
  apples-to-apples. A clustered ClickHouse with primary-key tuning, skip indexes,
  and part-merge behaviour at scale is a different system and is not what ran here.
- **1–10M rows is below where ClickHouse's storage design pays off.** MergeTree's
  ordering and indexing, and ClickHouse's distributed scale-out, engage at much
  larger data and on selective primary-key lookups. Neither engine was
  hand-tuned — defaults, no skip indexes, no pragmas.
- **This does not contradict the Lab's other ClickHouse evidence.** The 145×
  number is a real ClickHouse *server* against *Splunk* (a schema-on-read SIEM)
  on 10M Zeek records — a columnar-vs-SIEM comparison at a different scale. The
  Capability Matrix scores ClickHouse top for the dashboard-serving archetype on
  that large-scale latency value. C3 is columnar-vs-columnar, embedded, mid-scale.
  Different comparison, different scale; the results sit beside each other, not
  against each other.

## What the result is, stated plainly

The engines agreed on every answer, in every config, at both scales — so the
"interchangeable" claim holds for *correctness*: the SQL and the answers port. On
latency they traded by workload but the gaps were modest (≤ ~2.6×), and DuckDB
was generally ahead for this embedded, single-node OCSF workload, with ClickHouse
edging the time-bucket rollup in its own MergeTree and DuckDB loading the corpus
several times faster. The honest takeaway is not "DuckDB beats ClickHouse" — it
is that at single-node OCSF-analytics scale the swap is cheap and the answers are
identical, which is the cost-paradox claim with a measurement under it instead of
an assertion.

## What would move the result

A larger corpus, a selective lookup on the MergeTree sort key, a clustered
ClickHouse, or a workload weighted toward wide scans rather than selective
filters could each move ClickHouse ahead. The win counts here are a function of
this query mix and this scale; change either and re-run. That is the point of
shipping the harness, not just the table.

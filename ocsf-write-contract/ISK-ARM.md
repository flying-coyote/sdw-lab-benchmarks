# BENCH-D — the never-write (ISK) arm: pre-registration and execution paths

The third write contract in BENCH-D is **never-write**: producing to Kafka *is* the write, and
the store is a logical Iceberg view rendered over the Kafka log at query time. Streambased's
**ISK (Iceberg Service for Kafka)** is the concrete instance — a REST Iceberg catalog that
renders Kafka metadata as Iceberg metadata at runtime, paired with **SSK**, an S3-compatible
storage-catalog interface. There is no data-file commit; the Kafka append is the durability
event, and an Iceberg query reads the log through the catalog.

## Why it isn't in the local first pass

ISK is a **cloud service**, not a self-hostable binary. The public example repo
([`streambased-io/isk-usage-examples`](https://github.com/streambased-io/isk-usage-examples))
ships only the *client* side — a local Spark/Trino docker-compose that points at Streambased
Cloud's regional ISK and SSK endpoints and authenticates with an account API key/secret. Its
prerequisites are explicit: an account on `beta.streambased.cloud` configured with a Kafka
cluster, plus the `ACCESS_KEY` / `SECRET_KEY` / `ISK_ENDPOINT` / `SSK_ENDPOINT` env values. So
the never-write engine can't run on the single-machine substrate the other two arms use, and it
can't be measured without either cloud access or the vendor. Recorded as pending rather than
estimated, per the benchmark's no-silent-caps rule.

## Pre-registered workload and metrics (fixed before any run)

So that whoever runs it — us on the beta, or the vendor — is held to the same method, the
never-write arm is pinned here, aligned to the two measured arms:

- **Ingest.** The identical seeded OCSF stream the file-write and SQL-transaction arms ingest
  (`run.py`'s `gen_batches`), produced to a Kafka topic at the same small-batch and large-batch
  rungs. Same logical input, so the read-contract check is apples-to-apples.
- **Freshness, not commit latency.** Never-write has no commit, so the comparable metric is
  **ingest-to-queryable freshness**: wall-clock from event-produced-to-Kafka to
  event-visible-through-an-Iceberg-query via ISK. This is reported as freshness and is a
  *different mechanism* from the other arms' commit latency; blending the two into one "latency"
  column is a category error and is forbidden here.
- **Write amplification.** ISK materializes no incremental Iceberg data files (the Kafka log is
  the data; SSK serves storage), so its incremental file write is ~zero — a categorical
  advantage that travels with a categorical caveat: durability and retention are Kafka's, not a
  materialized-file store's, so the cold/forensic-tier obligations (multi-year immutable
  retention, the §1005/17a-4 surface) are exactly where never-write is weakest. That asymmetry
  is the point of the tiering thesis and must be reported, not hidden by the zero-amplification
  number.
- **Read-contract coherence (the load-bearing check).** Does the same logical data read
  *identically* through ISK's Iceberg interface as through the file-write (Iceberg) and
  SQL-transaction (DuckLake) tiers — same row count, same aggregate? This is the BENCH-D premise
  (one read contract across three write contracts), and it is the single most valuable thing the
  ISK arm would add.

## Execution paths, by evidence tier

1. **Self-run on the beta (first-party, cloud-disclosed) — Tier B.** We provision a
   `beta.streambased.cloud` account + Kafka cluster, produce the pre-registered OCSF stream, and
   run the freshness + read-coherence measurement via the local Spark/Trino client. First-party
   and reproducible-with-an-account, but it runs in the vendor's cloud, not on the single machine,
   so the result is disclosed as "Streambased Cloud beta, our measurement, our workload," and the
   latencies are cloud-and-region-specific. This is the preferred path if the beta is open.
2. **Vendor-run on this pre-registered workload (vendor-provided) — Tier C.** Streambased runs
   the workload above and returns the numbers, which we publish **flagged as vendor-provided**
   and method-controlled (their execution, our frozen workload + metrics). Lower tier because we
   didn't execute it, but better than marketing numbers because the workload is pre-registered
   here. We retain the right to reproduce it on the beta to promote it to Tier B.
3. **Vendor-published marketing numbers — Tier C/D, not used as a measurement.** The existing
   public ISK performance claims are not folded into the headline; they are context, labelled as
   the claim under test, exactly as the C2/C1 benchmarks treat vendor claims.

The coordination plan and the (Jeremy's-to-send) outreach drafts live in project1 at
`02-projects/external-engagements/streambased-isk-coordination.md`.

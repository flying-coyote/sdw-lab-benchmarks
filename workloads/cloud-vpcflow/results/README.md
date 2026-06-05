# Cloud / VPC Flow Results

**Status:** empty (2026-05-24). Populated per benchmark run.

## Result schema (planned)

Each run writes:

- `run-manifests/<timestamp>.yaml` — run metadata: substrate candidate + version, hardware, corpus version, Stratus technique set, OCSF normalizer version, ingest rate target, actual ingest rate observed, sandbox-account-ID (anonymized in public material), AWS region
- `query-latencies/<timestamp>.csv` — per-query cold / warm latencies + standard error
- `ingest-throughput/<timestamp>.csv` — sustained throughput time series at 1-second granularity
- `cost-actuals.md` — running log of actual cloud spend per run, including delayed-surfacing AWS charges (data-event CloudTrail, GuardDuty if enabled, S3 transfer), reconciled against the $500–1,500/quarter envelope at `~/project1/02-projects/securitydataworks/lab/infrastructure-cost-envelope.md`

## Headline metrics

Per the workload README, candidates are:

- Sustained streaming ingest rate at fixed CPU/memory budget under mixed semi-structured + structured records
- Cardinality-explosion query latency (`GROUP BY src_ip, dst_ip, action` at line-rate volume)
- Cross-plane correlation JOIN performance (`api_activity` → `network_activity` within session window)
- JSON projection performance under high-fanout request-parameter blobs

The published methodology PDF will fix one or two as the headline after spec phase converges on the substrate-axis story. Most likely: sustained streaming ingest rate (the highest-stakes claim distinguishing cloud from EDR and NDR archetypes) plus cross-plane JOIN latency (the cleanest architectural-pattern test).

## Cost-actuals discipline

Cloud-spend nondeterminism is a real benchmark hazard. Document:

- Every line item from the AWS Bills view, not just the "spot instance" or "S3" categories
- Charges that surfaced *after* the run window (CloudTrail data events, S3 lifecycle, occasionally a delayed cross-region transfer line)
- The headroom against the per-run estimate ($50–200) and the quarterly envelope

A run that exceeds $200 — even if the methodology is correct — is a methodology problem to document, not a number to suppress.

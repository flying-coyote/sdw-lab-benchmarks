# EDR/Sysmon Results

**Status:** empty (2026-05-24). Populated per benchmark run.

## Result schema (planned)

Each benchmark run writes:

- `run-manifests/<timestamp>.yaml` — run metadata: substrate candidate, version, hardware, corpus version, ATT&CK technique set, OCSF normalizer version, ingest rate target, actual ingest rate observed
- `query-latencies/<timestamp>.csv` — per-query cold/warm latencies + standard error
- `ingest-throughput/<timestamp>.csv` — sustained throughput time series
- `cost-actuals.md` — running log of actual cloud/local spend against the budget envelope in `~/project1/02-projects/securitydataworks/lab/infrastructure-cost-envelope.md`

## Headline metrics

Per the workload README, the headline candidates are:

- Sustained ingest rate at fixed CPU/memory budget
- Point-lookup latency by `(host, process_guid)`
- Recursive-CTE process-tree reconstruction time at depth N
- LATERAL JOIN performance against synthetic asset inventory

The published methodology PDF will fix one or two as the headline once spec phase converges on the substrate-axis story.

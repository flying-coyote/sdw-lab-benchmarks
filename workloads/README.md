# Workload specs: storage-and-query platform archetypes (EDR and cloud)

Workload *specifications* for two archetypes of the platform benchmark, which asks how well a storage and
query platform holds up under a given shape of security telemetry. They were migrated from the
now-retired `splunk-db-connect-benchmark` repo, whose role this lab took over and which held nothing else
by then. They are planning documents (the workload shape, a deterministic data-generation plan and a query
set), and neither has been built into a runnable harness here yet. Together with the Zeek/NDR flagship
(`../zeek-flagship-rerun/`) they make up the three planned archetypes.

- **`edr-sysmon/`**: endpoint telemetry in the shape of Sysmon process activity, the second archetype.
- **`cloud-vpcflow/`**: cloud network and control-plane telemetry (VPC flow logs and CloudTrail), the third archetype.

The `ocsf-context-collapse` workload that sat beside these in the old repo is already built in this lab as
[`../bench-a-context-collapse/`](../bench-a-context-collapse/), so it was not migrated, and only its
unbuilt siblings moved here.

When one of these is built, it becomes a top-level bench folder with a `bench.yaml` and a README in the
layout of [`../docs/BENCH-LAYOUT.md`](../docs/BENCH-LAYOUT.md), and it follows
[`../BENCHMARKING-METHODOLOGY.md`](../BENCHMARKING-METHODOLOGY.md): CV reported, configuration parity or
same-files registration, isolation, a seeded corpus, a pre-registration under principle 12, and a headline
that can fail under principle 11. This folder holds the spec until then, and the bench index in the
top-level README does not list it.

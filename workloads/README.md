# Workload specs — substrate benchmark archetypes (bench-b/c)

Workload *specifications* for two substrate benchmark archetypes, migrated from the now-retired
`splunk-db-connect-benchmark` repo (its predecessor role superseded by this lab; these specs were the
only thing it still held). These are pre-registration / planning docs — the workload shape, a
deterministic data-generation plan, and a query set — not yet implemented as runnable harnesses here.
They define the second and third substrate archetypes alongside the implemented context-collapse work.

- **`edr-sysmon/`** — endpoint/EDR (Sysmon process-activity) substrate. Second archetype.
- **`cloud-vpcflow/`** — cloud network (VPC flow log) substrate. Third archetype.

The `ocsf-context-collapse` workload that lived beside these in the old repo is **already implemented**
in this lab as [`../bench-a-context-collapse/`](../bench-a-context-collapse/) — it was not migrated to
avoid duplicating the live benchmark; only its unimplemented siblings moved here.

When one of these is built into a runnable benchmark, it should follow the lab's
[`BENCHMARKING-METHODOLOGY.md`](../BENCHMARKING-METHODOLOGY.md) (CV reported, config-parity or
same-files registration, isolation, deterministic seeded corpus) and graduate to a top-level
`*/run.py` directory like the other benchmarks; this folder holds the spec until then.

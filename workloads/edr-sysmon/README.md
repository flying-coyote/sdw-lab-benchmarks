# EDR / Sysmon Workload Archetype

**Status:** Spec only (2026-05-24) — workload scoped; full benchmark run not yet started.

**Confirmed:** 2026-05-24 plan-mode decision selected EDR/Sysmon as the second substrate-benchmark archetype after NDR/Zeek. Tracked under LAB Q4 2026.

## Workload archetype

Sysmon (Sysinternals' free Windows endpoint logger) configured with the SwiftOnSecurity community config (community-maintained, Tier C) is the practitioner reference for the *shape* of EDR data — even when the production EDR is CrowdStrike Falcon, SentinelOne, or Microsoft Defender. This workload exercises the substrate against process-tree-shaped, high-cardinality endpoint telemetry: process-create, file-write, network-connect, registry-modify, image-load, and DNS-query event streams.

The data-generation driver is **Atomic Red Team** (Red Canary, open-source) — 261 ATT&CK techniques across 1,225 tests as of recent count (Tier C — Red Canary blog). Atomic Red Team techniques execute against a SwiftOnSecurity-config'd Sysmon target VM; the Sysmon events captured to Windows Event Log are exported and normalized to OCSF for substrate ingestion.

## Representative substrate metric

The substrate stress for EDR data is **ingest throughput at high cardinality combined with point-lookup and process-tree-JOIN performance**, not analytical aggregation (which the Zeek/NDR workload already exercises).

- Sustained ingest target: 10K–100K events/sec
- Cardinality dominated by `(host, process_guid, parent_process_guid, image_path)` tuples
- Headline metric candidates:
  - Sustained ingest rate at fixed CPU / memory budget
  - Point-lookup latency by `(host, process_guid)`
  - Recursive-CTE process-tree reconstruction time at depth N
  - LATERAL JOIN performance against synthetic asset inventory for severity scoring

## Methodology summary

This workload follows the practice's lab methodology principles (see `~/project1/02-projects/securitydataworks/LAB.md`):

- **Reproducibility first** — public methodology document; data-generation harness reproducible from open-source primitives (Sysmon + SwiftOnSecurity config + Atomic Red Team)
- **Identical workload across candidates** — query suite and event corpus pinned before any substrate candidate is run
- **Documented caveats** — workload archetypes for which the result generalizes vs. doesn't (e.g., this workload says nothing about EDR *detection quality*; it tests *substrate adequacy* for EDR telemetry shape)
- **Vendor cooperation invited but not required** — vendor configurations are documented as such, not folded silently into headline numbers

## Public-language constraint

Per [`project_benchmark_publication_strategy.md`](../../../.claude/projects/-home-jerem-project1/memory/project_benchmark_publication_strategy.md), the public methodology PDF does not name commercial vendors in comparative performance claims. Substitute "schema-on-read SIEM" for Splunk. Reference implementation stays NDA-gated (the leverage trio: PDF + NDA + named external reviewer).

## Data generation plan

See [`data/generation-plan.md`](data/generation-plan.md).

## Query suite

See [`queries/README.md`](queries/README.md) (skeleton — queries to be added during build phase).

## Docker harness

Reuse the existing top-level `~/splunk-db-connect-benchmark/docker-compose.yml`. Do not fork. EDR-specific services (Sysmon log forwarder, OCSF normalizer for Process Activity / File System Activity / Network Activity classes) will be added as additional services in the existing compose file, not as a parallel compose file.

## Out of scope

- This workload tests substrate adequacy for EDR telemetry shape; it does not evaluate EDR detection quality
- Client-data POV runs are out of scope per the retired POV-on-customer-data decision (2026-05-18; see [`project_security_data_consulting_model.md`](../../../.claude/projects/-home-jerem-project1/memory/project_security_data_consulting_model.md))
- Linux EDR (Wazuh-style agent telemetry) is a future extension; this workload is Windows / Sysmon only

## References

- Workload category brief: `~/project1/02-projects/securitydataworks/data-source-categories/edr.md`
- Cost envelope: `~/project1/02-projects/securitydataworks/lab/infrastructure-cost-envelope.md` (EDR archetype line: ~$5–20 per run, up to $100 / quarter Q3 2026 budget line)
- Vendor universe context: `~/project1/02-projects/securitydataworks/vendor-tracking-2026.md` §XII Telemetry Sources — EDR / XDR
- Lab methodology principles: `~/project1/02-projects/securitydataworks/LAB.md`

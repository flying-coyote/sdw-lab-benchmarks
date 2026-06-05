# Cloud / VPC Flow Workload Archetype

**Status:** Spec only (2026-05-24) — workload scoped; full benchmark build gated on EDR archetype shipping first.

**Confirmed:** Third substrate-benchmark archetype after NDR/Zeek and EDR/Sysmon. Per the 2026-05-24 SDW market-readiness plan, A9 sequencing is gated on A1 (EDR) shipping; spec is parallel-track so it's ready when the build slot opens.

## Workload archetype

Cloud telemetry is the highest-volume and most heterogeneous of the data-source categories — three sub-shapes braided into one substrate problem:

- **Data-plane network** — VPC Flow Logs (AWS), NSG Flow (Azure), VPC Flow (GCP). Line-oriented flat records at line-rate. Densely segmented cloud networks can drive millions of flows/sec aggregated, dwarfing the NDR archetype's volume profile.
- **Control plane** — CloudTrail (AWS), Activity Logs (Azure), Audit Logs (GCP). Nested JSON, bursty volume (deploy cycles, API-call storms), every API call is a record.
- **Posture / runtime** — CNAPP findings (Wiz, Lacework, Orca, Prisma Cloud) and runtime detection (Falco). Continuously-evaluated drift state, not pure events.

The data-generation driver is **Stratus Red Team** (Datadog, open-source — `github.com/DataDog/stratus-red-team`). It is the cloud-native analog to Atomic Red Team — adversary emulation against AWS, Azure, GCP, and Kubernetes control planes (27+ techniques as of recent count, Tier C — Datadog blog). Stratus runs in a sandbox cloud account; the resulting CloudTrail + VPC Flow output is exported, normalized to OCSF, and ingested by the substrate under test.

**Scope decision:** AWS-first. The bulk of public cloud telemetry an architect deals with is AWS-shaped, Stratus Red Team has the deepest AWS technique coverage, and AWS Spot pricing makes the cost envelope tractable. Azure and GCP variants are future extensions, not part of this initial spec.

## Representative substrate metric

The substrate stress for cloud data is **streaming ingest at high cardinality combined with semi-structured JSON parsing performance**. This is distinct from the NDR archetype (analytical aggregates) and the EDR archetype (point lookups + tree joins) — it stresses the parts of the substrate the other two don't.

- Sustained ingest target: 100K events/sec mixing CloudTrail JSON + VPC Flow flat records
- Cardinality dominated by `(account_id, region, principal_arn, resource_arn)` for control plane and `(src_ip, dst_ip, src_port, dst_port, action)` for data plane
- Headline metric candidates:
  - Sustained streaming ingest rate at fixed CPU/memory budget under mixed semi-structured + structured records
  - Cardinality-explosion query latency (`GROUP BY src_ip, dst_ip, action` at line-rate volume)
  - Cross-plane correlation JOIN performance (`api_activity` → `network_activity` within session window)
  - JSON projection performance under high-fanout request-parameter blobs

## Methodology summary

Same lab-methodology principles as the EDR and NDR archetypes (see `~/project1/02-projects/securitydataworks/LAB.md`):

- **Reproducibility first** — public methodology document; data-generation harness reproducible from open-source primitives (Stratus Red Team + a clean AWS sandbox account)
- **Identical workload across candidates** — same query suite and event corpus against each substrate
- **Documented caveats** — cloud-spend nondeterminism is a real caveat; record sandbox-account costs alongside benchmark numbers
- **Vendor cooperation invited but not required**

## Public-language constraint

Per [`project_benchmark_publication_strategy.md`](../../../.claude/projects/-home-jerem-project1/memory/project_benchmark_publication_strategy.md), public methodology does not name commercial vendors in comparative performance claims. Substitute "schema-on-read SIEM" for Splunk; if comparing against cloud-native security stacks (Sentinel, Chronicle, Security Lake), check each one's EULA / terms before naming in comparative claims.

## Cost-envelope note

This is the most cloud-spend-intensive archetype. Per `~/project1/02-projects/securitydataworks/lab/infrastructure-cost-envelope.md`, the line item is:

| Archetype | Est. $/run | Q3 2026 budget line |
|---|---|---|
| Cloud / VPC Flow | $50–200 | up to $800 (Q4) |

Run-by-run actuals captured in `results/cost-actuals.md`. The cost envelope is committed to the *envelope* ($500–1,500/quarter), not to AWS specifically — Hetzner bare-metal as ingest-target host with AWS-sandbox-only for the Stratus generation is a viable cost-reduction posture.

## Data generation plan

See [`data/generation-plan.md`](data/generation-plan.md).

## Query suite

See [`queries/README.md`](queries/README.md) (skeleton — queries authored during build phase).

## Docker harness

Reuse the existing top-level `~/splunk-db-connect-benchmark/docker-compose.yml`. Cloud-specific services (CloudTrail ingester, VPC Flow parser, OCSF normalizer for API Activity / Cloud API Activity / Network Activity) added as additional services to the existing compose file, not a parallel one.

## Out of scope

- Azure and GCP variants — future extensions; spec covers AWS only
- Posture / drift evaluation — CNAPP findings ingestion is interesting but stress-tests a different substrate axis (merge-on-read for continuous evaluation) and belongs in a separate archetype if pursued
- Client-data POV runs — retired per 2026-05-18 decision in [`project_security_data_consulting_model.md`](../../../.claude/projects/-home-jerem-project1/memory/project_security_data_consulting_model.md)
- Long-running cloud retention — runs are short-lived (hours); no ongoing sandbox accounts maintained

## Sequencing dependency

**Gated on EDR archetype shipping first.** Reasons:

1. Methodology lessons from the EDR build may want to retroactively reshape this spec (especially around OCSF normalization library structure, which both archetypes share)
2. Cost-envelope discipline benefits from EDR run actuals before this archetype's larger cloud spend lands
3. Substrate candidates that passed EDR may not be the same set that's interesting for cloud — selection economy matters when re-running a third time

## References

- Workload category brief: `~/project1/02-projects/securitydataworks/data-source-categories/cloud-web.md`
- Cost envelope: `~/project1/02-projects/securitydataworks/lab/infrastructure-cost-envelope.md`
- Vendor universe context: `~/project1/02-projects/securitydataworks/vendor-tracking-2026.md` §I (cloud-native substrates), §X (Sentinel federation), §XIX (CNAPP)
- Lab methodology principles: `~/project1/02-projects/securitydataworks/LAB.md`
- Sibling archetypes: [`../edr-sysmon/README.md`](../edr-sysmon/README.md), the top-level Zeek/NDR work (planned move to `../ndr-zeek/`)

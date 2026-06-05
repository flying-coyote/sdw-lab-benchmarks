# Cloud / VPC Flow Data Generation Plan

**Status:** spec (2026-05-24). Implementation pending — gated on EDR archetype shipping.

## Building blocks (all free or pay-per-use, no NFR-gated)

| Component | Purpose | Source |
|---|---|---|
| AWS sandbox account (Organizations OU) | Stratus target + native log emission | AWS — pay-per-use; sandbox usage measured in dollars not tens of dollars per run |
| Stratus Red Team | Cloud-native adversary emulation runner | github.com/DataDog/stratus-red-team (Apache 2.0) |
| AWS CloudTrail | Control-plane API event capture | Native; logs to S3 |
| AWS VPC Flow Logs | Data-plane network flow capture | Native; logs to CloudWatch or S3 |
| AWS GuardDuty (optional) | Detection-finding overlay for richer corpus | Native; pay-per-event |
| OCSF normalizer | CloudTrail JSON + VPC Flow → OCSF API Activity / Cloud API Activity / Network Activity classes | Built alongside (extend zeek-to-ocsf-mapping pattern) |
| Terraform | Sandbox account scaffolding | HashiCorp (open-source variant) |
| `aws-vault` or AWS SSO | Credential management for the sandbox | `github.com/99designs/aws-vault` |

## Pipeline

```
Terraform stands up AWS sandbox VPC + IAM + S3 buckets
        │
        ▼
Stratus Red Team executes techniques against sandbox account
        │
        ▼  Native AWS services emit CloudTrail + VPC Flow Logs
        │
        ▼  S3 → local export (CloudTrail JSON; VPC Flow flat records)
        │
        ▼  OCSF normalizer maps to:
        │     • Cloud API Activity (3005) for CloudTrail mgmt events
        │     • API Activity (3005) for CloudTrail data events
        │     • Network Activity (4001) for VPC Flow Logs
        │
        ▼  Substrate ingest (candidate under test)
```

## Volume targets

- Baseline sandbox idle: CloudTrail ~5 events/sec, VPC Flow ~10 records/sec
- Stratus Red Team active execution: CloudTrail bursts to 100–1,000 events/sec during technique execution
- For sustained-ingest benchmark: replay captured Stratus output in loop, scaled to target rate (100K mixed events/sec target)
- Mix ratio: roughly 70/30 VPC Flow to CloudTrail by record count (VPC Flow volume dominates in real environments)

## Corpus generation method

Same two-path pattern as the EDR archetype:

1. **Live capture** — Stratus techniques run against a live sandbox; CloudTrail + VPC Flow captured in real time via S3 export. Lower throughput, higher fidelity. Use for spec / smoke runs.
2. **Replay** — capture once, replay-at-scale via a timing-driven loop. Use for sustained-throughput benchmark runs.

The captured corpus (CloudTrail JSON files, VPC Flow records, OCSF-normalized) ships under NDA per the leverage-trio publication strategy.

## Stratus technique selection

Stratus Red Team covers 27+ AWS techniques as of recent count, organized by ATT&CK tactic (initial access, persistence, lateral movement, defense evasion, etc.). For substrate benchmarking, technique mix matters more than threat coverage:

- ≥3 techniques producing high-volume CloudTrail management events (e.g., `iam.create-admin-user`, `lambda.overwrite-code`)
- ≥3 techniques exercising data-plane VPC Flow (techniques that establish meaningful east-west traffic — currently sparse in Stratus; may need to layer in a separate synthetic east-west traffic generator like `tcpkali` or AWS-native LoadGenerator)
- ≥2 techniques exercising CloudTrail data events (e.g., S3 data events, DynamoDB data events) for the high-volume data-event slice

Exact technique IDs per run captured in `results/run-manifests/`.

## VPC Flow volume strategy

VPC Flow is the volume driver in this archetype. Two augmentation paths to hit the 100K events/sec target without a real production workload:

1. **Synthetic east-west traffic** — `tcpkali`, `iperf3`, or AWS-native LoadGenerator instances generating cross-AZ traffic in the sandbox; cheap when run for minutes, not hours
2. **Replay augmentation** — record a small window of organic Stratus + synthetic traffic, replay at scale on the ingest side (the substrate doesn't know real-time vs. replay)

Replay augmentation is the default — cheaper and more reproducible. Synthetic traffic generation is reserved for capturing the *original* corpus.

## OCSF mapping strategy

Extend the existing zeek-to-ocsf-mapping pattern. CloudTrail → OCSF mapping is well-documented in the OCSF GitHub repo (Tier A — OCSF standards); AWS published a mapper. VPC Flow → OCSF Network Activity is the same target class as Zeek `conn.log`, so the existing NDR normalizer logic should partially reuse.

- CloudTrail management event → OCSF Cloud API Activity (3005) with `activity_id` per CRUD verb
- CloudTrail data event → OCSF API Activity (3005) with `category_uid: 3` (Identity & Access Management) or `category_uid: 5` (Discovery) per resource
- VPC Flow record → OCSF Network Activity (4001) with `connection_info.protocol_name` per the `protocol` field

Document mapping decisions per source type in `data/ocsf-mapping.md` (TBD during build phase).

## Cost-envelope discipline

This is the heaviest archetype on cost. The corpus generation step should be:

- **Scoped to minutes, not hours** — Stratus + traffic generators run for a few minutes to capture the corpus; nothing left running
- **Sandbox-account scoped** — Terraform tears down the entire VPC + IAM + S3 buckets after capture; no persistent footprint
- **Captured once per benchmark cycle** — corpus is reused across all candidate substrates; not re-generated per candidate

Per `results/cost-actuals.md` (TBD), log every run's actual AWS bill including charges that surface days later (CloudTrail data-event charges, GuardDuty if enabled, S3 transfer).

## Caveats to document

- **Sandbox-vs-production distortion** — sandbox VPCs have different traffic shape than production; document this clearly
- **Stratus AWS-bias** — Azure and GCP variants will need separate sandbox accounts and separate Stratus profiles; this spec is AWS-only
- **CloudTrail data-event cost surface** — enabling data events on all S3 buckets is the standard "production realism" choice but compounds cost fast; pick a representative subset
- **GuardDuty optionality** — adds a finding-overlay slice useful for cross-detection JOIN queries but costs more per event; default OFF, document on/off in run manifest

## Provider alternative posture

The corpus generation step requires AWS (Stratus targets AWS-native services). The *substrate-under-test* host does not — Hetzner bare-metal as the ingest host with corpus generated in AWS-sandbox and exported is the cost-reduced path. Provider commitment per [`../../../project1/02-projects/securitydataworks/lab/infrastructure-cost-envelope.md`](../../../project1/02-projects/securitydataworks/lab/infrastructure-cost-envelope.md) is to the envelope, not to AWS for the host.

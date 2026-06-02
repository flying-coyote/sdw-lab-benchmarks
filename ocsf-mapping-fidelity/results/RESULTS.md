# Results — OCSF field-mapping fidelity (C1)

- OCSF version: **1.8.0**  ·  evidence tier: B (reproducible, first-party mapping judgement against real documented vendor schemas and the real OCSF 1.8.0 schema; not production telemetry)
- Determinism (re-score is byte-identical): **True**  
- Every OCSF target below is validated against the checked-in 1.8.0 schema subset; an invented attribute would fail the run.

## Scope

- **Okta** — System Log LogEvent -> Authentication (3002); anchored on Okta's okta/okta-ocsf-syslog reference mapper where it maps
- **CrowdStrike** — Detection Summary Event (Event Streams) -> Detection Finding (2004); best-effort vs OCSF 1.8.0 (no public vendor field mapping)
- Okta inventory is the documented typed schema; CrowdStrike inventory is the publicly-reproduced Detection Summary Event, NOT the gated full FDR schema. Coverage is over each scoped field set, not all telemetry.

## Coverage per source

`coverage` counts only fields that land on a typed OCSF attribute with semantics preserved. `coerced` = a typed home exists but a boundary is crossed (enum narrows, array collapses, id/label lost). `unmapped` = no typed home; only OCSF `unmapped`/`raw_data` can hold it.

| source | OCSF class | fields | typed | coerced | unmapped | coverage | lossy |
|---|---|--:|--:|--:|--:|--:|--:|
| okta | authentication (3002) | 50 | 29 | 7 | 14 | 58% | 42% |
| crowdstrike | detection_finding (2004) | 43 | 30 | 9 | 4 | 70% | 30% |

## Okta: the schema gap vs the shipped-mapper gap

OCSF 1.8.0 has a typed (or coercible) home for 36 of 50 Okta fields, but Okta's own reference mapper (`okta/okta-ocsf-syslog`) carries only 18 of 50 into the OCSF event. So 18 fields have an OCSF home the shipped mapper leaves on the floor:

> `uuid`, `eventType`, `version`, `actor.id`, `actor.type`, `client.id`, `client.userAgent.rawUserAgent`, `client.userAgent.os`, `client.zone`, `request.ipChain`, `transaction.id`, `authenticationContext.credentialProvider`, `authenticationContext.credentialType`, `authenticationContext.issuer.id`, `securityContext.asNumber`, `securityContext.asOrg`, `securityContext.isp`, `securityContext.domain`

Several of those are detection-relevant (the autonomous-system fields, the ISP/domain enrichment, the network zone, the credential type). The schema can hold them; the integration does not.

## Detections — which break, and on which field

Detection-breaking = a field a named detection needs that does not map cleanly (coerced or unmapped). Two detections survive clean — the result is *which* break, not that everything does.

| detection | source | breaks on |
|---|---|---|
| Anonymizing-proxy / Tor login | okta | `securityContext.isProxy` (unmapped) |
| Impossible travel | okta | — (all fields typed) |
| MFA fatigue / push bombing | okta | `authenticationContext.credentialType` (coerced), `outcome.result` (coerced) |
| ThreatInsight / risk-based signal | okta | `debugContext.debugData` (unmapped) |
| Suspicious ASN | okta | — (all fields typed) |
| True source IP behind proxy | okta | `request.ipChain` (coerced) |
| ATT&CK technique hunt | crowdstrike | `event.Technique` (coerced), `event.Tactic` (coerced) |
| Multi-stage process lineage | crowdstrike | `event.GrandparentImageFileName` (coerced), `event.GrandparentCommandLine` (unmapped) |
| IOC pivot on indicator type | crowdstrike | `event.IOCType` (coerced) |
| Response-action audit | crowdstrike | `event.PatternDispositionValue` (coerced) |
| Known-bad hash | crowdstrike | — (all fields typed) |

## Field-by-field (auditable)

The full per-field mapping, status and rationale is in `results.json` and `mapping.py`. Lossy fields, grouped:

### okta — coerced (7)

- `client.device` → `device.type` — device label (Computer/Mobile) -> device.type; shipped mapper puts it in src_endpoint.interface_id, a coercion either way
- `request.ipChain` → `src_endpoint.intermediate_ips` — proxy chain -> ip list; per-hop geo and ordering are lost; shipped mapper drops it
- `outcome.result` → `status_id` — 7-value enum (SUCCESS/FAILURE/CHALLENGE/SKIPPED/ALLOW/DENY/UNKNOWN) -> ~3-value status_id; CHALLENGE/SKIPPED/ALLOW/DENY collapse
- `transaction.type` → `logon_type_id` — WEB/JOB -> logon_type enum; shipped mapper maps WEB->99 (Other)
- `authenticationContext.authenticationProvider` → `auth_protocol_id` — provider enum -> auth_protocol enum; shipped mapper maps FACTOR->Other
- `authenticationContext.credentialProvider` → `auth_factors` — RSA/DUO/YUBIKEY -> auth_factors[]; provider->factor mapping is lossy; shipped mapper drops it
- `authenticationContext.credentialType` → `auth_factors` — 12-value scheme enum (OTP/SMS/PASSWORD/PUSH...) collapses to is_mfa + factor_type; PUSH-vs-OTP distinction lost; shipped mapper drops it

### okta — unmapped (14)

- `legacyEventType` — deprecated; no typed home
- `actor.detailEntry` — free-form map; no typed home
- `client.userAgent.browser` — OCSF has no parsed-browser attribute; only the raw UA has a home
- `target.id` — Authentication 3002 has no target/resource array; heterogeneous target[] (app/user/group) has no faithful home
- `target.type` — no target array on Authentication
- `target.alternateId` — no target array on Authentication
- `target.displayName` — no target array on Authentication
- `target.detailEntry` — free-form map; no typed home
- `transaction.detail` — free-form map; no typed home
- `debugContext.debugData` — free-form map carrying risk/threat signals, deviceFingerprint, behaviors; shipped mapper extracts only requestUri+url, the rest lands in unmapped
- `authenticationContext.authenticationStep` — currently always 0; no home
- `authenticationContext.issuer.type` — issuer source info; no typed home
- `authenticationContext.interface` — third-party UI string; no typed home
- `securityContext.isProxy` — OCSF endpoint has no boolean is-proxy flag (proxy_endpoint is an address, not a flag); high-signal fraud bit has no typed home

### crowdstrike — coerced (9)

- `event.Severity` → `severity_id` — CrowdStrike numeric severity scale -> OCSF severity_id enum; scale remap
- `event.Tactic` → `attacks.tactic` — tactic name string -> attack.tactic object {name,uid}; the TA-id is absent, only name populates
- `event.Technique` → `attacks.technique` — technique name/label -> attack.technique object {name,uid}; name and T-id do not both survive a flat string
- `event.GrandparentImageFileName` → `evidences.process.ancestry` — OCSF process models one parent level + ancestry[]/lineage path; grandparent has no named slot, flattens into ancestry
- `event.IOCType` → `observables.type_id` — free string (hash_sha256/domain/ipv4) -> observable.type_id integer enum; IOC types outside the enum fail the lookup
- `event.PatternDispositionValue` → `disposition_id` — bitmask of multiple actions taken -> single-valued disposition_id; the multi-action set collapses to one
- `event.NetworkAccesses` → `evidences` — array of {RemoteAddress,...} -> evidences[]; inner structure only partially modeled
- `event.ExecutablesWritten` → `evidences` — array of written executables w/ hashes -> evidences[]; partial
- `event.DnsRequests` → `evidences` — array of DNS objects -> evidences[]/observables[]; partial

### crowdstrike — unmapped (4)

- `event.Objective` — adversary objective; no OCSF Detection Finding attribute
- `event.GrandparentCommandLine` — ancestry/lineage carry path only, not a command line for ancestor processes; grandparent cmd line has no home
- `event.PatternDispositionFlags` — named boolean flags object; no typed home
- `event.ScanResults` — AV scan results array; no clean Detection Finding home


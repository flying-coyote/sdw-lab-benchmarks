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
| palo_alto | network_activity (4001) | 83 | 46 | 8 | 29 | 55% | 45% |
| cisco_asa | network_activity (4001) | 26 | 16 | 3 | 7 | 62% | 38% |
| cisco_umbrella | dns_activity (4003) | 13 | 6 | 2 | 5 | 46% | 54% |

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
| NAT-aware true-source attribution | palo_alto | `natsrc` (unmapped), `natsport` (unmapped) |
| App-ID evasion / tunneled-app | palo_alto | `tunneled_app` (unmapped), `technology_of_app` (unmapped), `characteristic_of_app` (unmapped) |
| Shadow-IT unsanctioned SaaS | palo_alto | `sanctioned_state_of_app` (unmapped), `is_saas_of_app` (unmapped), `category_of_app` (unmapped) |
| Firewall action / session-teardown audit | palo_alto | `action` (coerced), `session_end_reason` (coerced) |
| Long-lived high-volume beacon | palo_alto | — (all fields typed) |
| NAT-aware true-source attribution (ASA) | cisco_asa | `mapped_src_ip` (unmapped), `mapped_src_port` (unmapped) |
| Connection-lifecycle correlation | cisco_asa | `action` (coerced) |
| Session-teardown reason analysis | cisco_asa | `teardown_reason` (coerced), `action` (coerced) |
| ICMP tunneling / covert channel | cisco_asa | `icmp_type` (unmapped), `icmp_code` (unmapped) |
| Byte-volume exfil by destination | cisco_asa | — (all fields typed) |
| DNS tunneling by query characteristics | cisco_umbrella | — (all fields typed) |
| Identity-attributed DNS risk | cisco_umbrella | `most_granular_identity` (coerced), `most_granular_identity_type` (coerced) |
| Content-category / blocked-category policy | cisco_umbrella | `categories` (unmapped), `blocked_categories` (unmapped) |
| Egress-IP correlation | cisco_umbrella | `external_ip` (unmapped) |
| Blocked-domain hunt | cisco_umbrella | — (all fields typed) |

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

### palo_alto — coerced (8)

- `subtype` → `activity_id` — start/end/drop/deny -> activity_id enum; drop/deny are actions not lifecycle states, so they collapse
- `action` → `action_id` — allow/deny/drop/drop-icmp/reset-client/reset-server/reset-both/drop-all -> action_id (Allowed/Denied/...); the drop-vs-reset-vs-deny distinction collapses [firewall action-enum narrowing]
- `category` → `url.categories` — PA URL-category (single PANW-taxonomy value) -> url.categories (string preserved), but OCSF's typed url.category_ids enum uses a different category taxonomy, so an OCSF-category-id pivot loses the value [URL-category taxonomy seam]
- `session_end_reason` → `status_detail` — PA session-end-reason enum (tcp-fin/tcp-rst-from-client/tcp-rst-from-server/threat/policy-deny/aged-out/...) -> status_detail free string; OCSF Network Activity has no typed session-termination enum
- `dynusergroup_name` → `src_endpoint.owner.groups.name` — single PA dynamic-user-group name -> source user's groups[]; PA's policy-evaluated dynamic membership flattens to a static group name
- `xff_ip` → `src_endpoint.intermediate_ips` — X-Forwarded-For true-client IP -> intermediate_ips; Network Activity has no http_request (only proxy_http_request), so the real client lands in the proxy-hop list and loses its 'true source' meaning
- `src_category` → `src_endpoint.type_id` — Device-ID source category -> endpoint type_id enum; the Device-ID category taxonomy and OCSF's endpoint-type enum do not align [device-id taxonomy]
- `dst_category` → `dst_endpoint.type_id` — Device-ID destination category -> endpoint type_id enum; taxonomy mismatch [device-id taxonomy]

### palo_alto — unmapped (29)

- `natsrc` — post-NAT source IP; Network Activity models ONE src_endpoint (the original) with no translated-address attribute, so the post-NAT address has no typed home [pre/post-NAT collapse]
- `natdst` — post-NAT destination IP; no translated-address slot on dst_endpoint [pre/post-NAT collapse]
- `vsys` — virtual-system partition id; no OCSF home
- `logset` — log-forwarding profile name (config metadata); no OCSF home
- `natsport` — post-NAT source port; no translated-port slot [pre/post-NAT collapse]
- `natdport` — post-NAT destination port; no translated-port slot [pre/post-NAT collapse]
- `flags` — 32-bit PA session-characteristics bitfield (NAT-applied, decrypted, proxy-session, captive-portal, pcap) — NOT TCP flags; high-signal bits like decrypted/NAT-applied have no OCSF home
- `actionflags` — Panorama log-forwarding bitfield (internal); no OCSF home
- `vsys_name` — named virtual system; no OCSF home
- `action_source` — action provenance (from-policy / from-application); no OCSF home
- `tunnel` — tunnel encapsulation type (GRE/IPSec/GTP); Network Activity 4001 has no tunnel-type attribute
- `parent_session_id` — parent-tunnel session linkage for inner flows; no OCSF parent-session attribute [structure collapse]
- `parent_start_time` — parent-tunnel session start; no home
- `src_profile` — granular Device-ID profile (e.g. 'Apple iPhone'); OCSF has no device-profile attribute
- `dst_profile` — granular Device-ID destination profile; no OCSF device-profile attribute
- `src_edl` — source-IP External Dynamic List membership (threat-intel list name); OCSF endpoint has no list-membership attribute
- `dst_edl` — destination-IP External Dynamic List membership; no OCSF home
- `src_dag` — source Dynamic Address Group membership; no OCSF home
- `dst_dag` — destination Dynamic Address Group membership; no OCSF home
- `flow_type` — proxy vs non-proxy flow type; OCSF expresses proxy presence structurally (proxy_endpoint set), not as an enum, so the label has no home
- `subcategory_of_app` — App-ID subcategory; OCSF has no application-taxonomy attributes [app-id taxonomy seam]
- `category_of_app` — App-ID category; no OCSF application-taxonomy home [app-id taxonomy seam]
- `technology_of_app` — App-ID technology (browser-based/client-server/network-protocol/peer-to-peer); no OCSF home [app-id taxonomy seam]
- `risk_of_app` — App-ID static application-risk rating (1-5); distinct from event risk_level_id (the event's risk, not the app's inherent rating), so no faithful home
- `characteristic_of_app` — App-ID characteristics (evasive/tunnels-other-apps/used-by-malware/...); no OCSF home [app-id taxonomy seam]
- `container_of_app` — App-ID parent application; OCSF has no application-hierarchy attribute
- `tunneled_app` — tunneled application carried inside the parent app; no OCSF home [app-id taxonomy seam]
- `is_saas_of_app` — App-ID SaaS indicator; no OCSF home
- `sanctioned_state_of_app` — App-ID sanctioned-SaaS indicator; no OCSF home

### cisco_asa — coerced (3)

- `severity_level` → `severity_id` — ASA/syslog severity 0-7 (8 levels) -> severity_id enum (~6 levels); 8->6 remap
- `action` → `action_id` — Built/Teardown/Deny -> action_id (Allowed/Denied); Built and Teardown both collapse to Allowed, so the connection-lifecycle distinction OCSF would put in activity_id is lost from this single field
- `teardown_reason` → `status_detail` — teardown reason enum (TCP FINs/TCP Reset/SYN Timeout/Connection timeout/...) -> status_detail free string; OCSF Network Activity has no typed session-termination enum

### cisco_asa — unmapped (7)

- `mapped_src_ip` — NAT-mapped source IP; Network Activity has no translated-address slot [pre/post-NAT collapse]
- `mapped_src_port` — NAT-mapped source port; no translated-port slot [pre/post-NAT collapse]
- `mapped_dst_ip` — NAT-mapped destination IP; no translated-address slot [pre/post-NAT collapse]
- `mapped_dst_port` — NAT-mapped destination port; no translated-port slot [pre/post-NAT collapse]
- `teardown_initiator` — which side initiated the teardown; no OCSF attribute
- `icmp_type` — ICMP type; OCSF Network Activity has no ICMP type/code attributes
- `icmp_code` — ICMP code; OCSF Network Activity has no ICMP type/code attributes

### cisco_umbrella — coerced (2)

- `most_granular_identity` → `src_endpoint.name` — the requesting identity is heterogeneous (roaming computer / AD user / network / site); flattening it to a single endpoint name loses the type-discriminated meaning that most_granular_identity_type carries [heterogeneous identity]
- `most_granular_identity_type` → `src_endpoint.type_id` — Umbrella identity-type (Roaming Computer/AD User/Network/Site/...) -> endpoint type_id enum; the taxonomy does not align, and types like 'AD User'/'Network'/'Site' are not endpoint types at all [identity-type taxonomy]

### cisco_umbrella — unmapped (5)

- `identities` — comma-list of ALL associated identities (device + user + network + AD groups at once); OCSF DNS Activity has no multi-identity list [structure collapse / heterogeneous]
- `external_ip` — egress/NAT public IP of the same requester; src_endpoint.ip already holds the internal client, and there is no second-address slot for the post-NAT egress [pre/post-NAT collapse]
- `categories` — Umbrella content/security categories matched by the domain (Umbrella taxonomy); OCSF DNS Activity has no domain-category attribute (url.categories is HTTP/url-bound, and DNS Activity has no url) [content-category taxonomy seam]
- `identity_types` — comma-list of the types of all associated identities; no OCSF home [structure collapse]
- `blocked_categories` — the categories that caused the block (Umbrella taxonomy); OCSF DNS Activity has no blocked-category/domain-category attribute [content-category taxonomy seam]


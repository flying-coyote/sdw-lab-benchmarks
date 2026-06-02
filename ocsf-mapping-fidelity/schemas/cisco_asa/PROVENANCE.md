# Cisco ASA — provenance

`inventory.json` is the connection-event field set of **Cisco ASA / Secure
Firewall ASA** syslog, scored against OCSF **Network Activity (4001)**.

## Source schema

- **Authoritative:** Cisco *Secure Firewall ASA Series Syslog Messages* guide
  (`cisco.com/.../asa-syslog/syslog-messages-302003-to-342008.html` and the
  106xxx range). ASA does not emit a single fixed record; it emits ~2000
  message-ID-keyed messages, each with its own documented format. This inventory
  scopes to the **connection-event family** — the messages that carry the network
  5-tuple — and takes the union of their documented fields:
  - **302013 / 302014** Built / Teardown TCP connection
  - **302015 / 302016** Built / Teardown UDP connection
  - **302020 / 302021** Built / Teardown ICMP connection
  - **302303–302306** Built / Teardown SCTP connection
  - **106023 / 106100** Deny / ACL-hit by access-group
- **Corroborated** against two independent reproductions: the **Elastic Filebeat
  `cisco` module** (`cisco.asa`, which parses these message IDs into ECS — e.g.
  `source.nat.ip` for the mapped address, `event.action` for Built/Teardown/Deny),
  and the **Splunk Add-on for Cisco ASA** (`Splunk_TA_cisco-asa`, `cisco:asa`
  sourcetype). ManageEngine EventLog Analyzer and LogRhythm publish the same
  message formats as a third and fourth agreeing reproduction.

## What is documented vs reproduced

The message formats and field elements are **documented first-party** by Cisco.
Because ASA fields are positional tokens inside free text rather than a typed
schema, `inventory.json` records the practitioner type implied by each field's
documented role; for the enumerated fields (`action`, `direction`, `protocol`,
`teardown_reason`, `severity_level`) the documented members are in the note. This is
best-effort on type, not on field existence.

## Vendor OCSF mapping that exists

There is **no public field-level Cisco-ASA → OCSF 1.8.0 crosswalk** to anchor each
field on. Cisco's OCSF direction is via Secure Firewall / the broader telemetry
roadmap, not a published ASA-syslog field mapping. So the ASA half is a **best-effort
mapping against the real OCSF 1.8.0 schema** (every target validated), recorded
field-by-field in `mapping.py` with rationale, and labelled best-effort — like
CrowdStrike and Palo Alto. No `official` flag is carried.

## Scope and honesty notes

- Scored against **Network Activity (4001)** only. ASA's VPN, AAA/authentication,
  IPS, and system messages route to other OCSF classes (Authentication, Detection
  Finding, etc.) and are out of scope for this cut.
- This is a **message-family union**, so not every field is present on every event:
  `duration` / `bytes` / `teardown_reason` / `teardown_initiator` appear on Teardown
  messages, `acl_id` on Deny/ACL-hit, `icmp_type` / `icmp_code` on the ICMP variants.
  The note on each field records which.
- The instructive contrast with Palo Alto: ASA Teardown reports a **single total
  byte count**, not the directional `bytes_sent` / `bytes_received` PAN-OS carries —
  so the directional traffic split that maps cleanly for Palo Alto is simply absent at
  the source here. That is a source limitation, recorded as such, not a mapping loss.
- Coverage is over the scoped connection-event field set, not all ASA telemetry.

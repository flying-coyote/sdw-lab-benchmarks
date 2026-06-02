# Cisco Umbrella DNS — provenance

`inventory.json` is the **DNS log** column set of Cisco Umbrella, scored against
OCSF **DNS Activity (4003)**.

## Source schema

- **Authoritative:** Cisco Umbrella documentation, *Log Management → Log Formats and
  Versioning → DNS Log Formats* (`docs.umbrella.com` / `securitydocs.cisco.com`).
  Umbrella DNS logs are gzip-compressed CSV written every ~10 minutes to a managed or
  customer-owned S3 bucket. The column set scored here is the documented v3+ DNS-log
  format (13 columns).
- **Corroborated** against two independent parser reproductions that agree on the
  column order: the **Cyderes** Cisco-Umbrella-DNS parser knowledge base (which
  includes a real sample log line confirming all 13 columns and their order), and the
  **Google SecOps (Chronicle)** `cisco-udns` / `umbrella-dns` default parser. The
  Umbrella column order in the Cyderes sample —
  `Timestamp, MostGranularIdentity, Identities, InternalIP, ExternalIP, Action,
  QueryType, ResponseCode, Domain, Categories, MostGranularIdentityType,
  IdentityTypes, BlockedCategories` — is reproduced exactly.

## What is documented vs reproduced

The column names and order are **documented first-party** by Cisco and reproduced by
both mirrors. Because the CSV is untyped text, `inventory.json` records the
practitioner type implied by each column; the enumerated columns (`action`,
`response_code`) and the comma-list columns (`identities`, `categories`,
`identity_types`, `blocked_categories`) are noted as such.

## Vendor OCSF mapping that exists

There is **no public field-level Cisco-Umbrella-DNS → OCSF 1.8.0 crosswalk** to
anchor each field on (Umbrella's OCSF direction is via Cisco XDR / the broader
telemetry roadmap, not a published DNS-log field mapping). So the Umbrella half is a
**best-effort mapping against the real OCSF 1.8.0 schema** (every target validated),
recorded field-by-field in `mapping.py` with rationale, and labelled best-effort —
like the firewalls and CrowdStrike. No `official` flag is carried.

## Scope and honesty notes

- Scored against **DNS Activity (4003)** only. Umbrella's Proxy, Cloud Firewall, and
  IP logs are separate log types that route to HTTP Activity / Network Activity and
  are out of scope for this cut.
- Newer Umbrella schema versions add columns this cut does **not** score: identity
  UUIDs / identity-type UUIDs, DNS-over-HTTPS / public-site indicators, and (for
  proxy logs) a Request Method. The v3+ 13-column DNS set is what both mirrors
  reproduce consistently, so that is the scored set; the newer columns are named here
  rather than silently omitted.
- The result is shaped by what Umbrella adds on top of plain DNS: the DNS resolution
  facts (query, rcode, action, client IP, time) have typed OCSF homes, but Umbrella's
  value-add — its heterogeneous **identity** model and its domain **content-category**
  taxonomy — largely does not, which is where the coverage goes. That is a finding
  about OCSF DNS Activity's scope, not a defect in the log.
- Coverage is over the scoped DNS-log column set, not all Umbrella telemetry.

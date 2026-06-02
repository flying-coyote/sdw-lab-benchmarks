# Palo Alto Networks PAN-OS TRAFFIC log — provenance

`inventory.json` is the field set of the PAN-OS **TRAFFIC** log (a firewall
session record), scored against OCSF **Network Activity (4001)**.

## Source schema

- **Authoritative:** Palo Alto Networks PAN-OS Administrator's Guide, *Monitoring →
  Use Syslog for Monitoring → Syslog Field Descriptions → Traffic Log Fields*
  (`docs.paloaltonetworks.com/pan-os/11-0/.../traffic-log-fields`). The TRAFFIC log
  is a fixed-position comma-separated record; the field names in `inventory.json` are
  PANW's own documented syslog field identifiers (`src`, `natsrc`, `bytes_sent`,
  `session_end_reason`, `*_of_app`, the Device-ID `src_*`/`dst_*` block, etc.).
- **Corroborated** against two independent reproductions that agree on the same field
  set: **Elastic Filebeat `panw` module** (`exported-fields-panw` and the
  `panw/panos` ingest pipeline, which parses the TRAFFIC and THREAT subtypes), and
  **Google SecOps (Chronicle)** default parser for Palo Alto firewall
  (`pan-firewall`). Panther's `PaloAltoNetworks.Firewall` schema is a third agreeing
  reproduction.

## What is documented vs reproduced

The field names, order, and descriptions are **documented first-party** by PANW (this
is not a gated schema). The per-field native type is not always stated as a strict
type in the syslog reference (the record is comma-separated text), so `inventory.json`
records the practitioner type (ip / integer / timestamp / enum) implied by the
description; where a value is an enumerated set, the documented members are listed in
the note. This is best-effort on type only, not on field existence.

## Why anchor on the field reference, not a shipped parser (first-hand)

The reason this inventory is transcribed against PANW's authoritative field reference
rather than trusting a shipped integration is that I have repaired one of those
integrations directly. In 2023, while at a regulated utility, I submitted
[PaloAltoNetworks/Splunk-Apps PR #294](https://github.com/PaloAltoNetworks/Splunk-Apps/pull/294)
("Added PanOS 11 syslog standard fields; repaired broken field extracts & name
collisions") against Palo Alto's own Splunk app, tested against large-scale existing
`pan:*` data. Two of the fixes are exactly the failure mode this benchmark cares
about: because the TRAFFIC and CONFIG logs are positional comma-separated records, a
single wrong field assignment cascades into every field after it — `[extract_userid]`
had omitted `src_user`, and `[extract_config]` had included `devicegroup_level3` /
`devicegroup_level4` fields that do not exist in the data, so everything downstream
parsed into the wrong column. A separate fix resolved a name collision where
`serial_number` was overwriting the reporting device serial (`dvc_serial`) with the
asset serial. The PR was never merged and the repository has since been archived.

That experience is why the field-by-field mapping here is the point: a vendor's own
shipped integration carried hundreds of incorrect or missing extractions for years,
which is the Palo Alto-side echo of the Okta implementation-gap finding — the schema
can hold a field, and the shipped integration still gets it wrong. It also informs two
scoping calls below: the reporting-firewall `serial` maps to `device.uid` (the
`dvc_serial`, distinct from the per-asset `serialnumber`/`host_serial` in the excluded
GlobalProtect block), and the Panorama device-group-hierarchy fields are excluded in
part because their mishandling is precisely what broke the CONFIG-log parse.

## Vendor OCSF mapping that exists

PANW publishes **Cortex / Strata Logging Service** with an OCSF export, and there is
community tooling (e.g. the OCSF `pan_*` mappings) that targets Network Activity, but
there is **no single authoritative, public, field-by-field PAN-OS-TRAFFIC → OCSF
1.8.0 crosswalk** to anchor each field on. So the Palo Alto half is a **best-effort
mapping against the real OCSF 1.8.0 schema** (every target validated against the
checked-in subset), recorded field-by-field in `mapping.py` with rationale, and
labelled best-effort — exactly as CrowdStrike is. No `official` flag is carried for
Palo Alto.

## Scope and honesty notes — the excluded families

The TRAFFIC log documents ~117 real leaf fields (excluding the FUTURE_USE
placeholders, which are not fields). This benchmark scores the **83-field core NGFW
traffic-session record** and excludes five license/platform-gated extension families,
named here with counts so the scope is transparent rather than a convenient subset:

- **SD-WAN (7):** `policy_id`, `link_switches`, `link_change_count`, `sdwan_cluster`,
  `sdwan_device_type`, `sdwan_cluster_type`, `sdwan_site`.
- **5G / SCTP mobile-network inspection (8):** `tunnelid/imsi`, `monitortag/imei`,
  `assoc_id`, `chunks`, `chunks_sent`, `chunks_received`, `nssai_sst`, `nssai_sd`.
- **CN-Series / Kubernetes container (5):** `container_id`, `pod_namespace`,
  `pod_name`, `k8s_cluster_id`, `cluster_name`.
- **GlobalProtect host-info (2):** `hostid`, `serialnumber`.
- **AI-security (2):** `ai_traffic`, `ai_fwd_error` (PAN-OS 11.1+/12.1+).

Also excluded: the four Panorama device-group-hierarchy IDs (`dg_hier_level_1..4`),
the HA/processing-internal fields (`session_owner`, `offloaded`, `http2_connection`,
`high_res_timestamp` — a high-resolution duplicate of `receive_time`), the two
12.1.2+ advanced-device-id fields (`src_adv_dev_id`, `dst_adv_dev_id`), and the eight
fields PANW explicitly labels **"Internal use only"** (the TCP RTT, out-of-sequence,
retransmit, and zero-window counters). The exclusion boundary is **structural**
(optional feature families and internal/duplicate fields), not fidelity-based: the
scored set is the session record a standard NGFW deployment emits. A reader who wants
those families scored can add them; most are platform metadata with no OCSF Network
Activity home, so including them would lower coverage further, not raise it.

- Scored against **Network Activity (4001)** only. The THREAT/URL/WildFire subtypes
  route to Detection Finding (2004) / other classes and are out of scope for this cut.
- Coverage is over the scoped TRAFFIC field set, not all PAN-OS telemetry.

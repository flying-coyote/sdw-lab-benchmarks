# CrowdStrike Falcon — provenance

`inventory.json` is the **Detection Summary Event** field set from CrowdStrike's
Falcon Event Streams API, scored against OCSF Detection Finding (2004).

## What is public vs gated — read this first

CrowdStrike's full **Falcon Data Replicator (FDR)** schema (900+ event types) is
**not public**; it is gated behind login at falcon.crowdstrike.com, and CrowdStrike's
own canonical FDR→OCSF mapping files are explicitly account-manager-gated
("Contact your CrowdStrike account manager to obtain the FDR OCSF mapping files",
per the `CrowdStrike/aws-security-lake` repo). So this benchmark deliberately scopes
to the one CrowdStrike event whose field set is **publicly and consistently
documented**: the Detection Summary Event.

Because CrowdStrike's own dictionary is gated, the field names and types in
`inventory.json` come from independent third-party reproductions that agree with
each other, not from CrowdStrike directly:

- **Elastic Filebeat 8.19** CrowdStrike module — `exported-fields-crowdstrike`
- **Panther** `Crowdstrike.EventStreams` schema
- **Splunk** research detection "CrowdStrike Falcon Stream Alerts" (corroborates the
  detection-relevant fields and `sourcetype CrowdStrike:Event:Streams:JSON`)
- CrowdStrike's **Falcon Event Streams Add-on Guide v3.5+** (V11-19-24-TS,
  2024-11-19) confirms operational facts (`PatternDispositionValue` is a numeric
  bitmask) but points the field dictionary at the gated console URL.
- `CrowdStrike/falconpy` discussions #205/#208 confirm: the nested arrays
  (`NetworkAccesses`, `DnsRequests`, `ScanResults`, `DocumentsAccessed`,
  `ExecutablesWritten`) are conditional; `DetectName` is being phased out toward
  Objective/Tactic/Technique; `PatternDispositionFlags.InddetMask` is deprecated in
  favor of the integer bitmask.

Two sources disagree on a few types (`Severity` float vs integer; `ProcessId` /
`ParentProcessId` string vs integer). `inventory.json` records the disputed types as
`number` / `string|integer`. This does not affect the mapping disposition, but it is
disclosed.

## Vendor OCSF mapping that exists (class-level only)

There is **no public field-level CrowdStrike→OCSF mapping**. What is public is the
*class-level* routing, confirmed by AWS:

- AWS CloudWatch "Source configuration for CrowdStrike" states the integration
  supports **OCSF v1.5.0** and that CrowdStrike FDR actions map to **Detection
  Findings (2004)** and **Process Activity (1007)**.
- AWS Security Lake lists CrowdStrike Falcon Data Replicator as a Source integration
  that "transforms the data into OCSF schema."
- The closest public field-level material is third-party (Query's data model maps the
  Alerts API to **Detection Finding** and supports entity search on Username/IP/MAC/
  Hostname/File Hash/File Name/Command Line/Process ID; Query's open FDR pipeline
  targets the older OCSF **v1.2.0**).

Because no CrowdStrike-published field mapping exists, the CrowdStrike half of this
benchmark is a **best-effort mapping against the real OCSF 1.8.0 schema** (every
target validated against the checked-in schema subset), recorded field-by-field in
`mapping.py` with rationale. It is labelled as best-effort, not as a vendor mapping.

## Scope and honesty notes

- Detection Summary Event only — **not** the full FDR schema. A coverage figure here
  is for that one event, not for all CrowdStrike telemetry.
- Scored against **Detection Finding (2004)**, the class AWS confirms CrowdStrike
  detections route to. Process telemetry would route to Process Activity (1007); not
  scored here.
- Conditional nested arrays (`NetworkAccesses`, `DnsRequests`, `ExecutablesWritten`,
  `ScanResults`) have inner structures none of the public sources fully enumerate;
  they are scored as single array fields, with the structure-collapse noted.

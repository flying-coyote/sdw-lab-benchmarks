# Results — pipeline normalization-fidelity (task #10)

- OCSF version: **1.8.0**  ·  evidence tier: B (reproducible; first-party reference mapping vs a tool's shipped mapping, seeded synthetic corpus — not production telemetry)
- Tool: **tenzir**  ·  mapping artifact: `tenzir 6.0.0 / library 671e049 zeek::ocsf::map`
- Field fidelity = of the gold's typed+coerced source fields, the fraction the tool lands on a populated OCSF attribute. Value fidelity = of those, the fraction whose value survives. Semantic = class/activity/type_uid + the five failure classes.
- Every gold OCSF target is validated against the merged C1+ext 1.8.0 subset; an invented attribute fails the run. Coverage != fidelity: a source the tool produced no output for scores 0%.

## Three-level fidelity per source

| source | OCSF class | records | coverage | field | value | class | activity_id |
|---|---|--:|--:|--:|--:|--:|--:|
| zeek_conn | network_activity (4001) | 100000 | 100% | 80% | 92% | 100% | 17% |
| cloudtrail | api_activity (6003) | 100000 | 0% | 0% | 0% | 0% | 0% |
| sysmon | process_activity (1007) | 100000 | 0% | 0% | 0% | 0% | 0% |
| auth | authentication (3002) | 100000 | 0% | 0% | 0% | 0% | 0% |

## Failure classes reproduced (README level 3)

Fraction of records where each recurring crosswalk failure class shows up in this tool's shipped mapping (P4: the seams are OCSF's own if every tool reproduces them).

| source | context_collapse | entity_role | multi_event_collapse | observables_flattening | severity_remap |
|---|--:|--:|--:|--:|--:|
| zeek_conn | — | 0% | — | 0% | — |
| cloudtrail | 100% | — | — | — | 100% |
| sysmon | — | — | 100% | 100% | — |
| auth | 100% | — | — | — | 100% |

## Where the fidelity went (auditable)

### zeek_conn

- field-fidelity losses (gold-typed/coerced fields the tool dropped): `history`×100000, `service`×100000, `uid`×100000
- value-fidelity losses (landed but value mangled): `ts`×100000, `duration`×53

### cloudtrail

- field-fidelity losses (gold-typed/coerced fields the tool dropped): `awsRegion`×100000, `eventID`×100000, `eventName`×100000, `eventSource`×100000, `eventTime`×100000, `eventVersion`×100000, `requestID`×100000, `sourceIPAddress`×100000
- value-fidelity losses (landed but value mangled): none

### sysmon

- field-fidelity losses (gold-typed/coerced fields the tool dropped): `CommandLine`×100000, `EventID`×100000, `Hashes`×100000, `Image`×100000, `IntegrityLevel`×100000, `LogonId`×100000, `ParentCommandLine`×100000, `ParentImage`×100000
- value-fidelity losses (landed but value mangled): none

### auth

- field-fidelity losses (gold-typed/coerced fields the tool dropped): `auth_protocol`×100000, `dst_host`×100000, `event_id`×100000, `logon_type`×100000, `mfa`×100000, `result`×100000, `src_ip`×100000, `timestamp`×100000
- value-fidelity losses (landed but value mangled): none


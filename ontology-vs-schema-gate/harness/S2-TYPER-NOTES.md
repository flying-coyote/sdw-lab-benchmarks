# S2 source typer: author notes (2026-11-17)

Module: `harness/s2_source_typer.py`
sha256: `421b745365417c05c4dfbaaf1591cb716bfcdc74e63a14f3ce6180b8ffedcc68`

Interface, per HARNESS-ADDENDUM.md section 5: `source_kind(schema: str, field: str) -> str | None`. It returns an OCSF 1.8.0 object name taken from `schema-ocsf-1.8.0-api-2026-11-16/objects/`, or `None` to abstain. The module is stdlib-only and imports nothing from the harness. It is deterministic, with no network access and no model calls at runtime. Run `python3 -B harness/s2_source_typer.py` for the self-test. The self-test checks three things:

- every field in the six request files has a table row, and no row is extra;
- every value the module returns is a file stem in the 178-object listing;
- typed plus abstained equals the per-schema totals below.

## Counts

| Schema | Fields | Typed | Abstained |
| --- | --- | --- | --- |
| Microsoft ASIM | 133 | 103 | 30 |
| Splunk CIM | 78 | 61 | 17 |
| Elastic ECS | 128 | 106 | 22 |
| OpenTelemetry | 64 | 56 | 8 |
| Google UDM | 78 | 51 | 27 |
| Zeek | 51 | 34 | 17 |
| **Total** | **532** | **411** | **121** |

The self-test prints counts only. The abstained fields are listed explicitly as `_N` in the module's tables, and a one-line loop over `_TABLES` lists them by name.

## Open interface questions for the caller

1. **Field list key.** Section 5 says the fields to cover are "the `source_fields` lists" in `s1_table_work/request-*.json`. Those files have no `source_fields` key; they have `schema` plus `leaf_tokens`, which maps each leaf token to a list of full field strings. I keyed the tables on the full strings exactly as they appear, including the odd ones (`.port`, `event.category: malware`, `TargetUserIdType=SID`, `orig+resp_bytes`, `id.*`). If `arms.run_s2` passes a leaf token instead, `source_kind` falls back to the full fields that share that leaf and returns a kind only when they all agree. I did not read `arms.py`, so I don't know which form it passes.
2. **`extends` normalisation.** The task brief said to normalise through `extends` "as section 5 says", but section 5 says nothing about it. The module returns the most specific object the docs support (`device`, `network_endpoint` and `process` stay as they are) and leaves any normalisation to the harness. The one place it deliberately returns a parent is CIM `src`/`dest`, which return `endpoint` (rule R3).

## Rules

The full text is in the module docstring. In summary:

- **R1:** a field types to its owning entity, which is the most specific OCSF object whose 1.8.0 attribute list holds the property. I checked attribute lists for `endpoint`, `network_endpoint`, `device`, `file`, `process`, `user`, `group`, `url`, `http_request`, `http_response`, `network_connection_info`, `network_traffic`, `product`, `rule`, `malware`, `session` and `osint`, among others.
- **R2:** where the owning object lacks the property, the nested object takes it. Process image hash and size go to `file`, because OCSF `process` has neither. A field whose value names another entity (file owner, process user) types to that entity, `user`.
- **R3:** participant hosts type to `network_endpoint`, and reporting, observing or executing hosts type to `device`. A field that is a participant in one CIM data model and the executing host in another (CIM `src`/`dest`) types to `endpoint`, the common parent.
- **R4:** flow counters type to `network_traffic`. Protocol, direction, flow or session id, community id, TCP flags and connection state type to `network_connection_info`.
- **R5:** HTTP request-side fields type to `http_request` and the cookie header to `http_cookie`. Response-side fields type to `http_response`, and URLs and their parts to `url`.
- **R6:** abstain on event-level scalars, which describe the record or activity rather than an entity: timestamps, severity, action, outcome, event type or id, duration, and the risk or confidence scores of a detection. The exception is a score or date documented as a property of a threat *indicator*. ECS `threat.indicator.confidence` and `first_seen` type to `osint`, whose attributes include `confidence` and `created_time`. ASIM `ThreatConfidence` and `ThreatFirstReportedTime` are documented as properties of the threat a detection identified, so they abstain.
- **R7:** abstain in three cases:
  - the token has no fieldset prefix;
  - a wildcard covers a noun of mixed kinds (UDM `principal.*`, ASIM `Src*`);
  - the schema's own docs give the token different entity meanings. Examples:
    - Zeek `method`, `status_code`, `request_body_len` and `user_agent` appear in both http.log and sip.log.
    - Zeek `service` means the confirmed protocols in conn.log and the requested Kerberos service in kerberos.log.
    - CIM `app` and `status` mean different things in different data models.
- **R8:** return values are raw object names, with no `extends` normalisation.

Judgement calls a reviewer may want to check:

- ASIM `ThreatId`/`ThreatName`/`ThreatCategory` type to `malware`, because the ASIM docs say "threat or malware". UDM `security_result.threat_name` abstains, because its definition ("a vendor-assigned classification common across multiple customers") does not mention malware.
- ECS `threat.indicator.*` types to `osint`, and `threat.software.name` abstains (the software could be malware or a tool).
- ASIM `TargetAppName` and UDM `target.application` type to `application`.
- ASIM `NetworkRuleName`/`NetworkRuleNumber` and CIM `rule` type to `rule`, not `firewall_rule`.
- UDM `intermediary.ip` and ASIM `SrcNatIpAddr` type to `network_endpoint`, not `network_proxy`.
- Zeek `uid` types to `network_connection_info`. All six logs I fetched (conn, http, sip, files, notice, krb) define it as the connection's unique id.

Limits on the evidence behind some typings:

- CIM `user_name` is defined on the Change page ("the user name of the user or entity performing the change"), not on the Authentication page, and it types to `user`.
- Zeek `username` types to `user` from http.log. None of the other five logs I fetched defines it, and I did not survey every Zeek log.
- Zeek `name` and `notice` come from weird.log, which I did not fetch, so they abstain.

## What I read

Local files:

- `~/sdw-lab-benchmarks/ontology-vs-schema-gate/HARNESS-ADDENDUM.md`: section 5 only (lines 152 to 173). To find it, I first ran `grep -n '^#'` over the whole file, which showed only the heading lines of every section and none of their body text.
- `~/sdw-lab-benchmarks/ontology-vs-schema-gate/harness/s1_table_work/request-{asim,cim,ecs,opentelemetry,udm,zeek}.json`, in full.
- `~/sdw-lab-benchmarks/ocsf-deterministic-mapper/schema-ocsf-1.8.0-api-2026-11-16/FETCH-META.json`.
- `~/sdw-lab-benchmarks/ocsf-deterministic-mapper/schema-ocsf-1.8.0-api-2026-11-16/objects/*.json`. A script loaded every file in this directory and printed only `name`, `extends` and `caption` for all 178 objects. That includes OCSF's own `d3fend`, `d3f_tactic` and `d3f_technique` object definitions, which appear in the printed list as names and captions only; I opened none of them beyond that one line each. A second script printed the attribute-name lists of about 30 candidate objects, none of them D3FEND objects.
- Directory listings of `harness/`, `harness/s1_table_work/` and the `schema-ocsf-1.8.0-api-classes-2026-11-17/` directory. I saw these as file names only and opened no files in them.

Public documentation, all fetched 2026-11-17:

- Microsoft ASIM:
  - https://learn.microsoft.com/en-us/azure/sentinel/normalization-common-fields
  - https://learn.microsoft.com/en-us/azure/sentinel/network-normalization-schema
  - https://learn.microsoft.com/en-us/azure/sentinel/web-normalization-schema
  - https://learn.microsoft.com/en-us/azure/sentinel/process-events-normalization-schema
  - https://learn.microsoft.com/en-us/azure/sentinel/authentication-normalization-schema
  - https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema-file-event
  - https://learn.microsoft.com/en-us/azure/sentinel/normalization-entity-user
  - https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema-user-management
- Splunk CIM 6.0. docs.splunk.com returned 403, so I used help.splunk.com:
  - https://help.splunk.com/en/splunk-enterprise/common-information-model/6.0/data-models/network-traffic
  - https://help.splunk.com/en/splunk-enterprise/common-information-model/6.0/data-models/endpoint
  - https://help.splunk.com/en/splunk-enterprise/common-information-model/6.0/data-models/web
  - https://help.splunk.com/en/splunk-enterprise/common-information-model/6.0/data-models/authentication
  - https://help.splunk.com/en/splunk-enterprise/common-information-model/6.0/data-models/change
  - https://help.splunk.com/en/splunk-enterprise/common-information-model/6.0/data-models/intrusion-detection
- Elastic ECS. The pages state no version.
  - https://www.elastic.co/docs/reference/ecs/ecs-threat
  - https://www.elastic.co/docs/reference/ecs/ecs-network
  - https://www.elastic.co/docs/reference/ecs/ecs-file
  - https://www.elastic.co/docs/reference/ecs/ecs-process
  - https://www.elastic.co/docs/reference/ecs/ecs-observer
  - https://www.elastic.co/docs/reference/ecs/ecs-server
  - https://www.elastic.co/docs/reference/ecs/ecs-source
  - https://www.elastic.co/docs/reference/ecs/ecs-destination
  - https://www.elastic.co/docs/reference/ecs/ecs-client
  - https://www.elastic.co/docs/reference/ecs/ecs-user
  - https://www.elastic.co/docs/reference/ecs/ecs-group
  - https://www.elastic.co/docs/reference/ecs/ecs-host
  - https://www.elastic.co/docs/reference/ecs/ecs-http
  - https://www.elastic.co/docs/reference/ecs/ecs-url
  - https://www.elastic.co/docs/reference/ecs/ecs-user_agent
  - https://www.elastic.co/docs/reference/ecs/ecs-rule
  - https://www.elastic.co/docs/reference/ecs/ecs-service
  - https://www.elastic.co/docs/reference/ecs/ecs-agent
  - https://www.elastic.co/docs/reference/ecs/ecs-hash
  - https://www.elastic.co/docs/reference/ecs/ecs-event
- Google SecOps UDM: https://docs.cloud.google.com/chronicle/docs/reference/udm-field-list. I read characters 0 to 300,000 in three passes; the last 12,880 characters were never read. cloud.google.com redirects to this URL.
- OpenTelemetry:
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/process/
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/file/
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/network/
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/http/
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/session/
  - https://opentelemetry.io/docs/specs/otel/logs/data-model/
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/client/
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/server/
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/source/
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/destination/
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/user/
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/user-agent/
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/url/
  - https://opentelemetry.io/docs/specs/semconv/registry/attributes/host/
- Zeek:
  - https://docs.zeek.org/en/master/scripts/base/protocols/conn/main.zeek.html
  - https://docs.zeek.org/en/master/scripts/base/protocols/http/main.zeek.html
  - https://docs.zeek.org/en/master/scripts/base/protocols/sip/main.zeek.html
  - https://docs.zeek.org/en/master/scripts/base/frameworks/files/main.zeek.html
  - https://docs.zeek.org/en/master/scripts/base/frameworks/notice/main.zeek.html
  - https://docs.zeek.org/en/master/scripts/base/protocols/krb/main.zeek.html

Every URL the module cites appears in this list, and I checked the rows under each citation against the definition that came back. One caveat on that check: WebFetch passes each page through a summarising model, so what I read was extracted or paraphrased text, not raw HTML. The Zeek record tables in particular came back paraphrased rather than verbatim, and the ECS, UDM and ASIM answers were mostly quoted.

I opened no vendor "mapping to OCSF" page and no third-party crosswalk.

## Blindness statement

I, the S2 typer author (a fresh Claude subagent spawned 2026-11-17), complied with the blindness rule in section 5 and in the task brief. I did not open or grep any of the following:

- anything under `~/project1/02-projects/d3fend-wall/`;
- any copy of `ocsf_d3fend_corpus_validation.py`, or anything under `repro/` or `results/`;
- `harness/arms.py`, `inject.py`, `score.py` or `common.py`. The brief allowed `common.py`, but section 5 forbids it, so I left it closed;
- `harness/s1_source_type_table.csv`, `s1_table_work/response-*` or `s1_table_work/BRIEF.md`;
- `ADJUDICATION-SHEET.csv`, the E2 key, or the six crosswalk files;
- any D3FEND ontology or data file.

I did not search for `SEG_RULES` or `SEG_ARTIFACT`.

Incidental exposures, disclosed in full:

- An `ls` of `harness/` and `s1_table_work/` showed the forbidden file names. I opened none of those files.
- Section 5's own text names `SEG_RULES`, `SEG_ARTIFACT` and `source_type()` as things the harness author read. I saw only those names, never their content.
- The heading grep showed the titles of sections 1 to 4 and 6 to 9 of the addendum, and of its "Main-session rulings" block.
- My object-listing script printed the name, `extends` and caption of OCSF's `d3fend`, `d3f_tactic` and `d3f_technique` object definitions. These are OCSF schema objects inside the allowed objects directory, not D3FEND ontology files. I read nothing beyond those three lines, and no typing decision used them.

None of these exposures carried any source-field typing information.

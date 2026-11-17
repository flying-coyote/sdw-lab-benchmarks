---
type: reference
date: 2026-05-31
ocsf-version: 1.8.0
title: "OCSF Field Matrix — six source schemas, one destination"
created: 2026-05-31
---

# OCSF Field Matrix — six source schemas, one destination

This is the master comparison view that unifies the six schema→OCSF crosswalks in this directory: [Splunk CIM](cim-ocsf-crosswalk.md), [Google Chronicle UDM](udm-ocsf-crosswalk.md), [Microsoft Sentinel ASIM](asim-ocsf-crosswalk.md), [Elastic Common Schema (ECS)](ecs-ocsf-crosswalk.md), [OpenTelemetry (OTel)](otel-ocsf-crosswalk.md), and [Zeek](zeek-ocsf-crosswalk.md). Each of those documents maps one source schema *into* OCSF 1.8.0, class by class. This matrix inverts that: OCSF is the spine, each source is a column, and every row is one OCSF attribute. Read across a row to see how the six sources each reach (or fail to reach) the same OCSF field; read down a column to see how much of a given OCSF class a source can populate.

How to read it. The first column is the OCSF attribute as a dot-path (`user.name`, `src_endpoint.ip`, `severity_id`, `connection_info.direction_id`). Required attributes for the class are listed first and marked **req**; commonly-mapped recommended/optional attributes follow. Each cell is the source field that feeds that OCSF attribute, pulled from that source's crosswalk — terse, with a transform hint where one matters (`(enum)`, `(×1000)`, `(ns→ms)`). A `—` means the source has no field for that OCSF attribute: the column can't reach that part of OCSF. A trailing `~` flags a low-confidence or inferred mapping in that source's crosswalk, so you can see the soft spots at a glance. The "Unmapped" subsection at the bottom of each class lists the meaningful source fields that have no OCSF home at all — what OCSF can't hold from that source, drawn from each crosswalk's context-collapse seams and `unmapped` rows.

Legend: `—` = no source field for this OCSF attribute. `~` = inferred / low-confidence mapping (the source crosswalk rated it low, or the home is schema-permitted but not schema-dictated). A cell with a transform hint in parentheses needs that conversion (`(enum)` = integer-enum bridge with a string caption; `(×1000)` = seconds→milliseconds; `(×1024)` = KB→bytes; `(ns→ms)` = nanoseconds→milliseconds; `(int)` = string→integer cast). Column order is deliberate: CIM → ASIM → UDM/ECS → OTel runs roughly from sparsest to densest, which the `—` density makes visible; Zeek sits last as the connection-centric outlier.

Zeek is the sixth column, and it has a distinctive shape the others don't. It is *connection-centric* — one record per protocol transaction across many log files, stitched by a shared `uid`, not one self-contained event — and *sensor-side/executable*: the mapping is backed by Zeek scripts that emit OCSF-shaped records at the monitoring point, not a vendor's normalized-store schema on paper. Most consequentially for this matrix, Zeek is *network-only*: a passive wire observer is blind to authentication, process, and IAM events, so its columns on Authentication (3002), Process Activity (1007), and Account Change (3001) are all `—` — the column honestly shows what a network sensor cannot see. Zeek's real strengths land in OCSF classes *outside* this seven-class matrix — DNS Activity (4003), SSH Activity (4007), Email Activity (4009), DHCP Activity (4004), plus the `tls`/`digital_certificate` objects — which the [Zeek crosswalk](zeek-ocsf-crosswalk.md) tabulates but this matrix does not.

Three cross-source patterns the matrix surfaces, called out because they recur on almost every table:

First, **`severity_id` is required by 3002/4001/4002/1007 (and 2004) but the sources disagree wildly on whether they can supply it.** UDM (`security_result.severity`) and ASIM (`EventSeverity`) carry it natively on every event; OTel carries a clean banded `SeverityNumber` (log-level, not threat-level). CIM has no severity field on Authentication, Network, Web, or Endpoint — a mapper must *invent* it. ECS has `event.severity` but it is a source-defined integer with no controlled vocabulary, so it is closer to "invent/band per source" than to "read." Zeek's base logs (conn/http) are pure observation and carry no severity at all — like CIM, a mapper must synthesize it, and Zeek's only real severity lives on `notice.log`, which routes to the findings class (2004). So on the activity classes the same required field is native in two columns, weak in one, and invented/absent in three (CIM, ECS-ish, Zeek) — the single most consequential structural split in the matrix.

Second, **no source can supply OCSF's `disposition_id` cleanly on the activity classes, because 4001/4002/1007/1001 don't have a `disposition_id` attribute** (verified 1.8.0 in all six crosswalks). The firewall/EDR/proxy sources (CIM `action`, ASIM `DvcAction`, UDM/ECS verdict fields) all carry an allow/deny verdict, but it has nowhere to land on those classes and falls to `status_id`/`unmapped`. Zeek is the limiting case from the other direction: as a passive wire observer it carries *no verdict at all* on its base logs (it watches, it never enforces), so on 4001/4002 there is nothing to strand — its disposition gap is source-side, not OCSF-side. `disposition_id` exists only on the findings class (2004), where the verdict finally has a home (Zeek's `notice.log` `actions` reach it there). This is an OCSF-side gap on the activity classes, identical across every column that carries a verdict.

Third, **the columns get visibly denser (fewer `—`) moving left to right across CIM → ASIM → UDM/ECS**, and **OTel is sparse outside Network and HTTP**. CIM pays the most `—` on severity and on the operation/verdict split; ASIM closes the severity and verdict gaps but pays a flat→nested lift; UDM and ECS are densest (typed, nested, native severity, clean routing). OTel fills the envelope (time, severity, device, metadata) and the ECS-derived endpoint/HTTP/process/file namespaces cleanly, but has no operation verbs for process/file/auth and *nothing at all* for findings or change — so its columns on 3001 and 2004 are nearly empty. Zeek breaks the density gradient on a different axis: it is *dense* on the network classes (4001/4002 endpoints, traffic, connection_info, and a clean `community_uid` win) but wholly `—` on the three classes a network sensor cannot observe — 3002, 1007, 3001 — so its blindness is by event *category*, not by field richness.

---

## Authentication (3002)

OCSF Authentication, `class_uid` 3002, category Identity & Access Management. Required: `activity_id`, `category_uid`, `class_uid`, `metadata`, `severity_id`, `time`, `type_uid`, `user`; plus the constraint **at least one of `dst_endpoint` / `service`**.

| OCSF attribute (dot-path) | Splunk CIM | Google UDM | Microsoft ASIM | Elastic ECS | OpenTelemetry | Zeek |
|---|---|---|---|---|---|---|
| `activity_id` **req** | `action` (enum)~ | `metadata.event_type` (enum) | `EventType` (enum) | `event.type` (enum) | — | — |
| `severity_id` **req** | — | `security_result.severity` (enum) | `EventSeverity` (enum) | `event.severity`~ | `SeverityNumber` (enum) | — |
| `time` **req** | `_time` | `metadata.event_timestamp` | `EventStartTime` | `@timestamp`/`event.start` | `Timestamp` (ns→ms) | — |
| `metadata` **req** | `vendor_product` (split) | `metadata.product_name`/`vendor_name` | `EventProduct`/`EventVendor` | `observer.*`/`event.provider` | `Resource`/`EventName` | — |
| `user.name` **req** | `user` | `principal.user.userid` | `TargetUsername` | `user.name` | `user.name` | — |
| `dst_endpoint` or `service` **req (constraint)** | `dest`/`app` | `target.*`/`target.application` | `Target`/`TargetAppName` | `destination`/`server`/`service.name` | `destination.*`/`server.address`~ | — |
| `category_uid` / `class_uid` / `type_uid` **req** | const | const | const | const | const | — |
| `status_id` (+ `status`) | `action` (enum) | `security_result.action` (enum) | `EventResult` (enum) | `event.outcome` (enum) | — | — |
| `status_detail` | `reason` | `security_result.summary`/`.description` | `EventResultDetails` | `event.action` | `SeverityText`~ | — |
| `user.uid` | `user_id` | `principal.user.windows_sid`~ | `TargetUserId` | `user.id` | `user.id` | — |
| `user.sid` | — | `principal.user.windows_sid`~ | `TargetUserId` (`TargetUserIdType=SID`) | — | — | — |
| `user.full_name` | — | `principal.user.user_display_name` | — | `user.full_name`~ | — | — |
| `user.email_addr` | — | `principal.user.email_addresses` | `TargetUsername` (`UPN`) | `user.email` | — | — |
| `user.type_id` (+ `user.type`) | `user_type` (enum) | `principal.user.user_role` (enum) | `TargetUserType` (enum) | — | — | — |
| `user.domain` | — | — | — | `user.domain`~ | — | — |
| `actor.user.name` | `src_user`~ | `target.user.userid`~ | `ActorUsername` | `user.target.name`~ | — | — |
| `actor.user.uid` | — | — | `ActorUserId` | — | — | — |
| `src_endpoint.ip` / `.hostname` | `src` | `principal.ip`/`.hostname` / `src.*` | `Src`/`SrcIpAddr`/`SrcHostname` | `source.ip`/`source.address` | `Resource`/`source.*`~ | — |
| `src_endpoint.domain` | `src_nt_domain`~ | `principal.administrative_domain`~ | `SrcDomain`~ | `source.domain`~ | — | — |
| `dst_endpoint.hostname` / `.ip` | `dest` | `target.hostname`/`.ip` | `Target`/`TargetHostname`/`TargetIpAddr` | `destination.ip`/`server.address` | `destination.*`~ | — |
| `dst_endpoint.domain` | `dest_nt_domain`~ | — | — | — | — | — |
| `service.name` | `app`~ | `target.application`/`target.resource.name`~ | `TargetAppName`/`TargetUrl`~ | `service.name`~ | `server.address`~ | — |
| `auth_protocol_id` (+ `auth_protocol`) | `authentication_method`~ | `network.application_protocol` (enum)~ | `LogonProtocol` (enum) | `network.protocol`~ | — | — |
| `is_mfa` | — | — | `LogonMethod` (`MFA`)~ | — | — | — |
| `logon_type_id` (+ `logon_type`) | — | — | `EventSubType` (enum) | — | — | — |
| `session.uid` | — | — | — | — | `session.id`~ | — |
| `metadata.event_code` | `signature_id` | `metadata.product_log_id` | `EventOriginalType`/`EventUid` | `event.code` | `EventName`~ | — |
| `metadata.uid` | — | `metadata.id` | `EventOriginalUid` | `event.id` | — | — |
| `duration` | `duration` (×1000) | — | — | — | — | — |
| `message` | `signature`~ | `security_result.rule_name`~ | — | — | `Body`~ | — |

**Unmapped — notable source fields with no OCSF home (→ `unmapped`/`enrichments`)**

- **CIM**: `authentication_service` (Okta/AzureAD IdP product, category error to force into `auth_protocol`); `*_bunit`/`*_category`/`*_priority` (Asset & Identity enrichment); `account_switch_type_id` has no CIM source (the inverse gap).
- **UDM**: `security_result.action = CHALLENGE` (MFA step-up — neither success nor failure); extra `email_addresses` beyond the primary; ticket/preauth semantics (Kerberos collapse, no event_type).
- **ASIM**: `TargetUserIdType`/`TargetUsernameType` provenance (`AADID`/`OktaId`/`AWSId` collapse into `user.uid`); `EventType = Elevate` (no 3002 activity); `EventResult = Partial`; `*RiskLevel`/`Threat*`/`AdditionalFields` bag.
- **ECS**: array `event.category` co-selection overflow (`["authentication","session"]`); Kerberos ticket activities (recover from `event.code`); uncontrolled `event.severity` banding judgment.
- **OTel**: `TraceId`/`SpanId`/`TraceFlags` (trace context, no OCSF home); `session.previous_id`; no auth operation/result/protocol/MFA at all (the richest part of 3002 has zero OTel source); `enduser.*` deprecation churn.
- **Zeek**: nothing maps to 3002 — Zeek is a network sensor with no authentication-event vantage. Its closest signals route *elsewhere*: `ssh.log` → SSH Activity (4007, a network-connection class, not an auth event), and `kerberos.log`/`ntlm.log` (roadmap, not base-log) would be the real auth source. So the whole 3002 column is `—`: not lossy, just out of vantage.

---

## Network Activity (4001)

OCSF Network Activity, `class_uid` 4001, category Network Activity. Required: `activity_id`, `category_uid`, `class_uid`, `metadata`, `severity_id`, `time`; plus the constraint **at least one of `src_endpoint` / `dst_endpoint`**. Fixture-validated against Cisco ASA→OCSF JSON in all five crosswalks.

| OCSF attribute (dot-path) | Splunk CIM | Google UDM | Microsoft ASIM | Elastic ECS | OpenTelemetry | Zeek |
|---|---|---|---|---|---|---|
| `activity_id` **req** | `action` (enum) | `security_result.action` (enum) | `DvcAction`+`EventSubType` (enum) | `event.type` (enum) | — (default Traffic) | `conn_state` (enum)~ |
| `severity_id` **req** | — | `security_result.severity` (enum) | `EventSeverity` (enum) | `event.severity`~ | `SeverityNumber` (enum) | — (invent) |
| `time` **req** | `_time` | `metadata.event_timestamp` | `EventStartTime` | `@timestamp` | `Timestamp` (ns→ms) | `ts` (s→ms) |
| `metadata` **req** | `vendor_product` (split) | `metadata.product_name`/`vendor_name` | `EventProduct`/`EventVendor` | `observer.*` | `Resource`/`EventName` | Zeek/Corelight (construct) |
| `src_endpoint` or `dst_endpoint` **req (constraint)** | `src`/`dest` | `principal.*`/`target.*` | `Src*`/`Dst*` | `source.*`/`destination.*` | `source.*`/`destination.*` | `id.orig_*`/`id.resp_*` |
| `category_uid` / `class_uid` **req** | const | const | const | const | const | const |
| `src_endpoint.ip` | `src`/`src_ip` | `principal.ip` | `SrcIpAddr` | `source.ip`/`source.address` | `source.address` / `client.address`~ | `id.orig_h` |
| `src_endpoint.port` | `src_port` | `principal.port` | `SrcPortNumber` | `source.port` | `source.port`~ | `id.orig_p` |
| `src_endpoint.hostname` | `src`~ | `principal.hostname` | `SrcHostname` | `source.domain`~ | `source.address`~ | — |
| `src_endpoint.mac` | `src_mac` | `principal.mac` | `SrcMacAddr` | `source.mac` | — | `orig_l2_addr` (policy)~ |
| `dst_endpoint.ip` | `dest`/`dest_ip` | `target.ip` | `DstIpAddr` | `destination.ip`/`destination.address` | `destination.address` / `server.address`~ | `id.resp_h` |
| `dst_endpoint.port` | `dest_port` | `target.port` | `DstPortNumber` | `destination.port` | `destination.port`~ | `id.resp_p` |
| `dst_endpoint.hostname` | `dest`~ | `target.hostname` | `DstHostname` | `destination.domain`~ | `destination.address`~ | — |
| `dst_endpoint.mac` | `dest_mac` | `target.mac` | `DstMacAddr` | `destination.mac` | — | `resp_l2_addr` (policy)~ |
| `connection_info.protocol_name` (+ `protocol_num`) | `transport`/`protocol` | `network.ip_protocol` (enum) | `NetworkProtocol` (enum) | `network.transport`/`network.iana_number` | `network.transport`~ | `proto` (+derive num) |
| `connection_info.protocol_ver_id` | — | — | `NetworkProtocolVersion` (enum)~ | `network.type` (enum)~ | `network.type`~ | — |
| `connection_info.direction_id` (+ `direction`) | `direction` (enum) | `network.direction` (enum) | `NetworkDirection` (enum)~ | `network.direction` (enum)~ | `network.io.direction`~ | `local_orig`/`local_resp` (derive)~ |
| `connection_info.uid` | `session_id`/`flow_id` | `network.session_id` | `NetworkSessionId` | `network.community_id`~ | — | `uid` (join key) |
| `connection_info.community_uid` | — | — | — | `network.community_id`~ | — | `community_id` (1:1) |
| `connection_info.tcp_flags` | `tcp_flag` (bitmask)~ | — | `TcpFlagsSyn`/`Ack`/... (bitmask)~ | — | — | — |
| `traffic.bytes_in` | `bytes_in` | `network.received_bytes` | `DstBytes` | `destination.bytes` | — (in metrics) | `resp_bytes` |
| `traffic.bytes_out` | `bytes_out` | `network.sent_bytes` | `SrcBytes` | `source.bytes` | — (in metrics) | `orig_bytes` |
| `traffic.bytes` | `bytes` | — | `NetworkBytes` | `network.bytes` | — (in metrics) | `orig+resp_bytes` |
| `traffic.packets_in` / `packets_out` / `packets` | `packets_in`/`packets_out`/`packets` | — | `DstPackets`/`SrcPackets`/`NetworkPackets` | `destination.packets`/`source.packets`/`network.packets` | — (in metrics) | `resp_pkts`/`orig_pkts`/sum |
| `status_id` | `action`~ | `security_result.action`~ | `EventResult`~ | `event.outcome`~ | — | — |
| `duration` | `duration` (×1000) | `network.session_duration` (×1000) | `NetworkDuration` | — | — | `duration` (×1000) |
| `app_name` | `app`~ | `network.application_protocol`/`target.application`~ | `NetworkApplicationProtocol`~ | `network.protocol`~ | `network.protocol.name`~ | `service` (L7) |
| `firewall_rule.uid` / `.name` | `rule`~ | — | `NetworkRuleName`/`NetworkRuleNumber` | `rule.name`/`rule.id`~ | — | — |
| `actor.user.name` / `user.name` | `user`~ | — | `SrcUsername`/`DstUsername`~ | `source.user.name`/`destination.user.name`~ | — | — |
| `src_endpoint.intermediate_ips[]` | `src_translated_ip`~ | `intermediary.ip`/`.hostname`~ | `SrcNatIpAddr`~ | `source.nat.ip`/`.port`~ | — | — |
| `metadata.correlation_uid` | — | `network.parent_session_id`~ | — | — | — | `tunnel_parents` |
| `device` | `dvc`/`dvc_ip`~ | `observer.ip`/`.hostname` / `intermediary.*`~ | `Dvc`~ | `host.*`~ | `Resource` → `host.*` | — |

**Unmapped — notable source fields with no OCSF home (→ `unmapped`/`enrichments`)**

- **CIM**: `src_translated_ip`/`src_translated_port`/`dest_translated_ip`/`dest_translated_port` (NAT — no OCSF symmetric pre/post pair); `*_zone` (`src_zone`/`dest_zone`/`dvc_zone` — admin labels, not the fixed `boundary_id` enum).
- **UDM**: `network.parent_session_id` (no first-class parent-session link); `BROADCAST`/`MULTICAST` direction (no OCSF `direction_id` slot); NAT context (`intermediary` cleaner on input, still no OCSF pair).
- **ASIM**: `SrcNatIpAddr`/`DstNatIpAddr`/`*NatPortNumber` (NAT, no OCSF pair); `SrcZone`/`DstZone`/`DvcZone`; `Local`/`External` directions (no OCSF slot); `Encrypt`/`Decrypt`/`VPNroute` `DvcAction` (belongs in Tunnel Activity 4014).
- **ECS**: `source.nat.*`/`destination.nat.*` (NAT, no OCSF pair); `observer.ingress.zone`/`egress.zone`; over-rich `network.direction` (7 values → OCSF's 4, `external` collapses); multi-valued `event.category`/`event.type` overflow (`["network","session"]`); `network.community_id` when it can't claim `connection_info.uid`.
- **OTel**: `TraceId`/`SpanId` (trace context); `client.*`/`server.*` second coordinate system (vantage vs packet-direction); byte/packet counters (live in OTel **metrics**, not log/span attributes); no flow lifecycle (Open/Close/Reset have no OTel source); no verdict/zone/NAT (OTel isn't a firewall).
- **Zeek**: `history` (per-packet flag-history string `ShADadFf` — no OCSF native, lands in `connection_info.history`/`unmapped`); `conn_state` nuance beyond `activity_id` (the 13-state TCP vocabulary collapses to 7 lifecycle slots, so the orig-vs-resp-aborted distinction RSTO/RSTR survives only in `status_detail`); `local_orig`/`local_resp` (the local/remote pair derives direction but has no symmetric OCSF home); `orig_ip_bytes`/`resp_ip_bytes` (IP-layer counts vs OCSF's payload-only `traffic.bytes`); `missed_bytes` (capture-loss counter). The seam Zeek alone carries: the **cross-log `uid` re-stitch** — conn/dns/http/ssl rows share a `uid`→`connection_info.uid` but OCSF holds them as separate events with no native re-assembly, so reconstructing one flow is the consumer's query-time job.

---

## HTTP Activity (4002)

OCSF HTTP Activity, `class_uid` 4002, category Network Activity. Required: `activity_id`, `category_uid`, `class_uid`, `metadata`, `severity_id`, `time`. (`src_endpoint`/`dst_endpoint` are recommended, not required — no endpoint constraint.)

| OCSF attribute (dot-path) | Splunk CIM | Google UDM | Microsoft ASIM | Elastic ECS | OpenTelemetry | Zeek |
|---|---|---|---|---|---|---|
| `activity_id` **req** | `http_method` (enum) | `network.http.method` (enum) | `HttpRequestMethod` (enum) | `http.request.method` (enum) | `http.request.method` (enum) | `method` (enum) |
| `severity_id` **req** | — | `security_result.severity` (enum) | `EventSeverity` (enum) | `event.severity`~ | `SeverityNumber` (enum) | — (invent) |
| `time` **req** | `_time` | `metadata.event_timestamp` | `EventStartTime` | `@timestamp` | `Timestamp` (ns→ms) | `ts` (s→ms) |
| `metadata` **req** | `vendor_product` (split) | `metadata.product_name`/`vendor_name` | `EventProduct`/`EventVendor` | `observer.*` | `Resource`/`EventName` | Zeek/Corelight (construct) |
| `category_uid` / `class_uid` **req** | const | const | const | const | const | const |
| `http_request.http_method` | `http_method` | `network.http.method` | `HttpRequestMethod` | `http.request.method` | `http.request.method` (+ `method_original`) | `method` |
| `http_request.url.text` | `url` | `target.url` | `Url` | `url.full`/`url.original` | `url.full` | `host`+`uri` (construct)~ |
| `http_request.url.hostname` | `url_domain` | `target.url` (parse) | `HttpHost`~ | `url.domain` | `url.domain`~ | `host` |
| `http_request.url.path` | `uri_path` | `target.url` (parse) | `Url` (parse) | `url.path` | `url.path` | `uri` (split) |
| `http_request.url.query_string` | `uri_query` | `target.url` (parse) | `Url` (parse) | `url.query` | `url.query` | `uri` (split) |
| `http_request.url.scheme` | — | — | — | `url.scheme` | `url.scheme` | — |
| `http_request.url.port` | — | — | — | `url.port` | `url.port`~ | — |
| `http_request.version` | — | — | `HttpVersion` | `http.version` | `network.protocol.version`~ | `version` |
| `http_request.user_agent` | `http_user_agent` | `network.http.user_agent` | `HttpUserAgent`/`UserAgent` | `user_agent.original` | `user_agent.original` | `user_agent` |
| `http_request.referrer` | `http_referrer` | `network.http.referral_url` | `HttpReferrer` | `http.request.referrer` | `http.request.header.referer`~ | `referrer` |
| `http_request.x_forwarded_for[]` | — | — | `HttpRequestXff`~ | — | `http.request.header.x-forwarded-for`~ | `proxied`~ |
| `http_request.uid` | — | — | — | `http.request.id`~ | — | — |
| `http_request.length` | `url_length`~ | — | `HttpRequestBodyBytes`~ | `http.request.body.bytes`~ | `http.request.body.size`~ | `request_body_len` |
| `http_request.cookies` | — | — | `HttpCookie`~ | — | — | — |
| `http_response.code` | `status` (int) | `network.http.response_code` | `EventResultDetails`/`HttpStatusCode` | `http.response.status_code` | `http.response.status_code` | `status_code` |
| `http_response.content_type` | `http_content_type`~ | — | `HttpContentType`/`HttpContentFormat`~ | `http.response.mime_type`~ | — | — |
| `http_response.length` | — | — | `HttpResponseBodyBytes`~ | `http.response.body.bytes`~ | `http.response.body.size`~ | `response_body_len` |
| `status_id` | `status`/`action`~ | `network.http.response_code`/`security_result.action`~ | `EventResult`/`DvcAction`~ | `event.outcome`/`event.type`~ | `http.response.status_code`~ | `status_code` (bucket)~ |
| `traffic.bytes_in` | `bytes_in` | `network.received_bytes` | `SrcBytes`/`DstBytes` | `destination.bytes` | — | — |
| `traffic.bytes_out` | `bytes_out` | `network.sent_bytes` | `SrcBytes` | `source.bytes` | — | — |
| `src_endpoint.ip` / `.hostname` | `src` | `principal.ip`/`.hostname` | `SrcIpAddr`/`IpAddr` | `source.ip`/`client.ip` | `client.address`~ | `id.orig_h` |
| `dst_endpoint.ip` / `.port` | `dest`/`dest_port` | `target.ip`/`.hostname` | `DstIpAddr`/`DstPortNumber` | `destination.ip`/`.port`/`server.*` | `server.address`/`.port`~ | `id.resp_h`/`id.resp_p` |
| `actor.user.name` | `user`~ | `principal.user.userid`~ | `SrcUsername`~ | `source.user.name`~ | — | `username`~ |
| `app_name` | `app`~ | `network.application_protocol`~ | — | — | — | — |
| `duration` | `duration`/`response_time` | `network.session_duration` (×1000) | `HttpRequestTime`/`HttpResponseTime`~ | — | — | — |
| `file` (HTTP upload) | — | — | `FileName`/`FileMD5`/`FileSHA256`/`FileSize`~ | — | — | `orig_fuids`/`resp_fuids` (→files.log)~ |

**Unmapped — notable source fields with no OCSF home (→ `unmapped`/`enrichments`)**

- **CIM**: `category` (proxy URL category — gambling/news); `cached` (cache-hit flag); `site`; `http_user_agent_length`; `action` (proxy allow/block disposition — 4002 has no `disposition_id`).
- **UDM**: `network.http.parsed_user_agent` (structured UA — OCSF keeps only raw); `security_result.category` (URL/threat category); `security_result.action` (disposition, no home on 4002).
- **ASIM**: `UrlCategory`; `UrlOriginal` (pre-rewrite URL — no OCSF pre/post pair); `HttpIsProxied`; `EventType` proxy-vs-server-vs-API vantage (`HTTPsession`/`WebServerSession`/`ApiRequest`); `DvcAction` (disposition).
- **ECS**: multi-valued `event.category` (`["network","web"]` selection); `event.type: denied`/`allowed` (disposition, no home on 4002); uncontrolled `event.severity`.
- **OTel**: `http.route` (low-cardinality route template, not a real path); generic `http.request.header.<key>`/`response.header.<key>` map (only referer/XFF are named OCSF fields); `http.request.resend_count`; no proxy disposition (OTel HTTP is a client/server transaction, not a proxy decision).
- **Zeek**: no proxy disposition to map *and none to strand* — Zeek's http.log carries **no allow/block verdict** (it watched the request, it never enforced), so unlike CIM/ASIM there is nothing to drop to `unmapped` (a coverage gap, not a stranded field); `origin` header (no exact 4002 home); `tags` (per-request indicator set → `unmapped`/`enrichments`); `orig_fuids`/`resp_fuids` (the transferred file's hash/name live in files.log — full HTTP-with-payload context is a `uid`-style cross-log stitch, the same re-assembly seam as 4001).

---

## Process Activity (1007)

OCSF Process Activity, `class_uid` 1007, category System Activity. Required: `activity_id`, `actor`, `category_uid`, `class_uid`, `device`, `metadata`, `process`, `severity_id`, `time`, `type_uid`.

| OCSF attribute (dot-path) | Splunk CIM | Google UDM | Microsoft ASIM | Elastic ECS | OpenTelemetry | Zeek |
|---|---|---|---|---|---|---|
| `activity_id` **req** | `action` (enum)~ | `metadata.event_type` (enum) | `EventType` (enum) | `event.type` (enum) | — (descriptive, no verb) | — |
| `severity_id` **req** | — | `security_result.severity` (enum) | `EventSeverity` (enum) | `event.severity`~ | `SeverityNumber` (enum) | — |
| `time` **req** | `_time` | `metadata.event_timestamp` | `EventStartTime` | `@timestamp` | `Timestamp` (ns→ms) | — |
| `metadata` **req** | `vendor_product` (split) | `metadata.product_name`/`vendor_name` | `EventProduct`/`EventVendor` | `observer.*`/`agent.*` | `Resource`/`EventName` | — |
| `process` **req** | `process`/`process_name`/`process_id` | `target.process.*` | `TargetProcess*` | `process.*` | `process.*` | — |
| `actor` **req** | `parent_process`/`user`~ | `principal.process`/`principal.user` | `ActingProcess*`/`ActorUsername` | `process.parent.*`/`process.user.*` | `process.parent_pid`~ | — |
| `device` **req** | `dest` | `principal.hostname`/`.asset_id` | `Dvc`/`DvcHostname`/`DvcId` | `host.*` | `Resource` → `host.*` | — |
| `category_uid` / `class_uid` / `type_uid` **req** | const | const | const | const | const | — |
| `process.cmd_line` | `process` | `target.process.command_line` | `TargetProcessCommandLine`/`CommandLine` | `process.command_line` | `process.command_line` | — |
| `process.name` | `process_name` | `target.process.file.full_path`~ | `TargetProcessName`/`Process` | `process.name` | `process.command`~ | — |
| `process.pid` | `process_id` | `target.process.pid` | `TargetProcessId` (int) | `process.pid` | `process.pid` | — |
| `process.uid` | `process_guid`~ | `target.process.product_specific_process_id`~ | `TargetProcessGuid`~ | `process.entity_id`~ | — | — |
| `process.file.name` | `process_exec`~ | `target.process.file.full_path` | `TargetProcessName` | — | `process.executable.name` | — |
| `process.file.path` | `process_path` | `target.process.file.full_path` | `TargetProcessName` | `process.executable` | `process.executable.path` | — |
| `process.file.hashes[]` | `process_hash` (parse)~ | `target.process.file.md5`/`.sha256` | `TargetProcessMD5`/`SHA1`/`SHA256`/`SHA512` | `process.hash.md5`/`sha1`/`sha256` | — | — |
| `process.file.size` | — | — | `TargetProcessFileSize` | — | — | — |
| `process.working_directory` | `process_current_directory` | — | `TargetProcessCurrentDirectory` | `process.working_directory` | `process.working_directory` | — |
| `process.integrity_id` (+ `integrity`) | `process_integrity_level` (enum)~ | — | `TargetProcessIntegrityLevel` (enum)~ | — | — | — |
| `process.exit_code` | — | — | `TargetProcessStatusCode`~ | `process.exit_code`~ | `process.exit.code`~ | — |
| `process.user.name` | `user`~ | `target.user.userid`~ | `TargetUsername`~ | `user.effective.name`~ | `process.owner` / `process.user.name`~ | — |
| `actor.process.cmd_line` | `parent_process`~ | `principal.process.command_line` | `ActingProcessCommandLine` | `process.parent.command_line`~ | — | — |
| `actor.process.name` | `parent_process_name`~ | — | `ActingProcessName` | — | — | — |
| `actor.process.pid` | `parent_process_id`~ | — | `ActingProcessId` | `process.parent.pid` | `process.parent_pid`~ | — |
| `actor.process.file.path` | `parent_process_path`~ | `principal.process.file.full_path` | `ActingProcessName` | `process.parent.executable` | — | — |
| `actor.process.file.hashes[]` | — | `principal.process.file.md5`/`.sha256` | `ActingProcessMD5`/`SHA256` | — | — | — |
| `actor.process.parent_process.{name,pid,uid}` | — | `principal.process.parent_process.pid`~ | `ParentProcessName`/`Id`/`Guid`~ | — | — | — |
| `actor.user.name` | `user`~ | `principal.user.userid` | `ActorUsername`/`User` | `process.user.name`/`user.name` | `process.real_user.name`~ | — |
| `actor.user.uid` | `user_id`~ | `principal.user.windows_sid`~ | `ActorUserId` | `process.user.id`~ | `process.real_user.id`~ | — |
| `process.created_time` | — | — | — | `process.start`~ | `process.creation.time` (ISO→ms)~ | — |

**Unmapped — notable source fields with no OCSF home (→ `unmapped`/`enrichments`)**

- **CIM**: `action` disposition (allowed/blocked/deferred — operation≠verdict, no `disposition_id` on 1007); single `user` collapses launcher-vs-effective (setuid before/after lost); packed `process_hash` if not split.
- **UDM**: `security_result.action` verdict (no `disposition_id` on 1007); Set User ID(5) has no event_type; injection target/module detail beyond `principal→target` pair.
- **ASIM**: `DvcAction` verdict (no home on 1007); `TargetProcessTokenElevation` (UAC token); `ActorUserIdType`/`TargetUserIdType` provenance; only create/terminate `EventType` (no Open/Inject/Set-UID).
- **ECS**: uncontrolled `event.severity`; Inject(4)/Open(3)/Set-UID(5) only via `event.action` mining; multi-valued `event.category` (`["process","library"]`); EDR allow/block verdict (no home on 1007).
- **OTel**: no operation verb (descriptive state — `activity_id` defaulted); `process.real_user.*`/`saved_user.*` (EUID/RUID/SUID triple — OCSF has no saved-user slot); thin `actor` (bare `parent_pid`, not a populated process object); `process.command_args` array.
- **Zeek**: nothing maps to 1007 — a process is a host-side construct, and Zeek sees only the wire. There is no `process`, `actor`, `cmd_line`, `pid`, or process hash anywhere in the Zeek base logs, so the entire 1007 column is `—` by vantage, not by lossy mapping. Process telemetry comes from EDR/Sysmon, not a network sensor.

---

## File System Activity (1001)

OCSF File System Activity, `class_uid` 1001, category System Activity. Required: `activity_id`, `actor`, `category_uid`, `class_uid`, `device`, `file`, `metadata`, `time`, `type_uid`. (`severity_id` is recommended here, not required — a relief for every source, especially OTel whose severity is log-level only.)

| OCSF attribute (dot-path) | Splunk CIM | Google UDM | Microsoft ASIM | Elastic ECS | OpenTelemetry | Zeek |
|---|---|---|---|---|---|---|
| `activity_id` **req** | `action` (enum) | `metadata.event_type` (enum) | `EventType` (enum) | `event.type` (enum) | — (descriptive, no verb) | — (no host-side op) |
| `actor` **req** | `process_guid`/`user`~ | `principal.process`/`principal.user` | `ActingProcess*`/`ActorUsername` | `process.*`/`user.name` | — (pair with `process.*` else stub) | — (no actor on wire) |
| `time` **req** | `_time` | `metadata.event_timestamp` | `EventStartTime` | `@timestamp` | `Timestamp` (ns→ms) | `ts` (s→ms) |
| `metadata` **req** | `vendor_product` (split) | `metadata.product_name`/`vendor_name` | `EventProduct`/`EventVendor` | `observer.*`/`agent.*` | `Resource`/`EventName` | Zeek/Corelight (construct) |
| `file` **req** | `file_name`/`file_path` | `target.file.*` | `TargetFile*` | `file.*` | `file.*` | `fuid`/`filename`/hashes |
| `device` **req** | `dest` | `principal.hostname`/`.asset_id` | `Dvc`/`DvcHostname`/`DvcId` | `host.hostname`/`host.id` | `Resource` → `host.*` | — |
| `category_uid` / `class_uid` / `type_uid` **req** | const | const | const | const | const | const |
| `file.name` | `file_name` | `target.file.full_path` (basename) | `TargetFileName`/`FileName` | `file.name` | `file.name` | `filename` |
| `file.path` | `file_path` | `target.file.full_path` | `TargetFilePath`/`FilePath` | `file.path` | `file.path` | — |
| `file.parent_folder` | — | — | `TargetFileDirectory`~ | `file.directory` | `file.directory` | — |
| `file.ext` | — | — | `TargetFileExtension` | `file.extension` | `file.extension` | — |
| `file.mime_type` | — | `target.file.mime_type`~ | `TargetFileMimeType` | `file.mime_type` | — | `mime_type` |
| `file.type_id` (+ `type`) | — | — | `TargetFilePathType`~ | `file.type` (enum)~ | `file.symbolic_link.target_path`~ | `mime_type` (bucket)~ |
| `file.hashes[]` | `file_hash` (parse)~ | `target.file.md5`/`.sha256`/`.sha1` | `TargetFileMD5`/`SHA1`/`SHA256`/`SHA512`/`Hash` | `file.hash.md5`/`sha1`/`sha256` | — (no hash attribute) | `md5`/`sha1`/`sha256` (typed) |
| `file.size` | `file_size` (×1024)~ | `target.file.size` | `TargetFileSize` | `file.size` | `file.size` | `total_bytes` |
| `file.created_time` | `file_create_time` | — | `TargetFileCreationTime` | `file.created` | `file.created` (ISO→ms)~ | — |
| `file.modified_time` | `file_modify_time` | — | — | `file.mtime` | `file.modified` (ISO→ms)~ | — |
| `file.accessed_time` | `file_access_time` | — | — | `file.accessed` | `file.accessed` (ISO→ms)~ | — |
| `file.owner.name` | — | — | — | `file.owner` | `file.owner.name`~ | — |
| `file.owner.uid` / `.sid` | — | — | — | — | `file.owner.id`~ | — |
| `actor.process.uid` | `process_guid`~ | `principal.process.product_specific_process_id`~ | `ActingProcessGuid`~ | `process.entity_id` | — | — |
| `actor.process.cmd_line` | — | `principal.process.command_line` | `ActingProcessCommandLine`~ | — | — | — |
| `actor.process.file.path` | — | — | `ActingProcessName` | `process.executable` | — | — |
| `actor.process.name` | — | — | `ActingProcessName`/`Process` | `process.name` | — | — |
| `actor.user.name` | `user`~ | `principal.user.userid` | `ActorUsername`/`User` | `user.name`/`process.user.name` | — | — |
| `actor.user.uid` | — | — | `ActorUserId` | `user.id`~ | — | — |
| `status_id` | — | `security_result.action`~ | — | `event.outcome`~ | — | — |
| `severity_id` (rec) | — | `security_result.severity` (enum) | `EventSeverity` (enum) | `event.severity`~ | `SeverityNumber` (enum) | — (invent) |

**Unmapped — notable source fields with no OCSF home (→ `unmapped`/`enrichments`)**

- **CIM**: KB→bytes `file_size` trap if `×1024` missed; packed `file_hash`; OCSF's richer activity set (Mount/Unmount/Encrypt/Decrypt — loss runs the *other* way, CIM has only 5 verbs).
- **UDM**: `FILE_SYNC` verb (no exact OCSF id); `security_result.action` verdict (no `disposition_id` on 1001).
- **ASIM**: `SrcFilePath`/`SrcFileName` (pre-op file on rename/copy/move — OCSF models one `file`); `TargetFilePathType` (Windows Share/Unix/URL/S3 provenance); `EventSubType` (Upload/Checkout/Recycled SharePoint sub-ops); `*IdType` provenance.
- **ECS**: `file.target_path` (symlink/move destination — one `file` only); `file.ctime` (metadata-change time, no OCSF slot); Rename(5)/Set-Security(7) only via `event.action`; multi-valued `event.category` (`["file","configuration"]`).
- **Zeek**: the whole class is a *routing mismatch* — files.log records files Zeek **carved off the wire** (reassembled from HTTP/SMTP/FTP/SMB), not a host-side filesystem op, so its real home is **Network File Activity (4010)**, not 1001 (this matrix tabulates 1001 only; the 4010 mapping lives in the [Zeek crosswalk](zeek-ocsf-crosswalk.md) §6). Routing files.log to 1001 implies a host-side Create/Read/Delete Zeek never saw, so `activity_id` and the host-side `actor`/`device` are all `—`. Even on 4010 the required `actor` is a hollow stub (no process or user behind a passively-carved file — worse than CIM's actor gap). Also unmapped: `seen_bytes` vs `total_bytes` (captured-vs-declared, OCSF `file.size` is one number); `source` (the carrying protocol — HTTP/SMTP/FTP_DATA); `conn_uids`/`fuid` (the cross-log handle http/smtp point at).
- **OTel**: **no hash attribute** (the IOC-matching field — biggest gap on this path); no operation verb (descriptive); `file.changed` (ctime) and `file.mode` (octal perms — finer than OCSF); thin `actor` unless a `process.*` block co-rides the record.

---

## Account Change (3001)

OCSF Account Change, `class_uid` 3001, category Identity & Access Management — the most common destination of each source's 1:many change router (Change/USER_*/User Management/`iam`). Required: `activity_id`, `category_uid`, `class_uid`, `metadata`, `time`, `type_uid`, `user`. (`actor` is recommended, not required; `severity_id` is **not** required on 3001 — a notable contrast with 3002/4001/4002/1007.)

| OCSF attribute (dot-path) | Splunk CIM | Google UDM | Microsoft ASIM | Elastic ECS | OpenTelemetry | Zeek |
|---|---|---|---|---|---|---|
| `activity_id` **req** | `action` (enum)~ | `metadata.event_type` (enum) | `EventType` (enum) | `event.type`+`event.action` (enum)~ | — | — |
| `time` **req** | `_time` | `metadata.event_timestamp` | `EventStartTime` | `@timestamp` | — | — |
| `metadata` **req** | `vendor_product` (split) | `metadata.product_name`/`vendor_name` | `EventProduct`/`EventVendor` | `observer.*`/`event.provider` | — | — |
| `user.name` **req** (affected account) | `src_user`/`object`~ | `target.user.userid` | `TargetUsername` | `user.target.name` | — | — |
| `category_uid` / `class_uid` / `type_uid` **req** | const | const | const | const | — | — |
| `user.uid` | `object_id`~ | `target.user.windows_sid`~ | `TargetUserId` | `user.target.id` | — | — |
| `user.sid` | — | `target.user.windows_sid`~ | `TargetUserId` (`SID`) | — | — | — |
| `user.full_name` | — | — | `TargetUsername`~ | — | — | — |
| `user.email_addr` | — | — | `TargetUsername` (`UPN`)~ | `user.target.email`~ | — | — |
| `user.type_id` (+ `type`) | — | — | `TargetUserType` (enum)~ | — | — | — |
| `actor.user.name` (rec, modifier) | `user`/`user_name`~ | `principal.user.userid` | `ActorUsername`/`User` | `user.name` (initiator) | — | — |
| `actor.user.uid` | — | — | `ActorUserId` | `user.id`~ | — | — |
| `actor.process.cmd_line` | `command`~ | `principal.process.command_line`~ | `ActingProcessName`~ | — | — | — |
| `group.name` / `.uid` | `object`/`object_id` (if group)~ | — | `GroupName`/`GroupId`~ | `group.name`/`group.id`~ | — | — |
| `status_id` (+ `status_detail`) | `status`/`result`/`result_id`~ | `security_result.action`~ | `EventResult`/`EventResultDetails`~ | `event.outcome`/`event.reason`~ | — | — |
| `src_endpoint.*` | `src`~ | `principal.hostname`/`.ip`~ | `Src`/`SrcIpAddr`~ | `source.ip`~ | — | — |
| `dst_endpoint.*` / `device.*` | `dest`~ | `target.hostname`/`.resource.name`~ | — | — | — | — |
| `severity_id` (NOT required) | — | `security_result.severity` (enum) | `EventSeverity` (enum) | `event.severity`~ | — | — |

**Unmapped — notable source fields with no OCSF home (→ `unmapped`/`enrichments`)**

- **CIM**: `object_attrs` (free-form changed-attributes blob — the before/after content, the most forensic part, is opaque); polymorphic `object`/`object_id`/`object_path` scattering across categories; the modifier/modified inversion (`src_user`→`actor.user`, `object`→`user` must be *crossed* — a frequent silent bug); `object_category` (routing key, not a value).
- **UDM**: `target.resource.attribute_labels[]` / change-detail label bag (opaque change content); coarse `USER_*` activity enum (no distinct enable/disable/lock event_types).
- **ASIM**: `EventSubType`/`UpdatedPropertyName` + `PreviousPropertyValue`/`NewPropertyValue` and `OldValue`/`NewValue` (explicit before/after — *richest of all five sources*, but OCSF has no typed before/after home); `*IdType`/`*UsernameType` provenance; two-schema routing (User Management vs Audit Event).
- **ECS**: `user.changes.*` (the new values — after-only, before is implicit `user.target.*`); coarse `event.type` (3 verbs) needing `event.action` mining for the full 3001 enum; spread across `iam`/`configuration`/`registry`/`host`/`package` categories.
- **OTel**: everything — **no change/audit concept** (no before/after, no account-lifecycle verbs); OTel maps nothing to 3001 (an *absence*, not a lossy map).
- **Zeek**: everything — account creation/modification/deletion is an IAM event on a directory or host, not on the wire. A network sensor never sees a `useradd`, a group change, or a password reset, so Zeek maps nothing to 3001 (an *absence* by vantage, like OTel — not a lossy map).

---

## Detection Finding (2004)

OCSF Detection Finding, `class_uid` 2004, category Findings — the home for malware/IDS/threat detections. Required: `activity_id`, `category_uid`, `class_uid`, `finding_info`, `metadata`, `severity_id`, `time`, `type_uid`. This is the **one class with a `disposition_id` attribute**, so the verdict that has no home on 4001/4002/1007/1001 finally lands here. Affected hosts go into `evidences[]`/`resources[]`/`observables[]`, not top-level `src_endpoint`/`dst_endpoint`.

| OCSF attribute (dot-path) | Splunk CIM | Google UDM | Microsoft ASIM | Elastic ECS | OpenTelemetry | Zeek |
|---|---|---|---|---|---|---|
| `activity_id` **req** (finding lifecycle) | `signature`→Create(1)~ | `security_result`→Create(1)~ | inspection→Create(1)~ | `event.kind`→Create(1)~ | — | point-in-time→Create(1)~ |
| `severity_id` **req** | `severity` (enum) | `security_result.severity` (enum) | `ThreatRiskLevel` (band) / `EventSeverity` | `event.risk_score_norm`/`event.severity` (band)~ | `SeverityNumber` (enum)~ | Notice severity (enum) |
| `finding_info` **req** | `signature`/`signature_id` | `security_result.threat_name`/`rule_id` | `ThreatName`/`ThreatId` | `rule.name`/`rule.id` | — | `note`/`msg` |
| `time` **req** | `_time` | `metadata.event_timestamp` | `EventStartTime` | `@timestamp` | — | `ts` (s→ms) |
| `metadata` **req** | `vendor_product` (split) | `metadata.product_name`/`vendor_name` | `EventProduct`/`EventVendor` | `observer.*` | — | Zeek/Corelight (construct) |
| `category_uid` / `class_uid` / `type_uid` **req** | const | const | const | const | — | const |
| `finding_info.title` | `signature` | `security_result.threat_name`/`rule_name`~ | `ThreatName`~ | `rule.name`~ | — | `note` / `name` (weird) |
| `finding_info.uid` | `signature_id`~ | `security_result.rule_id`~ | `ThreatId`~ | `rule.id`/`rule.uuid`~ | — | `note`~ |
| `finding_info.desc` | — | `security_result.summary`/`.description`~ | — | `rule.description`~ | — | `msg` |
| `disposition_id` | `action` (enum)~ | `security_result.action` (enum) | `DvcAction` (enum)~ | `event.type: denied`/`allowed`~ | — | `actions` (enum)~ |
| `malware[].name` | `signature`~ | `security_result.threat_name`~ | `ThreatName`~ | `threat.software.name`~ | — | — |
| `malware[].classification_ids[]` | `category` (enum)~ | `security_result.category` (enum)~ | `ThreatCategory`~ | `event.category: malware`~ | — | — |
| `confidence_id` / `confidence_score` | — | — | `ThreatConfidence`~ | `threat.indicator.confidence`~ | — | — |
| `risk_score` | — | — | `ThreatRiskLevel`~ | `event.risk_score`~ | — | — |
| `attack.tactic.uid` / `.name` | — | — | — | `threat.tactic.id`/`.name`~ | — | — |
| `attack.technique.uid` / `.name` | — | — | — | `threat.technique.id`/`.name`~ | — | — |
| `attack.sub_technique.uid` | — | — | — | `threat.technique.subtechnique.id`~ | — | — |
| `evidences[].src_endpoint` | `src`~ | `principal.*`~ | `SrcIpAddr` (IDS)~ | `source.ip`~ | — | `src`/`id.orig_h` |
| `evidences[].dst_endpoint` | `dest`~ | `target.ip`/`.hostname`~ | `DstIpAddr` (IDS)~ | `destination.ip`~ | — | `dst`/`id.resp_h` |
| `evidences[].file.name` / `.path` | `file_name`/`file_path`~ | `target.file.full_path`~ | `TargetFilePath`/`ThreatFilePath`~ | `file.path`~ | — | — |
| `evidences[].file.hashes[]` | `file_hash`~ | `target.file.md5`/`.sha256`~ | `TargetFileMD5`~ | `file.hash.*`~ | — | — |
| `evidences[].user.name` | `user`~ | `principal.user.userid`~ | `ActorUsername`/`TargetUsername`~ | `user.name`~ | — | — |
| `observables[]` | `file_hash`~ | `target.file.md5`/`.sha256`~ | `ThreatIpAddr`+`ThreatField`~ | `threat.indicator.*` (STIX)~ | — | `src`/`dst`/`id.*`~ |
| `first_seen_time` / `last_seen_time` | — | — | `ThreatFirstReportedTime`/`LastReportedTime`~ | `threat.indicator.first_seen`/`last_seen`~ | — | — |
| `status_id` / `is_alert` | — | — | `ThreatIsActive`~ | — | — | `notice` (weird→is_alert)~ |

**Unmapped — notable source fields with no OCSF home (→ `unmapped`/`enrichments`)**

- **CIM**: `ids_type` (network/host/application/wireless — no OCSF enum); vendor-defined `category` long tail → Other; finding-lifecycle `activity_id` is empty (CIM detections are point-in-time → all collapse to Create(1)); endpoints must be demoted from flat `src`/`dest` into `evidences[]`.
- **UDM**: *repeated* `security_result` (multiple verdicts per event vs OCSF's singular finding — fan-out or collapse); `ANALYST_UPDATE_*` lifecycle is a *separate* event (the two-event correlation OCSF doesn't expect); closed `category` enum tail → Other.
- **ASIM**: **no finding schema at all** — the finding is *promoted* out of an activity event's inspection fields + Network `IDS` type, and `SecurityAlert` (the real alert table) is outside ASIM; `ThreatRiskLevel` (0–100) is finer than the 4-bucket `EventSeverity`.
- **ECS**: `threat.group.id`/`.name` (`G0037`/FIN6 — ATT&CK attribution, no OCSF slot); `threat.software.id` (`S0552`); sub-technique detail beyond what OCSF's `attack` object holds — ECS *out-models* OCSF on ATT&CK; vuln-scans route to Vulnerability Finding 2002 (`vulnerability.id`/`vulnerability.score.base`) instead.
- **Zeek**: `weird.log:name` granularity (the protocol-anomaly type — `bad_TCP_checksum` etc. — most weirds are benign oddities, so a sane pipeline filters on the `notice` flag before flooding 2004); `sub` (notice sub-message detail beyond `msg`); `remote_location.country_code`/`.city` (geo enrichment → `evidences[].*.location`, no top-level home); no malware/ATT&CK/confidence/risk semantics at all — a Zeek notice is a *detector firing*, not a threat-intel-graded finding, so the `malware[]`/`attack.*`/`confidence_id`/`risk_score` half of 2004 is empty. The cert/x509 crypto fields a TLS-anomaly notice references (`SSL::Invalid_Server_Cert` and the like) live in **x509.log** (`key_alg`/`sig_alg`/`key_length`), which has no certificate *event* class and lands in `unmapped` — a structural gap Zeek shares with CIM. And the cross-log `uid` re-stitch is a *noted seam* here too: a notice references a flagged connection by `uid`, but the full flow context (conn/http/ssl rows) stays separate, so reconstructing what the finding fired on is the consumer's query-time job.
- **OTel**: everything — **no detection/finding concept** (no verdict, no threat/malware/confidence/risk semantics); OTel maps nothing to 2004 (an *absence*, not a lossy map).

---

## What the empty cells teach

The `—` clusters are the real finding of this matrix, and they cluster in two distinct ways.

**Source-side blindness — a `—` in one column but not others.** These show where a single source is structurally unable to reach a part of OCSF that its peers reach. The clearest illustration in the matrix is **Zeek's three all-`—` columns — Authentication (3002), Process Activity (1007), and Account Change (3001).** Those columns are not lossy mappings; they are *empty by vantage*. Zeek is a network sensor, and authentication, process execution, and IAM account changes are not things that happen on the wire — they happen on a host or in a directory. A passive packet observer cannot see a logon, a `useradd`, or a process spawn, so the whole column reads `—` not because OCSF can't hold the data but because the source never witnessed the event. That is a *cleaner, more total* form of source-side blindness than the partial gaps the other columns show, and it is the honest answer to "what is a network sensor blind to." The partial gaps are familiar: CIM's `severity_id` column is empty on 3002/4001/4002/1007 — CIM's activity data models carry no severity, so a faithful mapper invents it, and two mappers will invent differently (the ASA fixtures' "deny=Critical" is one convention, not a standard); Zeek hits the same severity gap on its base logs (conn/http), invented for the same reason — it observes rather than judges. OTel's columns on 3001 (Account Change) and 2004 (Detection Finding) are almost entirely `—` — not because the mapping is lossy but because OTel is an observability schema with *no* change-audit or detection concept; the fields were never captured. OTel's `process.file.hashes[]` and `file.hashes[]` cells are empty because OTel `file.*` carries no hash attribute, so the single most security-relevant file field — the hash an IOC match depends on — is unreachable from that source. Read down any column and the `—` runs trace its structural edges: Zeek is blind to everything off the wire (auth, process, IAM) but dense on the network classes; CIM is blind to severity and to the operation/verdict split; OTel is blind to findings, change, and deep auth; ASIM is blind to a normalized finding schema (it promotes from inspection fields); UDM and ECS are blind to the least.

**OCSF-side bottleneck — a `—` across ALL six columns.** These are the more important finding, because they are not a source's fault: they are fields OCSF asks for (or fields the sources carry richly) that OCSF *itself* cannot hold. This is the category to keep distinct from Zeek's all-`—` columns above: Zeek's 3002/1007/3001 emptiness is *one source* being blind, while these rows are *every source at once* hitting an OCSF wall. `disposition_id` is `—` for every verdict-bearing source on 4001/4002/1007/1001 — every firewall/proxy/EDR source carries an allow/deny verdict, and OCSF's activity classes have no attribute to receive it, so it scatters to `status_id`/`unmapped` and only finds a home on the findings class (2004). (Zeek is the exception that proves the rule here: it has *no* verdict on its base logs to strand, because it observes rather than enforces — so its 4001/4002 disposition `—` is source-side, not the OCSF wall the other five hit.) On 3001 (Account Change), the before/after of the change is `—` across all six columns even though ASIM gives it explicitly (`OldValue`/`NewValue`), ECS gives the after (`user.changes.*`), and UDM gives a label bag — OCSF has no typed before/after home, so the most forensically valuable part of an audit event survives only as `unmapped` text. Identifier provenance is the same story: ASIM's `*IdType` discriminators (which directory issued a `uid` — AADID vs OktaId vs AWSId) have no OCSF tag, so they collapse into `user.uid` for every source that carries them. And ATT&CK attribution (group `G0037`, software `S0552`, sub-technique depth) is richer in ECS's `threat.*` than OCSF's `attack` object can hold. Two OCSF-side gaps Zeek surfaces sharply and the other five do not: **no TLS event class** (ssl.log rides a `tls{}` object on a 4001 event) and **no certificate event class** (x509.log → a `digital_certificate` object plus `unmapped`, with the crypto-algorithm fields homeless) — the certificate gap independently flagged by the CIM crosswalk too, which makes it a strong upstream-OCSF signal.

So the matrix reads two ways. Down a column, it grades a source: how much of OCSF can this schema reach, and where is it structurally blind. Zeek is the sharpest demonstration of the column reading — dense on the network classes, totally `—` on the three classes (3002/1007/3001) a network sensor cannot observe, the cleanest source-side blindness in the set. Across a row, it grades OCSF: where every source carries something OCSF can't receive, the schema — not the source — is the bottleneck. The all-column-empty rows are the upstream-OCSF gaps worth flagging: `disposition_id` on activity classes, typed before/after on change classes, identifier-provenance tags on the user/device objects, ATT&CK-attribution depth on findings, and the missing TLS-event and certificate-event classes Zeek's ssl.log/x509.log expose. Those are where the destination, not any source, is the limiting factor.

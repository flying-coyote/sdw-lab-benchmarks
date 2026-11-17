"""S2 source typer for the ontology-vs-schema gate (HARNESS-ADDENDUM.md section 5).

Interface (section 5): ``source_kind(schema: str, field: str) -> str | None`` returns the
name of an OCSF 1.8.0 object (a file stem in ``schema-ocsf-1.8.0-api-2026-11-16/objects/``)
that the source field denotes, or ``None`` to abstain.

Written blind by a fresh author: typed only from each source schema's own public field
documentation and the OCSF 1.8.0 object list/attribute lists. No crosswalk, no mapping
page, no harness code other than the request files was consulted. See S2-TYPER-NOTES.md.

Typing rule, applied identically to all six schemas
---------------------------------------------------
R1  A field is typed to the OCSF object whose instance the field's value is a property of
    (the owning entity), choosing the most specific object whose attribute list in OCSF
    1.8.0 holds that property. Examples: an IP/port/MAC/hostname of a connection side ->
    network_endpoint; a PID or command line -> process; a username or user id -> user.
R2  Where the property has no home on the owning object but does on a nested one, the
    nested object wins. OCSF ``process`` has no hash or size attribute, so the hash/size of
    a process image file -> file. A field whose value *is* a reference to another entity
    (file owner username, process effective user) -> that entity (user).
R3  Participant hosts on either side of an activity (source/destination/target/client/
    server/principal) -> network_endpoint. The reporting, observing or executing host
    (ASIM Dvc*, CIM dvc*, ECS host.*/observer.*, OTel host.*, UDM observer.*) -> device.
    A field documented as meaning a participant in one data model and the executing host
    in another (CIM ``src``/``dest``) -> endpoint, the common OCSF parent of both.
R4  Byte/packet counters of a flow -> network_traffic. Protocol, transport, direction,
    flow/session id, community id, TCP flags, connection state -> network_connection_info.
R5  HTTP request-side headers and sizes -> http_request (cookie header -> http_cookie);
    response-side status/content-type/sizes/latency -> http_response. URL and URL parts
    -> url.
R6  Event-level scalars that describe the record or the activity rather than an entity
    (timestamps, severity, action, outcome/result, event type/id, message, duration,
    risk/confidence scores of a detection) -> None. They are class attributes or metadata,
    not entities. Exception: a score or date documented as a property of a threat
    *indicator* (ECS threat.indicator.confidence / first_seen) belongs to the indicator
    entity (OCSF osint, which carries confidence and created_time), whereas ASIM
    ThreatConfidence / ThreatFirstReportedTime are documented as properties of the threat
    identified by the detection, so they stay None.
R7  Abstain (None) when the docs give the token no single meaning: bare tokens with no
    fieldset prefix (``.port``, ``sha1``, ``last_seen``), wildcards over a mixed noun
    (UDM ``principal.*``, ASIM ``Src*``), or a field documented with different entity
    meanings across the schema's own logs/data models (Zeek ``method``, ``status_code``
    occur in both http.log and sip.log; CIM ``app`` is a protocol in Network_Traffic but
    an application in Web/Authentication).
R8  Returned values are the OCSF object *name* as it appears in the objects/ listing,
    unnormalised; any ``extends`` normalisation (device->endpoint, network_endpoint->
    endpoint, process->process_entity) is left to the harness.

Every URL cited below was fetched on 2026-11-17 and the rows under it checked against
the returned definitions (WebFetch, which returns model-summarised page text).
"""

from __future__ import annotations

# Every value any table below may return. The self-test checks each against the
# OCSF 1.8.0 objects/ directory listing.
OCSF_KINDS = frozenset({
    "agent", "application", "device", "endpoint", "file", "group", "http_cookie",
    "http_request", "http_response", "malware", "network_connection_info",
    "network_endpoint", "network_traffic", "osint", "process", "product", "rule",
    "service", "session", "sub_technique", "tactic", "technique", "url", "user",
})

_N = None  # explicit abstention marker, kept in tables so every listed field is accounted for

# ---------------------------------------------------------------------------
# Microsoft ASIM
# ---------------------------------------------------------------------------
_ASIM: dict[str, str | None] = {
    # Common fields: https://learn.microsoft.com/en-us/azure/sentinel/normalization-common-fields
    # Event* fields describe the record (R6); EventProduct/EventVendor name the product.
    "EventOriginalType": _N, "EventOriginalUid": _N, "EventResult": _N,
    "EventResultDetails": _N, "EventSeverity": _N, "EventStartTime": _N,
    "EventSubType": _N, "EventType": _N, "EventUid": _N,
    "EventProduct": "product", "EventVendor": "product",
    # Device fields = reporting / executing device (R3).
    "Dvc": "device", "DvcHostname": "device", "DvcId": "device",
    "DvcAction": _N,  # action taken by the reporting system (R6)

    # Network Session: https://learn.microsoft.com/en-us/azure/sentinel/network-normalization-schema
    "Src": "network_endpoint", "IpAddr": "network_endpoint",
    "SrcIpAddr": "network_endpoint", "SrcHostname": "network_endpoint",
    "SrcDomain": "network_endpoint", "SrcMacAddr": "network_endpoint",
    "SrcPortNumber": "network_endpoint", "SrcNatIpAddr": "network_endpoint",
    "DstIpAddr": "network_endpoint", "DstHostname": "network_endpoint",
    "DstMacAddr": "network_endpoint", "DstPortNumber": "network_endpoint",
    "SrcUsername": "user", "DstUsername": "user",
    "SrcBytes": "network_traffic", "DstBytes": "network_traffic",
    "SrcPackets": "network_traffic", "DstPackets": "network_traffic",
    "NetworkBytes": "network_traffic", "NetworkPackets": "network_traffic",
    "NetworkDirection": "network_connection_info", "NetworkProtocol": "network_connection_info",
    "NetworkProtocolVersion": "network_connection_info",
    "NetworkApplicationProtocol": "network_connection_info",
    "NetworkSessionId": "network_connection_info", "TcpFlagsSyn": "network_connection_info",
    "NetworkDuration": _N,  # session duration, event-level (R6)
    "NetworkRuleName": "rule", "NetworkRuleNumber": "rule",
    # Inspection fields (same text in network/process/file/auth pages): "threat or malware".
    "ThreatId": "malware", "ThreatName": "malware", "ThreatCategory": "malware",
    "ThreatConfidence": _N, "ThreatRiskLevel": _N, "ThreatIsActive": _N,
    "ThreatFirstReportedTime": _N, "ThreatField": _N,
    "ThreatIpAddr": _N,  # IP of some field named by ThreatField; side unknown (R7)
    # File-event inspection: "A file path for which a threat was identified".
    "ThreatFilePath": "file",

    # Web Session: https://learn.microsoft.com/en-us/azure/sentinel/web-normalization-schema
    "Url": "url",
    "HttpVersion": "http_request", "HttpRequestMethod": "http_request",
    "HttpReferrer": "http_request", "HttpUserAgent": "http_request", "UserAgent": "http_request",
    "HttpRequestXff": "http_request", "HttpHost": "http_request",
    "HttpRequestBodyBytes": "http_request",
    "HttpCookie": "http_cookie",
    "HttpStatusCode": "http_response", "HttpContentType": "http_response",
    "HttpContentFormat": "http_response", "HttpResponseBodyBytes": "http_response",
    "HttpResponseTime": "http_response",  # time to receive the response -> latency
    "HttpRequestTime": _N,  # no request-side home in OCSF http_request
    "FileName": "file", "FileMD5": "file", "FileSHA256": "file", "FileSize": "file",
    "FilePath": "file",  # File Event alias to TargetFilePath
    "Hash": "file",  # alias to best hash of the target file / target process image / upload (R2)

    # Process Event: https://learn.microsoft.com/en-us/azure/sentinel/process-events-normalization-schema
    "ActingProcess*": "process", "TargetProcess*": "process",
    "ActingProcessCommandLine": "process", "ActingProcessGuid": "process",
    "ActingProcessId": "process", "ActingProcessName": "process",
    "ActingProcessMD5": "file",  # "MD5 hash of the acting process image file" (R2)
    "CommandLine": "process", "Process": "process", "ParentProcessName": "process",
    "TargetProcessCommandLine": "process", "TargetProcessCurrentDirectory": "process",
    "TargetProcessGuid": "process", "TargetProcessId": "process",
    "TargetProcessIntegrityLevel": "process", "TargetProcessName": "process",
    "TargetProcessStatusCode": "process",  # exit code of the target process
    "TargetProcessMD5": "file", "TargetProcessFileSize": "file",  # image file (R2)
    "ActorUserId": "user", "ActorUsername": "user", "User": "user",
    "TargetUserId": "user", "TargetUsername": "user", "TargetUserType": "user",

    # User entity: https://learn.microsoft.com/en-us/azure/sentinel/normalization-entity-user
    # SID is a UserIdType value, UPN a UsernameType value: both identify a user.
    "SID": "user", "UPN": "user", "TargetUserIdType=SID": "user",

    # User management (group fields): https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema-user-management
    "GroupId": "group", "GroupName": "group",

    # Authentication: https://learn.microsoft.com/en-us/azure/sentinel/authentication-normalization-schema
    "Target": "network_endpoint",  # renamed TargetDvc: the target system
    "TargetHostname": "network_endpoint", "TargetIpAddr": "network_endpoint",
    "TargetAppName": "application",  # "name of the application to which the authorization is required"
    "TargetUrl": "url",
    "LogonMethod": _N, "LogonProtocol": _N,  # properties of the authentication activity
    "MFA": _N,  # not an ASIM field name; a LogonMethod value / result detail

    # File Event: https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema-file-event
    "TargetFile*": "file",
    "TargetFileCreationTime": "file", "TargetFileDirectory": "file",
    "TargetFileExtension": "file", "TargetFileMD5": "file", "TargetFileMimeType": "file",
    "TargetFileName": "file", "TargetFilePath": "file", "TargetFilePathType": "file",
    "TargetFileSize": "file",

    # R7 abstentions: no ASIM field by these exact names, or mixed wildcards.
    "Ack": _N, "Guid": _N, "Id": _N, "LastReportedTime": _N,
    "SHA1": _N, "SHA256": _N, "SHA512": _N,
    "Src*": _N, "Dst*": _N,  # Src*/Dst* prefixes span user, endpoint and traffic fields
}

# ---------------------------------------------------------------------------
# Splunk CIM 6.0
# ---------------------------------------------------------------------------
_CIM: dict[str, str | None] = {
    # Network_Traffic: https://help.splunk.com/en/splunk-enterprise/common-information-model/6.0/data-models/network-traffic
    "src_ip": "network_endpoint", "src_port": "network_endpoint", "src_mac": "network_endpoint",
    "src_translated_ip": "network_endpoint",
    "dest_ip": "network_endpoint", "dest_port": "network_endpoint", "dest_mac": "network_endpoint",
    "bytes": "network_traffic", "bytes_in": "network_traffic", "bytes_out": "network_traffic",
    "packets": "network_traffic", "packets_in": "network_traffic", "packets_out": "network_traffic",
    "direction": "network_connection_info", "protocol": "network_connection_info",
    "transport": "network_connection_info", "tcp_flag": "network_connection_info",
    "flow_id": "network_connection_info", "session_id": "network_connection_info",
    "dvc": "device", "dvc_ip": "device",  # "The device that reported the traffic event"
    "rule": "rule",
    "vendor_product": "product",
    "_time": _N, "action": _N, "duration": _N, "response_time": _N,
    # "app" = application protocol in Network_Traffic, hosted application in Web,
    # "application involved" in Authentication (R7).
    "app": _N,
    # src/dest: remote host in Network_Traffic/Web, executing endpoint in Endpoint (R3).
    "src": "endpoint", "dest": "endpoint",

    # Endpoint (Processes, Filesystem): https://help.splunk.com/en/splunk-enterprise/common-information-model/6.0/data-models/endpoint
    "process": "process", "process_current_directory": "process", "process_exec": "process",
    "process_guid": "process", "process_id": "process", "process_integrity_level": "process",
    "process_name": "process", "process_path": "process",
    "process_hash": "file",  # digests of the process image (R2)
    "parent_process": "process", "parent_process_id": "process",
    "parent_process_name": "process", "parent_process_path": "process",
    "file_access_time": "file", "file_create_time": "file", "file_modify_time": "file",
    "file_hash": "file", "file_name": "file", "file_path": "file", "file_size": "file",

    # Web: https://help.splunk.com/en/splunk-enterprise/common-information-model/6.0/data-models/web
    "http_method": "http_request", "http_referrer": "http_request",
    "http_user_agent": "http_request",
    "http_content_type": "http_response",  # "content-type of the requested HTTP resource"
    "url": "url", "url_domain": "url", "url_length": "url",
    "uri_path": "url", "uri_query": "url",
    "category": _N,  # traffic category (Web) / signature category (IDS)
    "status": _N,  # HTTP status in Web, update status in Change (R7)

    # Authentication: https://help.splunk.com/en/splunk-enterprise/common-information-model/6.0/data-models/authentication
    # (user_name is defined on the Change page: "user name of the user or entity performing the change")
    "user": "user", "user_id": "user", "user_name": "user", "user_type": "user",
    "src_user": "user",
    "src_nt_domain": "network_endpoint", "dest_nt_domain": "network_endpoint",
    "authentication_method": _N, "reason": _N,
    "signature": _N, "signature_id": _N,  # event signature names/codes (R6)

    # Change: https://help.splunk.com/en/splunk-enterprise/common-information-model/6.0/data-models/change
    "command": _N,  # "command that initiated the change": not documented as a process
    "object": _N, "object_id": _N,  # generic affected object (user, volume, interface ...)
    "result": _N, "result_id": _N,

    # Intrusion_Detection: https://help.splunk.com/en/splunk-enterprise/common-information-model/6.0/data-models/intrusion-detection
    "severity": _N,
}

# ---------------------------------------------------------------------------
# Elastic ECS
# ---------------------------------------------------------------------------
_ECS: dict[str, str | None] = {
    # Fieldset wildcards. Per-fieldset pages under https://www.elastic.co/docs/reference/ecs/
    # https://www.elastic.co/docs/reference/ecs/ecs-agent ("software entity ... that collects")
    "agent.*": "agent", "destination.*": "network_endpoint", "source.*": "network_endpoint",
    "server.*": "network_endpoint",  # ecs-server: "the responder in a network connection"
    "destination": "network_endpoint", "server": "network_endpoint",
    "file.*": "file", "file.hash.*": "file",
    "host.*": "device", "observer.*": "device",  # ecs-observer: device that detects/observes
    "process.*": "process", "process.parent.*": "process", "process.user.*": "user",
    "threat.indicator.*": "osint",

    # Event fieldset https://www.elastic.co/docs/reference/ecs/ecs-event : record-level (R6)
    "@timestamp": _N, "event.action": _N, "event.category: malware": _N, "event.code": _N,
    "event.id": _N, "event.kind": _N, "event.outcome": _N, "event.provider": _N,
    "event.reason": _N, "event.risk_score": _N, "event.risk_score_norm": _N,
    "event.severity": _N, "event.start": _N, "event.type": _N, "event.type: denied": _N,

    # Source / destination / client / server: https://www.elastic.co/docs/reference/ecs/ecs-source
    # https://www.elastic.co/docs/reference/ecs/ecs-destination https://www.elastic.co/docs/reference/ecs/ecs-client
    "source.address": "network_endpoint", "source.domain": "network_endpoint",
    "source.ip": "network_endpoint", "source.mac": "network_endpoint",
    "source.nat.ip": "network_endpoint", "source.port": "network_endpoint",
    "destination.address": "network_endpoint", "destination.domain": "network_endpoint",
    "destination.ip": "network_endpoint", "destination.mac": "network_endpoint",
    "destination.port": "network_endpoint",
    "server.address": "network_endpoint", "client.ip": "network_endpoint",
    "source.bytes": "network_traffic", "destination.bytes": "network_traffic",
    "source.packets": "network_traffic", "destination.packets": "network_traffic",
    "source.user.name": "user", "destination.user.name": "user",

    # Network: https://www.elastic.co/docs/reference/ecs/ecs-network
    "network.bytes": "network_traffic", "network.packets": "network_traffic",
    "network.community_id": "network_connection_info", "network.direction": "network_connection_info",
    "network.iana_number": "network_connection_info", "network.protocol": "network_connection_info",
    "network.transport": "network_connection_info", "network.type": "network_connection_info",

    # File: https://www.elastic.co/docs/reference/ecs/ecs-file
    # Hash nesting (file.hash, process.hash): https://www.elastic.co/docs/reference/ecs/ecs-hash
    "file.accessed": "file", "file.created": "file", "file.directory": "file",
    "file.extension": "file", "file.hash.md5": "file", "file.mime_type": "file",
    "file.mtime": "file", "file.name": "file", "file.path": "file", "file.size": "file",
    "file.type": "file",
    "file.owner": "user",  # "File owner's username" (R2)

    # Process: https://www.elastic.co/docs/reference/ecs/ecs-process
    "process.command_line": "process", "process.parent.command_line": "process",
    "process.entity_id": "process", "process.executable": "process",
    "process.parent.executable": "process", "process.exit_code": "process",
    "process.name": "process", "process.pid": "process", "process.parent.pid": "process",
    "process.start": "process", "process.working_directory": "process",
    "process.hash.md5": "file",  # "Hashes, usually file hashes" (R2)
    "process.user.id": "user", "process.user.name": "user",

    # User / group: https://www.elastic.co/docs/reference/ecs/ecs-user https://www.elastic.co/docs/reference/ecs/ecs-group
    "user.domain": "user", "user.email": "user", "user.full_name": "user", "user.id": "user",
    "user.name": "user", "user.effective.name": "user",
    "user.target.email": "user", "user.target.id": "user", "user.target.name": "user",
    "group.id": "group", "group.name": "group",

    # Host: https://www.elastic.co/docs/reference/ecs/ecs-host
    "host.hostname": "device", "host.id": "device",

    # HTTP / URL / user_agent: https://www.elastic.co/docs/reference/ecs/ecs-http
    # https://www.elastic.co/docs/reference/ecs/ecs-url https://www.elastic.co/docs/reference/ecs/ecs-user_agent
    "http.request.body.bytes": "http_request", "http.request.id": "http_request",
    "http.request.method": "http_request", "http.request.referrer": "http_request",
    "http.version": "http_request", "user_agent.original": "http_request",
    "http.response.body.bytes": "http_response", "http.response.mime_type": "http_response",
    "http.response.status_code": "http_response",
    "url.domain": "url", "url.full": "url", "url.original": "url", "url.path": "url",
    "url.port": "url", "url.query": "url", "url.scheme": "url",

    # Rule / service: https://www.elastic.co/docs/reference/ecs/ecs-rule https://www.elastic.co/docs/reference/ecs/ecs-service
    "rule.description": "rule", "rule.id": "rule", "rule.name": "rule", "rule.uuid": "rule",
    "service.name": "service",

    # Threat: https://www.elastic.co/docs/reference/ecs/ecs-threat
    "threat.indicator.confidence": "osint", "threat.indicator.first_seen": "osint",
    "threat.tactic.id": "tactic", "threat.technique.id": "technique",
    "threat.technique.subtechnique.id": "sub_technique",
    "threat.software.name": _N,  # software used by the threat: malware or tool, not stated

    # R7: no ECS field by these exact names (no fieldset prefix).
    ".name": _N, ".port": _N, "allowed": _N, "last_seen": _N, "sha1": _N, "sha256": _N,
}

# ---------------------------------------------------------------------------
# OpenTelemetry semantic conventions (attribute registry) + logs data model
# ---------------------------------------------------------------------------
_OTEL: dict[str, str | None] = {
    # Logs data model: https://opentelemetry.io/docs/specs/otel/logs/data-model/  (record-level, R6)
    # host.*: https://opentelemetry.io/docs/specs/semconv/registry/attributes/host/ ("a computing instance")
    "Body": _N, "EventName": _N, "SeverityNumber": _N, "SeverityText": _N, "Timestamp": _N,
    "Resource": _N,  # "the observed entity that generated the log": any entity kind

    # Namespace wildcards (registry pages below).
    "destination.*": "network_endpoint", "source.*": "network_endpoint",
    "file.*": "file", "host.*": "device", "process.*": "process",

    # client/server/source/destination: https://opentelemetry.io/docs/specs/semconv/registry/attributes/client/
    # https://opentelemetry.io/docs/specs/semconv/registry/attributes/server/
    # https://opentelemetry.io/docs/specs/semconv/registry/attributes/source/
    # https://opentelemetry.io/docs/specs/semconv/registry/attributes/destination/
    "client.address": "network_endpoint", "server.address": "network_endpoint",
    "source.address": "network_endpoint", "destination.address": "network_endpoint",
    "source.port": "network_endpoint", "destination.port": "network_endpoint",

    # File: https://opentelemetry.io/docs/specs/semconv/registry/attributes/file/
    "file.accessed": "file", "file.created": "file", "file.modified": "file",
    "file.directory": "file", "file.extension": "file", "file.name": "file",
    "file.path": "file", "file.size": "file", "file.symbolic_link.target_path": "file",
    "file.owner.id": "user", "file.owner.name": "user",

    # Process: https://opentelemetry.io/docs/specs/semconv/registry/attributes/process/
    "process.command": "process", "process.command_line": "process",
    "process.creation.time": "process", "process.exit.code": "process",
    "process.executable.name": "process", "process.executable.path": "process",
    "process.parent_pid": "process", "process.pid": "process",
    "process.working_directory": "process",
    "process.owner": "user", "process.real_user.id": "user",
    "process.real_user.name": "user", "process.user.name": "user",

    # User / session: https://opentelemetry.io/docs/specs/semconv/registry/attributes/user/
    # https://opentelemetry.io/docs/specs/semconv/registry/attributes/session/
    "user.id": "user", "user.name": "user",
    "session.id": "session",

    # Network: https://opentelemetry.io/docs/specs/semconv/registry/attributes/network/
    "network.io.direction": "network_connection_info",
    "network.protocol.name": "network_connection_info",
    "network.protocol.version": "network_connection_info",
    "network.transport": "network_connection_info", "network.type": "network_connection_info",

    # HTTP / user_agent / url: https://opentelemetry.io/docs/specs/semconv/registry/attributes/http/
    # https://opentelemetry.io/docs/specs/semconv/registry/attributes/user-agent/
    # https://opentelemetry.io/docs/specs/semconv/registry/attributes/url/
    "http.request.method": "http_request", "http.request.body.size": "http_request",
    "http.request.header.referer": "http_request",
    "http.request.header.x-forwarded-for": "http_request",
    "user_agent.original": "http_request",
    "http.response.body.size": "http_response", "http.response.status_code": "http_response",
    "url.domain": "url", "url.full": "url", "url.path": "url", "url.port": "url",
    "url.query": "url", "url.scheme": "url",

    # R7: unprefixed tokens.
    ".port": _N,
    "method_original": _N,  # registry defines http.request.method_original, not this token
}

# ---------------------------------------------------------------------------
# Google SecOps (Chronicle) UDM
# ---------------------------------------------------------------------------
# All rows: https://docs.cloud.google.com/chronicle/docs/reference/udm-field-list
_UDM: dict[str, str | None] = {
    # Event nouns. principal/target/src/intermediary hold any entity kind (R7);
    # target.file / target.process are typed sub-messages.
    "principal.*": _N, "target.*": _N, "src.*": _N, "intermediary.*": _N,
    "target.file.*": "file", "target.process.*": "process",

    # Noun network identity of a participant (R3).
    "principal.hostname": "network_endpoint", "target.hostname": "network_endpoint",
    "principal.ip": "network_endpoint", "target.ip": "network_endpoint",
    "intermediary.ip": "network_endpoint",
    "observer.ip": "device",  # observer: reports on activity, e.g. a sniffer
    "principal.mac": "network_endpoint", "target.mac": "network_endpoint",
    "principal.port": "network_endpoint", "target.port": "network_endpoint",
    "principal.administrative_domain": _N,  # no description returned by the fetched page
    "target.application": "application",  # "The name of an application or service"
    "target.url": "url",
    "target.resource.name": _N,  # generic resource (scheduled task, calendar entry ...)

    # Process / file.
    "principal.process": "process",
    "principal.process.command_line": "process", "target.process.command_line": "process",
    "principal.process.parent_process.pid": "process", "target.process.pid": "process",
    "principal.process.product_specific_process_id": "process",
    "target.process.product_specific_process_id": "process",
    "principal.process.file.full_path": "file", "target.file.full_path": "file",
    "target.process.file.full_path": "file",
    "principal.process.file.md5": "file", "target.file.md5": "file",
    "target.process.file.md5": "file",
    "target.file.mime_type": "file", "target.file.size": "file",

    # User.
    "principal.user": "user", "principal.user.email_addresses": "user",
    "principal.user.user_display_name": "user", "principal.user.user_role": "user",
    "principal.user.userid": "user", "target.user.userid": "user",
    "principal.user.windows_sid": "user", "target.user.windows_sid": "user",

    # Network.
    "network.application_protocol": "network_connection_info",
    "network.direction": "network_connection_info",
    "network.ip_protocol": "network_connection_info",
    "network.session_id": "network_connection_info",
    "network.parent_session_id": "network_connection_info",
    "network.received_bytes": "network_traffic", "network.sent_bytes": "network_traffic",
    "network.session_duration": _N,  # duration (R6)
    "network.http.method": "http_request", "network.http.referral_url": "http_request",
    "network.http.user_agent": "http_request",
    "network.http.response_code": "http_response",

    # SecurityResult.
    "security_result": _N, "security_result.action": _N, "security_result.category": _N,
    "security_result.severity": _N, "security_result.summary": _N,
    "security_result.rule_id": "rule", "security_result.rule_name": "rule",
    # threat_name: "A vendor-assigned classification common across multiple customers";
    # the page does not say malware, so abstain (R7).
    "security_result.threat_name": _N,

    # Metadata (record-level, R6) except the product it names.
    "metadata.event_timestamp": _N, "metadata.event_type": _N, "metadata.id": _N,
    "metadata.product_log_id": _N, "metadata.product_name": "product",

    # R7: unprefixed tokens.
    ".asset_id": _N, ".description": _N, ".hostname": _N, ".ip": _N,
    ".resource.name": _N, ".sha1": _N, ".sha256": _N,
    "rule_id": _N, "rule_name": _N, "vendor_name": _N,
}

# ---------------------------------------------------------------------------
# Zeek logs. Field names carry no log name, so a token is typed only when every Zeek
# log that defines it gives it the same entity meaning (R7).
# ---------------------------------------------------------------------------
_ZEEK: dict[str, str | None] = {
    # conn.log: https://docs.zeek.org/en/master/scripts/base/protocols/conn/main.zeek.html
    # uid: "unique ID for the connection" in every log fetched (conn, http, sip, files, notice,
    # krb: https://docs.zeek.org/en/master/scripts/base/protocols/krb/main.zeek.html)
    "uid": "network_connection_info",
    "community_id": "network_connection_info", "conn_state": "network_connection_info",
    "proto": "network_connection_info",
    "service": _N,  # conn.log: confirmed protocols; kerberos.log: the Kerberos service requested
    "local_orig": "network_connection_info",  # conn + files: whether the originating side is local
    "local_resp": "network_connection_info",
    "orig_bytes": "network_traffic", "resp_bytes": "network_traffic",
    "orig_pkts": "network_traffic", "resp_pkts": "network_traffic",
    "orig+resp_bytes": "network_traffic",
    "orig_l2_addr": "network_endpoint", "resp_l2_addr": "network_endpoint",
    "id.orig_h": "network_endpoint", "id.orig_p": "network_endpoint",
    "id.resp_h": "network_endpoint", "id.resp_p": "network_endpoint",
    "id.orig_*": "network_endpoint", "id.resp_*": "network_endpoint",
    "id.*": _N,  # the 4-tuple spans both endpoints
    "tunnel_parents": _N,  # uids of other connections
    "duration": _N,  # conn duration vs file-analysis duration in files.log; event-level anyway
    "ts": _N,

    # files.log: https://docs.zeek.org/en/master/scripts/base/frameworks/files/main.zeek.html
    "fuid": "file", "filename": "file", "mime_type": "file", "total_bytes": "file",
    "md5": "file", "sha1": "file", "sha256": "file",

    # http.log: https://docs.zeek.org/en/master/scripts/base/protocols/http/main.zeek.html
    # sip.log:  https://docs.zeek.org/en/master/scripts/base/protocols/sip/main.zeek.html
    "referrer": "http_request", "proxied": "http_request",  # http.log only
    "orig_fuids": "file", "resp_fuids": "file",  # file unique IDs (http.log entities)
    "uri": "url",  # "URI used in the request" in both http.log and sip.log
    "username": "user",  # http.log Basic auth username; not defined in the other logs fetched
    # Same token, different protocol objects in http.log vs sip.log (or other logs):
    "method": _N, "status_code": _N, "request_body_len": _N, "response_body_len": _N,
    "user_agent": _N, "version": _N, "host": _N,

    # notice.log: https://docs.zeek.org/en/master/scripts/base/frameworks/notice/main.zeek.html
    "src": "network_endpoint", "dst": "network_endpoint",  # source/destination address
    "note": _N, "msg": _N, "actions": _N,
    # weird.log name/notice fields; not verified against a fetched page (R7).
    "name": _N, "notice": _N,
}

_TABLES: dict[str, dict[str, str | None]] = {
    "Microsoft ASIM": _ASIM,
    "Splunk CIM": _CIM,
    "Elastic ECS": _ECS,
    "OpenTelemetry": _OTEL,
    "Google UDM": _UDM,
    "Zeek": _ZEEK,
}


def _leaf(field: str) -> str:
    return field.rsplit(".", 1)[-1]


def source_kind(schema: str, field: str) -> str | None:
    """Return the OCSF 1.8.0 object the source field denotes, or None to abstain.

    Exact full-field lookup first. If the caller passes a leaf token instead of the full
    field, fall back to the full fields in the table with that leaf, and return a kind
    only when they all agree on one non-None kind.
    """
    table = _TABLES.get(schema)
    if table is None:
        return None
    if field in table:
        return table[field]
    kinds = {k for f, k in table.items() if _leaf(f) == field}
    if len(kinds) == 1:
        return next(iter(kinds))
    return None


def _self_test() -> None:
    import json
    from pathlib import Path

    here = Path(__file__).resolve().parent
    objects = here.parents[1] / "ocsf-deterministic-mapper" / "schema-ocsf-1.8.0-api-2026-11-16" / "objects"
    names = {p.stem for p in objects.glob("*.json")}
    assert OCSF_KINDS <= names, OCSF_KINDS - names
    files = {
        "Microsoft ASIM": "asim", "Splunk CIM": "cim", "Elastic ECS": "ecs",
        "OpenTelemetry": "opentelemetry", "Google UDM": "udm", "Zeek": "zeek",
    }
    for schema, stem in files.items():
        req = json.loads((here / "s1_table_work" / f"request-{stem}.json").read_text())
        assert req["schema"] == schema
        fields = sorted({f for fs in req["leaf_tokens"].values() for f in fs})
        missing = [f for f in fields if f not in _TABLES[schema]]
        extra = [f for f in _TABLES[schema] if f not in fields]
        assert not missing, (schema, missing)
        assert not extra, (schema, extra)
        typed = [f for f in fields if source_kind(schema, f) is not None]
        for f in typed:
            assert source_kind(schema, f) in OCSF_KINDS, (schema, f)
        print(f"{schema}: {len(fields)} fields, {len(typed)} typed, {len(fields) - len(typed)} abstained")


if __name__ == "__main__":
    _self_test()

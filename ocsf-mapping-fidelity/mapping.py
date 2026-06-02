"""The C1 field-by-field mappings — the reviewable, non-black-box core.

Each source field gets one mapping record:

  ocsf      the OCSF 1.8.0 attribute path it lands on (dotted), or "unmapped" /
            "raw_data" when no typed attribute can hold it. Every non-catch-all
            path is validated against schemas/ocsf/ocsf_1.8.0_subset.json by the
            harness, so a path that does not exist in the real schema fails loudly.
  status    one of:
              "typed"    lands on a typed OCSF attribute, semantics preserved
              "coerced"  lands on a typed attribute but crosses a boundary —
                         an enum narrows, an array collapses to a scalar, a
                         structured value flattens, or an id/label is lost
              "unmapped" no typed home; only "unmapped"/"raw_data" can hold it
  note      the rationale, so the judgement is auditable rather than asserted

The Okta records also carry `official`: whether Okta's own shipped reference
mapper (okta/okta-ocsf-syslog, the Amazon Security Lake Lambda) actually carries
the field into the OCSF event. The gap between "a typed OCSF home exists" and
"the shipped mapper uses it" is one of the two results this benchmark produces.

CrowdStrike has no public field-level vendor mapping (its FDR OCSF mapping files
are account-manager-gated), so its records are a best-effort mapping against the
real OCSF 1.8.0 schema, every target validated, labelled as best-effort — not as
a vendor mapping.
"""

# --- Okta System Log -> OCSF Authentication (3002) -------------------------
# `official` = does Okta's okta/okta-ocsf-syslog reference Lambda carry this field
# into the OCSF event (true), or drop it (false)? Anchored on its app.py/README.

OKTA_MAPPING = {
    "uuid": {"ocsf": "metadata.uid", "status": "typed", "official": False,
             "note": "event id -> metadata.uid"},
    "published": {"ocsf": "time", "status": "typed", "official": True,
                  "note": "publish timestamp -> time/ref_time"},
    "eventType": {"ocsf": "metadata.event_code", "status": "typed", "official": False,
                  "note": "raw type string preserved in event_code; its semantics also drive class/activity selection"},
    "version": {"ocsf": "metadata.log_version", "status": "typed", "official": False,
                "note": "Okta log schema version -> metadata.log_version"},
    "severity": {"ocsf": "severity_id", "status": "typed", "official": True,
                 "note": "DEBUG/INFO/WARN/ERROR -> severity_id enum; faithful enum remap"},
    "legacyEventType": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                        "note": "deprecated; no typed home"},
    "displayMessage": {"ocsf": "message", "status": "typed", "official": True,
                       "note": "-> message"},
    "actor.id": {"ocsf": "user.uid", "status": "typed", "official": False,
                 "note": "actor is the authenticating user for a login"},
    "actor.type": {"ocsf": "user.type", "status": "typed", "official": False,
                   "note": "User/SystemPrincipal -> user.type (free string preserves it)"},
    "actor.alternateId": {"ocsf": "user.email_addr", "status": "typed", "official": True,
                          "note": "login/email -> user.email_addr"},
    "actor.displayName": {"ocsf": "user.full_name", "status": "typed", "official": True,
                          "note": "-> user.full_name"},
    "actor.detailEntry": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                          "note": "free-form map; no typed home"},
    "client.id": {"ocsf": "actor.app_uid", "status": "typed", "official": False,
                  "note": "OAuth client id -> actor.app_uid"},
    "client.userAgent.rawUserAgent": {"ocsf": "http_request.user_agent", "status": "typed", "official": False,
                                       "note": "raw UA -> http_request.user_agent"},
    "client.userAgent.os": {"ocsf": "src_endpoint.os.name", "status": "typed", "official": False,
                            "note": "OS parsed from UA -> src_endpoint.os.name"},
    "client.userAgent.browser": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                                 "note": "OCSF has no parsed-browser attribute; only the raw UA has a home"},
    "client.geographicalContext.geolocation.lat": {"ocsf": "src_endpoint.location.lat", "status": "typed", "official": True,
                                                    "note": "geo carried (Okta puts it in enrichments; typed home is src_endpoint.location)"},
    "client.geographicalContext.geolocation.lon": {"ocsf": "src_endpoint.location.long", "status": "typed", "official": True,
                                                    "note": "geo carried via enrichments"},
    "client.geographicalContext.city": {"ocsf": "src_endpoint.location.city", "status": "typed", "official": True,
                                        "note": "geo carried via enrichments"},
    "client.geographicalContext.state": {"ocsf": "src_endpoint.location.region", "status": "typed", "official": True,
                                         "note": "state -> location.region"},
    "client.geographicalContext.country": {"ocsf": "src_endpoint.location.country", "status": "typed", "official": True,
                                           "note": "geo carried via enrichments"},
    "client.geographicalContext.postalCode": {"ocsf": "src_endpoint.location.postal_code", "status": "typed", "official": True,
                                              "note": "geo carried via enrichments"},
    "client.zone": {"ocsf": "src_endpoint.zone", "status": "typed", "official": False,
                    "note": "Okta network zone -> network_endpoint.zone; shipped mapper drops it"},
    "client.ipAddress": {"ocsf": "src_endpoint.ip", "status": "typed", "official": True,
                         "note": "-> src_endpoint.ip"},
    "client.device": {"ocsf": "device.type", "status": "coerced", "official": True,
                      "note": "device label (Computer/Mobile) -> device.type; shipped mapper puts it in src_endpoint.interface_id, a coercion either way"},
    "request.ipChain": {"ocsf": "src_endpoint.intermediate_ips", "status": "coerced", "official": False,
                        "note": "proxy chain -> ip list; per-hop geo and ordering are lost; shipped mapper drops it"},
    "outcome.result": {"ocsf": "status_id", "status": "coerced", "official": True,
                       "note": "7-value enum (SUCCESS/FAILURE/CHALLENGE/SKIPPED/ALLOW/DENY/UNKNOWN) -> ~3-value status_id; CHALLENGE/SKIPPED/ALLOW/DENY collapse"},
    "outcome.reason": {"ocsf": "status_detail", "status": "typed", "official": True,
                       "note": "-> status_detail (free string)"},
    "target.id": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                  "note": "Authentication 3002 has no target/resource array; heterogeneous target[] (app/user/group) has no faithful home"},
    "target.type": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                    "note": "no target array on Authentication"},
    "target.alternateId": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                           "note": "no target array on Authentication"},
    "target.displayName": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                           "note": "no target array on Authentication"},
    "target.detailEntry": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                           "note": "free-form map; no typed home"},
    "transaction.id": {"ocsf": "metadata.correlation_uid", "status": "typed", "official": False,
                       "note": "-> metadata.correlation_uid"},
    "transaction.type": {"ocsf": "logon_type_id", "status": "coerced", "official": True,
                         "note": "WEB/JOB -> logon_type enum; shipped mapper maps WEB->99 (Other)"},
    "transaction.detail": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                           "note": "free-form map; no typed home"},
    "debugContext.debugData": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                               "note": "free-form map carrying risk/threat signals, deviceFingerprint, behaviors; shipped mapper extracts only requestUri+url, the rest lands in unmapped"},
    "authenticationContext.authenticationProvider": {"ocsf": "auth_protocol_id", "status": "coerced", "official": True,
                                                      "note": "provider enum -> auth_protocol enum; shipped mapper maps FACTOR->Other"},
    "authenticationContext.authenticationStep": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                                                 "note": "currently always 0; no home"},
    "authenticationContext.credentialProvider": {"ocsf": "auth_factors", "status": "coerced", "official": False,
                                                 "note": "RSA/DUO/YUBIKEY -> auth_factors[]; provider->factor mapping is lossy; shipped mapper drops it"},
    "authenticationContext.credentialType": {"ocsf": "auth_factors", "status": "coerced", "official": False,
                                            "note": "12-value scheme enum (OTP/SMS/PASSWORD/PUSH...) collapses to is_mfa + factor_type; PUSH-vs-OTP distinction lost; shipped mapper drops it"},
    "authenticationContext.issuer.id": {"ocsf": "session.issuer", "status": "typed", "official": False,
                                        "note": "SAML/token issuer -> session.issuer"},
    "authenticationContext.issuer.type": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                                          "note": "issuer source info; no typed home"},
    "authenticationContext.externalSessionId": {"ocsf": "session.uid", "status": "typed", "official": True,
                                               "note": "-> session.uid; session-correlation key"},
    "authenticationContext.interface": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                                        "note": "third-party UI string; no typed home"},
    "securityContext.asNumber": {"ocsf": "src_endpoint.autonomous_system.number", "status": "typed", "official": False,
                                 "note": "ASN -> network_endpoint.autonomous_system.number; shipped mapper drops the whole securityContext"},
    "securityContext.asOrg": {"ocsf": "src_endpoint.autonomous_system.name", "status": "typed", "official": False,
                              "note": "AS org -> autonomous_system.name; shipped mapper drops it"},
    "securityContext.isp": {"ocsf": "src_endpoint.isp", "status": "typed", "official": False,
                            "note": "-> network_endpoint.isp; shipped mapper drops it"},
    "securityContext.domain": {"ocsf": "src_endpoint.domain", "status": "typed", "official": False,
                               "note": "-> network_endpoint.domain; shipped mapper drops it"},
    "securityContext.isProxy": {"ocsf": "unmapped", "status": "unmapped", "official": False,
                                "note": "OCSF endpoint has no boolean is-proxy flag (proxy_endpoint is an address, not a flag); high-signal fraud bit has no typed home"},
}

# --- CrowdStrike Detection Summary Event -> OCSF Detection Finding (2004) ----
# Best-effort against the real OCSF 1.8.0 schema; no public CrowdStrike field
# mapping exists (FDR OCSF mapping files are account-manager-gated).

CROWDSTRIKE_MAPPING = {
    "metadata.eventType": {"ocsf": "metadata.event_code", "status": "typed",
                           "note": "raw type preserved; semantics also drive class selection"},
    "metadata.eventCreationTime": {"ocsf": "time", "status": "typed", "note": "-> time"},
    "metadata.offset": {"ocsf": "metadata.sequence", "status": "typed", "note": "stream position -> metadata.sequence"},
    "metadata.customerIDString": {"ocsf": "metadata.tenant_uid", "status": "typed", "note": "CID -> tenant_uid"},
    "metadata.version": {"ocsf": "metadata.log_version", "status": "typed", "note": "-> metadata.log_version"},
    "event.DetectName": {"ocsf": "finding_info.title", "status": "typed", "note": "-> finding_info.title"},
    "event.DetectDescription": {"ocsf": "finding_info.desc", "status": "typed", "note": "-> finding_info.desc"},
    "event.Severity": {"ocsf": "severity_id", "status": "coerced",
                       "note": "CrowdStrike numeric severity scale -> OCSF severity_id enum; scale remap"},
    "event.SeverityName": {"ocsf": "severity", "status": "typed", "note": "-> severity (string)"},
    "event.Tactic": {"ocsf": "attacks.tactic", "status": "coerced",
                     "note": "tactic name string -> attack.tactic object {name,uid}; the TA-id is absent, only name populates"},
    "event.Technique": {"ocsf": "attacks.technique", "status": "coerced",
                        "note": "technique name/label -> attack.technique object {name,uid}; name and T-id do not both survive a flat string"},
    "event.Objective": {"ocsf": "unmapped", "status": "unmapped",
                        "note": "adversary objective; no OCSF Detection Finding attribute"},
    "event.FileName": {"ocsf": "evidences.process.file.name", "status": "typed",
                       "note": "-> evidences[].process.file.name"},
    "event.FilePath": {"ocsf": "evidences.process.file.path", "status": "typed", "note": "-> evidences[].process.file.path"},
    "event.CommandLine": {"ocsf": "evidences.process.cmd_line", "status": "typed", "note": "-> evidences[].process.cmd_line"},
    "event.MD5String": {"ocsf": "evidences.process.file.hashes", "status": "typed",
                        "note": "-> file.hashes[] fingerprint{algorithm_id, value}"},
    "event.SHA1String": {"ocsf": "evidences.process.file.hashes", "status": "typed", "note": "-> file.hashes[]"},
    "event.SHA256String": {"ocsf": "evidences.process.file.hashes", "status": "typed", "note": "-> file.hashes[]; also observables[] type_id=8"},
    "event.ComputerName": {"ocsf": "device.hostname", "status": "typed", "note": "-> device.hostname"},
    "event.UserName": {"ocsf": "evidences.actor.user.name", "status": "typed", "note": "-> evidences[].actor.user.name"},
    "event.LocalIP": {"ocsf": "device.ip", "status": "typed", "note": "-> device.ip"},
    "event.MACAddress": {"ocsf": "device.mac", "status": "typed", "note": "-> device.mac"},
    "event.SensorId": {"ocsf": "device.agent_list", "status": "typed",
                       "note": "Falcon AID -> device.agent_list[].uid (the sensor, distinct from device identity)"},
    "event.MachineDomain": {"ocsf": "device.domain", "status": "typed", "note": "-> device.domain"},
    "event.ProcessId": {"ocsf": "evidences.process.pid", "status": "typed", "note": "-> evidences[].process.pid"},
    "event.ParentProcessId": {"ocsf": "evidences.process.parent_process.pid", "status": "typed", "note": "-> parent_process.pid"},
    "event.ParentImageFileName": {"ocsf": "evidences.process.parent_process.file.path", "status": "typed", "note": "-> parent_process.file.path"},
    "event.ParentCommandLine": {"ocsf": "evidences.process.parent_process.cmd_line", "status": "typed", "note": "-> parent_process.cmd_line"},
    "event.GrandparentImageFileName": {"ocsf": "evidences.process.ancestry", "status": "coerced",
                                       "note": "OCSF process models one parent level + ancestry[]/lineage path; grandparent has no named slot, flattens into ancestry"},
    "event.GrandparentCommandLine": {"ocsf": "unmapped", "status": "unmapped",
                                     "note": "ancestry/lineage carry path only, not a command line for ancestor processes; grandparent cmd line has no home"},
    "event.IOCType": {"ocsf": "observables.type_id", "status": "coerced",
                      "note": "free string (hash_sha256/domain/ipv4) -> observable.type_id integer enum; IOC types outside the enum fail the lookup"},
    "event.IOCValue": {"ocsf": "observables.value", "status": "typed", "note": "-> observables[].value"},
    "event.PatternDispositionDescription": {"ocsf": "disposition", "status": "typed", "note": "-> disposition (string)"},
    "event.PatternDispositionValue": {"ocsf": "disposition_id", "status": "coerced",
                                      "note": "bitmask of multiple actions taken -> single-valued disposition_id; the multi-action set collapses to one"},
    "event.PatternDispositionFlags": {"ocsf": "unmapped", "status": "unmapped",
                                      "note": "named boolean flags object; no typed home"},
    "event.FalconHostLink": {"ocsf": "finding_info.src_url", "status": "typed", "note": "-> finding_info.src_url"},
    "event.ProcessStartTime": {"ocsf": "evidences.process.created_time", "status": "typed", "note": "-> process.created_time"},
    "event.ProcessEndTime": {"ocsf": "evidences.process.terminated_time", "status": "typed", "note": "-> process.terminated_time"},
    "event.DetectId": {"ocsf": "finding_info.uid", "status": "typed", "note": "-> finding_info.uid"},
    "event.NetworkAccesses": {"ocsf": "evidences", "status": "coerced",
                              "note": "array of {RemoteAddress,...} -> evidences[]; inner structure only partially modeled"},
    "event.ExecutablesWritten": {"ocsf": "evidences", "status": "coerced",
                                 "note": "array of written executables w/ hashes -> evidences[]; partial"},
    "event.DnsRequests": {"ocsf": "evidences", "status": "coerced",
                          "note": "array of DNS objects -> evidences[]/observables[]; partial"},
    "event.ScanResults": {"ocsf": "unmapped", "status": "unmapped",
                          "note": "AV scan results array; no clean Detection Finding home"},
}

# --- Named detections: the fields each one depends on -----------------------
# detection-breaking = the lossy (status != typed) fields a named detection needs.
# Two detections here are clean (all fields typed) on purpose — the result is not
# "everything breaks," it is which detections break and on which field.

DETECTIONS = [
    {"name": "Anonymizing-proxy / Tor login", "source": "okta",
     "desc": "flag a login from a known anonymizing proxy",
     "fields": ["securityContext.isProxy", "securityContext.asOrg", "client.ipAddress"]},
    {"name": "Impossible travel", "source": "okta",
     "desc": "two logins too far apart in space for the time between them",
     "fields": ["client.geographicalContext.city", "client.geographicalContext.country",
                "client.geographicalContext.geolocation.lat", "client.geographicalContext.geolocation.lon",
                "client.ipAddress", "published"]},
    {"name": "MFA fatigue / push bombing", "source": "okta",
     "desc": "repeated MFA challenges of a specific factor type against one user",
     "fields": ["authenticationContext.credentialType", "outcome.result", "actor.alternateId"]},
    {"name": "ThreatInsight / risk-based signal", "source": "okta",
     "desc": "act on Okta's risk and threat signals for a sign-in",
     "fields": ["debugContext.debugData", "client.ipAddress"]},
    {"name": "Suspicious ASN", "source": "okta",
     "desc": "match the source autonomous system against a threat-intel ASN list",
     "fields": ["securityContext.asNumber", "securityContext.asOrg", "client.ipAddress"]},
    {"name": "True source IP behind proxy", "source": "okta",
     "desc": "recover the real client IP and per-hop geo from the forwarding chain",
     "fields": ["request.ipChain", "client.ipAddress"]},
    {"name": "ATT&CK technique hunt", "source": "crowdstrike",
     "desc": "pivot on a specific ATT&CK technique id across detections",
     "fields": ["event.Technique", "event.Tactic"]},
    {"name": "Multi-stage process lineage", "source": "crowdstrike",
     "desc": "reconstruct grandparent->parent->process chains for a detection",
     "fields": ["event.GrandparentImageFileName", "event.GrandparentCommandLine", "event.ParentImageFileName"]},
    {"name": "IOC pivot on indicator type", "source": "crowdstrike",
     "desc": "search by indicator type and value across detections",
     "fields": ["event.IOCType", "event.IOCValue"]},
    {"name": "Response-action audit", "source": "crowdstrike",
     "desc": "audit exactly which actions Falcon took on a detection",
     "fields": ["event.PatternDispositionValue"]},
    {"name": "Known-bad hash", "source": "crowdstrike",
     "desc": "match the executable hash against a reputation feed",
     "fields": ["event.SHA256String", "event.MD5String"]},
]

"""Task #10 — deterministic source corpora + per-record gold OCSF mapping.

The pipeline-normalization-fidelity bench feeds the SAME pinned multi-source
corpus to three pipeline tools (Tenzir / Cribl / Vector), each using its most
official shipped OCSF mapping, and scores what each tool's mapping preserves
against a gold key. This module builds that corpus and the gold key; it does
NOT run any pipeline tool (that is `score.py`, and the tools are external).

Four source classes, ~100k records each (README "sized for mapping fidelity,
not throughput; per-record"):

  zeek_conn   Zeek conn.log (network)        -> Network Activity   (4001)  [C1 class]
  cloudtrail  AWS CloudTrail (cloud audit)   -> API Activity       (6003)  [ext class]
  sysmon      Sysmon process events (EDR)    -> Process Activity   (1007)  [ext class]
  auth        authentication / identity      -> Authentication     (3002)  [C1 class]

Determinism is the whole point of a pinned corpus: everything that could vary
run-to-run is centralised in `../lib/common.py` — one master seed, one fixed
wall-clock anchor (BASE_EPOCH), no `datetime.now()`, no unseeded randomness.
A re-run reproduces every record and therefore the gold key and its digests
exactly. `--check` regenerates twice and asserts byte-identical, the same
determinism discipline as the C1 / flattening runners.

WHAT THE GOLD KEY IS (and is not)
---------------------------------
Each generated record carries, beside its raw source fields, a `_gold` block:

  class       the OCSF class the record belongs in (the semantic-fidelity answer
              for class assignment), e.g. "network_activity"
  activity_id the correct OCSF activity_id enum for this record (semantic answer)
  type_uid    class_uid*100 + activity_id (semantic answer; derivable, pinned so
              score.py never has to recompute the convention)
  fields      a per-source-field mapping in the C1 `{ocsf,status,note}` shape:
                ocsf    dotted OCSF 1.8.0 attribute path the field SHOULD land on,
                        or a catch-all ("unmapped"/"raw_data") when no typed home
                        exists. score.py validates every non-catch-all path against
                        the merged C1+ext 1.8.0 subset with C1's resolve_ocsf_path,
                        so a gold path that does not exist in the real schema fails
                        loudly — the gold key cannot invent an OCSF attribute.
                status  "typed" / "coerced" / "unmapped" — the SAME tiering C1 uses.
                        This is the field-fidelity ceiling: the best a faithful
                        mapping could do for this field. A tool that drops a
                        gold-typed field is scored lossy against it.
                value   the canonical OCSF VALUE the gold mapping produces for this
                        record (after any faithful coercion). This is the
                        value-fidelity answer key: score.py compares the tool's
                        emitted value at `ocsf` against this, so type coercion,
                        truncation, enum mistranslation and timestamp zone/precision
                        loss are caught (README scoring level 2).
  semantic    the five recurring crosswalk failure-class probes the README level 3
              checks (entity-role inversion, multi-event collapse, severity remap,
              observables flattening, context-collapse), each as a small expected
              fact score.py re-checks against the tool's emitted OCSF.

The gold mapping is the SAME judgement instrument as C1's `mapping.py`, applied
per source class at OCSF 1.8.0; it is the "hand-verified reference mapping" the
README names. It is intentionally NOT a tool's mapping — coverage != fidelity,
and the gap between "a faithful mapping could carry this" and "the shipped tool
does" is exactly what the bench measures.

This file authors the corpus + gold key. STRICT no-run discipline: generation is
a pure function of the seed; nothing here imports or executes a pipeline tool,
and `score.py` (not this) consumes a tool's emitted output.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from common import (  # noqa: E402
    BASE_EPOCH, MASTER_SEED, canonical, new_rng, sha256_file,
)

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")

# Per-source sub-seed offsets off MASTER_SEED (one private PRNG each, so the four
# corpora are independent yet fully determined by the master seed). The README
# pins ~100k per source; N_PER_SOURCE is the knob and is recorded in the manifest.
N_PER_SOURCE = 100_000
SUB_SEEDS = {"zeek_conn": 1001, "cloudtrail": 1002, "sysmon": 1003, "auth": 1004}

# Class UIDs (confirmed in the two PROVENANCE.md files against schema.ocsf.io/1.8.0).
CLASS_UID = {
    "network_activity": 4001,
    "api_activity": 6003,
    "process_activity": 1007,
    "authentication": 3002,
}

# ---------------------------------------------------------------------------
# Small deterministic value pools. Kept compact and seed-drawn so the corpus
# reproduces exactly; the point is mapping fidelity per record, not realism of
# the population. Anything drawn here goes through the per-source PRNG.
# ---------------------------------------------------------------------------
_PROTOS = ["tcp", "udp", "icmp"]
_CONN_STATES = ["SF", "S0", "REJ", "RSTO", "RSTR", "OTH"]  # Zeek conn_state
_SERVICES = ["http", "ssl", "dns", "ssh", "-"]
_AWS_SERVICES = ["s3.amazonaws.com", "iam.amazonaws.com", "sts.amazonaws.com",
                 "ec2.amazonaws.com", "kms.amazonaws.com"]
_AWS_OPS = ["GetObject", "PutObject", "AssumeRole", "Decrypt", "RunInstances",
            "ConsoleLogin", "CreateUser"]
_AWS_REGIONS = ["us-east-1", "us-west-2", "eu-west-1"]
_PROC_NAMES = ["powershell.exe", "cmd.exe", "rundll32.exe", "svchost.exe",
               "explorer.exe", "winword.exe", "mshta.exe"]
_PARENTS = ["explorer.exe", "services.exe", "winlogon.exe", "outlook.exe"]
_TZ_OFFSETS = [0, -300, -480, 60, 330, 540]  # minutes; cross-zone is a README probe


def _ip(rng, a=10):
    return f"{a}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


# ===========================================================================
# zeek_conn  ->  Network Activity (4001)
# ===========================================================================
def _gen_zeek(rng, i, t):
    proto = rng.choice(_PROTOS)
    state = rng.choice(_CONN_STATES)
    orig_bytes = rng.randint(0, 5_000_000)
    resp_bytes = rng.randint(0, 5_000_000)
    duration = round(rng.random() * 120.0, 6)
    # Zeek conn_state -> OCSF Network Activity disposition is the classic
    # enum mistranslation seam: 6 Zeek states collapse onto OCSF's few
    # disposition_id buckets, so the state field is a COERCED gold target.
    raw = {
        "ts": t + round(rng.random(), 6),
        "uid": f"C{i:09d}",
        "id.orig_h": _ip(rng, 10), "id.orig_p": rng.randint(1024, 65535),
        "id.resp_h": _ip(rng, 93), "id.resp_p": rng.choice([80, 443, 53, 22, 3389]),
        "proto": proto, "service": rng.choice(_SERVICES),
        "duration": duration, "orig_bytes": orig_bytes, "resp_bytes": resp_bytes,
        "conn_state": state, "history": "ShADadFf"[:rng.randint(2, 8)],
        "orig_pkts": rng.randint(1, 2000), "resp_pkts": rng.randint(0, 2000),
    }
    gold_fields = {
        "ts": {"ocsf": "time", "status": "typed",
               "value": int(raw["ts"] * 1000),
               "note": "epoch float seconds -> OCSF time (ms). Faithful = ms integer; truncation/zone loss is the value-fidelity probe."},
        "uid": {"ocsf": "metadata.uid", "status": "typed", "value": raw["uid"],
                "note": "Zeek connection uid -> metadata.uid"},
        "id.orig_h": {"ocsf": "src_endpoint.ip", "status": "typed", "value": raw["id.orig_h"],
                      "note": "originator host -> src_endpoint.ip (entity-role: originator==source)"},
        "id.orig_p": {"ocsf": "src_endpoint.port", "status": "typed", "value": raw["id.orig_p"],
                      "note": "originator port -> src_endpoint.port"},
        "id.resp_h": {"ocsf": "dst_endpoint.ip", "status": "typed", "value": raw["id.resp_h"],
                      "note": "responder host -> dst_endpoint.ip (entity-role: responder==destination)"},
        "id.resp_p": {"ocsf": "dst_endpoint.port", "status": "typed", "value": raw["id.resp_p"],
                      "note": "responder port -> dst_endpoint.port"},
        "proto": {"ocsf": "connection_info.protocol_name", "status": "typed", "value": raw["proto"],
                  "note": "L4 proto name -> connection_info.protocol_name"},
        "service": {"ocsf": "app_name", "status": "coerced", "value": raw["service"],
                    "note": "Zeek service label is a DPI guess, '-' means none; coerced onto app_name (lossy: '-' has no clean OCSF null)"},
        "duration": {"ocsf": "duration", "status": "coerced", "value": int(round(raw["duration"] * 1000)),
                     "note": "seconds(float) -> OCSF duration(ms int); sub-ms precision lost = value-fidelity probe"},
        "orig_bytes": {"ocsf": "traffic.bytes_out", "status": "typed", "value": raw["orig_bytes"],
                       "note": "originator bytes -> traffic.bytes_out"},
        "resp_bytes": {"ocsf": "traffic.bytes_in", "status": "typed", "value": raw["resp_bytes"],
                       "note": "responder bytes -> traffic.bytes_in"},
        "conn_state": {"ocsf": "status_code", "status": "coerced", "value": raw["conn_state"],
                       "note": "6 Zeek states collapse onto OCSF disposition buckets; raw state preserved in status_code, the enum remap is lossy (failure-class: severity/enum remap)"},
        "history": {"ocsf": "connection_info.tcp_flags", "status": "coerced", "value": raw["history"],
                    "note": "Zeek history letters are richer than OCSF tcp_flags bitmask; coerced"},
        "orig_pkts": {"ocsf": "traffic.packets_out", "status": "typed", "value": raw["orig_pkts"],
                      "note": "-> traffic.packets_out"},
        "resp_pkts": {"ocsf": "traffic.packets_in", "status": "typed", "value": raw["resp_pkts"],
                      "note": "-> traffic.packets_in"},
    }
    # Network Activity activity_id: 6 = Traffic (the conn.log grain). type_uid convention pinned.
    activity_id = 6
    semantic = {
        "entity_role": {"probe": "originator->src, responder->dst",
                        "expect": {"src_endpoint.ip": raw["id.orig_h"], "dst_endpoint.ip": raw["id.resp_h"]},
                        "note": "entity-role inversion failure-class: a tool that swaps orig/resp inverts source and destination"},
        "observables_flattening": {"probe": "src/dst ip+port present as typed endpoints, not flattened into one observables blob",
                                    "expect_paths": ["src_endpoint.ip", "dst_endpoint.ip"],
                                    "note": "observables-flattening failure-class"},
    }
    return raw, "network_activity", activity_id, gold_fields, semantic


# ===========================================================================
# cloudtrail  ->  API Activity (6003)
# ===========================================================================
def _gen_cloudtrail(rng, i, t):
    op = rng.choice(_AWS_OPS)
    svc = rng.choice(_AWS_SERVICES)
    region = rng.choice(_AWS_REGIONS)
    err = rng.random() < 0.12  # a minority error -> drives status + disposition
    raw = {
        "eventVersion": "1.09",
        "eventID": f"{i:08d}-aws-evt",
        "eventTime": _iso_utc(t),                  # CloudTrail ships ISO-8601 Z
        "eventSource": svc, "eventName": op,
        "awsRegion": region,
        "sourceIPAddress": _ip(rng, 203),
        "userIdentity.type": rng.choice(["IAMUser", "AssumedRole", "Root"]),
        "userIdentity.arn": f"arn:aws:iam::{rng.randint(10**11, 10**12):012d}:user/u{rng.randint(0, 999)}",
        "userIdentity.accountId": f"{rng.randint(10**11, 10**12):012d}",
        "userAgent": rng.choice(["aws-cli/2.15", "Boto3/1.34", "console.amazonaws.com"]),
        "errorCode": "AccessDenied" if err else None,
        "readOnly": op.startswith(("Get", "Describe", "Console")),
        "requestID": f"req-{rng.randint(0, 10**9):09d}",
    }
    gold_fields = {
        "eventVersion": {"ocsf": "metadata.product.version", "status": "typed", "value": raw["eventVersion"],
                         "note": "CloudTrail record version -> metadata.product.version (deep leaf on product)"},
        "eventID": {"ocsf": "metadata.uid", "status": "typed", "value": raw["eventID"],
                    "note": "-> metadata.uid"},
        "eventTime": {"ocsf": "time", "status": "coerced", "value": _epoch_ms(t),
                      "note": "ISO-8601 Z string -> OCSF time(ms int); parse + zone normalise. A tool keeping wall-clock string or dropping TZ is the timestamp value-fidelity probe"},
        "eventSource": {"ocsf": "api.service.name", "status": "typed", "value": raw["eventSource"],
                        "note": "service endpoint -> api.service.name (service is a deep object)"},
        "eventName": {"ocsf": "api.operation", "status": "typed", "value": raw["eventName"],
                      "note": "API call -> api.operation"},
        "awsRegion": {"ocsf": "cloud.region", "status": "typed", "value": raw["awsRegion"],
                      "note": "-> cloud.region (cloud is deep)"},
        "sourceIPAddress": {"ocsf": "src_endpoint.ip", "status": "coerced", "value": raw["sourceIPAddress"],
                            "note": "CloudTrail sourceIPAddress can be a service DNS name, not an IP; coerced onto src_endpoint.ip (a non-IP value is the coercion seam)"},
        "userIdentity.type": {"ocsf": "actor.user.type", "status": "typed", "value": raw["userIdentity.type"],
                              "note": "-> actor.user.type"},
        "userIdentity.arn": {"ocsf": "actor.user.uid", "status": "typed", "value": raw["userIdentity.arn"],
                             "note": "principal ARN -> actor.user.uid"},
        "userIdentity.accountId": {"ocsf": "cloud.account.uid", "status": "typed", "value": raw["userIdentity.accountId"],
                                   "note": "-> cloud.account.uid (account deep under cloud)"},
        "userAgent": {"ocsf": "http_request.user_agent", "status": "typed", "value": raw["userAgent"],
                      "note": "-> http_request.user_agent"},
        "errorCode": {"ocsf": "status_detail", "status": "coerced", "value": raw["errorCode"],
                      "note": "presence/absence of errorCode drives status_id; the string lands in status_detail. Absence==success is the absence-vs-null seam"},
        "readOnly": {"ocsf": "unmapped", "status": "unmapped", "value": raw["readOnly"],
                     "note": "no typed OCSF home for the read-only flag; lands in unmapped"},
        "requestID": {"ocsf": "api.request.uid", "status": "typed", "value": raw["requestID"],
                      "note": "-> api.request.uid (request is a deep object)"},
    }
    # API Activity activity_id: 1=Create 2=Read 3=Update 4=Delete; pick by op verb (semantic answer key).
    activity_id = _aws_activity(op)
    semantic = {
        "severity_remap": {"probe": "an error event maps to a non-Informational severity, success stays Informational",
                           "expect": {"is_error": bool(err)},
                           "note": "severity-remap failure-class: errorCode presence must lift severity, not be dropped"},
        "context_collapse": {"probe": "service + operation kept as distinct api.* fields, not collapsed into one event_name string",
                             "expect_paths": ["api.service.name", "api.operation"],
                             "note": "context-collapse failure-class"},
    }
    return raw, "api_activity", activity_id, gold_fields, semantic


# ===========================================================================
# sysmon  ->  Process Activity (1007)
# ===========================================================================
def _gen_sysmon(rng, i, t):
    name = rng.choice(_PROC_NAMES)
    parent = rng.choice(_PARENTS)
    pid = rng.randint(400, 60000)
    ppid = rng.randint(400, 60000)
    raw = {
        "EventID": 1,  # Sysmon process-create
        "UtcTime": _sysmon_time(t),                # Sysmon "YYYY-MM-DD HH:MM:SS.mmm" (UTC, no offset)
        "ProcessGuid": "{%08x-0000-0000-0000-000000000000}" % (i & 0xFFFFFFFF),
        "ProcessId": pid,
        "Image": f"C:\\Windows\\System32\\{name}",
        "CommandLine": f"{name} -enc {rng.randint(0, 10**9)}",
        "User": f"CORP\\u{rng.randint(0, 999)}",
        "Hashes": f"SHA256={rng.getrandbits(256):064x}",
        "ParentProcessId": ppid,
        "ParentImage": f"C:\\Windows\\explorer\\{parent}",
        "ParentCommandLine": f"{parent}",
        "IntegrityLevel": rng.choice(["Low", "Medium", "High", "System"]),
        "LogonId": f"0x{rng.randint(0, 10**7):x}",
    }
    gold_fields = {
        "EventID": {"ocsf": "activity_id", "status": "coerced", "value": 1,
                    "note": "Sysmon EventID 1 (process-create) selects OCSF activity_id=1 (Launch); the numeric id is remapped, not carried (enum remap)"},
        "UtcTime": {"ocsf": "time", "status": "coerced", "value": _epoch_ms(t),
                    "note": "Sysmon UtcTime 'YYYY-MM-DD HH:MM:SS.mmm' has NO offset; faithful parse assumes UTC -> time(ms). A tool parsing it as local time is the timestamp-zone value-fidelity probe"},
        "ProcessGuid": {"ocsf": "process.uid", "status": "typed", "value": raw["ProcessGuid"],
                        "note": "-> process.uid"},
        "ProcessId": {"ocsf": "process.pid", "status": "typed", "value": raw["ProcessId"],
                      "note": "-> process.pid"},
        "Image": {"ocsf": "process.file.path", "status": "typed", "value": raw["Image"],
                  "note": "full image path -> process.file.path"},
        "CommandLine": {"ocsf": "process.cmd_line", "status": "typed", "value": raw["CommandLine"],
                        "note": "-> process.cmd_line"},
        "User": {"ocsf": "actor.user.name", "status": "typed", "value": raw["User"],
                 "note": "DOMAIN\\user -> actor.user.name"},
        "Hashes": {"ocsf": "process.file.hashes", "status": "coerced", "value": raw["Hashes"],
                   "note": "Sysmon packs algo=value (and may multi-hash) into one string; OCSF wants a fingerprint array (algorithm_id,value). String->array split is the coercion (observables flattening if dropped)"},
        "ParentProcessId": {"ocsf": "process.parent_process.pid", "status": "typed", "value": raw["ParentProcessId"],
                            "note": "-> process.parent_process.pid (process tree edge)"},
        "ParentImage": {"ocsf": "process.parent_process.file.path", "status": "typed", "value": raw["ParentImage"],
                        "note": "-> process.parent_process.file.path"},
        "ParentCommandLine": {"ocsf": "process.parent_process.cmd_line", "status": "typed", "value": raw["ParentCommandLine"],
                              "note": "-> process.parent_process.cmd_line; many shipped mappings drop the parent cmdline (multi-event/lineage collapse)"},
        "IntegrityLevel": {"ocsf": "process.integrity", "status": "coerced", "value": raw["IntegrityLevel"],
                           "note": "Low/Medium/High/System label -> process.integrity (string) + integrity_id enum; label kept, id remap is the coercion"},
        "LogonId": {"ocsf": "session.uid", "status": "typed", "value": raw["LogonId"],
                    "note": "Windows LogonId -> session.uid"},
    }
    activity_id = 1  # Launch
    semantic = {
        "multi_event_collapse": {"probe": "parent process kept as a distinct nested process, not collapsed so the lineage edge is lost",
                                 "expect_paths": ["process.parent_process.pid", "process.parent_process.file.path"],
                                 "note": "multi-event/lineage-collapse failure-class: the process tree is where EDR mappings lose the most (README P2)"},
        "observables_flattening": {"probe": "the SHA256 hash survives as a typed fingerprint, not lost when the algo=value string is flattened",
                                   "expect_paths": ["process.file.hashes"],
                                   "note": "observables-flattening failure-class"},
    }
    return raw, "process_activity", activity_id, gold_fields, semantic


# ===========================================================================
# auth  ->  Authentication (3002)
# ===========================================================================
def _gen_auth(rng, i, t):
    success = rng.random() < 0.8
    mfa = rng.random() < 0.6
    tz = rng.choice(_TZ_OFFSETS)
    raw = {
        "event_id": f"auth-{i:08d}",
        "timestamp": _iso_offset(t, tz),           # local wall-clock + numeric offset
        "user_name": f"u{rng.randint(0, 9999)}@corp.example",
        "user_id": f"S-1-5-21-{rng.randint(0, 10**9)}",
        "src_ip": _ip(rng, 198),
        "dst_host": f"host{rng.randint(0, 200)}.corp.example",
        "auth_protocol": rng.choice(["Kerberos", "NTLM", "SAML", "OIDC"]),
        "logon_type": rng.choice(["Interactive", "Network", "RemoteInteractive", "Service"]),
        "result": "SUCCESS" if success else rng.choice(["FAILURE", "DENY", "CHALLENGE"]),
        "mfa": mfa,
        "failure_reason": None if success else rng.choice(["BAD_PASSWORD", "LOCKED_OUT", "EXPIRED"]),
        "tz_offset_min": tz,
    }
    gold_fields = {
        "event_id": {"ocsf": "metadata.uid", "status": "typed", "value": raw["event_id"],
                     "note": "-> metadata.uid"},
        "timestamp": {"ocsf": "time", "status": "coerced", "value": _epoch_ms(t),
                      "note": "local wall-clock + numeric offset -> OCSF time(ms) at UTC; the offset must be applied. Dropping it floats the timestamp (timestamp-zone value-fidelity probe, cross-zone correlation seam)"},
        "user_name": {"ocsf": "user.name", "status": "typed", "value": raw["user_name"],
                      "note": "-> user.name"},
        "user_id": {"ocsf": "user.uid", "status": "typed", "value": raw["user_id"],
                    "note": "SID -> user.uid"},
        "src_ip": {"ocsf": "src_endpoint.ip", "status": "typed", "value": raw["src_ip"],
                   "note": "-> src_endpoint.ip (the authenticating client)"},
        "dst_host": {"ocsf": "dst_endpoint.hostname", "status": "typed", "value": raw["dst_host"],
                     "note": "target host -> dst_endpoint.hostname (entity-role: dst is the service being authenticated to)"},
        "auth_protocol": {"ocsf": "auth_protocol", "status": "coerced", "value": raw["auth_protocol"],
                          "note": "free string -> auth_protocol(string) + auth_protocol_id enum; id remap is the coercion (Kerberos/NTLM map cleanly, SAML/OIDC narrow)"},
        "logon_type": {"ocsf": "logon_type", "status": "coerced", "value": raw["logon_type"],
                       "note": "Windows logon-type label -> logon_type + logon_type_id enum; id remap is the coercion"},
        "result": {"ocsf": "status_id", "status": "coerced", "value": raw["result"],
                   "note": "SUCCESS/FAILURE/DENY/CHALLENGE collapses onto OCSF status_id (Success/Failure/Unknown); CHALLENGE has no clean bucket (enum mistranslation)"},
        "mfa": {"ocsf": "is_mfa", "status": "typed", "value": raw["mfa"],
                "note": "-> is_mfa (boolean; absence must NOT become false — absence-vs-null seam)"},
        "failure_reason": {"ocsf": "status_detail", "status": "coerced", "value": raw["failure_reason"],
                           "note": "failure detail -> status_detail; null on success (absence-vs-null seam)"},
        "tz_offset_min": {"ocsf": "timezone_offset", "status": "typed", "value": raw["tz_offset_min"],
                          "note": "the source offset -> timezone_offset; a tool that drops it cannot reconstruct UTC"},
    }
    # Authentication activity_id: 1=Logon 2=Logoff 3=AuthTicket 4=ServiceTicket; here Logon.
    activity_id = 1
    semantic = {
        "severity_remap": {"probe": "a failed auth lifts severity above Informational",
                           "expect": {"is_failure": not success},
                           "note": "severity-remap failure-class"},
        "context_collapse": {"probe": "src (client) and dst (target host) kept distinct, not collapsed to one endpoint",
                             "expect_paths": ["src_endpoint.ip", "dst_endpoint.hostname"],
                             "note": "entity-role / context-collapse: a tool that puts the target host in src inverts the auth direction"},
    }
    return raw, "authentication", activity_id, gold_fields, semantic


# ---------------------------------------------------------------------------
# timestamp helpers — all anchored on the FIXED BASE_EPOCH, never the wall clock.
# Different string SHAPES per source on purpose: each source ships its own
# timestamp idiom, and the value-fidelity probes (zone/precision loss) need the
# original shape to be faithfully reconstructible to one canonical UTC ms.
# ---------------------------------------------------------------------------
def _epoch_ms(t):
    return int(t) * 1000


def _iso_utc(t):
    import time as _time
    return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(int(t)))


def _sysmon_time(t):
    import time as _time
    return _time.strftime("%Y-%m-%d %H:%M:%S", _time.gmtime(int(t))) + ".000"


def _iso_offset(t, off_min):
    # Render the SAME instant t as a local wall-clock string with a numeric
    # offset, so dropping the offset visibly floats it. t is the true UTC second.
    import time as _time
    local = int(t) + off_min * 60
    sign = "+" if off_min >= 0 else "-"
    a = abs(off_min)
    base = _time.strftime("%Y-%m-%dT%H:%M:%S", _time.gmtime(local))
    return f"{base}{sign}{a // 60:02d}:{a % 60:02d}"


def _aws_activity(op):
    if op.startswith(("Get", "Describe", "List", "Console")):
        return 2  # Read
    if op.startswith(("Put", "Create", "Run")):
        return 1  # Create
    if op.startswith(("Update", "Modify", "Assume", "Decrypt")):
        return 3  # Update
    if op.startswith("Delete"):
        return 4  # Delete
    return 0  # Unknown


# ---------------------------------------------------------------------------
# corpus assembly
# ---------------------------------------------------------------------------
_GENERATORS = {
    "zeek_conn": _gen_zeek,
    "cloudtrail": _gen_cloudtrail,
    "sysmon": _gen_sysmon,
    "auth": _gen_auth,
}
# README "fixed wall-clock anchor"; spread events over a window off BASE_EPOCH.
_WINDOW_S = 7 * 86_400


def generate_source(source, n=N_PER_SOURCE):
    """Deterministically build `n` records for one source. Each record is
    {raw fields..., "_gold": {...}}. Pure function of the seed; no clock."""
    rng = new_rng(SUB_SEEDS[source])
    gen = _GENERATORS[source]
    records = []
    for i in range(n):
        # ordered, seed-drawn timestamp within the window (no datetime.now())
        t = BASE_EPOCH + rng.randint(0, _WINDOW_S - 1)
        raw, ocsf_class, activity_id, gold_fields, semantic = gen(rng, i, t)
        class_uid = CLASS_UID[ocsf_class]
        rec = dict(raw)
        rec["_gold"] = {
            "class": ocsf_class,
            "class_uid": class_uid,
            "activity_id": activity_id,
            "type_uid": class_uid * 100 + activity_id,
            "fields": gold_fields,
            "semantic": semantic,
        }
        records.append(rec)
    # Stable order keyed on each source's record id, so the JSONL digest is
    # reproducible regardless of how records were appended.
    records.sort(key=_record_sort_key)
    return records


def _record_sort_key(rec):
    """A stable per-source record id for deterministic ordering."""
    for k in ("uid", "eventID", "ProcessGuid", "event_id"):
        if k in rec:
            return (k, rec[k])
    return ("", canonical(rec))


def _gold_class_summary(records):
    """Field-fidelity ceiling per source: the typed/coerced/unmapped split the
    gold key itself implies (the best a faithful mapping could do). Mirrors the
    C1 summary shape so RESULTS.md tables line up across C1 and this bench."""
    # All records of a source share the same field schema, so summarise the first.
    fields = records[0]["_gold"]["fields"]
    total = len(fields)
    typed = sum(1 for r in fields.values() if r["status"] == "typed")
    coerced = sum(1 for r in fields.values() if r["status"] == "coerced")
    unmapped = sum(1 for r in fields.values() if r["status"] == "unmapped")
    return {
        "total_fields": total, "typed": typed, "coerced": coerced, "unmapped": unmapped,
        "gold_coverage": round(typed / total, 4),
        "gold_coverage_incl_coerced": round((typed + coerced) / total, 4),
    }


def write_source(source, records):
    os.makedirs(WORK, exist_ok=True)
    corpus_path = os.path.join(WORK, f"{source}.corpus.jsonl")
    gold_path = os.path.join(WORK, f"{source}.gold.jsonl")
    with open(corpus_path, "w") as cf, open(gold_path, "w") as gf:
        for rec in records:
            gold = rec["_gold"]
            rec_id = _record_sort_key(rec)[1]
            raw = {k: v for k, v in rec.items() if k != "_gold"}
            # corpus = exactly what a pipeline tool ingests (raw source fields, no
            # answer key) PLUS an explicit `_id` the tool must carry through to its
            # emitted OCSF as `_id` so score.py can join emitted->gold. The id is
            # already a real source field (uid / eventID / ProcessGuid / event_id);
            # `_id` is the stable, source-agnostic alias of it.
            raw["_id"] = rec_id
            cf.write(canonical(raw) + "\n")
            # gold = the answer key, joined to the corpus row by the record id
            gf.write(canonical({"_id": _record_sort_key(rec)[1], **gold}) + "\n")
    return corpus_path, gold_path


def write_manifest(per_source):
    """Pin every corpus + gold file by sha256 (the repo's 'pin the artifact'
    discipline; these JSONL files are single-threaded writes so the byte hash is
    reproducible, unlike a parallel Parquet write)."""
    manifest = {
        "benchmark": "pipeline-normalization-fidelity (task #10)",
        "master_seed": MASTER_SEED,
        "base_epoch": BASE_EPOCH,
        "n_per_source": N_PER_SOURCE,
        "window_seconds": _WINDOW_S,
        "ocsf_version": "1.8.0",
        "sources": {},
    }
    for source, info in per_source.items():
        manifest["sources"][source] = {
            "ocsf_class": info["class"],
            "class_uid": CLASS_UID[info["class"]],
            "records": info["records"],
            "gold_field_ceiling": info["summary"],
            "corpus_file": os.path.basename(info["corpus_path"]),
            "corpus_sha256": sha256_file(info["corpus_path"]),
            "gold_file": os.path.basename(info["gold_path"]),
            "gold_sha256": sha256_file(info["gold_path"]),
        }
    path = os.path.join(WORK, "corpus_manifest.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    return path, manifest


def main():
    ap = argparse.ArgumentParser(
        description="Generate the pinned 4-source corpus + gold OCSF key for the "
                    "pipeline-normalization-fidelity bench (task #10). Authoring only; "
                    "no pipeline tool is run here.")
    ap.add_argument("--n", type=int, default=N_PER_SOURCE,
                    help=f"records per source (default {N_PER_SOURCE}, the pre-registered ~100k)")
    ap.add_argument("--sources", nargs="*", default=list(SUB_SEEDS),
                    choices=list(SUB_SEEDS),
                    help="subset of sources to generate (default: all four)")
    ap.add_argument("--check", action="store_true",
                    help="regenerate each source twice and assert byte-identical (determinism gate); "
                         "does not write")
    ap.add_argument("--no-write", action="store_true",
                    help="generate + report but do not write corpus/gold/manifest files")
    args = ap.parse_args()

    if args.check:
        ok = True
        for source in args.sources:
            a = generate_source(source, args.n)
            b = generate_source(source, args.n)
            same = canonical(a) == canonical(b)
            ok = ok and same
            print(f"  {source:11s} n={len(a):6d}  determinism: {'OK' if same else 'FAIL'}")
        print(f"determinism: {'OK' if ok else 'FAIL'}")
        raise SystemExit(0 if ok else 1)

    per_source = {}
    for source in args.sources:
        records = generate_source(source, args.n)
        summary = _gold_class_summary(records)
        info = {"class": records[0]["_gold"]["class"], "records": len(records), "summary": summary}
        if not args.no_write:
            cpath, gpath = write_source(source, records)
            info["corpus_path"] = cpath
            info["gold_path"] = gpath
        per_source[source] = info
        s = summary
        print(f"  {source:11s} -> {info['class']:18s} ({CLASS_UID[info['class']]})  "
              f"records={info['records']:6d}  gold-fields={s['total_fields']:2d} "
              f"typed={s['typed']:2d} coerced={s['coerced']:2d} unmapped={s['unmapped']:2d}  "
              f"gold-coverage={s['gold_coverage']:.2f}")

    if not args.no_write:
        mpath, _ = write_manifest(per_source)
        print(f"wrote {len(per_source)} source corpora + gold keys + manifest under {WORK}/")
        print(f"manifest: {mpath}")
    else:
        print("(--no-write: nothing written)")


if __name__ == "__main__":
    main()

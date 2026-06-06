"""Project the OTRF Security-Datasets APT29 day-1 telemetry into per-logsource tables.

The de-gamed version of BENCH-A: instead of a lab-generated corpus with a planted chain whose
indicators the lab also chose, this uses a **real public attack dataset** (MITRE ATT&CK APT29 evaluation,
collected by OTRF/Mordor) that **unmodified upstream SigmaHQ rules are written against**. We keep the
**canonical Sigma field names** as columns (Image, CommandLine, DestinationPort, QueryName,
TargetUserName, …) so a rule compiled by pySigma runs over the store with only a table-name substitution
— no hand field-mapping that could bias which rules fire.

Output (one parquet per Sigma logsource category, under _work/raw/):
  process_creation  (Sysmon EventID 1)
  network_connection(Sysmon EventID 3)
  dns_query         (Sysmon EventID 22)
  authentication    (Security 4624/4625)
  ps_script         (PowerShell 4104)

Two timestamps are carried on every row: _event_ms (UtcTime — when it happened) and _ingest_ms
(EventReceivedTime — when the pipeline saw it). Store N's documented time-collapse uses _ingest_ms only.
"""

import glob
import json
import os
import sys
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")
RAW = os.path.join(WORK, "raw")


def _ms(s):
    """'2020-05-02 02:55:56.157' (UTC) -> epoch ms; tolerant of missing fractional secs."""
    if not s or s == "-":
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return int(datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).timestamp() * 1000)
        except ValueError:
            continue
    return None


# Sigma logsource category -> (EventID match, list of canonical fields to project from the raw event)
PROJECTIONS = {
    "process_creation": {
        "match": lambda e: e.get("EventID") == 1 and "Sysmon" in e.get("Channel", ""),
        "fields": ["Image", "CommandLine", "ParentImage", "ParentCommandLine", "User", "Hostname",
                   "ProcessGuid", "OriginalFileName", "CurrentDirectory", "IntegrityLevel",
                   "Company", "Description", "Product", "Hashes"],
    },
    "network_connection": {
        "match": lambda e: e.get("EventID") == 3 and "Sysmon" in e.get("Channel", ""),
        "fields": ["Image", "SourceIp", "SourcePort", "DestinationIp", "DestinationPort",
                   "DestinationHostname", "Protocol", "User", "Hostname", "Initiated"],
    },
    "dns_query": {
        "match": lambda e: e.get("EventID") == 22 and "Sysmon" in e.get("Channel", ""),
        "fields": ["QueryName", "QueryResults", "QueryStatus", "Image", "Hostname"],
    },
    "authentication": {
        "match": lambda e: e.get("EventID") in (4624, 4625),
        "fields": ["TargetUserName", "TargetDomainName", "LogonType", "IpAddress", "IpPort",
                   "WorkstationName", "AuthenticationPackageName", "Hostname", "SubjectUserName",
                   "ProcessName", "Status"],
    },
    "ps_script": {
        "match": lambda e: e.get("EventID") == 4104,
        "fields": ["ScriptBlockText", "Path", "Hostname"],
    },
    "image_load": {
        "match": lambda e: e.get("EventID") == 7 and "Sysmon" in e.get("Channel", ""),
        "fields": ["Image", "ImageLoaded", "Signature", "SignatureStatus", "Signed", "Hashes",
                   "OriginalFileName", "Company", "Description", "Product", "Hostname"],
    },
    "file_event": {
        "match": lambda e: e.get("EventID") == 11 and "Sysmon" in e.get("Channel", ""),
        "fields": ["Image", "TargetFilename", "CreationUtcTime", "Hostname"],
    },
    "registry_event": {
        "match": lambda e: e.get("EventID") in (12, 13, 14) and "Sysmon" in e.get("Channel", ""),
        "fields": ["EventType", "TargetObject", "Details", "Image", "NewName", "Hostname"],
    },
    "process_access": {
        "match": lambda e: e.get("EventID") == 10 and "Sysmon" in e.get("Channel", ""),
        "fields": ["SourceImage", "TargetImage", "GrantedAccess", "CallTrace",
                   "SourceProcessGUID", "TargetProcessGUID", "Hostname"],
    },
    "create_remote_thread": {
        "match": lambda e: e.get("EventID") == 8 and "Sysmon" in e.get("Channel", ""),
        "fields": ["SourceImage", "TargetImage", "StartAddress", "StartFunction", "StartModule",
                   "Hostname"],
    },
    "pipe_created": {
        "match": lambda e: e.get("EventID") in (17, 18) and "Sysmon" in e.get("Channel", ""),
        "fields": ["PipeName", "Image", "Hostname"],
    },
}


def project():
    os.makedirs(RAW, exist_ok=True)
    src = glob.glob(os.path.join(WORK, "apt29_evals_day1_manual_*.json"))
    if not src:
        sys.exit("APT29 day-1 JSON not found in _work/ — download+extract apt29_day1.zip first.")
    rows = {k: [] for k in PROJECTIONS}
    n = 0
    with open(src[0]) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            n += 1
            for cat, spec in PROJECTIONS.items():
                if spec["match"](e):
                    row = {fld: e.get(fld) for fld in spec["fields"]}
                    row["_event_ms"] = _ms(e.get("UtcTime") or e.get("EventTime"))
                    row["_ingest_ms"] = _ms(e.get("EventReceivedTime")) or row["_event_ms"]
                    row["_host"] = e.get("Hostname") or e.get("host")
                    rows[cat].append(row)
                    break
    summary = {}
    for cat, rs in rows.items():
        cols = PROJECTIONS[cat]["fields"] + ["_event_ms", "_ingest_ms", "_host"]
        # every column as string except the two time columns; pyarrow infers from pydict of lists
        table = pa.table({c: pa.array([str(r.get(c)) if (r.get(c) is not None and c not in
                                       ("_event_ms", "_ingest_ms")) else r.get(c) for r in rs])
                          for c in cols}) if rs else pa.table({c: pa.array([], type=pa.string())
                                                               for c in cols})
        pq.write_table(table, os.path.join(RAW, f"{cat}.parquet"))
        summary[cat] = len(rs)
    summary["_total_events_scanned"] = n
    json.dump(summary, open(os.path.join(WORK, "projection_summary.json"), "w"), indent=2)
    print("projected:", json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    project()

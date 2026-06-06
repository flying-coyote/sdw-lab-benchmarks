"""Build Store F (fidelity) and Store N (documented coarsening) from the projected APT29 raw.

Both stores carry the SAME columns (canonical Sigma field names) so a single pySigma-compiled rule runs
against either with only a table-name substitution — the only variable is the coarsening, applied blind
to the rules. Coarsening knobs are the documented volume-driven defaults (see STORE-N-NORMALIZATION.md):
command-line / script-block truncation, rare-DNS sampling, dropping high-cost auxiliary fields
(ParentCommandLine, Hashes, QueryResults), and a single ingestion timestamp. None of these is chosen to
make a particular rule fail; they are what a cost-pressured normalization does, and the rules were cloned
from upstream SigmaHQ without knowledge of the coarsening.
"""

import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_work", "raw")
WORK = os.path.join(HERE, "_work")
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import configure_duckdb  # noqa: E402

CMDLINE_TRUNC = 64      # documented field-length cap (long-arg payloads lost past it)
SCRIPT_TRUNC = 64       # same cap applied to PowerShell script blocks
DNS_RARE_MIN = 3        # rare-query sampling: drop QueryName seen fewer than this many times

TABLES = ["process_creation", "network_connection", "dns_query", "authentication", "ps_script",
          "image_load", "file_event", "registry_event", "process_access", "create_remote_thread",
          "pipe_created"]


def _views(con):
    for t in TABLES:
        con.execute(f"CREATE OR REPLACE VIEW raw_{t} AS SELECT * FROM '{RAW}/{t}.parquet'")


def build_store_f(con):
    d = os.path.join(WORK, "store_f"); os.makedirs(d, exist_ok=True)
    for t in TABLES:
        con.execute(f"COPY (SELECT * FROM raw_{t}) TO '{d}/{t}.parquet' (FORMAT parquet)")
    return d


def build_store_n(con, cmd_trunc=CMDLINE_TRUNC, script_trunc=SCRIPT_TRUNC, dns_rare_min=DNS_RARE_MIN):
    d = os.path.join(WORK, "store_n"); os.makedirs(d, exist_ok=True)

    # process_creation: cmdline truncated; ParentCommandLine + hashes/origname/company/desc/product/
    # currentdir dropped (high-cost auxiliary fields a lean normalization sheds); time -> ingest only.
    con.execute(f"""COPY (
        SELECT Image, left(CommandLine, {cmd_trunc}) AS CommandLine, ParentImage,
               NULL AS ParentCommandLine, User, Hostname, NULL AS ProcessGuid,
               NULL AS OriginalFileName, NULL AS CurrentDirectory, IntegrityLevel,
               NULL AS Company, NULL AS Description, NULL AS Product, NULL AS Hashes,
               _ingest_ms AS _event_ms, _ingest_ms, _host
        FROM raw_process_creation) TO '{d}/process_creation.parquet' (FORMAT parquet)""")

    # network_connection: dst kept (rules key it), SourcePort/Initiated dropped; time -> ingest.
    con.execute(f"""COPY (
        SELECT Image, SourceIp, NULL AS SourcePort, DestinationIp, DestinationPort,
               DestinationHostname, Protocol, User, Hostname, NULL AS Initiated,
               _ingest_ms AS _event_ms, _ingest_ms, _host
        FROM raw_network_connection) TO '{d}/network_connection.parquet' (FORMAT parquet)""")

    # dns_query: rare queries sampled out; QueryResults dropped; time -> ingest.
    con.execute(f"""COPY (
        SELECT QueryName, NULL AS QueryResults, QueryStatus, Image, Hostname,
               _ingest_ms AS _event_ms, _ingest_ms, _host
        FROM raw_dns_query
        WHERE QueryName IN (SELECT QueryName FROM raw_dns_query GROUP BY QueryName
                            HAVING count(*) >= {dns_rare_min})
        ) TO '{d}/dns_query.parquet' (FORMAT parquet)""")

    # authentication: workstation/process/subject dropped (identity flattened to target); time -> ingest.
    con.execute(f"""COPY (
        SELECT TargetUserName, TargetDomainName, LogonType, IpAddress, NULL AS IpPort,
               NULL AS WorkstationName, AuthenticationPackageName, Hostname,
               NULL AS SubjectUserName, NULL AS ProcessName, Status,
               _ingest_ms AS _event_ms, _ingest_ms, _host
        FROM raw_authentication) TO '{d}/authentication.parquet' (FORMAT parquet)""")

    # ps_script: script block truncated (the big one — encoded/obfuscated blocks lost past the cap).
    con.execute(f"""COPY (
        SELECT left(ScriptBlockText, {script_trunc}) AS ScriptBlockText, Path, Hostname,
               _ingest_ms AS _event_ms, _ingest_ms, _host
        FROM raw_ps_script) TO '{d}/ps_script.parquet' (FORMAT parquet)""")

    # image_load: signature/hash/origname/company/desc/product dropped (auxiliary enrichment a lean
    # normalization sheds → rules keying unsigned/hash/originalfilename go blind); keep image paths.
    con.execute(f"""COPY (
        SELECT Image, ImageLoaded, NULL AS Signature, NULL AS SignatureStatus, NULL AS Signed,
               NULL AS Hashes, NULL AS OriginalFileName, NULL AS Company, NULL AS Description,
               NULL AS Product, Hostname, _ingest_ms AS _event_ms, _ingest_ms, _host
        FROM raw_image_load) TO '{d}/image_load.parquet' (FORMAT parquet)""")

    # file_event: keep target filename + image (a lean store keeps the core); time -> ingest.
    con.execute(f"""COPY (
        SELECT Image, TargetFilename, NULL AS CreationUtcTime, Hostname,
               _ingest_ms AS _event_ms, _ingest_ms, _host
        FROM raw_file_event) TO '{d}/file_event.parquet' (FORMAT parquet)""")

    # registry_event: Details truncated (long values lost), NewName dropped; keep object + image.
    con.execute(f"""COPY (
        SELECT EventType, TargetObject, left(Details, {cmd_trunc}) AS Details, Image,
               NULL AS NewName, Hostname, _ingest_ms AS _event_ms, _ingest_ms, _host
        FROM raw_registry_event) TO '{d}/registry_event.parquet' (FORMAT parquet)""")

    # process_access: CallTrace truncated (the discriminating field for LSASS-access rules), GUIDs
    # dropped; keep source/target image + granted access.
    con.execute(f"""COPY (
        SELECT SourceImage, TargetImage, GrantedAccess, left(CallTrace, {cmd_trunc}) AS CallTrace,
               NULL AS SourceProcessGUID, NULL AS TargetProcessGUID, Hostname,
               _ingest_ms AS _event_ms, _ingest_ms, _host
        FROM raw_process_access) TO '{d}/process_access.parquet' (FORMAT parquet)""")

    # create_remote_thread: StartAddress/StartFunction dropped (rules key them); keep images + module.
    con.execute(f"""COPY (
        SELECT SourceImage, TargetImage, NULL AS StartAddress, NULL AS StartFunction, StartModule,
               Hostname, _ingest_ms AS _event_ms, _ingest_ms, _host
        FROM raw_create_remote_thread) TO '{d}/create_remote_thread.parquet' (FORMAT parquet)""")

    # pipe_created: keep pipe name + image; time -> ingest (a near-control — little to coarsen).
    con.execute(f"""COPY (
        SELECT PipeName, Image, Hostname, _ingest_ms AS _event_ms, _ingest_ms, _host
        FROM raw_pipe_created) TO '{d}/pipe_created.parquet' (FORMAT parquet)""")
    return d


def _bytes(p):
    return sum(os.path.getsize(os.path.join(p, f)) for f in os.listdir(p) if f.endswith(".parquet"))


def build(con=None):
    own = con is None
    if own:
        con = configure_duckdb(duckdb.connect(":memory:"))
    _views(con)
    f = build_store_f(con)
    n = build_store_n(con)
    cost = {"store_f_bytes": _bytes(f), "store_n_bytes": _bytes(n)}
    if own:
        con.close()
    return cost


if __name__ == "__main__":
    print(build())

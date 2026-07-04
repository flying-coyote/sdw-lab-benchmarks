"""Normalize the EvidenceForge branch-office-example raw corpus into OCSF-shaped DuckDB/parquet
tables, using the SAME table + column names Store F uses (bench-a-context-collapse/stores.py), so
run_arm.py can compile and execute the 4 committed sigma rules (rules/*.yml) unchanged against a
realistic, independently-generated corpus instead of the synthetic BENCH-A testbed.

Provenance: EvidenceForge @ 7cbcc6a9, scenario scenarios/branch-office-example/scenario.yaml
(pinned copy: scenario.pinned.yaml), eval 97.12/100 acceptance_passed=True. Regeneration:
  ~/.local/bin/uv run eforge generate scenarios/branch-office-example/scenario.yaml -o <out> --force
(deterministic — internal seed 42 + the pinned time_window; no runtime --seed flag).

SCOPE — this is a minimal, rule-driven mapping, not a full crosswalk-fidelity instrument. Only the
fields the 4 committed rules (rules/*.yml) and the ground-truth join need are carried:

  network (class_uid 4001)  <- Zeek conn.json (ZEEK-BO-CORE), all rows.
  dns     (class_uid 4003)  <- Zeek dns.json (ZEEK-BO-CORE), all rows.
  process (class_uid 1007)  <- Sysmon EventID 1 (ProcessCreate) + Windows Security EventID 4688
                                (process-creation audit), UNIONED across the 7 Windows hosts and
                                NOT deduplicated -- two independent sensors seeing the same process
                                is realistic dual EDR + native-audit-log visibility, not double
                                counting a bug. Linux process telemetry (WEB-BO-01's ecar-sourced
                                recon: `id`, `ip addr`, `ss -tulpn`) is explicitly OUT of scope for
                                this table -- the mission scoped process normalization to the two
                                Windows-native sources, so the web-tier recon steps (evt-002/evt-003)
                                do not appear here. That is a scope decision, not a corpus gap.
  api     (class_uid 6003)  <- cloudtrail. NO SOURCE EXISTS: this on-prem branch-office scenario has
                                no AWS/cloud activity at all. Built as an empty, correctly-typed
                                0-row table -- a scenario-scope finding (the rule is architecturally
                                untestable here), not a normalization miss.
  auth    (class_uid 3002)  <- Windows Security EventID 4624/4625. SUPPORTING table only; no rule
                                queries it. Included because the mission asked for an Authentication
                                mapping and because it independently carries the red-herring
                                (rh-001, victor.hale's failed VPN reconnect).
  http    (class_uid 4002)  <- proxy_access.log (Squid explicit-proxy CONNECT log). SUPPORTING /
                                corroboration table only; none of the 4 rules queries an http/proxy
                                category. Kept because it is the ONLY source that ties the C2 beacon
                                back to nina.kapoor's real workstation identity -- see the
                                proxy-indirection note below -- and because run_arm.py uses it to
                                independently corroborate the c2_domain miss without changing the
                                rule's verdict.

Host/IP map: parsed from scenario.pinned.yaml's environment.systems list (not hardcoded), so this
normalizer and the pinned scenario can never drift apart.

STRUCTURAL QUIRK CARRIED THROUGH HONESTLY, NOT PAPERED OVER: the explicit forward proxy
(PROXY-BO-01, 10.44.20.30) resolves DNS and holds the outbound TLS session on behalf of proxied
clients. So Zeek (the network-sensor vantage point) sees PROXY-BO-01 as the dns/network src_ip for
the C2 beacon, not WS-NKAPOOR-01 (10.44.10.24) -- the workstation's own address never appears in the
dns/network sensor tables for that traffic. Only proxy_access.log ties the beacon back to
nina.kapoor's real identity and host. So src_hostname in network/dns reflects the SENSOR's vantage
point for any proxied flow, not necessarily the true originating host -- a real normalization
pipeline hits this same ambiguity, and resolving it is a proxy-log-join problem, not a
zeek-parsing problem.
"""

import datetime
import json
import os
import re
import sys

import duckdb
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))

# The corpus this arm was built and verified against (ground fact from the orchestrating session;
# see PRE-REG-evidenceforge-arm-2026-07-04.md and RESULTS-evidenceforge-arm-2026-07-04.md for the
# full provenance chain). Override with EF_ARM_CORPUS if re-running against a fresh regeneration.
DEFAULT_CORPUS = ("/tmp/claude-1000/-home-jerem-project1/3f346061-99d6-407a-9395-0757dbd37f05"
                   "/scratchpad/ef-branch")
CORPUS = os.environ.get("EF_ARM_CORPUS", DEFAULT_CORPUS)
DATA = os.path.join(CORPUS, "data")
SCENARIO = os.path.join(HERE, "scenario.pinned.yaml")
OUT = os.path.join(HERE, "_work", "store_ef")

NS = "{http://schemas.microsoft.com/win/2004/08/events/event}"

WINDOWS_HOSTS = ["DC-BO-01", "FILE-BO-01", "WS-MPATEL-01", "WS-OREED-01",
                 "WS-LMORRIS-01", "WS-NKAPOOR-01", "WS-VHALE-01"]

PROXY_LOG_RE = re.compile(
    r'^(?P<ip>\S+) \S+ (?P<ident>\S+) \[(?P<ts>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<url>\S+) [^"]*" (?P<status>\d+) (?P<bytes>\S+) '
    r'"(?P<referrer>[^"]*)" "(?P<ua>[^"]*)"'
)


def load_host_ip_map():
    """Host/IP inventory from the pinned scenario (not hardcoded) -- see module docstring."""
    with open(SCENARIO) as f:
        doc = yaml.safe_load(f)
    systems = doc["environment"]["systems"]
    host_to_ip = {s["hostname"]: s["ip"] for s in systems}
    ip_to_host = {v: k for k, v in host_to_ip.items()}
    return host_to_ip, ip_to_host


def to_ms(ts_seconds):
    return int(round(float(ts_seconds) * 1000))


def parse_iso_to_ms(iso_str):
    """'2024-05-14T12:01:29.8013146Z' -> epoch ms. Truncate sub-microsecond fractional digits
    (Windows EVTX SystemTime carries 7, Python's fromisoformat wants <=6)."""
    s = iso_str.rstrip("Z")
    if "." in s:
        head, frac = s.split(".", 1)
        frac = (frac + "000000")[:6]
        s = f"{head}.{frac}"
    dt = datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp() * 1000)


def parse_proxy_ts_to_ms(ts_str):
    """'14/May/2024:13:44:16 +0000' -> epoch ms."""
    dt = datetime.datetime.strptime(ts_str, "%d/%b/%Y:%H:%M:%S %z")
    return int(dt.timestamp() * 1000)


def read_ndjson(path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def iter_xml_events(xml_path):
    """Yield (event_id, iso_time_str, event_record_id, computer, data_dict) per <Event>.

    Uses defusedxml (not stdlib xml.etree) to parse -- the corpus here is EvidenceForge-generated
    synthetic data, not attacker-controlled input, but defusedxml is a drop-in that closes the
    XXE/billion-laughs class of stdlib ElementTree footguns at zero cost, so there is no reason not
    to use it even though this specific input is trusted."""
    import defusedxml.ElementTree as ET
    root = ET.parse(xml_path).getroot()
    for ev in root.findall(f"{NS}Event"):
        eid = ev.find(f"{NS}System/{NS}EventID").text
        time_str = ev.find(f"{NS}System/{NS}TimeCreated").get("SystemTime")
        rec_id = ev.find(f"{NS}System/{NS}EventRecordID").text
        computer = ev.find(f"{NS}System/{NS}Computer").text
        data = {d.get("Name"): (d.text or "") for d in ev.findall(f"{NS}EventData/{NS}Data")}
        yield eid, time_str, rec_id, computer, data


# --- table builders ----------------------------------------------------------------------------

def build_network(con, ip_to_host):
    path = os.path.join(DATA, "ZEEK-BO-CORE", "conn.json")
    rows = []
    for r in read_ndjson(path):
        src_ip = r.get("id.orig_h")
        dst_ip = r.get("id.resp_h")
        t = to_ms(r["ts"])
        rows.append((
            r["uid"], 4001, t, t,
            src_ip, ip_to_host.get(src_ip),
            dst_ip, r.get("id.resp_p"),
            r.get("proto"), r.get("orig_bytes"), r.get("resp_bytes"), r.get("duration"),
        ))
    con.execute("""CREATE TABLE network (
        event_uid VARCHAR, class_uid INTEGER, time BIGINT, logged_time BIGINT,
        src_ip VARCHAR, src_hostname VARCHAR, dst_ip VARCHAR, dst_port BIGINT,
        protocol_name VARCHAR, bytes_out BIGINT, bytes_in BIGINT, duration DOUBLE)""")
    con.executemany("INSERT INTO network VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def build_dns(con, ip_to_host):
    path = os.path.join(DATA, "ZEEK-BO-CORE", "dns.json")
    rows = []
    for r in read_ndjson(path):
        src_ip = r.get("id.orig_h")
        t = to_ms(r["ts"])
        answers = r.get("answers") or []
        answer = answers[0] if answers else None
        rows.append((
            r["uid"], 4003, t, src_ip, ip_to_host.get(src_ip), r.get("query"), answer,
        ))
    con.execute("""CREATE TABLE dns (
        event_uid VARCHAR, class_uid INTEGER, time BIGINT,
        src_ip VARCHAR, src_hostname VARCHAR, query_hostname VARCHAR, answer VARCHAR)""")
    con.executemany("INSERT INTO dns VALUES (?,?,?,?,?,?,?)", rows)
    return len(rows)


def build_process(con):
    rows = []
    for host in WINDOWS_HOSTS:
        base = os.path.join(DATA, f"{host}.northstar-branch.local")

        sysmon_path = os.path.join(base, "windows_event_sysmon.xml")
        if os.path.exists(sysmon_path):
            for eid, time_str, rec_id, computer, data in iter_xml_events(sysmon_path):
                if eid != "1":  # Sysmon EventID 1 = ProcessCreate
                    continue
                t = parse_iso_to_ms(time_str)
                pid = data.get("ProcessId")
                rows.append((
                    f"sysmon1:{computer}:{rec_id}", 1007, t, t,
                    computer.split(".")[0], data.get("User"),
                    data.get("Image"), data.get("CommandLine"), data.get("ParentImage"),
                    int(pid) if pid and pid.isdigit() else None,
                ))

        sec_path = os.path.join(base, "windows_event_security.xml")
        if os.path.exists(sec_path):
            for eid, time_str, rec_id, computer, data in iter_xml_events(sec_path):
                if eid != "4688":  # Windows Security EventID 4688 = process-creation audit
                    continue
                t = parse_iso_to_ms(time_str)
                pid_hex = data.get("NewProcessId")
                try:
                    pid = int(pid_hex, 16) if pid_hex else None
                except ValueError:
                    pid = None
                rows.append((
                    f"sec4688:{computer}:{rec_id}", 1007, t, t,
                    computer.split(".")[0], data.get("SubjectUserName"),
                    data.get("NewProcessName"), data.get("CommandLine"),
                    data.get("ParentProcessName"), pid,
                ))

    con.execute("""CREATE TABLE process (
        event_uid VARCHAR, class_uid INTEGER, time BIGINT, logged_time BIGINT,
        device_hostname VARCHAR, actor_user_uid VARCHAR, image_name VARCHAR,
        cmd_line VARCHAR, parent_image_name VARCHAR, pid BIGINT)""")
    con.executemany("INSERT INTO process VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def build_api(con):
    """No cloudtrail source exists in this on-prem scenario -- empty, correctly-typed table."""
    con.execute("""CREATE TABLE api (
        event_uid VARCHAR, class_uid INTEGER, time BIGINT, logged_time BIGINT,
        service VARCHAR, api_operation VARCHAR, actor_user_uid VARCHAR,
        src_ip VARCHAR, resource VARCHAR, mfa_present BOOLEAN, mfa_value BOOLEAN,
        aws_region VARCHAR)""")
    return 0


def build_auth(con):
    """Supporting table (no rule queries it): Windows Security 4624 (success) / 4625 (failure)."""
    rows = []
    for host in WINDOWS_HOSTS:
        sec_path = os.path.join(DATA, f"{host}.northstar-branch.local", "windows_event_security.xml")
        if not os.path.exists(sec_path):
            continue
        for eid, time_str, rec_id, computer, data in iter_xml_events(sec_path):
            if eid not in ("4624", "4625"):
                continue
            t = parse_iso_to_ms(time_str)
            src_ip = (data.get("IpAddress") or "").replace("::ffff:", "") or None
            rows.append((
                f"sec{eid}:{computer}:{rec_id}", 3002, t, t,
                data.get("TargetUserName"), None, src_ip,
                "SUCCESS" if eid == "4624" else "FAILURE",
                eid == "4624", None, computer.split(".")[0],
            ))
    con.execute("""CREATE TABLE auth (
        event_uid VARCHAR, class_uid INTEGER, time BIGINT, logged_time BIGINT,
        user_uid VARCHAR, src_country VARCHAR, src_ip VARCHAR, outcome VARCHAR,
        is_success BOOLEAN, is_remote BOOLEAN, target_host VARCHAR)""")
    con.executemany("INSERT INTO auth VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def build_http(con):
    """Supporting/corroboration table (no rule queries it): the explicit proxy's CONNECT log."""
    path = os.path.join(DATA, "PROXY-BO-01.northstar-branch.local", "proxy_access.log")
    rows = []
    with open(path) as f:
        for line in f:
            m = PROXY_LOG_RE.match(line.rstrip("\n"))
            if not m:
                continue
            g = m.groupdict()
            t = parse_proxy_ts_to_ms(g["ts"])
            ident = g["ident"]
            actor = ident.split("\\")[-1] if ident not in ("-", "") else None
            url = g["url"]
            host_part = url.split(":")[0] if ":" in url else url
            port_part = url.split(":")[1] if ":" in url else None
            rows.append((
                f"proxy:{t}:{g['ip']}:{len(rows)}", 4002, t,
                g["ip"], actor, g["method"], host_part,
                int(port_part) if port_part and port_part.isdigit() else None,
                int(g["status"]), int(g["bytes"]) if g["bytes"].isdigit() else None,
            ))
    con.execute("""CREATE TABLE http (
        event_uid VARCHAR, class_uid INTEGER, time BIGINT,
        src_ip VARCHAR, actor_user_uid VARCHAR, http_method VARCHAR,
        url_hostname VARCHAR, url_port BIGINT, status_code INTEGER, bytes BIGINT)""")
    con.executemany("INSERT INTO http VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def build(corpus=None):
    global CORPUS, DATA
    if corpus:
        CORPUS = corpus
        DATA = os.path.join(CORPUS, "data")
    if not os.path.isdir(DATA):
        print(f"Corpus data dir not found: {DATA}", file=sys.stderr)
        sys.exit(2)

    host_to_ip, ip_to_host = load_host_ip_map()
    os.makedirs(OUT, exist_ok=True)
    con = duckdb.connect(":memory:")

    counts = {}
    counts["network"] = build_network(con, ip_to_host)
    counts["dns"] = build_dns(con, ip_to_host)
    counts["process"] = build_process(con)
    counts["api"] = build_api(con)
    counts["auth"] = build_auth(con)
    counts["http"] = build_http(con)

    for table in counts:
        con.execute(f"COPY {table} TO '{os.path.join(OUT, table)}.parquet' (FORMAT parquet)")

    manifest = {
        "corpus": CORPUS,
        "host_to_ip": host_to_ip,
        "row_counts": counts,
        "total_rows": sum(counts.values()),
    }
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    con.close()
    return manifest


if __name__ == "__main__":
    m = build()
    print(json.dumps(m, indent=2, sort_keys=True))

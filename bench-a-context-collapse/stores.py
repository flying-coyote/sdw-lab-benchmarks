"""Build the two OCSF stores from the shared testbed's raw corpus.

Store F (fidelity-preserving) and Store N (normalized/coarse) are built from the
SAME raw JSONL, blind to the query battery. The difference between them is the only
variable BENCH-A measures, so every coarsening choice in Store N has to come from a
documented real-world pipeline default rather than from what would make an adversary
query fail — that discipline, and the basis for each choice, is written down in
STORE-N-NORMALIZATION.md, and the Tier-A gate is an independent practitioner
confirming Store N resembles what shops actually build.

Store F keeps atomic grain, all four time types, the per-domain identity tags, and a
stable event uid; absence is preserved (the no-MFA needle's `mfaAuthenticated` stays
absent via a `mfa_present` flag). Store N is the single coalesced event store: one
`time` field populated from ingestion, network rolled into 5-minute flows, identity
flattened to one best-available `user_uid`, command lines truncated, rare DNS sampled
out, MFA-absence coerced to false, no valid-time.

OCSF 1.8.0 paths: Authentication (3002), Network Activity (4001), and DNS Activity
(4003) use the field paths validated in the C1 subset. Process Activity (1007) and
API Activity (6003) are in the subset's "not scored here" set, so their column names
follow the canonical OCSF `process` / `actor` / `api` object semantics; BENCH-A scores
fidelity against ground truth, not OCSF-path existence (that is BENCH-B's metric).
"""

import json
import os

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "raw")
WORK = os.path.join(HERE, "_work")
GT = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "ground_truth.json")
import sys  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import configure_duckdb  # noqa: E402


def _ioc():
    """The chain's indicators from ground truth, so the stores track whichever chain was generated."""
    return json.load(open(GT))["ioc"]

ROLLUP_MS = 300_000        # Store N network rollup window: 5 minutes
CMDLINE_TRUNC = 64         # Store N command-line truncation
DNS_RARE_MIN = 3           # Store N drops DNS queries seen fewer than this many times


def _src(name):
    return os.path.join(RAW, f"{name}.jsonl").replace("'", "''")


def _views(con):
    """Register each raw source as a view; sample_size=-1 types sparse columns right."""
    for s in ("okta_auth", "okta_session", "zeek_conn", "zeek_dns",
              "sysmon_process", "cloudtrail"):
        con.execute(f"CREATE VIEW raw_{s} AS "
                    f"SELECT * FROM read_json_auto('{_src(s)}', sample_size=-1)")


def build_store_f(con):
    """Fidelity-preserving: atomic grain, all times, per-domain identity, absence kept."""
    d = os.path.join(WORK, "store_f")
    os.makedirs(d, exist_ok=True)

    # Authentication (3002) — both times, full identity, remote flag, target host, valid-time.
    con.execute(f"""COPY (
        SELECT _uid AS event_uid, 3002 AS class_uid,
               _event_time_ms AS time, _ingest_time_ms AS logged_time,
               actor_user AS user_uid, src_country, src_ip,
               outcome, (outcome='SUCCESS') AS is_success,
               (event_type='host.logon.remote') AS is_remote,
               target_host
        FROM raw_okta_auth) TO '{d}/auth.parquet' (FORMAT parquet)""")

    # Sessions — valid-time retained (start/end), the basis for point-in-time queries.
    con.execute(f"""COPY (
        SELECT _uid AS event_uid, actor_user AS user_uid, host,
               start_time_ms AS start_time, end_time_ms AS end_time,
               _event_time_ms AS time, _ingest_time_ms AS logged_time
        FROM raw_okta_session) TO '{d}/session.parquet' (FORMAT parquet)""")

    # Network Activity (4001) — ATOMIC: every connection kept, both byte directions.
    con.execute(f"""COPY (
        SELECT _uid AS event_uid, 4001 AS class_uid,
               _event_time_ms AS time, _ingest_time_ms AS logged_time,
               orig_h AS src_ip, orig_host AS src_hostname,
               resp_h AS dst_ip, resp_p AS dst_port, proto AS protocol_name,
               orig_bytes AS bytes_out, resp_bytes AS bytes_in, duration
        FROM raw_zeek_conn) TO '{d}/network.parquet' (FORMAT parquet)""")

    # DNS Activity (4003) — every query kept (first-seen is computable).
    con.execute(f"""COPY (
        SELECT _uid AS event_uid, 4003 AS class_uid,
               _event_time_ms AS time, orig_h AS src_ip, orig_host AS src_hostname,
               query AS query_hostname, answer
        FROM raw_zeek_dns) TO '{d}/dns.parquet' (FORMAT parquet)""")

    # Process Activity (1007) — FULL command line, parent, endpoint SID (per-domain identity).
    con.execute(f"""COPY (
        SELECT _uid AS event_uid, 1007 AS class_uid,
               _event_time_ms AS time, _ingest_time_ms AS logged_time,
               host AS device_hostname, user_sid AS actor_user_uid,
               image_name, command_line AS cmd_line, parent_image_name, process_id AS pid
        FROM raw_sysmon_process) TO '{d}/process.parquet' (FORMAT parquet)""")

    # API Activity (6003) — absence preserved: mfa_present distinguishes absent from false.
    con.execute(f"""COPY (
        SELECT _uid AS event_uid, 6003 AS class_uid,
               _event_time_ms AS time, _ingest_time_ms AS logged_time,
               split_part(event_source,'.',1) AS service, event_name AS api_operation,
               principal AS actor_user_uid, src_ip, resource,
               (mfaAuthenticated IS NOT NULL) AS mfa_present, mfaAuthenticated AS mfa_value,
               aws_region
        FROM raw_cloudtrail) TO '{d}/api.parquet' (FORMAT parquet)""")

    # Asset-inventory observable — the named chain assets resolved across their
    # hostname / IP / instance-id aliases, read from the ground-truth IOC block so it tracks
    # whichever chain was generated (not hardcoded). A fidelity store keeps this as an
    # enrichment/observable; it is what lets A9 count machines rather than identifiers.
    ioc = _ioc()
    rows = ",\n            ".join(
        f"('{ioc[f'{w}_host']}','{ioc[f'{w}_ip']}','{ioc[f'{w}_instance']}','{ioc[f'{w}_host']}')"
        for w in ("ws1", "ws2"))
    con.execute(f"""COPY (
        SELECT * FROM (VALUES
            {rows}
        ) AS t(hostname, ip, instance_uid, canonical_asset)
    ) TO '{d}/asset.parquet' (FORMAT parquet)""")
    return d


def build_store_n(con, rollup_ms=ROLLUP_MS, cmdline_trunc=CMDLINE_TRUNC, dns_rare_min=DNS_RARE_MIN):
    """Normalized/coarse single event store — the documented volume-driven default.

    The three coarsening knobs are parameters (defaulting to the documented values) so the
    dose-response harness can sweep them: a larger rollup window, a shorter cmdline cap, and a
    higher rare-DNS threshold are all "lazier" normalization."""
    d = os.path.join(WORK, "store_n")
    os.makedirs(d, exist_ok=True)

    # The single coalesced event table. time = INGESTION time (one field). Identity
    # flattened to one best-available user_uid (no per-domain tags → cross-source
    # linkage lost). device_host carries each source's NATIVE identifier (hostname from
    # EDR, IP from NDR) with no resolution → the same machine surfaces under two keys.
    # Network rolled to 5-min flows (atomic conns + cadence gone) but in/out bytes kept
    # separate (a real rollup does, so egress stays answerable — R4 must survive).
    # cmd_line truncated. MFA-absence coerced to false. Rare DNS sampled out. No valid-time.
    con.execute(f"""COPY (
        -- auth (first branch names the union's columns)
        SELECT _ingest_time_ms AS time, 3002 AS class_uid, actor_user AS user_uid,
               NULL AS device_host, src_ip AS src_ip, NULL AS dst_ip, NULL::INTEGER AS dst_port,
               NULL::BIGINT AS bytes_out, NULL::BIGINT AS bytes_in, NULL::INTEGER AS flow_count,
               NULL AS image_name, NULL AS cmd_line, src_country AS src_country,
               outcome AS outcome, NULL AS api_operation, NULL AS service,
               false AS is_mfa, NULL AS query_hostname
        FROM raw_okta_auth
        UNION ALL
        -- network: 5-min flow rollup per (src,dst,port); device_host = source-native IP (NDR)
        SELECT (_ingest_time_ms / {rollup_ms})::BIGINT * {rollup_ms}, 4001,
               NULL, orig_h, orig_h, resp_h, resp_p,
               sum(orig_bytes)::BIGINT, sum(resp_bytes)::BIGINT, count(*)::INTEGER,
               NULL, NULL, NULL, NULL, NULL, NULL, false, NULL
        FROM raw_zeek_conn
        GROUP BY 1, orig_h, resp_h, resp_p
        UNION ALL
        -- dns: rare queries (seen < DNS_RARE_MIN) sampled out under cardinality limits
        SELECT _ingest_time_ms, 4003, NULL, orig_h, orig_h, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, false, query
        FROM raw_zeek_dns
        WHERE query IN (SELECT query FROM raw_zeek_dns GROUP BY query HAVING count(*) >= {dns_rare_min})
        UNION ALL
        -- process: cmd_line truncated; device_host = hostname (EDR); SID is the flat user_uid
        SELECT _ingest_time_ms, 1007, user_sid, host, NULL, NULL, NULL,
               NULL, NULL, NULL, image_name, left(command_line, {cmdline_trunc}),
               NULL, NULL, NULL, NULL, false, NULL
        FROM raw_sysmon_process
        UNION ALL
        -- api: principal is the flat user_uid; MFA-absence coerced to false (structural loss)
        SELECT _ingest_time_ms, 6003, principal, NULL, src_ip, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL, NULL, NULL,
               event_name, split_part(event_source,'.',1), coalesce(mfaAuthenticated, false), NULL
        FROM raw_cloudtrail
    ) TO '{d}/events.parquet' (FORMAT parquet)""")
    return d


def _dir_bytes(path):
    return sum(os.path.getsize(os.path.join(path, f)) for f in os.listdir(path)
              if f.endswith(".parquet"))


def build(con=None):
    own = con is None
    if own:
        con = configure_duckdb(duckdb.connect(":memory:"))
    _views(con)
    f_dir = build_store_f(con)
    n_dir = build_store_n(con)
    cost = {"store_f_bytes": _dir_bytes(f_dir), "store_n_bytes": _dir_bytes(n_dir)}
    cost["fidelity_overhead_x"] = round(cost["store_f_bytes"] / cost["store_n_bytes"], 2)
    if own:
        con.close()
    return cost


if __name__ == "__main__":
    print(build())

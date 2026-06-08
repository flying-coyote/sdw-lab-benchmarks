"""The labeled NL2SQL question set for the OCSF silent-error benchmark.

Each question is a (natural-language ask the model sees, gold SQL that produces
the gold answer, gold answer / ground-truth needle, difficulty tier, scorer kind)
tuple over the shared testbed's **Store F** (the fidelity-preserving OCSF store
built by BENCH-A). The corpus and ground truth are NOT re-authored here — they are
the same `bench-a-context-collapse/_work/store_f/*.parquet` and
`ocsf-semantic-testbed/_work/ground_truth.json` the rest of the concept-graph
thread runs on, so this benchmark is comparable query-for-query.

WHAT IS NEW HERE vs. the BENCH-C text-to-SQL arm (`ocsf-semantic-query/run.py`):
that arm runs only 4 adversary-tail concept queries (A1, A2, A6, A8) — the hardest
"tail" slice. It found a weak local model fails *loudly* on the tail (hallucinated
columns/functions → SQL error or empty) and so posts a 0.00 silent rate, which left
the silent-vs-loud contrast un-exercised because the questions were all maximally
hard. This set is the missing BREADTH: ~30 questions spanning seven difficulty
tiers from a one-table filter up to the adversary tail, so the by-difficulty
breakdown can show WHERE silent errors concentrate (the hypothesis: not on the tail,
where a weak model fails loud, but in the mid-difficulty band — aggregation,
group-by, time-window — where the SQL plausibly runs and quietly returns the wrong
number).

GOLD DESIGN (no DuckDB at authoring time): every gold value is either a planted
ground-truth needle (read live from ground_truth.json at run time via `truth_key`)
or a literal corpus invariant taken from the deterministic generator/manifest
(`gold_literal`). The reference `gold_sql` is the query that PRODUCES that answer on
Store F; it is the human-authored answer key (never an LLM), and is the same logic
the BENCH-A `bench.py` battery uses for the adversary needles. The gold_sql is NOT
executed in this readiness pass — it is the documented oracle the run will check the
LLM's SQL against by comparing the executed RESULT, not the SQL text.

SCORER KINDS (must stay byte-identical in spirit to ocsf-semantic-query/run.py:score):
  substring  — correct iff str(gold) is a substring of any returned cell.
  uid        — correct iff str(gold) is exactly among returned cells.
  uidset     — correct iff the answer recovers >=50% of the needle set AND does not
               flood (len(returned) <= 4x len(needle)). recall floor + precision proxy.
  scalar     — correct iff the single returned value equals the gold value
               (numeric: within rel-tol 1e-9; string: exact). The mid-tier count/
               aggregation questions use this; a wrong-but-returned number is the
               canonical SILENT error this benchmark is built to surface.
  set        — correct iff the returned value set, as strings, == the gold set
               (order-insensitive). For group-by / multi-value answers.

DIFFICULTY TIERS (the breakdown axis):
  simple_filter    — one table, a WHERE predicate, project a column.
  aggregation      — one table, a single COUNT/SUM/etc. scalar.
  group_by         — one table, GROUP BY + an ordered/keyed result set.
  time_window      — one table, a BETWEEN/range predicate on a time column.
  multi_condition  — one table, several ANDed predicates (the realistic-analyst band).
  join             — two+ tables joined (cross-source — OCSF's hard case).
  adversary_tail   — the sparse planted needles (cadence / first-seen / absence / closure).
"""

# A literal corpus invariant is a value fixed by the deterministic generator
# (MASTER_SEED=20260601, manifest.json counts) — used only where it is a stable,
# documented fact of the corpus, not something an LLM should get to define. These
# are the gold answers for the routine tiers (the adversary tiers read needles from
# ground_truth.json at run time). Counts come from
# ocsf-semantic-testbed/_work/manifest.json (full scale) and the Store F build in
# bench-a-context-collapse/stores.py; the per-predicate counts (failed logins, etc.)
# are computed by the gold_sql at run time and compared to the LLM result, so only
# the whole-table counts and structural invariants are pinned literally here.
CORPUS = {
    "auth_total": 27233,        # manifest okta_auth; Store F f_auth row count
    "api_total": 28033,         # manifest cloudtrail; Store F f_api row count
    "dns_total": 18001,         # manifest zeek_dns; Store F f_dns row count
    "network_total": 60061,     # manifest zeek_conn; Store F f_network row count
    "process_total": 40002,     # manifest sysmon_process; Store F f_process row count
    "session_total": 4001,      # manifest okta_session; Store F f_session row count
}

# Analyst-known IOCs (host names, the compromised principal, ATT&CK-shaped event
# names) are FAIR query inputs — they are what an analyst pivots from after an
# initial detection, exactly the convention bench.py documents. Ground-truth *uids*
# are used only to score, never handed to the model in the NL prompt.
WS1_HOST = "WS1"
WS1_IP = "10.10.1.21"
WS2_IP = "10.10.1.22"
BEACON_PORT = 443
LATERAL_PORT = 3389

# The schema the model is shown (built live from Store F via DESCRIBE in run.py;
# this mirrors it for reference and for the questions' gold_sql).
TABLES = ("auth", "session", "network", "dns", "process", "api", "asset")


QUESTIONS = [
    # ---------------------------------------------------------------- simple_filter
    {
        "id": "F01", "tier": "simple_filter", "kind": "scalar",
        "nl": "How many authentication events have an outcome of FAILURE? Return the count.",
        "gold_sql": "SELECT count(*) FROM f_auth WHERE outcome='FAILURE'",
        "gold_via": "sql",  # gold computed by gold_sql at run time (deterministic corpus)
    },
    {
        "id": "F02", "tier": "simple_filter", "kind": "scalar",
        "nl": "How many authentication events were remote logons (is_remote is true)? Return the count.",
        "gold_sql": "SELECT count(*) FROM f_auth WHERE is_remote",
        "gold_via": "sql",
    },
    {
        "id": "F03", "tier": "simple_filter", "kind": "set",
        "nl": "List the distinct cloud API operation names recorded in the api table.",
        "gold_sql": "SELECT DISTINCT api_operation FROM f_api ORDER BY 1",
        "gold_via": "sql",
    },
    {
        "id": "F04", "tier": "simple_filter", "kind": "scalar",
        "nl": "How many process-creation events were recorded on host WS1 (device_hostname WS1)? Return the count.",
        "gold_sql": "SELECT count(*) FROM f_process WHERE device_hostname='WS1'",
        "gold_via": "sql",
    },
    {
        "id": "F05", "tier": "simple_filter", "kind": "scalar",
        "nl": "How many rows are in the network connection table in total? Return the count.",
        "gold_sql": "SELECT count(*) FROM f_network",
        "gold_literal": CORPUS["network_total"],
        "gold_via": "literal",
    },

    # ---------------------------------------------------------------- aggregation
    {
        "id": "G01", "tier": "aggregation", "kind": "scalar",
        "nl": "What is the total outbound bytes (sum of bytes_out) across all network connections? Return one number.",
        "gold_sql": "SELECT sum(bytes_out) FROM f_network",
        "gold_via": "sql",
    },
    {
        "id": "G02", "tier": "aggregation", "kind": "scalar",
        "nl": "How many distinct destination ports appear in the network connection table? Return the count.",
        "gold_sql": "SELECT count(DISTINCT dst_port) FROM f_network",
        "gold_via": "sql",
    },
    {
        "id": "G03", "tier": "aggregation", "kind": "scalar",
        "nl": "What is the average connection duration across all network connections? Return one number.",
        "gold_sql": "SELECT avg(duration) FROM f_network",
        "gold_via": "sql",
    },
    {
        "id": "G04", "tier": "aggregation", "kind": "scalar",
        "nl": "How many distinct source IP addresses appear in the network connection table? Return the count.",
        "gold_sql": "SELECT count(DISTINCT src_ip) FROM f_network",
        "gold_via": "sql",
    },
    {
        "id": "G05", "tier": "aggregation", "kind": "scalar",
        "nl": "How many distinct users (user_uid) appear in the authentication table? Return the count.",
        "gold_sql": "SELECT count(DISTINCT user_uid) FROM f_auth",
        "gold_via": "sql",
    },

    # ---------------------------------------------------------------- group_by
    {
        "id": "B01", "tier": "group_by", "kind": "set",
        "nl": "Return the top 5 destination ports by number of network connections (the ports only).",
        "gold_sql": "SELECT dst_port FROM f_network GROUP BY 1 ORDER BY count(*) DESC, dst_port LIMIT 5",
        "gold_via": "sql",
    },
    {
        "id": "B02", "tier": "group_by", "kind": "scalar",
        "nl": "Which authentication outcome value occurs most often? Return that single outcome value.",
        "gold_sql": "SELECT outcome FROM f_auth GROUP BY 1 ORDER BY count(*) DESC LIMIT 1",
        "gold_via": "sql",
    },
    {
        "id": "B03", "tier": "group_by", "kind": "set",
        "nl": "Return the top 10 process image names by event count (the image names only).",
        "gold_sql": "SELECT image_name FROM f_process GROUP BY 1 ORDER BY count(*) DESC, image_name LIMIT 10",
        "gold_via": "sql",
    },
    {
        "id": "B04", "tier": "group_by", "kind": "scalar",
        "nl": "Which cloud service (the service column) has the most API events? Return that single service name.",
        "gold_sql": "SELECT service FROM f_api GROUP BY 1 ORDER BY count(*) DESC LIMIT 1",
        "gold_via": "sql",
    },
    {
        "id": "B05", "tier": "group_by", "kind": "scalar",
        "nl": "How many distinct destination IP addresses did source host WS1 (src_hostname WS1) connect to? Return the count.",
        "gold_sql": "SELECT count(DISTINCT dst_ip) FROM f_network WHERE src_hostname='WS1'",
        "gold_via": "sql",
    },

    # ---------------------------------------------------------------- time_window
    {
        "id": "T01", "tier": "time_window", "kind": "scalar",
        "nl": "How many authentication events occurred on the chain day, the 24-hour window starting at epoch-ms 1767830400000 (inclusive) up to 1767916800000 (exclusive)? Return the count.",
        "gold_sql": "SELECT count(*) FROM f_auth WHERE time>=1767830400000 AND time<1767916800000",
        "gold_via": "sql",
    },
    {
        "id": "T02", "tier": "time_window", "kind": "scalar",
        "nl": "How many cloud API events fall in the 70-minute window from epoch-ms 1767866400000 (inclusive) to 1767870600000 (inclusive)? Return the count.",
        "gold_sql": "SELECT count(*) FROM f_api WHERE time BETWEEN 1767866400000 AND 1767870600000",
        "gold_via": "sql",
    },
    {
        "id": "T03", "tier": "time_window", "kind": "scalar",
        "nl": "How many network connections from source host WS1 occurred in the hour from epoch-ms 1767866400000 to 1767870000000 (inclusive)? Return the count.",
        "gold_sql": "SELECT count(*) FROM f_network WHERE src_hostname='WS1' AND time BETWEEN 1767866400000 AND 1767870000000",
        "gold_via": "sql",
    },
    {
        "id": "T04", "tier": "time_window", "kind": "scalar",
        "nl": "Across the network table, what is the span in milliseconds between the earliest and latest connection time (max(time) minus min(time))? Return one number.",
        "gold_sql": "SELECT max(time)-min(time) FROM f_network",
        "gold_via": "sql",
    },

    # ---------------------------------------------------------------- multi_condition
    {
        "id": "M01", "tier": "multi_condition", "kind": "scalar",
        "nl": "How many network connections went to destination port 443 with fewer than 1000 bytes_out? Return the count.",
        "gold_sql": "SELECT count(*) FROM f_network WHERE dst_port=443 AND bytes_out<1000",
        "gold_via": "sql",
    },
    {
        "id": "M02", "tier": "multi_condition", "kind": "scalar",
        "nl": "How many failed authentication events were also remote logons (outcome FAILURE and is_remote true)? Return the count.",
        "gold_sql": "SELECT count(*) FROM f_auth WHERE outcome='FAILURE' AND is_remote",
        "gold_via": "sql",
    },
    {
        "id": "M03", "tier": "multi_condition", "kind": "scalar",
        "nl": "How many AssumeRole API operations were called where mfa_present is true? Return the count.",
        "gold_sql": "SELECT count(*) FROM f_api WHERE api_operation='AssumeRole' AND mfa_present=true",
        "gold_via": "sql",
    },
    {
        "id": "M04", "tier": "multi_condition", "kind": "scalar",
        "nl": "How many process events on WS1 have a command line containing the text 'powershell'? Return the count.",
        "gold_sql": "SELECT count(*) FROM f_process WHERE device_hostname='WS1' AND cmd_line LIKE '%powershell%'",
        "gold_via": "sql",
    },
    {
        "id": "M05", "tier": "multi_condition", "kind": "scalar",
        "nl": "How many network connections went from source IP 10.10.1.21 to destination IP 10.10.1.22 on destination port 3389? Return the count.",
        "gold_sql": "SELECT count(*) FROM f_network WHERE src_ip='10.10.1.21' AND dst_ip='10.10.1.22' AND dst_port=3389",
        "gold_via": "sql",
    },

    # ---------------------------------------------------------------- join (cross-source)
    {
        "id": "J01", "tier": "join", "kind": "scalar",
        "nl": "Join the asset table to resolve identifiers: how many distinct canonical assets correspond to hostname WS1 or IP 10.10.1.21 or IP 10.10.1.22? Return the count.",
        "gold_sql": ("SELECT count(DISTINCT canonical_asset) FROM f_asset "
                     "WHERE hostname='WS1' OR ip IN ('10.10.1.21','10.10.1.22')"),
        "truth_key": "distinct_asset_count",
        "gold_via": "truth",  # planted needle = 2
    },
    {
        "id": "J02", "tier": "join", "kind": "scalar",
        "nl": ("For users who had at least one session on host WS1, how many authentication "
               "events did those same users generate? Join session and auth on the user identifier "
               "and return the count of matching auth events."),
        "gold_sql": ("SELECT count(*) FROM f_auth a "
                     "WHERE a.user_uid IN (SELECT user_uid FROM f_session WHERE host='WS1')"),
        "gold_via": "sql",
    },
    {
        "id": "J03", "tier": "join", "kind": "scalar",
        "nl": ("How many process events ran on hosts that the asset table lists as canonical "
               "assets? Join process.device_hostname to asset.hostname and return the count."),
        "gold_sql": ("SELECT count(*) FROM f_process p "
                     "JOIN f_asset s ON p.device_hostname = s.hostname"),
        "gold_via": "sql",
    },
    {
        "id": "J04", "tier": "join", "kind": "set",
        "nl": ("Which destination IPs did host WS1 both make a DNS-resolvable connection to "
               "and appear as a network source for? Return the distinct destination IPs that host "
               "WS1 (src_hostname WS1) connected to in the network table."),
        "gold_sql": "SELECT DISTINCT dst_ip FROM f_network WHERE src_hostname='WS1' ORDER BY 1",
        "gold_via": "sql",
    },

    # ---------------------------------------------------------------- adversary_tail
    # These are the BENCH-C concept-query needles. Same NL + truth_key + kind as
    # ocsf-semantic-query/run.py and the GRAPHRAG-READINESS table, so the tail slice
    # of this benchmark is directly comparable to the other arms.
    {
        "id": "A01", "tier": "adversary_tail", "kind": "uidset",
        "nl": ("Find the beaconing connection: a source/destination pair with roughly 60-second "
               "regular inter-arrival, low bytes, sustained for about an hour. Return the event_uid "
               "of each such connection."),
        "gold_sql": ("WITH cand AS (SELECT src_ip,dst_ip,dst_port FROM f_network GROUP BY 1,2,3 "
                     "HAVING count(*)>=30 AND (max(time)-min(time)) BETWEEN 50*60*1000 AND 75*60*1000 "
                     "AND avg(bytes_out+bytes_in)<2000) "
                     "SELECT n.event_uid FROM f_network n JOIN cand USING (src_ip,dst_ip,dst_port)"),
        "truth_key": "beacon_conn_uids",
        "gold_via": "truth",
    },
    {
        "id": "A02", "tier": "adversary_tail", "kind": "substring",
        "nl": "Return the exact PowerShell command line containing -EncodedCommand that executed on host WS1.",
        "gold_sql": ("SELECT cmd_line FROM f_process WHERE device_hostname='WS1' "
                     "AND cmd_line LIKE '%-EncodedCommand%'"),
        "truth_key": "powershell_encoded_cmd",
        "gold_via": "truth",
    },
    {
        "id": "A06", "tier": "adversary_tail", "kind": "uid",
        "nl": ("Find the privilege escalation: an AttachUserPolicy API call where MFA was not present "
               "(the mfa_present flag is false). Return its event_uid."),
        "gold_sql": ("SELECT event_uid FROM f_api WHERE api_operation='AttachUserPolicy' "
                     "AND mfa_present=false"),
        "truth_key": "nomfa_event_uid",
        "gold_via": "truth",
    },
    {
        "id": "A08", "tier": "adversary_tail", "kind": "substring",
        "nl": ("Find the DNS domain queried by host WS1 (source hostname WS1) that appears only once "
               "in the data (a first-seen, never-before-observed domain). Return the query_hostname."),
        "gold_sql": ("SELECT query_hostname FROM f_dns WHERE src_hostname='WS1' "
                     "GROUP BY 1 HAVING count(*)=1"),
        "truth_key": "c2_domain",
        "gold_via": "truth",
    },
    {
        "id": "A04", "tier": "adversary_tail", "kind": "uidset",
        "nl": ("Point-in-time query: return the event_uid of every session that was active (start_time "
               "<= the instant and end_time >= the instant) at epoch-ms 1767880980000."),
        "gold_sql": ("SELECT event_uid FROM f_session WHERE start_time<=1767880980000 "
                     "AND end_time>=1767880980000"),
        "truth_key": "pit_active_session_uids",
        "gold_via": "truth",
    },
]


def by_tier():
    """{tier: [question, ...]} preserving file order, for the run + the breakdown."""
    out = {}
    for q in QUESTIONS:
        out.setdefault(q["tier"], []).append(q)
    return out


def tier_counts():
    return {t: len(qs) for t, qs in by_tier().items()}


if __name__ == "__main__":
    import json
    print(f"{len(QUESTIONS)} questions across {len(by_tier())} tiers")
    print(json.dumps(tier_counts(), indent=2))
    # cheap structural self-check: ids unique, every q has nl/kind/tier/gold source
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids)), "duplicate question ids"
    for q in QUESTIONS:
        assert q["kind"] in {"substring", "uid", "uidset", "scalar", "set"}, q["id"]
        assert q["gold_via"] in {"sql", "literal", "truth"}, q["id"]
        if q["gold_via"] == "truth":
            assert "truth_key" in q, q["id"]
        if q["gold_via"] == "literal":
            assert "gold_literal" in q, q["id"]
        assert q["gold_sql"].strip().upper().startswith(("SELECT", "WITH")), q["id"]
    print("self-check ok:", ids)

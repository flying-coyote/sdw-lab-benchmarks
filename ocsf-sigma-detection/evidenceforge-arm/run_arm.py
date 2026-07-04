"""EvidenceForge external-validity arm of ocsf-sigma-detection.

Compiles the SAME 4 committed Sigma rules (../rules/*.yml) through the SAME pySigma sqlite backend
run.py uses, executes them over the OCSF-shaped store normalize_to_ocsf.py builds from a realistic,
independently-generated EvidenceForge corpus (not the synthetic BENCH-A testbed run.py normally
targets), and scores each rule's hits against GROUND_TRUTH.json's storyline steps by host + time-
window overlap (falling back to an exact identity key -- a Zeek connection uid -- when the ground
truth happens to carry one, since that is the strongest available join and real post-incident
ground truth reconstruction uses exact identifiers when it has them too).

Pre-registered: PRE-REG-evidenceforge-arm-2026-07-04.md. Full write-up:
RESULTS-evidenceforge-arm-2026-07-04.md (both at the ocsf-sigma-detection root).
"""

import datetime
import json
import os
import sys

import duckdb
from sigma.backends.sqlite import sqliteBackend
from sigma.collection import SigmaCollection

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_DIR = os.path.join(HERE, "..", "rules")
STORE = os.path.join(HERE, "_work", "store_ef")
RESULTS_DIR = os.path.join(HERE, "results")

sys.path.insert(0, HERE)
import normalize_to_ocsf as norm  # noqa: E402 -- reuses CORPUS/host-ip-map/time-parsing helpers

# rule file -> (Store-EF table it runs against, the ATT&CK stage, the ground-truth storyline step
# it should catch, or None if no instance was planted for it)
RULES = {
    "rdp_lateral.yml": {
        "table": "network", "att_ck": "T1021.001", "stage": "lateral movement",
        "storyline_id": "evt-004",
    },
    "c2_domain.yml": {
        "table": "dns", "att_ck": "T1071.001", "stage": "C2",
        "storyline_id": "evt-006",
    },
    "encoded_powershell.yml": {
        "table": "process", "att_ck": "T1059.001", "stage": "execution",
        "storyline_id": None,
    },
    "nomfa_privesc.yml": {
        "table": "api", "att_ck": "T1098", "stage": "priv-esc",
        "storyline_id": None,
    },
}

WINDOW_S = 300  # +/- 5min host+time-window join tolerance (see PRE-REG for the rationale)


def connect():
    con = duckdb.connect(":memory:")
    for t in ("network", "dns", "process", "api", "auth", "http"):
        path = os.path.join(STORE, f"{t}.parquet")
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM '{path}'")
    return con


def load_ground_truth():
    with open(os.path.join(norm.CORPUS, "GROUND_TRUTH.json")) as f:
        return json.load(f)


def step_time_ms(step_iso):
    return norm.parse_iso_to_ms(step_iso if step_iso.endswith("Z") else step_iso + "Z")


def window_overlap(rows, target_time_ms, target_hosts, window_s=WINDOW_S, pre_s=None, post_s=None):
    """rows: list of dicts with 'time' (ms) and 'hosts' (set of hostname strings resolved for that
    row). Returns the subset whose hosts intersect target_hosts AND whose time falls in
    [target_time - pre, target_time + post] (defaults to +/- window_s)."""
    pre_ms = (pre_s if pre_s is not None else window_s) * 1000
    post_ms = (post_s if post_s is not None else window_s) * 1000
    lo, hi = target_time_ms - pre_ms, target_time_ms + post_ms
    return [r for r in rows if lo <= r["time"] <= hi and (r["hosts"] & target_hosts)]


def run_rule(con, backend, rule_file, table):
    rules = SigmaCollection.from_yaml(open(os.path.join(RULES_DIR, rule_file)).read())
    sql = backend.convert(rules)[0]
    run_sql = sql.replace("SELECT *", "SELECT *").replace("<TABLE_NAME>", table)
    try:
        cols = [d[0] for d in con.execute(f"SELECT * FROM {table} LIMIT 0").description]
        matched = con.execute(run_sql).fetchall()
        matched_rows = [dict(zip(cols, row)) for row in matched]
        compiled = True
    except Exception as e:
        matched_rows, compiled = [], False
        sql = sql + f"   -- EXEC ERROR: {str(e)[:200]}"
    return sql, matched_rows, compiled


def main():
    if not os.path.isdir(STORE):
        print("Store EF not built -- run normalize_to_ocsf.py first.", file=sys.stderr)
        sys.exit(2)

    _, ip_to_host = norm.load_host_ip_map()
    gt = load_ground_truth()
    steps_by_id = {s["storyline_id"]: s for s in gt["storyline_steps"]}
    steps_by_id.update({f"red_herring:{s['storyline_id']}": s for s in gt.get("red_herring_steps", [])})
    events_by_storyline = {}
    for e in gt["events"]:
        events_by_storyline.setdefault(e["storyline_id"], []).append(e)

    con = connect()
    backend = sqliteBackend()
    rows = []

    for rf, meta in RULES.items():
        table = meta["table"]
        sql, matched_rows, compiled = run_rule(con, backend, rf, table)
        matched_uids = [r["event_uid"] for r in matched_rows]

        target_step = steps_by_id.get(meta["storyline_id"]) if meta["storyline_id"] else None
        target_events = events_by_storyline.get(meta["storyline_id"], []) if target_step else []

        detected = False
        detection_method = None
        tp_uids = []
        window_hits = []
        corroboration = None

        if target_step is not None:
            # storyline_steps carries no "time" of its own -- the per-event "time" (ISO 8601, on
            # gt["events"]) is the source of truth; use the earliest event for this storyline step.
            target_time_ms = min(step_time_ms(ev["time"]) for ev in target_events)
            target_hosts = {target_step["system"]}

            # Resolve a host set + time for every matched row, keyed by table shape.
            resolved = []
            for r in matched_rows:
                if table == "network":
                    hosts = {ip_to_host.get(r.get("src_ip")), ip_to_host.get(r.get("dst_ip"))} - {None}
                elif table == "dns":
                    hosts = {ip_to_host.get(r.get("src_ip"))} - {None}
                elif table == "process":
                    hosts = {r.get("device_hostname")} - {None}
                else:
                    hosts = set()
                resolved.append({"event_uid": r["event_uid"], "time": r["time"], "hosts": hosts})

            # Primary: exact-identity check against any explicit id the ground-truth event carries
            # (e.g. the Zeek connection uid on evt-004's rdp_session). Strongest available join.
            exact_ids = set()
            for ev in target_events:
                uid = ev.get("attributes", {}).get("uid")
                if uid:
                    exact_ids.add(uid)
            exact_hits = [r for r in matched_rows if r["event_uid"] in exact_ids] if exact_ids else []

            # Fallback / cross-check: host + time-window overlap (the general mechanism the mission
            # asks for, and the only one available where no exact id exists, e.g. evt-006's beacon).
            window_hits = window_overlap(resolved, target_time_ms, target_hosts)

            if exact_hits:
                detected = True
                detection_method = "exact-uid"
                tp_uids = [r["event_uid"] for r in exact_hits]
            elif window_hits:
                detected = True
                detection_method = "host+time-window"
                tp_uids = [r["event_uid"] for r in window_hits]
            else:
                detection_method = "none"

            # Narrative corroboration for c2_domain specifically: even though the LITERAL rule
            # misses (different IOC string), independently check whether the real beacon traffic is
            # visible in this arm's normalized store at all, and under what field values. Does not
            # change the rule's verdict -- the rule is scored as committed, not as it "should" be.
            if rf == "c2_domain.yml":
                real_domain = "northlakeportal.com"
                beacon_time = target_time_ms
                dns_corrob = con.execute(
                    "SELECT event_uid, time, src_ip, query_hostname, answer FROM dns "
                    "WHERE query_hostname = ? AND time BETWEEN ? AND ?",
                    [real_domain, beacon_time - WINDOW_S * 1000, beacon_time + 40 * 60 * 1000 + WINDOW_S * 1000],
                ).fetchall()
                http_corrob = con.execute(
                    "SELECT event_uid, time, src_ip, actor_user_uid, url_hostname FROM http "
                    "WHERE url_hostname = ? AND time BETWEEN ? AND ?",
                    [real_domain, beacon_time - WINDOW_S * 1000, beacon_time + 40 * 60 * 1000 + WINDOW_S * 1000],
                ).fetchall()
                corroboration = {
                    "real_c2_domain": real_domain,
                    "rule_hardcoded_domain": "cdn-telemetry-sync.net",
                    "dns_rows_for_real_domain": len(dns_corrob),
                    "dns_src_ip_sample": dns_corrob[0][2] if dns_corrob else None,
                    "dns_src_resolved_host": ip_to_host.get(dns_corrob[0][2]) if dns_corrob else None,
                    "http_proxy_rows_for_real_domain": len(http_corrob),
                    "http_actor_sample": http_corrob[0][3] if http_corrob else None,
                }

        tp = 1 if detected else 0
        fp = len(matched_uids) - (len(tp_uids) if detected else 0)
        precision = round((len(matched_uids) - fp) / len(matched_uids), 4) if matched_uids else None

        row = {
            "rule": rf, "table": table, "stage": meta["stage"], "att_ck": meta["att_ck"],
            "storyline_target": meta["storyline_id"], "compiled": compiled,
            "matches": len(matched_uids), "detected": detected, "detection_method": detection_method,
            "true_positive_uids": tp_uids, "false_positives": fp, "precision": precision,
            "window_join_hit_count": len(window_hits) if target_step is not None else None,
            "sql": sql,
        }
        if corroboration:
            row["corroboration"] = corroboration
        rows.append(row)

        print(f"  {meta['stage']:16} ({meta['att_ck']}): compiled={compiled} matches={len(matched_uids)} "
              f"detected={detected} method={row['detection_method']} fp={fp}")

    con.close()

    # `detected` is only ever set True inside the `target_step is not None` branch, so counting it
    # directly (rather than subtracting) is correct and not a double-count.
    no_target_n = sum(1 for r in rows if r["storyline_target"] is None)
    planted_n = len(rows) - no_target_n
    planted_detected_n = sum(1 for r in rows if r["storyline_target"] is not None and r["detected"])
    results = {
        "benchmark": "ocsf-sigma-detection/evidenceforge-arm",
        "evidence_tier": "B (single realistic scenario corpus, single machine, single run)",
        "corpus": norm.CORPUS,
        "corpus_provenance": {
            "repo": "/home/jerem/EvidenceForge", "commit": "7cbcc6a9",
            "scenario": "scenarios/branch-office-example/scenario.yaml",
            "eval_overall_score": 97.12, "eval_acceptance_passed": True,
        },
        "rules": len(rows),
        "planted_targets": planted_n,
        "planted_targets_detected": f"{planted_detected_n}/{planted_n}",
        "no_target_rules": no_target_n,
        "per_rule": rows,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    with open(os.path.join(RESULTS_DIR, "RESULTS.md"), "w") as f:
        f.write(render_md(results))
    print(f"\nwrote {os.path.join(RESULTS_DIR, 'results.json')} + RESULTS.md")


def render_md(res):
    lines = "\n".join(
        f"| {r['rule']} | {r['stage']} | {r['att_ck']} | {r['storyline_target'] or 'none planted'} | "
        f"{'DETECTED' if r['detected'] else ('N/A' if r['storyline_target'] is None else 'MISSED')} | "
        f"{r['matches']} | {r['false_positives']} | {r['precision']} |"
        for r in res["per_rule"])
    return f"""# EvidenceForge external-validity arm -- machine-generated summary

Tier B. Corpus: {res['corpus']}. Provenance: EvidenceForge @ {res['corpus_provenance']['commit']},
scenario `{res['corpus_provenance']['scenario']}`, eval {res['corpus_provenance']['eval_overall_score']}/100
acceptance_passed={res['corpus_provenance']['eval_acceptance_passed']}.

See ../RESULTS-evidenceforge-arm-2026-07-04.md for the full write-up, method, and honest caveats.
This file is the auto-generated per-run companion (mirrors the pattern in ../results/RESULTS.md).

| rule | stage | ATT&CK | storyline target | result | matches | false positives | precision |
|---|---|---|---|---|---|---|---|
{lines}
"""


if __name__ == "__main__":
    main()

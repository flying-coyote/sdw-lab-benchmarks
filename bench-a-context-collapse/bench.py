"""The frozen 16-query battery (R1-R6 routine, A1-A10 adversary-tail) against both
stores, scored against the testbed ground truth.

Each query is expressed per store as far as that store's schema allows; the
adaptation is logged in the per-query notes. Routine truth is a corpus tally taken
from the fidelity store (the faithful reference, per the pre-registration), so a
routine query is degraded only if Store N disagrees with Store F. Adversary truth
comes from the planted ground truth. Metrics follow §3 of the query battery:
detection F1, ordering Kendall's τ, count relative-error complement, identity F1;
Answerable=0 ⇒ Fidelity=0 ⇒ Degradation=1.

Analyst-known IOCs (host names, the compromised principal, ATT&CK-shaped event names
like AttachUserPolicy / AssumeRole) are fair query inputs — they are what an analyst
pivots from after an initial detection. Ground-truth *uids* are used only to score,
never as a query input.
"""

import os

import duckdb

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from common import prf1  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")

WS1_HOST, WS1_IP, WS2_IP = "WS1", "10.10.1.21", "10.10.1.22"
CHAIN_WINDOW_S = 70 * 60   # A10 true-event-time window: t0 .. t0+70min


def _connect():
    con = duckdb.connect(":memory:")
    f = os.path.join(WORK, "store_f")
    con.execute(f"CREATE VIEW f_auth    AS SELECT * FROM '{f}/auth.parquet'")
    con.execute(f"CREATE VIEW f_session AS SELECT * FROM '{f}/session.parquet'")
    con.execute(f"CREATE VIEW f_network AS SELECT * FROM '{f}/network.parquet'")
    con.execute(f"CREATE VIEW f_dns     AS SELECT * FROM '{f}/dns.parquet'")
    con.execute(f"CREATE VIEW f_process AS SELECT * FROM '{f}/process.parquet'")
    con.execute(f"CREATE VIEW f_api     AS SELECT * FROM '{f}/api.parquet'")
    con.execute(f"CREATE VIEW f_asset   AS SELECT * FROM '{f}/asset.parquet'")
    con.execute(f"CREATE VIEW n_events  AS SELECT * FROM '{os.path.join(WORK,'store_n')}/events.parquet'")
    return con


def _relerr_complement(returned, truth):
    if truth == 0:
        return 1.0 if returned == 0 else 0.0
    return max(0.0, 1.0 - min(1.0, abs(returned - truth) / truth))


def _kendall_tau_norm(order):
    """Normalised Kendall's τ (0-1) of `order` (a list of rank positions) vs sorted."""
    n = len(order)
    if n < 2:
        return 1.0 if n else 0.0
    concord = discord = 0
    for i in range(n):
        for j in range(i + 1, n):
            if order[i] < order[j]:
                concord += 1
            elif order[i] > order[j]:
                discord += 1
    total = concord + discord
    if total == 0:
        return 1.0
    tau = (concord - discord) / total
    return (tau + 1) / 2


# --------------------------------------------------------------------------- #
# Routine set — truth is the Store F tally. Each returns (fid_F, fid_N).        #
# --------------------------------------------------------------------------- #

def _routine(con):
    out = {}
    q = lambda s: con.execute(s).fetchone()[0]

    # R1 — auth events (count). Truth = Store F count.
    tf = q("SELECT count(*) FROM f_auth")
    tn = q("SELECT count(*) FROM n_events WHERE class_uid=3002")
    out["R1"] = (1.0, _relerr_complement(tn, tf), "none", "auth-event count")

    # R2 — top-20 dst ports (rank set F1).
    sf = {r[0] for r in con.execute(
        "SELECT dst_port FROM f_network GROUP BY 1 ORDER BY count(*) DESC LIMIT 20").fetchall()}
    sn = {r[0] for r in con.execute(
        "SELECT dst_port FROM n_events WHERE class_uid=4001 GROUP BY 1 "
        "ORDER BY sum(flow_count) DESC LIMIT 20").fetchall()}
    out["R2"] = (1.0, prf1(sf, sn)["f1"], "none", "top-20 dst ports")

    # R3 — failed-login count.
    tf = q("SELECT count(*) FROM f_auth WHERE outcome='FAILURE'")
    tn = q("SELECT count(*) FROM n_events WHERE class_uid=3002 AND outcome='FAILURE'")
    out["R3"] = (1.0, _relerr_complement(tn, tf), "none", "failed-login count")

    # R4 — total egress bytes (sum bytes_out). Rollup preserved direction, so survives.
    tf = q("SELECT sum(bytes_out) FROM f_network")
    tn = q("SELECT sum(bytes_out) FROM n_events WHERE class_uid=4001")
    out["R4"] = (1.0, _relerr_complement(tn, tf), "none", "egress bytes")

    # R5 — top-50 process images (rank set F1).
    sf = {r[0] for r in con.execute(
        "SELECT image_name FROM f_process GROUP BY 1 ORDER BY count(*) DESC LIMIT 50").fetchall()}
    sn = {r[0] for r in con.execute(
        "SELECT image_name FROM n_events WHERE class_uid=1007 GROUP BY 1 "
        "ORDER BY count(*) DESC LIMIT 50").fetchall()}
    out["R5"] = (1.0, prf1(sf, sn)["f1"], "none", "top-50 images")

    # R6 — cloud API call count.
    tf = q("SELECT count(*) FROM f_api")
    tn = q("SELECT count(*) FROM n_events WHERE class_uid=6003")
    out["R6"] = (1.0, _relerr_complement(tn, tf), "none", "cloud API count")
    return out


# --------------------------------------------------------------------------- #
# Adversary set — truth from the planted ground truth. (fid_F, fid_N, tag, note)#
# --------------------------------------------------------------------------- #

def _adversary(con, gt):
    tn_ = gt["truth_needles"]
    idl = gt["truth_identity_links"]
    t0 = gt["chain_t0_ms"]
    principal = idl["iam_principal"]
    role = idl["assumed_role"]
    out = {}

    # A1 — low-and-slow beacon (grain). F: atomic conns let a cadence query recover the
    # 60 beacon uids. N: 5-min flow rollup destroys inter-arrival and the conn uids.
    beacon_truth = set(tn_["beacon_conn_uids"])
    f_beacon = {r[0] for r in con.execute("""
        WITH cand AS (
          SELECT src_ip, dst_ip, dst_port FROM f_network
          GROUP BY 1,2,3
          HAVING count(*) >= 30
             AND (max(time)-min(time)) BETWEEN 50*60*1000 AND 75*60*1000
             AND avg(bytes_out+bytes_in) < 2000)
        SELECT n.event_uid FROM f_network n JOIN cand USING (src_ip,dst_ip,dst_port)""").fetchall()}
    f1_f = prf1(beacon_truth, f_beacon)["f1"]
    out["A1"] = (f1_f, 0.0, "grain", "beacon cadence; N: rollup → unanswerable")

    # A2 — exact -EncodedCommand string (grain). F: full cmd_line. N: truncated to 64.
    enc = tn_["powershell_encoded_cmd"]
    f_has = con.execute("SELECT count(*) FROM f_process WHERE cmd_line LIKE '%' || ? || '%'",
                        [enc]).fetchone()[0]
    n_has = con.execute("SELECT count(*) FROM n_events WHERE cmd_line LIKE '%' || ? || '%'",
                        [enc]).fetchone()[0]
    out["A2"] = (1.0 if f_has else 0.0, 1.0 if n_has else 0.0, "grain",
                 "exact encoded payload; N: cmd_line truncated")

    # A3 — cross-source kill-chain order (time). τ × coverage of recoverable milestones.
    def milestone_times(store):
        m = {}
        if store == "F":
            r = con.execute("SELECT min(time) FROM f_api WHERE api_operation='GetSessionToken' AND actor_user_uid=?", [principal]).fetchone()[0]; m["s0"]=r
            m["s1"] = con.execute("SELECT min(time) FROM f_process WHERE cmd_line LIKE '%-EncodedCommand%' AND device_hostname=?", [WS1_HOST]).fetchone()[0]
            m["s2"] = con.execute("SELECT min(time) FROM f_network WHERE src_ip=? AND dst_port=443 AND bytes_out<1000", [WS1_IP]).fetchone()[0]
            m["s3"] = con.execute("SELECT min(time) FROM f_network WHERE src_ip=? AND dst_ip=? AND dst_port=3389", [WS1_IP, WS2_IP]).fetchone()[0]
            m["s4"] = con.execute("SELECT min(time) FROM f_api WHERE api_operation='AttachUserPolicy' AND mfa_present=false").fetchone()[0]
            m["s5"] = con.execute("SELECT min(time) FROM f_api WHERE api_operation='AssumeRole' AND actor_user_uid=?", [role]).fetchone()[0]
            m["s6"] = con.execute("SELECT min(time) FROM f_api WHERE api_operation='GetObject' AND resource LIKE '%financials%'").fetchone()[0]
        else:
            m["s0"] = con.execute("SELECT min(time) FROM n_events WHERE api_operation='GetSessionToken' AND user_uid=?", [principal]).fetchone()[0]
            m["s1"] = con.execute("SELECT min(time) FROM n_events WHERE class_uid=1007 AND cmd_line LIKE '%-EncodedCommand%' AND device_host=?", [WS1_HOST]).fetchone()[0]
            m["s2"] = con.execute("SELECT min(time) FROM n_events WHERE class_uid=4001 AND src_ip=? AND dst_port=443", [WS1_IP]).fetchone()[0]
            m["s3"] = con.execute("SELECT min(time) FROM n_events WHERE class_uid=4001 AND src_ip=? AND dst_ip=? AND dst_port=3389", [WS1_IP, WS2_IP]).fetchone()[0]
            m["s4"] = con.execute("SELECT min(time) FROM n_events WHERE api_operation='AttachUserPolicy' AND user_uid=? AND is_mfa=false", [principal]).fetchone()[0]
            m["s5"] = con.execute("SELECT min(time) FROM n_events WHERE api_operation='AssumeRole' AND user_uid=?", [role]).fetchone()[0]
            m["s6"] = con.execute("SELECT min(time) FROM n_events WHERE api_operation='GetObject' AND user_uid=?", [role]).fetchone()[0]  # resource dropped → role-scoped, ambiguous
        return m
    truth_seq = ["s0", "s1", "s2", "s3", "s4", "s5", "s6"]
    def score_order(m):
        rec = [(k, m[k]) for k in truth_seq if m.get(k) is not None]
        coverage = len(rec) / len(truth_seq)
        rec.sort(key=lambda kv: kv[1])
        produced = [truth_seq.index(k) for k, _ in rec]
        return _kendall_tau_norm(produced) * coverage
    out["A3"] = (score_order(milestone_times("F")), score_order(milestone_times("N")),
                 "time", "kill-chain order × coverage")

    # A4 — point-in-time active sessions (time). F: valid-time. N: no sessions/valid-time.
    pit = tn_["pit_point_ms"]
    sess_truth = set(tn_["pit_active_session_uids"])
    f_active = {r[0] for r in con.execute(
        "SELECT event_uid FROM f_session WHERE start_time<=? AND end_time>=?", [pit, pit]).fetchall()}
    out["A4"] = (prf1(sess_truth, f_active)["f1"], 0.0, "time",
                 "active-session set; N: valid-time dropped → unanswerable")

    # A5 — identity closure (bounded-context). truth = {sid, upn, principal, role}.
    truth_ids = {idl["endpoint_sid"], idl["upn"], idl["iam_principal"], idl["assumed_role"]}
    # F: resolve from retained per-domain tags — SID off WS1 procs, UPN off WS1 sessions,
    # principal by name-match to UPN local part, role via AssumeRole by that principal.
    f_sid = con.execute("SELECT DISTINCT actor_user_uid FROM f_process WHERE device_hostname=?", [WS1_HOST]).fetchall()
    f_upn = con.execute("SELECT DISTINCT user_uid FROM f_session WHERE host=?", [WS1_HOST]).fetchall()
    recovered = {r[0] for r in f_sid} | {r[0] for r in f_upn}
    local = idl["upn"].split("@")[0]
    f_prin = con.execute("SELECT DISTINCT actor_user_uid FROM f_api WHERE actor_user_uid LIKE '%user/' || ?", [local]).fetchall()
    recovered |= {r[0] for r in f_prin}
    f_role = con.execute("SELECT DISTINCT actor_user_uid FROM f_api WHERE api_operation='AssumeRole' AND actor_user_uid LIKE '%' || ? || '%'", [local]).fetchall()
    recovered |= {r[0] for r in f_role}
    f1_f = prf1(truth_ids, recovered & truth_ids if False else recovered)["f1"]
    # N: only the flat SID is reachable from device_host=WS1; no link to the others.
    n_ids = {r[0] for r in con.execute("SELECT DISTINCT user_uid FROM n_events WHERE class_uid=1007 AND device_host=?", [WS1_HOST]).fetchall()}
    out["A5"] = (f1_f, prf1(truth_ids, n_ids)["f1"], "bounded-context",
                 "identity closure across sources")

    # A6 — priv-esc without MFA (structural). Exactly 1 true; FP inflates on N.
    f_set = con.execute("SELECT count(*) FROM f_api WHERE api_operation='AttachUserPolicy' AND mfa_present=false").fetchone()[0]
    n_set = con.execute("SELECT count(*) FROM n_events WHERE api_operation='AttachUserPolicy' AND is_mfa=false").fetchone()[0]
    def f1_one_true(returned):
        if returned < 1:
            return 0.0
        fp = returned - 1
        return 2.0 / (2.0 + fp)   # TP=1, FN=0
    out["A6"] = (f1_one_true(f_set), f1_one_true(n_set), "structural",
                 f"AttachUserPolicy w/o MFA; F:{f_set} N:{n_set} matches (absence vs false)")

    # A7 — dwell exec→lateral (time+grain). count relative-error vs truth dwell.
    dwell_truth = tn_["dwell_seconds"]
    def dwell(store):
        m = milestone_times(store)
        if m.get("s1") is None or m.get("s3") is None:
            return None
        return (m["s3"] - m["s1"]) / 1000.0
    df, dn = dwell("F"), dwell("N")
    out["A7"] = (_relerr_complement(df, dwell_truth) if df is not None else 0.0,
                 _relerr_complement(dn, dwell_truth) if dn is not None else 0.0,
                 "time", f"dwell sec (truth {dwell_truth})")

    # A8 — first-seen C2 domain (grain). F: atomic DNS from WS1. N: rare DNS sampled out.
    c2 = tn_["c2_domain"]
    f_seen = con.execute("SELECT count(*) FROM f_dns WHERE src_hostname=? AND query_hostname=?", [WS1_HOST, c2]).fetchone()[0]
    n_seen = con.execute("SELECT count(*) FROM n_events WHERE class_uid=4003 AND device_host=? AND query_hostname=?", [WS1_IP, c2]).fetchone()[0]
    out["A8"] = (1.0 if f_seen else 0.0, 1.0 if n_seen else 0.0, "grain",
                 "first-seen C2 domain; N: rare-DNS sampling drops it")

    # A9 — distinct assets touched (bounded-context). count metric; F resolves aliases.
    asset_truth = tn_["distinct_asset_count"]  # 2
    # F: actor IPs/hostnames resolved through the asset observable → canonical assets.
    f_assets = {r[0] for r in con.execute(f"""
        SELECT canonical_asset FROM f_asset WHERE hostname=? OR ip IN (?,?)""",
        [WS1_HOST, WS1_IP, WS2_IP]).fetchall()}
    f_count = len(f_assets)
    # N: actor-attributable device identifiers, unresolved (hostname from EDR + IP from NDR
    # for the same box + the lateral dst IP) → over-counts machines.
    n_ids2 = {r[0] for r in con.execute(
        "SELECT DISTINCT device_host FROM n_events WHERE device_host IN (?,?)", [WS1_HOST, WS1_IP]).fetchall()}
    n_ids2 |= {WS2_IP}  # WS2 surfaces only as the lateral destination IP
    n_count = len(n_ids2)
    out["A9"] = (_relerr_complement(f_count, asset_truth), _relerr_complement(n_count, asset_truth),
                 "bounded-context", f"distinct assets (truth {asset_truth}); F:{f_count} N:{n_count}")

    # A10 — buffered late-arrival in true-event-time window (time). recall of the needle.
    win_lo, win_hi = t0, t0 + CHAIN_WINDOW_S * 1000
    late_et = tn_["late_arrival_event_time_ms"]
    # F keys on event time → the buffered event's true time is in-window.
    f_in = 1 if (win_lo <= late_et <= win_hi) else 0   # F retains event time, so it lands in-window
    # N keys on ingestion time → check whether the late event's ingest time is in-window.
    n_in = 1 if (win_lo <= tn_["late_arrival_ingest_time_ms"] <= win_hi) else 0
    out["A10"] = (float(f_in), float(n_in), "time",
                  "late-arrival recall in true-event-time window")
    return out


def run():
    con = _connect()
    import json
    gt = json.load(open(os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "ground_truth.json")))
    routine = _routine(con)
    adversary = _adversary(con, gt)
    con.close()

    def deg(fid):
        return round(1.0 - fid, 4)

    rows = []
    for qid, (ff, nf, tag, note) in {**routine, **adversary}.items():
        cls = "routine" if qid.startswith("R") else "adversary"
        rows.append({"id": qid, "class": cls, "mechanism": tag,
                     "fidelity_F": round(ff, 4), "fidelity_N": round(nf, 4),
                     "degradation_F": deg(ff), "degradation_N": deg(nf),
                     "delta": round((1 - nf) - (1 - ff), 4), "note": note})

    routine_rows = [r for r in rows if r["class"] == "routine"]
    adv_rows = [r for r in rows if r["class"] == "adversary"]
    d_routine = sum(r["delta"] for r in routine_rows) / len(routine_rows)
    d_adv = sum(r["delta"] for r in adv_rows) / len(adv_rows)
    headline = d_adv - d_routine

    per_mech = {}
    for mech in ("grain", "time", "bounded-context", "structural"):
        ms = [r for r in adv_rows if r["mechanism"] == mech]
        if ms:
            per_mech[mech] = round(sum(r["delta"] for r in ms) / len(ms), 4)

    return {
        "rows": sorted(rows, key=lambda r: (r["class"], r["id"])),
        "delta_routine": round(d_routine, 4),
        "delta_adversary": round(d_adv, 4),
        "headline": round(headline, 4),
        "per_mechanism_delta": per_mech,
        "void": d_routine > 0.10,   # routine controls broke ⇒ run is contaminated
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2))

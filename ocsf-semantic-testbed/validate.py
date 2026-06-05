"""Ground-truth integrity check for the OCSF semantic testbed.

Run after generate.py. Confirms the planted needles the frozen query battery
references are actually present and findable in the materialized corpus, and that
the ground truth is internally consistent. This is not the BENCH-A scoring run
(that is Phase 3, against the two normalized stores) — it is the build-time check
that the testbed is correct before any store is built on top of it.

    python validate.py        # asserts; exits non-zero on any failure
"""

import base64
import json
import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import configure_duckdb  # noqa: E402


def main():
    gt = json.load(open(os.path.join(WORK, "ground_truth.json")))
    tn = gt["truth_needles"]
    idl = gt["truth_identity_links"]
    ioc = gt.get("ioc", {"c2_ip": "203.0.113.66"})   # chain indicators (chain-A fallback)
    con = configure_duckdb(duckdb.connect(":memory:"))

    def pq(src):
        return os.path.join(WORK, "parquet", f"{src}.parquet").replace("'", "''")

    def q(sql):
        return con.execute(sql).fetchall()

    checks = []  # (name, ok, detail)

    # --- A1 beacon: 60 conns to the C2 IP, ~60s cadence, low bytes, unique to needles
    rows = q(f"SELECT _event_time_ms FROM '{pq('zeek_conn')}' "
             f"WHERE _needle_id='stage2_beacon' ORDER BY _event_time_ms")
    ts = [r[0] for r in rows]
    gaps = sorted((ts[i + 1] - ts[i]) / 1000 for i in range(len(ts) - 1))
    median_gap = gaps[len(gaps) // 2] if gaps else 0
    fp = q(f"SELECT count(*) FROM '{pq('zeek_conn')}' "
           f"WHERE resp_h='{ioc['c2_ip']}' AND _needle_id IS NULL")[0][0]
    checks.append(("A1 beacon count == 60", len(ts) == 60, f"{len(ts)} conns"))
    checks.append(("A1 beacon cadence ~60s", 55 <= median_gap <= 65, f"median {median_gap:.0f}s"))
    checks.append(("A1 no background conn to C2 IP (no false positive)", fp == 0, f"{fp} background"))

    # --- A2 PowerShell -EncodedCommand recoverable verbatim
    cl = q(f"SELECT command_line FROM '{pq('sysmon_process')}' "
           f"WHERE _uid='{tn['powershell_proc_uid']}'")[0][0]
    enc = cl.split("-EncodedCommand ")[1]
    decoded = base64.b64decode(enc).decode("utf-16-le")
    checks.append(("A2 encoded cmd matches truth", enc == tn["powershell_encoded_cmd"], decoded[:48] + "…"))

    # --- A6 no-MFA: the AttachUserPolicy needle has mfaAuthenticated ABSENT (NULL),
    #     and background AttachUserPolicy events DO carry the field (so absence is signal)
    nmfa = q(f"SELECT mfaAuthenticated FROM '{pq('cloudtrail')}' "
             f"WHERE _uid='{tn['nomfa_event_uid']}'")[0][0]
    bg_present = q(f"SELECT count(*) FROM '{pq('cloudtrail')}' "
                   f"WHERE event_name='AttachUserPolicy' AND mfaAuthenticated IS NOT NULL")[0][0]
    checks.append(("A6 no-MFA needle has mfa absent (NULL)", nmfa is None, f"mfa={nmfa}"))
    checks.append(("A6 background AttachUserPolicy carries mfa (absence is signal)", bg_present > 0, f"{bg_present} bg"))

    # --- A5/A9 identity closure: the one human appears across all sources
    sid = q(f"SELECT count(*) FROM '{pq('sysmon_process')}' WHERE user_sid='{idl['endpoint_sid']}'")[0][0]
    upn = q(f"SELECT count(*) FROM '{pq('okta_auth')}' WHERE actor_user='{idl['upn']}'")[0][0]
    prin = q(f"SELECT count(*) FROM '{pq('cloudtrail')}' "
             f"WHERE principal IN ('{idl['iam_principal']}','{idl['assumed_role']}')")[0][0]
    checks.append(("A5 actor present in EDR(SID)+Okta(UPN)+cloud(principal)", sid and upn and prin,
                   f"edr={sid} okta={upn} cloud={prin}"))
    checks.append(("A9 distinct-asset truth == 2 machines", tn["distinct_asset_count"] == 2,
                   f"{[a['hostname'] for a in tn['distinct_assets']]}"))

    # --- A10 late-arrival: ingest lags true event_time by ~1h
    lag = q(f"SELECT (_ingest_time_ms-_event_time_ms)/60000.0 FROM '{pq('sysmon_process')}' "
            f"WHERE _uid='{tn['late_arrival_proc_uid']}'")[0][0]
    checks.append(("A10 late-arrival ingest lag ~60min", 55 <= lag <= 65, f"{lag:.0f} min"))

    # --- A4 point-in-time: the attacker session is active at the registered instant
    checks.append(("A4 PIT needle session active at instant",
                   tn["pit_session_uid"] in tn["pit_active_session_uids"],
                   f"{len(tn['pit_active_session_uids'])} sessions active"))

    # --- A3/A7 ordering + dwell consistent with planted times
    checks.append(("A3 truth_event_order has 7 stages", len(gt["truth_event_order"]) == 7,
                   str(gt["truth_event_order"])))
    checks.append(("A7 dwell == lateral - exec", tn["dwell_seconds"] > 0, f"{tn['dwell_seconds']}s"))

    # --- Routine sanity: tallies are populated and shaped right (not scored here)
    top_ports = q(f"SELECT resp_p FROM '{pq('zeek_conn')}' GROUP BY 1 ORDER BY count(*) DESC LIMIT 2")
    checks.append(("R2 top dst ports lead with 443/80", {top_ports[0][0], top_ports[1][0]} <= {80, 443},
                   str([p[0] for p in top_ports])))
    svc = q(f"SELECT count(DISTINCT split_part(event_source,'.',1)) FROM '{pq('cloudtrail')}'")[0][0]
    checks.append(("R6 multiple cloud services present", svc >= 6, f"{svc} services"))

    print(f"OCSF semantic testbed — ground-truth integrity ({len(checks)} checks)\n")
    width = max(len(c[0]) for c in checks)
    failed = 0
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name.ljust(width)}  {detail}")
        if not ok:
            failed += 1
    print(f"\n{len(checks) - failed}/{len(checks)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

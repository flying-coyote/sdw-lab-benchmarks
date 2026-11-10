#!/usr/bin/env python3
"""Score T7 captures against the pre-registered rubric (PREREGISTRATION.md). Written after the freeze.

Reads results/raw/<arm>/chains-rep*.json and results/raw/<arm>/capture/{events,admin-events}.json + container-log.txt.
Writes results/score.json and results/tables.md.
"""
from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"
ROOT_AUTHORITY = {"data:read", "data:write"}          # alice's role-derived authority
DATA_RE = re.compile(r"^data:")


def load_arm(arm):
    d = RAW / arm
    chains = sorted(d.glob("chains-rep*.json"))
    cap = d / "capture"
    return {
        "chains": [json.loads(p.read_text()) for p in chains],
        "chain_files": [p.name for p in chains],
        "events": json.loads((cap / "events.json").read_text()),
        "admin_events": json.loads((cap / "admin-events.json").read_text()),
        "log": (cap / "container-log.txt").read_text().splitlines(),
    }


def nonnull_keys(d):
    return sorted(k for k, v in d.items() if v not in (None, "", [], {}))


def parse_log_line(line, realm=None):
    """jboss-logging event line: type="X", realmId="...", key="value", ... -> dict (only event lines).
    The container log covers every realm (the admin-cli logins to master included), so lines are filtered to the
    bench realm by realmName."""
    if "org.keycloak.events" not in line:
        return None
    if realm and f'realmName="{realm}"' not in line:
        return None
    m = re.search(r'\btype="([A-Z_]+)"', line)
    if not m:
        return None
    kv = dict(re.findall(r'([A-Za-z_][\w.\-]*)="((?:[^"\\]|\\.)*)"', line))
    kv["_type"] = m.group(1)
    kv["_error_level"] = "WARN" in line
    return kv


def scopes_of(s):
    return set(s.split()) if isinstance(s, str) and s else set()


def hops_flat(chains):
    """Yield (rep, enforcer, scenario, hop record) for every hop in every rep."""
    for c in chains:
        for scen, hops in c["scenarios"].items():
            for h in hops:
                yield c["rep"], c.get("enforcer", False), scen, h


def match_event(events, hop, used):
    """Find the REST event for a hop: a detail equal to the token jti wins; else nearest by client+time (+session)."""
    cl = hop["claims"] if hop.get("claims") else {}
    jti = cl.get("jti")
    want_type = None
    g = hop["request"]["grant"]
    if g == "password":
        want_type = {"LOGIN"}
    elif g.startswith("token-exchange"):
        want_type = {"TOKEN_EXCHANGE"} if hop["status"] == 200 else {"TOKEN_EXCHANGE_ERROR"}
    elif g == "client_credentials":
        want_type = {"CLIENT_LOGIN"}
    elif g.startswith("authorization_code"):
        want_type = {"CODE_TO_TOKEN"} if hop["status"] == 200 else {"LOGIN_ERROR", "CODE_TO_TOKEN_ERROR"}
    cands = [e for e in events if e["type"] in want_type and id(e) not in used
             and e.get("clientId") == hop["request"]["client"]]
    if jti:
        for e in cands:
            if jti in (e.get("details") or {}).values():
                used.add(id(e))
                return e, "token_id_detail"
    sid = cl.get("sid")
    if sid:
        c2 = [e for e in cands if e.get("sessionId") == sid]
        if c2:
            cands = c2
    if cl.get("iat"):
        t = cl["iat"] * 1000
        cands = [e for e in cands if abs(e["time"] - t) < 15000]
        cands.sort(key=lambda e: abs(e["time"] - t))
    if cands:
        used.add(id(cands[0]))
        return cands[0], "client+session+time"
    return None, "unmatched"


def score_arm(arm, data):
    events = sorted(data["events"], key=lambda e: e["time"])
    out = {"arm": arm, "reps": len(data["chains"]), "n_events": len(events), "n_admin_events": len(data["admin_events"]),
           "n_log_event_lines": 0}
    # ---- field inventory (REST) ---------------------------------------------------------------------------
    inv = defaultdict(lambda: {"n": 0, "top": Counter(), "details": Counter()})
    for e in events:
        i = inv[e["type"]]
        i["n"] += 1
        i["top"].update(nonnull_keys({k: v for k, v in e.items() if k != "details"}))
        i["details"].update(nonnull_keys(e.get("details") or {}))
    out["rest_inventory"] = {t: {"n": v["n"], "top": dict(v["top"]), "details": dict(v["details"])} for t, v in inv.items()}
    ainv = defaultdict(lambda: {"n": 0, "top": Counter(), "resource_types": Counter(), "ops": Counter()})
    for a in data["admin_events"]:
        key = f'{a.get("operationType")}:{a.get("resourceType")}'
        i = ainv[key]
        i["n"] += 1
        i["top"].update(nonnull_keys(a))
    out["admin_inventory"] = {t: {"n": v["n"], "top": dict(v["top"])} for t, v in ainv.items()}
    # ---- log line inventory -----------------------------------------------------------------------------------
    loginv = defaultdict(lambda: {"n": 0, "keys": Counter()})
    log_events = []
    realm_name = {"S": "t7s", "D": "t7d"}[arm]
    for line in data["log"]:
        kv = parse_log_line(line, realm_name)
        if kv:
            log_events.append(kv)
            loginv[kv["_type"]]["n"] += 1
            loginv[kv["_type"]]["keys"].update(k for k in kv if not k.startswith("_"))
    out["n_log_event_lines"] = len(log_events)
    out["log_inventory"] = {t: {"n": v["n"], "keys": dict(v["keys"])} for t, v in loginv.items()}
    # H7 parity: REST detail keys + top keys vs log keys per type
    parity = {}
    for t, v in inv.items():
        rest_keys = set(v["top"]) | set(v["details"])
        rest_keys -= {"time", "type", "realmId"}            # time is the log timestamp; type/realmId always present
        lk = set(loginv.get(t, {}).get("keys", {}))
        parity[t] = {"rest_only": sorted(rest_keys - lk), "log_only": sorted(lk - rest_keys - {"realmName"}),
                     "n_rest": v["n"], "n_log": loginv.get(t, {}).get("n", 0)}
    out["H7_parity"] = parity
    # ---- match hops to events; claims inventory; H1 parent pointer ---------------------------------------------
    used = set()
    hop_rows = []
    claims_inv = defaultdict(Counter)
    by_jti = {}
    for rep, enf, scen, h in hops_flat(data["chains"]):
        if h.get("claims"):
            by_jti[h["claims"]["jti"]] = h
    h1_hits = []
    for rep, enf, scen, h in hops_flat(data["chains"]):
        e, how = match_event(events, h, used)
        cl = h.get("claims") or {}
        pos = h["label"].split("/", 1)[1]
        if cl:
            ci = claims_inv[(pos if "interleaved" not in h["label"] else re.sub(r"-\d$", "-k", pos))]
            ci["n"] += 1
            for k in ["jti", "sid", "session_state", "azp", "aud", "scope", "act", "may_act", "realm_access"]:
                if k in cl:
                    ci[k] += 1
            if h.get("signature_verified"):
                ci["sig_verified"] += 1
        row = {"rep": rep, "enforcer": enf, "scenario": scen, "label": h["label"], "status": h["status"],
               "event_type": e["type"] if e else None, "match": how, "ns": h.get("ns"),
               "scope_claim": cl.get("scope"), "roles": (cl.get("realm_access") or {}).get("roles"),
               "azp": cl.get("azp"), "aud": cl.get("aud"), "sid": cl.get("sid"), "act": cl.get("act"), "may_act": cl.get("may_act"),
               "event_details": (e or {}).get("details"), "event_sessionId": (e or {}).get("sessionId"),
               "error": (e or {}).get("error") or (h.get("response") or {}).get("error_description")}
        # H1: does any detail value equal the subject token's jti or azp?
        sj = h["request"].get("subject_token_jti")
        if e and sj:
            parent = by_jti.get(sj)
            vals = set(str(v) for v in (e.get("details") or {}).values()) | {str(e.get(k)) for k in ("clientId", "sessionId", "userId")}
            hit = {"subject_jti_in_event": sj in vals,
                   "subject_azp_in_details": bool(parent) and parent["claims"].get("azp") in set(str(v) for v in (e.get("details") or {}).values()),
                   "issued_jti_in_event": cl.get("jti") in vals if cl else None}
            row["H1"] = hit
            h1_hits.append(hit)
        hop_rows.append(row)
    out["hop_rows"] = hop_rows
    out["claims_inventory"] = {k: dict(v) for k, v in claims_inv.items()}
    out["H1"] = {"hops_checked": len(h1_hits),
                 "subject_jti_in_event": sum(h["subject_jti_in_event"] for h in h1_hits),
                 "subject_azp_in_details": sum(h["subject_azp_in_details"] for h in h1_hits),
                 "issued_jti_in_event": sum(bool(h["issued_jti_in_event"]) for h in h1_hits)}
    out["match_methods"] = dict(Counter(r["match"] for r in hop_rows))
    # ---- H4 detection over events alone (single-chain scenarios, non-enforcer) ------------------------------------
    det = defaultdict(lambda: {"chain_aware": 0, "root_only": 0, "n": 0, "scope_detail_present": 0})
    for c in data["chains"]:
        if c.get("enforcer"):
            continue
        for scen in ("baseline", "reacquire", "new"):
            hops = c["scenarios"].get(scen, [])
            t0 = next((h for h in hops if h["label"].endswith("T0-login") and h.get("claims")), None)
            if not t0:
                continue
            sid = t0["claims"].get("sid")
            chain_ev = [e for e in events if e.get("sessionId") == sid and e["type"] in ("LOGIN", "CODE_TO_TOKEN", "TOKEN_EXCHANGE")
                        and abs(e["time"] - t0["claims"]["iat"] * 1000) < 60000]
            chain_ev.sort(key=lambda e: e["time"])
            d = det[scen]
            d["n"] += 1
            scopes = [scopes_of((e.get("details") or {}).get("scope")) for e in chain_ev]
            if all(s for s in scopes) and len(scopes) >= 2:
                d["scope_detail_present"] += 1
            data_scopes = [{x for x in s if DATA_RE.match(x)} for s in scopes]
            flag_chain = any(not data_scopes[i] <= data_scopes[i - 1] for i in range(1, len(data_scopes)))
            flag_root = any(not s <= ROOT_AUTHORITY for s in data_scopes)
            d["chain_aware"] += int(flag_chain)
            d["root_only"] += int(flag_root)
            d.setdefault("example_scopes", [sorted(s) for s in data_scopes])
            d.setdefault("example_types", [e["type"] for e in chain_ev])
    if arm == "D":
        # delegated TOKEN_EXCHANGE events carry no sessionId: link each to the nearest earlier CODE_TO_TOKEN of the
        # same userId whose clientId equals the exchange's subject_token_client_id (the only pointer the event offers)
        detD = defaultdict(lambda: {"chain_aware": 0, "root_only": 0, "n": 0, "scope_detail_present": 0, "linked_by": "userId+subject_token_client_id+nearest-earlier-time"})
        c2t = [e for e in events if e["type"] == "CODE_TO_TOKEN"]
        for c in data["chains"]:
            for scen in ("baseline", "reacquire", "new"):
                hops = c["scenarios"].get(scen, [])
                t1 = next((h for h in hops if "delegated" in h["label"] and h.get("claims")), None)
                if not t1:
                    continue
                te = next((e for e in events if e["type"] == "TOKEN_EXCHANGE" and (e.get("details") or {}).get("token_id") == t1["claims"]["jti"]), None)
                if not te:
                    continue
                prior = [e for e in c2t if e.get("userId") == te.get("userId") and e.get("clientId") == te["details"].get("subject_token_client_id") and e["time"] <= te["time"]]
                parent = max(prior, key=lambda e: e["time"]) if prior else None
                d = detD[scen]; d["n"] += 1
                if parent is None:
                    continue
                s0 = {x for x in scopes_of(parent["details"].get("scope")) if DATA_RE.match(x)}
                s1 = {x for x in scopes_of(te["details"].get("scope")) if DATA_RE.match(x)}
                d["scope_detail_present"] += int(bool(s0) and bool(s1))
                d["chain_aware"] += int(not s1 <= s0)
                d["root_only"] += int(not s1 <= ROOT_AUTHORITY or not s0 <= ROOT_AUTHORITY)
                d.setdefault("example_scopes", [sorted(s0), sorted(s1)])
                d.setdefault("example_types", [parent["type"], te["type"]])
                # was the parent link right? truth: the CODE_TO_TOKEN whose token_id == subject_token_jti
                truth = next((e for e in c2t if e["details"].get("token_id") == t1["request"]["subject_token_jti"]), None)
                d["parent_link_correct"] = d.get("parent_link_correct", 0) + int(truth is parent)
        det = detD
    out["H4_detection"] = dict(det)
    # requested vs effective scope: does any event field record what was ASKED for, when the IdP dropped part of it?
    rq = {"hops": 0, "silently_reduced": 0, "requested_scope_recorded_anywhere": 0, "examples": []}
    for r in hop_rows:
        if r["status"] != 200 or not r["event_details"] or r["event_type"] not in ("TOKEN_EXCHANGE",):
            continue
        h_req = None
        for c in data["chains"]:
            for scen, hops in c["scenarios"].items():
                for h in hops:
                    if h["label"] == r["label"] and c["rep"] == r["rep"] and c.get("enforcer", False) == r["enforcer"]:
                        h_req = h["request"]["scope"]
        asked = {x for x in scopes_of(h_req) if DATA_RE.match(x)}
        got = {x for x in scopes_of(r["event_details"].get("scope")) if DATA_RE.match(x)}
        rq["hops"] += 1
        if not asked <= got:
            rq["silently_reduced"] += 1
            vals = " ".join(str(v) for v in r["event_details"].values())
            if any(x in vals for x in (asked - got)):
                rq["requested_scope_recorded_anywhere"] += 1
            if len(rq["examples"]) < 2:
                rq["examples"].append({"label": r["label"], "asked": sorted(asked), "event_scope": sorted(got), "token_scope": r["scope_claim"]})
    out["requested_vs_effective"] = rq
    # ---- H3 attribution on interleaved (arm S) -------------------------------------------------------------------
    if arm == "S":
        correct = total = 0
        per_rep = []
        for c in data["chains"]:
            if c.get("enforcer"):
                continue
            hops = c["scenarios"].get("interleaved", [])
            t0 = hops[0]
            sid = t0["claims"]["sid"]
            # events in this session
            ev = sorted([e for e in events if e.get("sessionId") == sid and e["type"] == "TOKEN_EXCHANGE"], key=lambda e: e["time"])
            # map hop -> event by token id detail if present, else by order within client
            a_hops = [h for h in hops if h["label"].startswith("interleaved/T1-")]
            b_hops = [h for h in hops if h["label"].startswith("interleaved/T2-")]
            a_ev = [e for e in ev if e["clientId"] == "agent-a"]
            b_ev = [e for e in ev if e["clientId"] == "agent-b"]

            def ev_for(h, pool):
                for e in pool:
                    if h["claims"]["jti"] in (e.get("details") or {}).values():
                        return e
                # fall back: same order as issuance (hops are recorded in call order; events in time order)
                return None
            a_map = {h["claims"]["jti"]: ev_for(h, a_ev) for h in a_hops}
            if any(v is None for v in a_map.values()):
                # order-based fallback
                for h, e in zip(a_hops, a_ev):
                    a_map[h["claims"]["jti"]] = e
                b_order = sorted(b_hops, key=lambda h: h["claims"]["iat"])
                b_map = {h["claims"]["jti"]: e for h, e in zip(b_order, b_ev)}
                fallback = True
            else:
                b_map = {h["claims"]["jti"]: ev_for(h, b_ev) for h in b_hops}
                fallback = False
            rep_c = 0
            for h in b_hops:
                be = b_map[h["claims"]["jti"]]
                if be is None:
                    total += 1
                    continue
                prior = [e for e in a_ev if e["time"] <= be["time"]]
                pred = max(prior, key=lambda e: e["time"]) if prior else None
                truth = a_map[h["request"]["subject_token_jti"]]
                ok = pred is not None and truth is not None and pred is truth
                correct += int(ok)
                rep_c += int(ok)
                total += 1
            per_rep.append({"rep": c["rep"], "correct_of_3": rep_c, "order": c.get("interleaved_order"),
                            "event_mapping": "order-fallback" if fallback else "token_id_detail"})
        out["H3_attribution"] = {"correct": correct, "total": total, "per_rep": per_rep}
    # ---- H5 enforcer error events -----------------------------------------------------------------------------------
    err = [e for e in events if e["type"] == "TOKEN_EXCHANGE_ERROR"]
    out["H5_error_events"] = {"n": len(err), "detail_keys": dict(Counter(k for e in err for k in (e.get("details") or {}))),
                              "errors": dict(Counter(e.get("error") for e in err)),
                              "example": err[0] if err else None}
    # ---- latency ---------------------------------------------------------------------------------------------------
    lat = defaultdict(list)
    for r in hop_rows:
        if r["ns"] and r["status"] == 200:
            key = re.sub(r"-\d$", "-k", r["label"].split("/", 1)[1])
            lat[key].append(r["ns"] / 1e6)
    out["latency_ms"] = {k: {"n": len(v), "median": round(statistics.median(v), 1),
                             "cv": round(statistics.pstdev(v) / statistics.mean(v), 3) if len(v) > 1 else None,
                             "min": round(min(v), 1), "max": round(max(v), 1)} for k, v in lat.items()}
    out["loadavg"] = [(c["rep"], c.get("enforcer", False), c["loadavg_before"][0], c["loadavg_after"][0]) for c in data["chains"]]
    # ---- status per scenario/label across reps -----------------------------------------------------------------------
    st = defaultdict(Counter)
    for r in hop_rows:
        st[(("enf:" if r["enforcer"] else "") + re.sub(r"-\d$", "-k", r["label"]))][r["status"]] += 1
    out["status_by_label"] = {k: dict(v) for k, v in st.items()}
    # event-set equality across reps (modulo ids/time): multiset of (type, clientId, error, sorted detail keys, scope) per scenario
    sig = defaultdict(list)
    for c in data["chains"]:
        for scen, hops in c["scenarios"].items():
            sids = {h["claims"].get("sid") for h in hops if h.get("claims")} - {None}
            evs = [e for e in events if e.get("sessionId") in sids]
            s = sorted((e["type"], e.get("clientId"), e.get("error"), tuple(sorted((e.get("details") or {}).keys())),
                        (e.get("details") or {}).get("scope")) for e in evs)
            sig[("enf:" if c.get("enforcer") else "") + scen].append(json.dumps(s))
    out["event_set_stability"] = {k: {"reps": len(v), "distinct_signatures": len(set(v))} for k, v in sig.items()}
    return out


def md_table(headers, rows):
    s = "| " + " | ".join(headers) + " |\n|" + "---|" * len(headers) + "\n"
    for r in rows:
        s += "| " + " | ".join(str(x) for x in r) + " |\n"
    return s


def main():
    res = {}
    for arm in ("S", "D"):
        if (RAW / arm / "capture" / "events.json").exists():
            res[arm] = score_arm(arm, load_arm(arm))
    (HERE / "results" / "score.json").write_text(json.dumps(res, indent=1, default=str))
    # tables
    md = ["# T7 scored tables (generated by score.py)\n"]
    for arm, r in res.items():
        md.append(f"\n## Arm {arm}: {r['reps']} chain files, {r['n_events']} user events, {r['n_admin_events']} admin events, "
                  f"{r['n_log_event_lines']} log event lines\n")
        md.append("\n### REST event field inventory\n")
        rows = [(t, v["n"], ", ".join(sorted(v["top"])), ", ".join(sorted(v["details"]))) for t, v in sorted(r["rest_inventory"].items())]
        md.append(md_table(["type", "n", "top-level fields (non-null)", "detail keys"], rows))
        md.append("\n### Log line keys vs REST (H7)\n")
        rows = [(t, v["n_rest"], v["n_log"], ", ".join(v["rest_only"]) or "-", ", ".join(v["log_only"]) or "-") for t, v in sorted(r["H7_parity"].items())]
        md.append(md_table(["type", "n REST", "n log", "REST-only keys", "log-only keys"], rows))
        md.append("\n### Claims inventory per token position\n")
        rows = [(k, v.get("n"), v.get("sig_verified"), v.get("jti", 0), v.get("sid", 0), v.get("azp", 0), v.get("aud", 0), v.get("scope", 0),
                 v.get("realm_access", 0), v.get("act", 0), v.get("may_act", 0)) for k, v in sorted(r["claims_inventory"].items())]
        md.append(md_table(["position", "n", "sig ok", "jti", "sid", "azp", "aud", "scope", "realm_access", "act", "may_act"], rows))
        md.append(f"\n### H1 parent pointer\n\n{json.dumps(r['H1'])}\n\nmatch methods: {json.dumps(r['match_methods'])}\n")
        md.append("\n### H4 detection from events alone\n")
        rows = [(k, v["n"], v["scope_detail_present"], v["chain_aware"], v["root_only"], v.get("parent_link_correct", "n/a (sessionId)"), v.get("example_types"), v.get("example_scopes"))
                for k, v in r["H4_detection"].items()]
        md.append(md_table(["scenario", "n", "scope detail on all hops", "chain-aware flagged", "root-only flagged", "parent link correct", "event types", "data scopes per hop (example)"], rows))
        md.append(f"\nrequested vs effective scope on successful exchanges: {json.dumps(r['requested_vs_effective'])}\n")
        if "H3_attribution" in r:
            md.append(f"\n### H3 attribution (interleaved)\n\n{json.dumps(r['H3_attribution'])}\n")
        md.append(f"\n### H5 TOKEN_EXCHANGE_ERROR events\n\n{json.dumps(r['H5_error_events'], default=str)[:1500]}\n")
        md.append("\n### Status by hop label across reps\n")
        md.append(md_table(["label", "statuses"], sorted(r["status_by_label"].items())))
        md.append("\n### Event-set stability across reps\n")
        md.append(md_table(["scenario", "reps", "distinct signatures"], [(k, v["reps"], v["distinct_signatures"]) for k, v in sorted(r["event_set_stability"].items())]))
        md.append("\n### Token endpoint round trip, ms (under contention; not a finding)\n")
        md.append(md_table(["hop", "n", "median", "CV", "min", "max"], [(k, v["n"], v["median"], v["cv"], v["min"], v["max"]) for k, v in sorted(r["latency_ms"].items())]))
        md.append(f"\nload average (1-min) before/after each rep: {r['loadavg']}\n")
        md.append("\n### Admin events (operation:resourceType)\n")
        md.append(md_table(["op:type", "n", "fields"], [(k, v["n"], ", ".join(sorted(v["top"]))) for k, v in sorted(r["admin_inventory"].items())]))
    (HERE / "results" / "tables.md").write_text("".join(md))
    print(json.dumps({a: {"H1": r["H1"], "H3": r.get("H3_attribution", {}).get("correct"), "H4": {k: (v["chain_aware"], v["root_only"], v["n"]) for k, v in r["H4_detection"].items()},
                          "H5_err_detail_keys": r["H5_error_events"]["detail_keys"], "claims": r["claims_inventory"]} for a, r in res.items()}, indent=1, default=str))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Map Keycloak audit events to OCSF 1.9.0 and validate against schema.ocsf.io (public validator, no spend).

Two producers are modelled per hop, because the brief's question is what the IdP alone can say:
  * events-only: fields taken from the REST event (what a SIEM collector gets from Keycloak);
  * token-in-hand: the same record plus claims from the issued token and the exchanging agent's own record of
    which subject token it presented (that is what `delegation.parent_uid` needs, and the IdP never emits it).

Category calls (ontology-thinking checklist): an exchange hop is an occurrent -> an `authentication` (3002) event,
not a delegation object by itself; the `delegation` object is the durable authorization context the hop created
(its uid is the issued token id). The requesting client is the actor (actor.app_name); the human principal is
`user`; the audience is the `service` the ticket is for. Activity 4 "Service Ticket Request" is Kerberos
vocabulary, used here for an OAuth token requested for a named service; the note is recorded in `unmapped`.
Admin events: user create and role-mapping are `account_change` (3001); client, scope, mapper and policy
creation are `entity_management` (3004), since those are not changes to a user account.
"""
from __future__ import annotations

import json
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"
VALIDATE = "https://schema.ocsf.io/api/v2/validate"
PRODUCT = {"name": "Keycloak", "vendor_name": "Keycloak", "version": "26.8.1"}
DELEGATION_ATTRS = ["uid", "parent_uid", "issuer_uid", "scopes", "audience", "created_time", "expiration_time"]  # main (1.10.0-dev)
DELEGATION_ATTRS_190 = ["uid", "parent_uid", "issuer_uid", "created_time"]                                    # 1.9.0 release
# dst_endpoint is producer configuration (the IdP's own token endpoint), not an event field; it satisfies the
# authentication class constraint at_least_one[service, dst_endpoint] and is labelled as configuration in unmapped.
DST = {"ip": "127.0.0.1", "port": 8080, "svc_name": "keycloak-token-endpoint"}

MAPPING_NOTES = {
    "TOKEN_EXCHANGE": "3002 activity_id 4 (Service Ticket Request): Kerberos caption reused for an OAuth 2.0 token requested for a named audience; alternative is 99 Other.",
    "LOGIN": "3002 activity_id 1 (Logon); ROPC in arm S, authorization code in arm D.",
    "CODE_TO_TOKEN": "3002 activity_id 99 (Other, 'Code to token'): token issuance step of the code flow; the LOGIN event is the authentication.",
    "CLIENT_LOGIN": "3002 activity_id 1 (Logon) with user.type_id 4 (Service): the client's service account.",
    "TOKEN_EXCHANGE_ERROR": "3002 activity_id 4, status_id 2 (Failure). Keycloak emits no userId on an enforcer refusal, so `user` (required) is left absent and the validator result is the finding.",
    "LOGIN_ERROR": "3002 activity_id 1, status_id 2.",
}


def base(ev, class_uid, activity_id, class_name, activity_name, realm_issuer, status_id=1):
    return {
        "class_uid": class_uid, "class_name": class_name, "category_uid": 3, "category_name": "Identity & Access Management",
        "activity_id": activity_id, "activity_name": activity_name, "type_uid": class_uid * 100 + activity_id,
        "severity_id": 1, "status_id": status_id, "time": ev["time"],
        "metadata": {"version": "1.9.0", "product": PRODUCT, "uid": ev["id"], "log_name": "keycloak-events",
                     "event_code": ev["type"], "profiles": ["ai_operation"]},
        "src_endpoint": {"ip": ev["ipAddress"]} if ev.get("ipAddress") else None,
        "dst_endpoint": dict(DST) if class_uid == 3002 else None,
    }


def clean(d):
    if isinstance(d, dict):
        return {k: clean(v) for k, v in d.items() if v not in (None, "", [], {}) and clean(v) not in (None, {}, [])}
    if isinstance(d, list):
        return [clean(x) for x in d]
    return d


def delegation_from_event(ev, realm_issuer):
    det = ev.get("details") or {}
    return {"uid": det.get("token_id"), "issuer_uid": realm_issuer,
            "scopes": det.get("scope", "").split() or None, "audience": det.get("audience"),
            "created_time": ev["time"]}


def map_user_event(ev, realm_issuer, token_rec=None):
    det = ev.get("details") or {}
    t = ev["type"]
    user = {"name": det.get("username"), "uid": ev.get("userId")} if (det.get("username") or ev.get("userId")) else None
    actor = {"app_name": ev.get("clientId"), "session": {"uid": ev.get("sessionId")} if ev.get("sessionId") else None}
    session = {"uid": ev.get("sessionId"), "issuer": realm_issuer} if ev.get("sessionId") else None
    token = {"uid": det.get("token_id"), "type_id": 6, "type": "OAuth 2.0 access token", "created_time": ev["time"]} if det.get("token_id") else None
    unmapped = {k: v for k, v in det.items() if k not in ("username", "scope", "audience", "token_id")}
    unmapped["mapping_note"] = MAPPING_NOTES.get(t, "")
    unmapped["dst_endpoint_source"] = "producer configuration (IdP token endpoint), not an event field"
    if t == "LOGIN":
        rec = base(ev, 3002, 1, "Authentication", "Logon", realm_issuer)
        rec.update({"auth_protocol_id": 6, "auth_protocol": "OAUTH 2.0", "is_new_logon": True, "user": user, "actor": actor,
                    "session": session, "authentication_token": token,
                    "delegation": delegation_from_event(ev, realm_issuer) if det.get("token_id") else None})
    elif t == "CODE_TO_TOKEN":
        rec = base(ev, 3002, 99, "Authentication", "Code to token", realm_issuer)
        rec.update({"auth_protocol_id": 6, "user": user, "actor": actor, "session": session, "authentication_token": token,
                    "delegation": delegation_from_event(ev, realm_issuer)})
    elif t == "CLIENT_LOGIN":
        rec = base(ev, 3002, 1, "Authentication", "Logon", realm_issuer)
        rec.update({"auth_protocol_id": 6, "user": {"name": det.get("username"), "uid": ev.get("userId"), "type_id": 4},
                    "actor": actor, "authentication_token": token})
    elif t == "TOKEN_EXCHANGE":
        rec = base(ev, 3002, 4, "Authentication", "Service Ticket Request", realm_issuer)
        deleg = delegation_from_event(ev, realm_issuer)
        if det.get("actor_id"):   # arm D: the actor client's service account
            actor["user"] = {"uid": det["actor_id"], "name": det.get("actor"), "type_id": 4}
        rec.update({"auth_protocol_id": 6, "user": user, "actor": actor, "session": session, "authentication_token": token,
                    "service": {"name": det.get("audience")} if det.get("audience") else None, "delegation": deleg})
    elif t == "TOKEN_EXCHANGE_ERROR":
        rec = base(ev, 3002, 4, "Authentication", "Service Ticket Request", realm_issuer, status_id=2)
        rec.update({"auth_protocol_id": 6, "user": user, "actor": actor, "status_code": ev.get("error"),
                    "status_detail": det.get("client_policy_error_detail") or det.get("reason"),
                    "service": {"name": det.get("audience")} if det.get("audience") else None})
    elif t == "LOGIN_ERROR":
        rec = base(ev, 3002, 1, "Authentication", "Logon", realm_issuer, status_id=2)
        rec.update({"auth_protocol_id": 6, "user": user, "actor": actor, "status_code": ev.get("error"), "status_detail": det.get("reason")})
    else:
        return None
    rec["unmapped"] = unmapped
    # token-in-hand enrichment (second producer): parent_uid from the agent's record, exp from the token
    if token_rec and rec.get("delegation"):
        cl = token_rec.get("claims") or {}
        rec["delegation"]["expiration_time"] = cl.get("exp", 0) * 1000 if cl.get("exp") else None
        if token_rec["request"].get("subject_token_jti"):
            rec["delegation"]["parent_uid"] = token_rec["request"]["subject_token_jti"]
        if cl.get("act"):
            rec["unmapped"]["act"] = cl["act"]
    return clean(rec)


def map_admin_event(ae, realm_issuer):
    rt, op = ae.get("resourceType"), ae.get("operationType")
    act_map = {"CREATE": 1, "UPDATE": 3, "DELETE": 4}
    actor = {"user": {"uid": (ae.get("authDetails") or {}).get("userId"), "type_id": 2}, "app_uid": (ae.get("authDetails") or {}).get("clientId")}
    rep = {}
    try:
        rep = json.loads(ae.get("representation") or "{}")
    except Exception:
        pass
    ev = {"time": ae["time"], "id": ae["id"], "type": f"ADMIN:{op}:{rt}", "ipAddress": (ae.get("authDetails") or {}).get("ipAddress")}
    if rt == "USER":
        rec = base(ev, 3001, act_map.get(op, 99), "Account Change", op.title(), realm_issuer)
        rec.update({"user": {"name": rep.get("username"), "uid": ae.get("resourcePath", "").split("/")[-1]}, "actor": actor})
    elif rt == "REALM_ROLE_MAPPING":
        rec = base(ev, 3001, 7, "Account Change", "Attach Policy", realm_issuer)
        path = ae.get("resourcePath", "").split("/")
        rec.update({"user": {"uid": path[1] if len(path) > 1 else None}, "actor": actor,
                    "policies": [{"name": r.get("name"), "uid": r.get("id")} for r in (rep if isinstance(rep, list) else [])]})
    else:
        rec = base(ev, 3004, act_map.get(op, 99), "Entity Management", op.title(), realm_issuer)
        name = rep.get("name") or rep.get("clientId") if isinstance(rep, dict) else None
        rec.update({"actor": actor, "entity": {"type": rt, "uid": ae.get("resourcePath"), "name": name},
                    "unmapped": {"resourcePath": ae.get("resourcePath"), "resourceType": rt}})
    return clean(rec)


def to_release_shape(rec):
    """1.9.0 release: delegation has only uid/parent_uid/issuer_uid/created_time; the main-only attributes move to unmapped."""
    r = json.loads(json.dumps(rec))
    d = r.get("delegation")
    if d:
        extra = {k: d.pop(k) for k in list(d) if k not in DELEGATION_ATTRS_190}
        if extra:
            r.setdefault("unmapped", {})["delegation_main_only"] = extra
    return r


def validate(rec, version=None, profiles="ai_operation"):
    # the version is selected by path (schema.ocsf.io/<version>/api/v2/validate); the `version` query parameter is
    # ignored by the server (checked 2026-11-10: a main-only attribute was rejected with ?version=1.10.0-dev and
    # accepted at the /1.10.0-dev/ path, and a bogus attribute is rejected at that path)
    url = (f"https://schema.ocsf.io/{version}/api/v2/validate" if version else VALIDATE) + (f"?profiles={profiles}" if profiles else "")
    r = urllib.request.Request(url, data=json.dumps(rec).encode(), headers={"Content-Type": "application/json"})
    v = json.load(urllib.request.urlopen(r, timeout=60))
    return {"errors": [(e.get("error"), e.get("attribute_path") or e.get("attribute")) for e in v.get("errors", [])],
            "warnings": [(w.get("warning"), w.get("attribute_path") or w.get("attribute")) for w in v.get("warnings", [])]}


def main():
    out = {"producers": {}, "fill": {}, "validation": {}}
    for arm, realm in (("S", "t7s"), ("D", "t7d")):
        d = RAW / arm
        if not (d / "capture" / "events.json").exists():
            continue
        issuer = f"http://127.0.0.1:8080/realms/{realm}"
        events = json.load(open(d / "capture" / "events.json"))
        admin = json.load(open(d / "capture" / "admin-events.json"))
        # token records by issued jti
        by_jti = {}
        for p in sorted(d.glob("chains-rep*.json")):
            c = json.load(open(p))
            for hops in c["scenarios"].values():
                for h in hops:
                    if h.get("claims"):
                        by_jti[h["claims"]["jti"]] = h
        recs_events_only, recs_token = [], []
        fill = defaultdict(lambda: {"events_only": Counter(), "token_in_hand": Counter(), "n": 0})
        for ev in events:
            r0 = map_user_event(ev, issuer)
            if not r0:
                continue
            recs_events_only.append(r0)
            tok = by_jti.get((ev.get("details") or {}).get("token_id"))
            r1 = map_user_event(ev, issuer, tok)
            recs_token.append(r1)
            if ev["type"] in ("TOKEN_EXCHANGE", "LOGIN", "CODE_TO_TOKEN"):
                f = fill[ev["type"]]
                f["n"] += 1
                for a in DELEGATION_ATTRS:
                    tag = "" if a in DELEGATION_ATTRS_190 else " (main-only)"
                    if (r0.get("delegation") or {}).get(a) not in (None, [], ""):
                        f["events_only"][a + tag] += 1
                    if (r1.get("delegation") or {}).get(a) not in (None, [], ""):
                        f["token_in_hand"][a + tag] += 1
        recs_admin = [map_admin_event(a, issuer) for a in admin]
        out["fill"][arm] = {t: {"n": v["n"], "events_only": dict(v["events_only"]), "token_in_hand": dict(v["token_in_hand"])} for t, v in fill.items()}
        # validate: every record (events-only + admin), and the token-in-hand records (de-duplicated by shape to save calls)
        vres = {}
        for name, recs, ver, shaper in (("events_only@1.9.0", recs_events_only, None, to_release_shape),
                                        ("token_in_hand@1.9.0", recs_token, None, to_release_shape),
                                        ("admin@1.9.0", recs_admin, None, lambda r: r),
                                        ("events_only@1.10.0-dev", recs_events_only, "1.10.0-dev", lambda r: r),
                                        ("token_in_hand@1.10.0-dev", recs_token, "1.10.0-dev", lambda r: r)):
            kinds_e, kinds_w, n = Counter(), Counter(), 0
            seen = set()
            per_type = defaultdict(lambda: {"n": 0, "errors": Counter()})
            for rec in recs:
                shape = json.dumps({"c": rec.get("class_uid"), "a": rec.get("activity_id"), "k": sorted(rec.keys()),
                                    "ek": rec.get("metadata", {}).get("event_code"),
                                    "dk": sorted((rec.get("delegation") or {}).keys()), "u": "user" in rec})
                if shape in seen:
                    continue
                seen.add(shape)
                v = validate(shaper(rec), version=ver, profiles="ai_operation" if rec.get("class_uid") == 3002 else None)
                n += 1
                key = rec.get("metadata", {}).get("event_code")
                per_type[key]["n"] += 1
                for e in v["errors"]:
                    kinds_e[f"{e[0]}@{e[1]}"] += 1
                    per_type[key]["errors"][f"{e[0]}@{e[1]}"] += 1
                for w in v["warnings"]:
                    kinds_w[f"{w[0]}@{w[1]}"] += 1
            vres[name] = {"distinct_shapes_validated": n, "records": len(recs), "error_kinds": dict(kinds_e),
                          "warning_kinds": dict(kinds_w), "per_event_code": {k: {"n": v["n"], "errors": dict(v["errors"])} for k, v in per_type.items()}}
        out["validation"][arm] = vres
        (HERE / "results" / f"ocsf_records_{arm}_events_only.jsonl").write_text("\n".join(json.dumps(r) for r in recs_events_only))
        (HERE / "results" / f"ocsf_records_{arm}_events_only_release190.jsonl").write_text("\n".join(json.dumps(to_release_shape(r)) for r in recs_events_only))
        (HERE / "results" / f"ocsf_records_{arm}_token_in_hand.jsonl").write_text("\n".join(json.dumps(r) for r in recs_token))
        (HERE / "results" / f"ocsf_records_{arm}_admin.jsonl").write_text("\n".join(json.dumps(r) for r in recs_admin))
        out["producers"][arm] = {"user_events": len(recs_events_only), "admin_events": len(recs_admin), "mapping_notes": MAPPING_NOTES}
    (HERE / "results" / "ocsf_mapping.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({"fill": out["fill"], "validation": {a: {k: (v["error_kinds"], v["distinct_shapes_validated"]) for k, v in vr.items()} for a, vr in out["validation"].items()}}, indent=1))


if __name__ == "__main__":
    main()

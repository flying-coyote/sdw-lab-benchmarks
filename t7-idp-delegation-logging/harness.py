#!/usr/bin/env python3
"""T7 harness: build the realm, run delegation chains, capture IdP audit surfaces.

Usage:
  harness.py setup   --arm S|D --realm NAME
  harness.py run     --arm S|D --realm NAME --rep K [--enforcer]
  harness.py capture --arm S|D --realm NAME --tag TAG --container NAME --since ISO

All outputs go under results/raw/<arm>/. Secrets are runtime fixtures (results/raw/<arm>/fixture-secrets.json).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import secrets
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kc  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"
REDIRECT = "http://127.0.0.1:9/cb"   # never served; only the Location header is parsed
USER = "alice"
ROLES = ["data-read", "data-write", "data-admin"]
USER_ROLES = ["data-read", "data-write"]           # root authority: alice never holds data-admin
DATA_SCOPES = ["data:read", "data:write", "data:admin"]
CLIENTS = ["app-frontend", "agent-a", "agent-b", "tool-api"]
NEXT_HOP = {"app-frontend": "agent-a", "agent-a": "agent-b", "agent-b": "tool-api"}


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def admin():
    pw = (HERE / "results" / ".admin-pw").read_text().strip()
    return kc.Admin(pw)


# ---------------------------------------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------------------------------------

def setup(arm, realm):
    A = admin()
    A.ensure_realm_absent(realm)
    rep = {
        "realm": realm, "enabled": True,
        "accessTokenLifespan": 600,
        "eventsEnabled": True, "eventsListeners": ["jboss-logging"], "enabledEventTypes": [],   # [] = all types
        "adminEventsEnabled": True, "adminEventsDetailsEnabled": True,
        "eventsExpiration": 86400,
    }
    if arm == "D":
        rep["adminPermissionsEnabled"] = True
    A.create_realm(rep)
    # realm roles
    for r in ROLES:
        A.post(f"/realms/{realm}/roles", {"name": r})
    # user alice with a runtime-generated password (fixture)
    upw = secrets.token_urlsafe(16)
    st, hdr, _ = A.post(f"/realms/{realm}/users", {"username": USER, "enabled": True, "email": "alice@example.test",
                                                    "emailVerified": True, "firstName": "Alice", "lastName": "Fixture",
                                                    "credentials": [{"type": "password", "value": upw, "temporary": False}]})
    uid = A.created_id(hdr)
    A.post(f"/realms/{realm}/users/{uid}/role-mappings/realm", [A.realm_role(realm, r) for r in USER_ROLES])
    # authority scopes: each data:* client scope maps exactly one realm role
    for s, r in zip(DATA_SCOPES, ROLES):
        st, hdr, _ = A.post(f"/realms/{realm}/client-scopes", {"name": s, "protocol": "openid-connect",
                                                                 "attributes": {"include.in.token.scope": "true",
                                                                                "display.on.consent.screen": "true"}})
        sid = A.created_id(hdr)
        A.post(f"/realms/{realm}/client-scopes/{sid}/scope-mappings/realm", [A.realm_role(realm, r)])
    # audience scopes: aud:<client> adds <client> to aud via an Audience mapper (no roles, so the audience= param
    # only filters them, per the Keycloak token-exchange docs)
    for c in ["agent-a", "agent-b", "tool-api"]:
        st, hdr, _ = A.post(f"/realms/{realm}/client-scopes", {"name": f"aud:{c}", "protocol": "openid-connect",
                                                                 "attributes": {"include.in.token.scope": "false",
                                                                                "display.on.consent.screen": "false"}})
        sid = A.created_id(hdr)
        A.post(f"/realms/{realm}/client-scopes/{sid}/protocol-mappers/models",
               {"name": f"aud-{c}", "protocol": "openid-connect", "protocolMapper": "oidc-audience-mapper",
                "config": {"included.client.audience": c, "access.token.claim": "true", "id.token.claim": "false"}})
    # clients
    fixture = {"realm": realm, "arm": arm, "label": "TEST FIXTURE - runtime-generated, localhost dev Keycloak only",
               "user": USER, "user_password": upw, "clients": {}}
    for c in CLIENTS:
        sec = secrets.token_urlsafe(24)
        crep = {"clientId": c, "enabled": True, "protocol": "openid-connect", "publicClient": False,
                "secret": sec, "fullScopeAllowed": False, "serviceAccountsEnabled": c in ("agent-a", "agent-b"),
                "standardFlowEnabled": c == "app-frontend", "directAccessGrantsEnabled": c == "app-frontend",
                "redirectUris": [REDIRECT] if c == "app-frontend" else [],
                "consentRequired": (arm == "D" and c == "app-frontend"),
                "defaultClientScopes": ["roles", "basic"] + ([f"aud:{NEXT_HOP[c]}"] if c in NEXT_HOP else []),
                "optionalClientScopes": (list(DATA_SCOPES) if c != "tool-api" else [])
                                        + (["delegation:client"] if (arm == "D" and c == "app-frontend") else []),
                "attributes": {}}
        if c in ("agent-a", "agent-b"):
            crep["attributes"]["standard.token.exchange.enabled"] = "true"
        A.post(f"/realms/{realm}/clients", crep)
        fixture["clients"][c] = sec
    # role scope mappings on client scopes need the client to NOT have full scope; done above.
    if arm == "D":
        setup_delegation_permissions(A, realm)
    fixture["setup_done"] = now_iso()
    (RAW / arm).mkdir(parents=True, exist_ok=True)
    (RAW / arm / "fixture-secrets.json").write_text(json.dumps(fixture, indent=1))
    # record realm/client representations as configured
    (RAW / arm / "realm-config.json").write_text(json.dumps({
        "realm": A.get(f"/realms/{realm}"),
        "clients": A.get(f"/realms/{realm}/clients"),
        "client_scopes": A.get(f"/realms/{realm}/client-scopes"),
    }, indent=1, default=str))
    print(json.dumps({"setup": realm, "arm": arm, "at": fixture["setup_done"]}))


def setup_delegation_permissions(A, realm):
    """FGAP V2: grant the 'delegate' scope on Users to the actor clients (client policy -> scope permission)."""
    ap = A.client_uuid(realm, "admin-permissions")
    rs = f"/realms/{realm}/clients/{ap}/authz/resource-server"
    info = {"resource_server": A.get(rs)}
    # discover the resource types / scopes the server exposes
    try:
        info["scopes"] = A.get(f"{rs}/scope")
    except kc.KCError as e:
        info["scopes_err"] = str(e)
    # one client policy naming both actor clients (a client policy matches any listed client); admin permissions
    # accept only the UNANIMOUS decision strategy (server 400 otherwise), so a single policy is the way to say "either"
    st, hdr, body = A.post(f"{rs}/policy/client", {"name": "actor-agents", "logic": "POSITIVE",
                                                     "clients": [A.client_uuid(realm, c) for c in ["agent-a", "agent-b"]]})
    pol_ids = [(body or {}).get("id") or A.created_id(hdr)]
    perm = {"name": "delegate-to-agents", "resourceType": "Users", "scopes": ["delegate"], "policies": pol_ids,
            "decisionStrategy": "UNANIMOUS", "logic": "POSITIVE"}
    try:
        st, hdr, body = A.post(f"{rs}/permission/scope", perm)
        info["permission"] = body
    except kc.KCError as e:
        info["permission_err"] = str(e)
        # fall back: list available scopes to help a human see what the server expects
        raise
    (RAW / "D").mkdir(parents=True, exist_ok=True)
    (RAW / "D" / "fgap-setup.json").write_text(json.dumps(info, indent=1, default=str))


# ---------------------------------------------------------------------------------------------------------
# chains
# ---------------------------------------------------------------------------------------------------------

def tok_record(realm, label, st, js, ns, request):
    rec = {"label": label, "status": st, "ns": ns, "request": request, "response": js}
    if st == 200 and js and "access_token" in js:
        try:
            rec["claims"] = kc.decode_verified(realm, js["access_token"])
            rec["signature_verified"] = True
        except Exception as e:  # record, never hide
            rec["claims"] = kc.decode_unverified(js["access_token"])
            rec["signature_verified"] = False
            rec["verify_error"] = repr(e)
        rec["response"] = {k: v for k, v in js.items() if k not in ("access_token", "refresh_token", "id_token")}
        rec["response"]["access_token_jti"] = rec["claims"].get("jti")
    return rec


def login_ropc(realm, fx, scope, label):
    st, js, ns = kc.ropc(realm, "app-frontend", fx["clients"]["app-frontend"], USER, fx["user_password"], scope)
    rec = tok_record(realm, f"{label}/T0-login", st, js, ns, {"grant": "password", "client": "app-frontend", "scope": scope})
    rec["__at"] = js.get("access_token") if st == 200 else None
    return rec


def run_S(realm, fx, rep, enforcer):
    out = {"arm": "S", "rep": rep, "enforcer": enforcer, "started": now_iso(), "scenarios": {}}
    S = out["scenarios"]
    # fixed scenario order; the interleaved one shuffles hop order with a seeded RNG per rep
    scen = {
        "baseline":  ("data:read", "data:read"),
        "reacquire": ("data:read", "data:read data:write"),      # write dropped at hop 1, re-granted at hop 2
        "new":       ("data:read", "data:read data:admin"),      # admin never held by alice
    }
    for name, (h1, h2) in scen.items():
        t0 = login_ropc(realm, fx, "data:read data:write", name)
        hops = [t0]
        if t0["status"] == 200:
            st, js, ns = kc.exchange(realm, "agent-a", fx["clients"]["agent-a"], t0["__at"], audience="agent-b", scope=h1)
            t1 = tok_record(realm, f"{name}/T1-agent-a", st, js, ns,
                            {"grant": "token-exchange", "client": "agent-a", "audience": "agent-b", "scope": h1,
                             "subject_token_jti": t0["claims"].get("jti")})
            hops.append(t1)
            if st == 200:
                st2, js2, ns2 = kc.exchange(realm, "agent-b", fx["clients"]["agent-b"], js["access_token"],
                                            audience="tool-api", scope=h2)
                hops.append(tok_record(realm, f"{name}/T2-agent-b", st2, js2, ns2,
                                       {"grant": "token-exchange", "client": "agent-b", "audience": "tool-api", "scope": h2,
                                        "subject_token_jti": t1["claims"].get("jti")}))
        t0.pop("__at", None)
        S[name] = hops
    if not enforcer:
        # interleaved: ONE login, three agent-a instances exchange the same T0, then three agent-b exchanges in a
        # shuffled order; truth is the subject_token_jti recorded per hop.
        rng = random.Random(20261109 + rep)
        t0 = login_ropc(realm, fx, "data:read data:write", "interleaved")
        hops = [t0]
        t1s = []
        h1_scopes = ["data:read", "data:read data:write", "data:write"]
        for i, h1 in enumerate(h1_scopes):
            st, js, ns = kc.exchange(realm, "agent-a", fx["clients"]["agent-a"], t0["__at"], audience="agent-b", scope=h1)
            r = tok_record(realm, f"interleaved/T1-{i}", st, js, ns,
                           {"grant": "token-exchange", "client": "agent-a", "audience": "agent-b", "scope": h1,
                            "subject_token_jti": t0["claims"].get("jti"), "chain": i})
            r["__at"] = js.get("access_token") if st == 200 else None
            t1s.append(r)
            hops.append(r)
        order = list(range(3))
        rng.shuffle(order)
        h2_scopes = {0: "data:read", 1: "data:read data:write", 2: "data:write"}
        for i in order:
            r1 = t1s[i]
            if not r1["__at"]:
                continue
            st, js, ns = kc.exchange(realm, "agent-b", fx["clients"]["agent-b"], r1["__at"], audience="tool-api",
                                     scope=h2_scopes[i])
            hops.append(tok_record(realm, f"interleaved/T2-{i}", st, js, ns,
                                   {"grant": "token-exchange", "client": "agent-b", "audience": "tool-api",
                                    "scope": h2_scopes[i], "subject_token_jti": r1["claims"].get("jti"), "chain": i}))
        for h in hops:
            h.pop("__at", None)
        out["interleaved_order"] = order
        S["interleaved"] = hops
    out["finished"] = now_iso()
    return out


def run_D(realm, fx, rep):
    """Preview RFC 8693 delegation: consent-granted may_act, then actor_token exchange -> act."""
    out = {"arm": "D", "rep": rep, "started": now_iso(), "scenarios": {}}
    S = out["scenarios"]
    fe = fx["clients"]["app-frontend"]

    def login(scope, label):
        st, js, steps = kc.browser_login(realm, "app-frontend", fe, USER, fx["user_password"], scope, REDIRECT)
        rec = tok_record(realm, f"{label}/T0-login", st, js, steps.get("code_to_token_ns", 0),
                         {"grant": "authorization_code+consent", "client": "app-frontend", "scope": scope})
        rec["browser_steps"] = {k: v for k, v in steps.items() if k != "code_to_token_ns"}
        rec["__at"] = js.get("access_token") if st == 200 and isinstance(js, dict) else None
        return rec

    def actor(client, label):
        st, js, ns = kc.client_credentials(realm, client, fx["clients"][client])
        r = tok_record(realm, f"{label}/actor-{client}", st, js, ns, {"grant": "client_credentials", "client": client})
        r["__at"] = js.get("access_token") if st == 200 else None
        return r

    # D1 baseline: alice consents to agent-a acting; agent-a exchanges with actor_token requesting data:read only
    for name, login_scope, h1 in [
        ("baseline",  "openid data:read data:write delegation:client:agent-a", "data:read"),
        ("reacquire", "openid data:read delegation:client:agent-a",            "data:read data:write"),  # write absent in T0
        ("new",       "openid data:read data:write delegation:client:agent-a", "data:read data:admin"),
    ]:
        hops = []
        t0 = login(login_scope, name); hops.append(t0)
        if t0["__at"]:
            act_a = actor("agent-a", name); hops.append(act_a)
            st, js, ns = kc.exchange(realm, "agent-a", fx["clients"]["agent-a"], t0["__at"], audience="agent-b",
                                     scope=h1, actor_token=act_a["__at"])
            t1 = tok_record(realm, f"{name}/T1-agent-a-delegated", st, js, ns,
                            {"grant": "token-exchange+actor_token", "client": "agent-a", "audience": "agent-b", "scope": h1,
                             "subject_token_jti": t0["claims"].get("jti"), "actor_token_jti": act_a.get("claims", {}).get("jti")})
            hops.append(t1)
            if name == "baseline" and st == 200:
                # hop-2 attempts from agent-b on the delegated token
                st2, js2, ns2 = kc.exchange(realm, "agent-b", fx["clients"]["agent-b"], js["access_token"],
                                            audience="tool-api", scope="data:read")
                hops.append(tok_record(realm, f"{name}/T2a-agent-b-standard", st2, js2, ns2,
                                       {"grant": "token-exchange", "client": "agent-b", "audience": "tool-api", "scope": "data:read",
                                        "subject_token_jti": t1["claims"].get("jti")}))
                act_b = actor("agent-b", name); hops.append(act_b)
                st3, js3, ns3 = kc.exchange(realm, "agent-b", fx["clients"]["agent-b"], js["access_token"],
                                            audience="tool-api", scope="data:read", actor_token=act_b["__at"])
                hops.append(tok_record(realm, f"{name}/T2b-agent-b-delegated", st3, js3, ns3,
                                       {"grant": "token-exchange+actor_token", "client": "agent-b", "audience": "tool-api",
                                        "scope": "data:read", "subject_token_jti": t1["claims"].get("jti"),
                                        "actor_token_jti": act_b.get("claims", {}).get("jti")}))
        for h in hops:
            h.pop("__at", None)
        S[name] = hops
    # D4: can one subject token pre-authorize two actors? (docs: a parameterized scope cannot repeat)
    t0 = login("openid data:read delegation:client:agent-a delegation:client:agent-b", "two-actors")
    t0.pop("__at", None)
    S["two-actors"] = [t0]
    out["finished"] = now_iso()
    return out


# ---------------------------------------------------------------------------------------------------------
# enforcer (client policy) on/off
# ---------------------------------------------------------------------------------------------------------

def set_enforcer(realm, on):
    A = admin()
    profiles = {"profiles": [{"name": "t7-downscope", "description": "T7 control arm",
                              "executors": [{"executor": "downscope-assertion-grant-enforcer", "configuration": {}}]}]} \
        if on else {"profiles": []}
    policies = {"policies": [{"name": "t7-downscope-all", "enabled": True, "profiles": ["t7-downscope"],
                              "conditions": [{"condition": "any-client", "configuration": {}}]}]} \
        if on else {"policies": []}
    if on:
        A.put(f"/realms/{realm}/client-policies/profiles", profiles)
        A.put(f"/realms/{realm}/client-policies/policies", policies)
    else:
        A.put(f"/realms/{realm}/client-policies/policies", policies)
        A.put(f"/realms/{realm}/client-policies/profiles", profiles)
    print(json.dumps({"enforcer": on, "realm": realm, "at": now_iso()}))


# ---------------------------------------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------------------------------------

def capture(arm, realm, tag, container, since):
    A = admin()
    d = RAW / arm / tag
    d.mkdir(parents=True, exist_ok=True)
    ev = A.events(realm)
    aev = A.admin_events(realm)
    (d / "events.json").write_text(json.dumps(ev, indent=1))
    (d / "admin-events.json").write_text(json.dumps(aev, indent=1))
    log = subprocess.run(["docker", "logs", "--since", since, container], capture_output=True, text=True)
    (d / "container-log.txt").write_text(log.stdout + log.stderr)
    print(json.dumps({"capture": tag, "events": len(ev), "admin_events": len(aev),
                      "log_lines": (log.stdout + log.stderr).count("\n"), "at": now_iso()}))


# ---------------------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["setup", "run", "capture", "enforcer", "clear-events"])
    ap.add_argument("--arm", required=True)
    ap.add_argument("--realm", required=True)
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--enforcer", action="store_true")
    ap.add_argument("--on", action="store_true")
    ap.add_argument("--tag")
    ap.add_argument("--container")
    ap.add_argument("--since")
    a = ap.parse_args()
    if a.cmd == "setup":
        setup(a.arm, a.realm)
    elif a.cmd == "enforcer":
        set_enforcer(a.realm, a.on)
    elif a.cmd == "clear-events":
        admin().clear_events(a.realm)
        print(json.dumps({"cleared": a.realm, "at": now_iso()}))
    elif a.cmd == "run":
        fx = json.loads((RAW / a.arm / "fixture-secrets.json").read_text())
        load0 = os.getloadavg()
        res = run_S(a.realm, fx, a.rep, a.enforcer) if a.arm == "S" else run_D(a.realm, fx, a.rep)
        res["loadavg_before"] = load0
        res["loadavg_after"] = os.getloadavg()
        tag = f"rep{a.rep}" + ("-enforcer" if a.enforcer else "")
        (RAW / a.arm).mkdir(parents=True, exist_ok=True)
        (RAW / a.arm / f"chains-{tag}.json").write_text(json.dumps(res, indent=1, default=str))
        summary = {k: [(h["label"], h["status"]) for h in v] for k, v in res["scenarios"].items()}
        print(json.dumps({"run": tag, "arm": a.arm, "statuses": summary}))
    elif a.cmd == "capture":
        capture(a.arm, a.realm, a.tag, a.container, a.since)


if __name__ == "__main__":
    main()

"""Keycloak admin/OIDC helpers for T7 (stdlib HTTP; PyJWT only for signature-verified claim decoding).

Everything here is a test fixture against a localhost-bound dev Keycloak. Secrets are generated at runtime
and written only under results/ with a fixture label; nothing here is a real credential.
"""
from __future__ import annotations

import base64
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

import jwt
from jwt import PyJWKClient

BASE = "http://127.0.0.1:8080"


class KCError(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _req(method, url, data=None, headers=None, form=False, timeout=60, opener=None, allow_redirects=True):
    """Returns (status, headers, body, monotonic_ns). With allow_redirects=False a 3xx is returned as-is."""
    headers = dict(headers or {})
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data, doseq=True).encode()
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        else:
            body = json.dumps(data).encode()
            headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    if opener is None:
        opener = urllib.request.build_opener(*([_NoRedirect] if not allow_redirects else []))
    t0 = time.perf_counter_ns()
    try:
        with opener.open(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, dict(r.headers), raw, time.perf_counter_ns() - t0
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, dict(e.headers), raw, time.perf_counter_ns() - t0


def jload(raw):
    try:
        return json.loads(raw.decode()) if raw else None
    except Exception:
        return {"_raw": raw.decode(errors="replace")[:2000]}


class Admin:
    def __init__(self, admin_pw, base=BASE):
        self.base = base
        self.admin_pw = admin_pw
        self.tok = None
        self.tok_at = 0

    def token(self):
        if self.tok and time.time() - self.tok_at < 40:
            return self.tok
        st, _, raw, _ = _req("POST", f"{self.base}/realms/master/protocol/openid-connect/token",
                             {"client_id": "admin-cli", "username": "admin", "password": self.admin_pw,
                              "grant_type": "password"}, form=True)
        if st != 200:
            raise KCError(f"admin token {st}: {raw[:300]}")
        self.tok = jload(raw)["access_token"]
        self.tok_at = time.time()
        return self.tok

    def call(self, method, path, data=None, ok=(200, 201, 204), params=None):
        url = f"{self.base}/admin{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        st, hdr, raw, _ = _req(method, url, data, {"Authorization": f"Bearer {self.token()}"})
        if st not in ok:
            raise KCError(f"{method} {path} -> {st}: {raw[:500]}")
        return st, hdr, jload(raw)

    def get(self, path, params=None):
        return self.call("GET", path, params=params)[2]

    def post(self, path, data, ok=(200, 201, 204)):
        return self.call("POST", path, data, ok=ok)

    def put(self, path, data):
        return self.call("PUT", path, data)

    def delete(self, path, ok=(204, 404)):
        return self.call("DELETE", path, ok=ok)

    def created_id(self, hdr):
        loc = hdr.get("Location") or hdr.get("location")
        return loc.rstrip("/").split("/")[-1] if loc else None

    # --- realm-level helpers -------------------------------------------------------------------------
    def serverinfo(self):
        return self.get("/serverinfo")

    def ensure_realm_absent(self, realm):
        self.delete(f"/realms/{realm}")

    def create_realm(self, rep):
        return self.post("/realms", rep)

    def client_uuid(self, realm, client_id):
        r = self.get(f"/realms/{realm}/clients", {"clientId": client_id})
        if not r:
            raise KCError(f"client {client_id} not found")
        return r[0]["id"]

    def client_secret(self, realm, uuid):
        return self.get(f"/realms/{realm}/clients/{uuid}/client-secret")["value"]

    def scope_uuid(self, realm, name):
        for s in self.get(f"/realms/{realm}/client-scopes"):
            if s["name"] == name:
                return s["id"]
        raise KCError(f"client scope {name} not found")

    def realm_role(self, realm, name):
        return self.get(f"/realms/{realm}/roles/{name}")

    def events(self, realm, max_total=5000):
        out, first = [], 0
        while True:
            page = self.get(f"/realms/{realm}/events", {"first": first, "max": 500})
            out.extend(page)
            if len(page) < 500 or len(out) >= max_total:
                break
            first += 500
        return out

    def admin_events(self, realm, max_total=5000):
        out, first = [], 0
        while True:
            page = self.get(f"/realms/{realm}/admin-events", {"first": first, "max": 500})
            out.extend(page)
            if len(page) < 500 or len(out) >= max_total:
                break
            first += 500
        return out

    def clear_events(self, realm):
        self.delete(f"/realms/{realm}/events")
        self.delete(f"/realms/{realm}/admin-events")


# --- OIDC client side ------------------------------------------------------------------------------------

def token_endpoint(realm, base=BASE):
    return f"{base}/realms/{realm}/protocol/openid-connect/token"


def post_token(realm, form, base=BASE):
    """POST to the token endpoint; returns (status, json, monotonic_ns)."""
    st, _, raw, ns = _req("POST", token_endpoint(realm, base), form, form=True)
    return st, jload(raw), ns


def ropc(realm, client_id, client_secret, username, password, scope, base=BASE):
    return post_token(realm, {"grant_type": "password", "client_id": client_id, "client_secret": client_secret,
                              "username": username, "password": password, "scope": scope}, base)


def client_credentials(realm, client_id, client_secret, scope=None, base=BASE):
    f = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}
    if scope:
        f["scope"] = scope
    return post_token(realm, f, base)


def exchange(realm, client_id, client_secret, subject_token, audience=None, scope=None, actor_token=None,
             requested_token_type="urn:ietf:params:oauth:token-type:access_token", base=BASE):
    f = {"grant_type": "urn:ietf:params:oauth:grant-type:token-exchange", "client_id": client_id,
         "client_secret": client_secret, "subject_token": subject_token,
         "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
         "requested_token_type": requested_token_type}
    if audience:
        f["audience"] = audience
    if scope:
        f["scope"] = scope
    if actor_token:
        f["actor_token"] = actor_token
        f["actor_token_type"] = "urn:ietf:params:oauth:token-type:access_token"
    return post_token(realm, f, base)


_jwks = {}


def decode_verified(realm, token, base=BASE):
    """Signature-verified decode against the realm JWKS (aud/exp not enforced here; we record, not authorize)."""
    if realm not in _jwks:
        _jwks[realm] = PyJWKClient(f"{base}/realms/{realm}/protocol/openid-connect/certs", cache_keys=True)
    key = _jwks[realm].get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=["RS256", "ES256", "EdDSA"],
                      options={"verify_aud": False, "verify_exp": False})


def decode_unverified(token):
    return jwt.decode(token, options={"verify_signature": False})


# --- scripted browser login (authorization code + consent) -------------------------------------------------

def browser_login(realm, client_id, client_secret, username, password, scope, redirect_uri, base=BASE):
    """Drive Keycloak's login form and consent form, then redeem the code. No browser: the two HTML forms'
    action URLs are parsed, and cookies are carried as a plain name->value dict (http.cookiejar withheld
    KC_RESTART on the form POST during instrument development, so the jar is not used)."""
    cookies = {}
    steps = {}

    def go(method, url, data=None):
        hdrs = {"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())} if cookies else {}
        st, hdr, raw, ns = _req(method, url, data, hdrs, form=data is not None, allow_redirects=False)
        # collect Set-Cookie (urllib folds repeated headers into one comma-joined string; split on cookie boundaries)
        sc = hdr.get("Set-Cookie") or hdr.get("set-cookie") or ""
        for part in re.split(r",(?=\s*[A-Za-z0-9_\-]+=)", sc):
            kv = part.strip().split(";")[0]
            if "=" in kv:
                k, v = kv.split("=", 1)
                cookies[k.strip()] = v.strip()
        return st, hdr, raw

    state = secrets.token_urlsafe(8)
    q = urllib.parse.urlencode({"client_id": client_id, "response_type": "code", "scope": scope,
                                "redirect_uri": redirect_uri, "state": state})
    st, hdr, raw = go("GET", f"{base}/realms/{realm}/protocol/openid-connect/auth?{q}")
    steps["auth_get"] = st
    if st in (302, 303):
        return st, {"error": "auth_redirected", "location": hdr.get("Location") or hdr.get("location")}, steps
    html = raw.decode(errors="replace")
    m = re.search(r'<form[^>]+id="kc-form-login"[^>]*>', html)
    if not m:
        return st, {"error": "no_login_form", "snippet": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))[:400]}, steps
    action = urllib.parse.urljoin(base, re.search(r'action="([^"]+)"', m.group(0)).group(1).replace("&amp;", "&"))
    st, hdr, raw = go("POST", action, {"username": username, "password": password, "credentialId": ""})
    steps["login_post"] = st
    loc = hdr.get("Location") or hdr.get("location")
    if st >= 400 or not loc:
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw.decode(errors="replace")))
        return st, {"error": "login_post_failed", "text": txt[:400]}, steps
    if loc.startswith(redirect_uri):
        code = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query).get("code", [None])[0]
        steps["consent"] = "not_shown"
    else:
        st, hdr, raw = go("GET", urllib.parse.urljoin(base, loc))
        steps["consent_get"] = st
        html = raw.decode(errors="replace")
        m = re.search(r'<form[^>]+action="([^"]+)"[^>]*>(.*?)</form>', html, re.S)
        if not m or 'name="code"' not in m.group(2):
            return st, {"error": "no_consent_form", "snippet": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))[:600]}, steps
        action = urllib.parse.urljoin(base, m.group(1).replace("&amp;", "&"))
        code_m = re.search(r'name="code"\s+value="([^"]+)"', m.group(2)) or \
            re.search(r'value="([^"]+)"\s+name="code"', m.group(2))
        steps["consent_items_shown"] = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", li)).strip()
                                        for li in re.findall(r"<li[^>]*>(.*?)</li>", m.group(2), re.S)]
        st, hdr, raw = go("POST", action, {"code": code_m.group(1), "accept": "Yes"})
        steps["consent_post"] = st
        loc = hdr.get("Location") or hdr.get("location")
        if not (loc and loc.startswith(redirect_uri)):
            return st, {"error": "consent_no_redirect", "location": loc}, steps
        code = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query).get("code", [None])[0]
        steps["consent"] = "accepted"
    st, js, ns = post_token(realm, {"grant_type": "authorization_code", "client_id": client_id,
                                    "client_secret": client_secret, "code": code, "redirect_uri": redirect_uri}, base)
    steps["code_to_token"] = st
    steps["code_to_token_ns"] = ns
    return st, js, steps

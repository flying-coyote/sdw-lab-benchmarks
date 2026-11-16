"""Post-hoc probe (2026-11-16, not pre-registered): are T8c's text-matching rules case-fragile across engines?

Background: R1 (../atlas-ocsf-observables/RESULTS.md l.125-132) found that pySigma-backend-sqlite compiles Sigma
`contains` to LIKE '%...%', which SQLite evaluates case-insensitively (ASCII) and DuckDB case-sensitively; the
ocsf-attack-coverage mixed-case check (../ocsf-attack-coverage/RESULTS-MIXED-CASE-2026-11-16.md) reproduced it on
that bench's one `contains` rule. T8c reported identical matched sets on both engines (RESULTS.md, H5), but its
corpus plants values in the rules' own case, so the exposure could not show. This probe reuses that check's method:
compile each tier (a) Sigma rule exactly as run.py does (compile_yaml -> to_api -> SELECT metadata_uid), and run the
hand-SQL leg classifier and content qualifier from run.py's own CTE strings, on SQLite and DuckDB over tiny tables
holding the matching value in its original case, lower, upper and one alternating mixed case, plus a non-match,
with every other column held at a matching value. Nothing in T8c's committed corpus, rules, run.py or results is
touched; run.py is imported read-only for its compile helpers and SQL strings.

  <venv from requirements.txt: pySigma 2.0.3, pySigma-backend-sqlite 2.1.1, duckdb 1.5.3>/bin/python -I mixed_case_probe_2026_11_16.py
Writes results/mixed-case-probe-2026-11-16.json.
"""
import json, os, sqlite3, sys
from importlib.metadata import version

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402  (read-only use of compile_yaml, to_api, LEGS_CTE, QUAL_CTE)

COLS = ["metadata_uid", "actor_session_uid", "delegation_parent_uid", "time_epoch", "api_operation",
        "api_request_data", "dst_endpoint_hostname"]
INT = {"time_epoch"}


def variants(v, token=None):
    """Case variants of v. With token, also upper-case only the token the predicate matches on and keep the rest of
    the value as it was (for the credential, the constant `api03-` prefix, leaving the case-significant key body)."""
    mixed = "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(v))
    out = [("original", v), ("lower", v.lower()), ("upper", v.upper()), ("mixed", mixed)]
    if token and token != v:
        out.append(("token-upper", v.replace(token, token.upper())))
    return out


def engines(rows):
    ddl = "CREATE TABLE api (" + ", ".join(f"{c} {'BIGINT' if c in INT else 'VARCHAR'}" for c in COLS) + ")"
    out = {}
    for eng in ("sqlite", "duckdb"):
        con = sqlite3.connect(":memory:") if eng == "sqlite" else duckdb.connect(":memory:")
        con.execute(ddl)
        for r in rows:
            con.execute(f"INSERT INTO api VALUES ({', '.join('?' * len(COLS))})", [r.get(c) for c in COLS])
        out[eng] = con
    return out


def base(uid, **kw):
    r = {"metadata_uid": uid, "actor_session_uid": "s-" + uid, "delegation_parent_uid": None, "time_epoch": 1000,
         "api_operation": "noop", "api_request_data": "{}", "dst_endpoint_hostname": "intranet.example"}
    r.update(kw)
    return r


# rule -> (column under test, rule's own value, how to wrap it into the column, fixed columns[, token])
# The a5 "non-match" row holds the hostname "benign-value", which is off the allowlist, so a5 fires on it by design.
TIER_A = {
    "a1_ingest_mail.yml": ("api_operation", "mail.fetch", "{}", {}),
    "a2_ingest_repo.yml": ("api_operation", "issue.read", "{}", {}),
    "a3_collect_mailbox.yml": ("api_operation", "mail.search", "{}", {}),
    "a4_read_procenv.yml": ("api_request_data", "/proc/self/environ", '{{"path": "{}"}}', {"api_operation": "file.read"}),
    "a5_outbound_offlist.yml#allowlisted": ("dst_endpoint_hostname", "github.com", "{}", {"api_operation": "http.open"}),
    "a5_outbound_offlist.yml#offlist": ("dst_endpoint_hostname", "exfil-sink.invalid", "{}", {"api_operation": "http.open"}),
    "a6_credential_shape.yml": ("api_request_data", run.gen_corpus.FIXTURE_DEPREFIXED,
                                '{{"url": "https://exfil-sink.invalid/r?v={}"}}', {"api_operation": "web.fetch"}, "api03-"),
}


def tier_a():
    res = {}
    for key, spec in TIER_A.items():
        col, val, wrap, fixed = spec[:4]
        token = spec[4] if len(spec) > 4 else None
        f = key.split("#")[0]
        sql = run.to_api(run.compile_yaml(f)[-1]).replace("SELECT *", "SELECT metadata_uid", 1)
        vs = variants(val, token) + [("non-match", "benign-value")]
        rows = []
        for i, (lab, v) in enumerate(vs):
            r = base(f"u{i}", **fixed)
            r[col] = wrap.format(v) if col == "api_request_data" else v
            rows.append(r)
        cons = engines(rows)
        matched = {}
        for eng, con in cons.items():
            try:
                hit = {x[0] for x in con.execute(sql).fetchall()}
                matched[eng] = {lab: f"u{i}" in hit for i, (lab, _) in enumerate(vs)}
            except Exception as e:  # recorded, not hidden
                matched[eng] = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
        res[key] = {"column": col, "compiled_sql": sql, "planted": dict(vs), "matched": matched,
                    "engines_agree": matched["sqlite"] == matched["duckdb"]}
    return res


def hand_sql():
    """The leg classifier and leg-3 content qualifier that b3/b4/c1/c2 share, from run.py's own CTE strings."""
    res = {}
    legs_sql = "WITH " + run.LEGS_CTE + "\nSELECT s, leg FROM legs"
    qual_sql = "WITH " + ",".join([run.LEGS_CTE, run.QUAL_CTE]) + "\nSELECT s, leg FROM qlegs"
    probes = {
        "leg2_procenv_path": ("api_request_data", '{{"path": "{}"}}', "/proc/self/environ", {"api_operation": "file.read"}, legs_sql, 2),
        "leg2_dotenv_path": ("api_request_data", '{{"path": "/app/{}"}}', ".env", {"api_operation": "file.read"}, legs_sql, 2),
        "leg2_credentials_json_path": ("api_request_data", '{{"path": "/srv/app/{}"}}', "credentials.json",
                                       {"api_operation": "file.read"}, legs_sql, 2),
        "leg3_allowlisted_host": ("dst_endpoint_hostname", "{}", "github.com", {"api_operation": "http.open"}, legs_sql, 3),
        "leg3_qualifier_credential": ("api_request_data", '{{"url": "https://exfil-sink.invalid/r?v={}"}}',
                                      run.gen_corpus.FIXTURE_DEPREFIXED,
                                      {"api_operation": "web.fetch", "dst_endpoint_hostname": "exfil-sink.invalid"},
                                      qual_sql, 3, "api03-"),
    }
    for name, spec in probes.items():
        col, wrap, val, fixed, sql, want = spec[:6]
        token = spec[6] if len(spec) > 6 else None
        vs = variants(val, token)
        rows = []
        for i, (lab, v) in enumerate(vs):
            r = base(f"u{i}", **fixed)
            r[col] = wrap.format(v)
            rows.append(r)
        cons = engines(rows)
        out = {}
        for eng, con in cons.items():
            got = dict(con.execute(sql).fetchall())
            out[eng] = {lab: (got.get(f"s-u{i}") == want) for i, (lab, _) in enumerate(vs)}
        res[name] = {"column": col, "classified_as_leg": want, "planted": dict(vs), "result": out,
                     "engines_agree": out["sqlite"] == out["duckdb"]}
    return res


def session_rules():
    """Rule level: one planted three-leg session per case variant (mail.fetch, then a file.read of the sensitive path,
    then a web.fetch to an off-allowlist host carrying the credential string), run through run.SESSION_SQL (b3, b4,
    c1, c2) on both engines. Two sweeps: vary the path with the credential as planted, and vary the credential with
    the path as planted. Each session is a root (no delegation parent), so the walk rules see it as its own root."""
    cred = run.gen_corpus.FIXTURE_DEPREFIXED
    sweeps = {"vary_leg2_path": (variants("/proc/self/environ"), None),
              "vary_leg3_credential": (None, variants(cred, "api03-"))}
    res = {}
    for sweep, (paths, creds) in sweeps.items():
        vs = paths or creds
        rows = []
        for i, (lab, v) in enumerate(vs):
            sess = f"sess-{i}"
            path = v if paths else "/proc/self/environ"
            c = v if creds else cred
            rows += [base(f"u{i}a", actor_session_uid=sess, time_epoch=1000, api_operation="mail.fetch"),
                     base(f"u{i}b", actor_session_uid=sess, time_epoch=1060, api_operation="file.read",
                          api_request_data=f'{{"path": "{path}"}}'),
                     base(f"u{i}c", actor_session_uid=sess, time_epoch=1120, api_operation="web.fetch",
                          dst_endpoint_hostname="exfil-sink.invalid",
                          api_request_data=f'{{"url": "https://exfil-sink.invalid/r?v={c}"}}')]
        cons = engines(rows)
        out = {}
        for rule, sql in run.SESSION_SQL.items():
            out[rule] = {}
            for eng, con in cons.items():
                hit = {x[0] for x in con.execute(sql).fetchall()}
                out[rule][eng] = {lab: f"sess-{i}" in hit for i, (lab, _) in enumerate(vs)}
            out[rule]["engines_agree"] = out[rule]["sqlite"] == out[rule]["duckdb"]
        res[sweep] = {"planted": dict(vs), "fired": out}
    return res


def session_rules_lowered():
    """Candidate fix, not part of T8c: the same session rules with every hand-SQL LIKE wrapped in lower() (SQLite has
    no ILIKE, and lower() runs on both engines), rebuilt through run.session_sql from patched copies of LEGS_CTE and
    QUAL_CTE, over the same planted sessions as session_rules(). run's module constants are restored afterwards."""
    legs0, qual0 = run.LEGS_CTE, run.QUAL_CTE
    try:
        run.LEGS_CTE = legs0.replace("api_request_data LIKE", "lower(api_request_data) LIKE")
        run.QUAL_CTE = qual0.replace("l.d LIKE", "lower(l.d) LIKE")
        assert run.LEGS_CTE.count("lower(") == 3 and run.QUAL_CTE.count("lower(") == 1
        sqls = {r: run.session_sql(q, w) for r, (q, w) in
                {"b4_session_sql_qualified": (True, False), "c2_walk_sql_qualified": (True, True)}.items()}
    finally:
        run.LEGS_CTE, run.QUAL_CTE = legs0, qual0
    cred = run.gen_corpus.FIXTURE_DEPREFIXED
    res = {}
    for sweep, (paths, creds) in {"vary_leg2_path": (variants("/proc/self/environ"), None),
                                  "vary_leg3_credential": (None, variants(cred, "api03-"))}.items():
        vs = paths or creds
        rows = []
        for i, (lab, v) in enumerate(vs):
            sess = f"sess-{i}"
            path = v if paths else "/proc/self/environ"
            c = v if creds else cred
            rows += [base(f"u{i}a", actor_session_uid=sess, time_epoch=1000, api_operation="mail.fetch"),
                     base(f"u{i}b", actor_session_uid=sess, time_epoch=1060, api_operation="file.read",
                          api_request_data=f'{{"path": "{path}"}}'),
                     base(f"u{i}c", actor_session_uid=sess, time_epoch=1120, api_operation="web.fetch",
                          dst_endpoint_hostname="exfil-sink.invalid",
                          api_request_data=f'{{"url": "https://exfil-sink.invalid/r?v={c}"}}')]
        cons = engines(rows)
        out = {}
        for rule, sql in sqls.items():
            out[rule] = {eng: {lab: f"sess-{i}" in {x[0] for x in con.execute(sql).fetchall()}
                               for i, (lab, _) in enumerate(vs)} for eng, con in cons.items()}
            out[rule]["engines_agree"] = out[rule]["sqlite"] == out[rule]["duckdb"]
        res[sweep] = {"planted": dict(vs), "fired": out}
    return res


def main():
    out = {"versions": {"pySigma": version("pySigma"), "pySigma-backend-sqlite": version("pySigma-backend-sqlite"),
                        "duckdb": duckdb.__version__, "sqlite": sqlite3.sqlite_version, "python": sys.version.split()[0]},
           "tier_a_sigma": tier_a(), "hand_sql": hand_sql(), "session_rules": session_rules(),
           "session_rules_lowered_candidate_fix": session_rules_lowered()}
    p = os.path.join(HERE, "results", "mixed-case-probe-2026-11-16.json")
    with open(p, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out["versions"]))
    for k, v in out["tier_a_sigma"].items():
        print(k, v["matched"])
    for k, v in out["hand_sql"].items():
        print(k, v["result"])
    for k, v in out["session_rules_lowered_candidate_fix"].items():
        for r, f in v["fired"].items():
            print("lowered", k, r, f)
    for k, v in out["session_rules"].items():
        for r, f in v["fired"].items():
            print(k, r, f)


if __name__ == "__main__":
    main()

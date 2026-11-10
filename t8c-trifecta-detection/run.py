"""T8c trifecta detection: single-step vs session vs session+delegation rules over a planted OCSF ai_operation store.

For each seed: build the corpus (gen_corpus.py), compile the Sigma rules with pySigma's sqlite backend, run them in
stdlib SQLite and DuckDB 1.5.3, run the hand SQL twins on both, and score DETECTED / NOISY / MISSED at T = 0.9.
Timings (perf_counter, median of 3) go to results/timings.json so results/coverage.json stays deterministic.

  taskset -c 0-3 nice -n 10 .venv/bin/python -I run.py [--scale N] [--seeds a,b,c] [--out results/coverage.json]
"""
import argparse, json, os, re, sqlite3, statistics, sys, time
import duckdb
from sigma.backends.sqlite import sqliteBackend
from sigma.collection import SigmaCollection

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_corpus  # noqa: E402

T_FLOOR = 0.9
SEEDS = [20261109, 20261110, 20261111]
WINDOW_S = 3600
BURST_N, BURST_S = 20, 300
ALLOW_SQL = ", ".join(f"'{h}'" for h in gen_corpus.ALLOWLIST)

TIER_A = {  # rule -> (file, leg)
    "a1_ingest_mail": ("a1_ingest_mail.yml", 1), "a2_ingest_repo": ("a2_ingest_repo.yml", 1),
    "a3_collect_mailbox": ("a3_collect_mailbox.yml", 2), "a4_read_procenv": ("a4_read_procenv.yml", 2),
    "a5_outbound_offlist": ("a5_outbound_offlist.yml", 3), "a6_credential_shape": ("a6_credential_shape.yml", 3),
}

LEGS_CTE = f"""
legs AS (
  SELECT actor_session_uid AS s, time_epoch AS t, dst_endpoint_hostname AS h, api_request_data AS d,
    CASE WHEN api_operation IN ('mail.fetch','issue.read','pr.read') THEN 1
         WHEN api_operation IN ('mail.search','contacts.list')
           OR (api_operation = 'file.read' AND (api_request_data LIKE '%/proc/self/environ%'
               OR api_request_data LIKE '%.env%' OR api_request_data LIKE '%credentials.json%')) THEN 2
         WHEN api_operation IN ('http.open','web.fetch') AND dst_endpoint_hostname NOT IN ({ALLOW_SQL}) THEN 3
    END AS leg
  FROM api)"""
# leg 3 qualified by content: the de-prefixed credential marker, or a burst of >= BURST_N calls to one host in BURST_S
QUAL_CTE = f"""
bursts AS (
  SELECT s, h FROM legs WHERE leg = 3 GROUP BY s, h HAVING COUNT(*) >= {BURST_N} AND MAX(t) - MIN(t) <= {BURST_S}),
qlegs AS (
  SELECT l.s, l.t, CASE WHEN l.leg = 3 AND NOT (l.d LIKE '%api03-%' OR EXISTS (SELECT 1 FROM bursts b WHERE b.s = l.s AND b.h = l.h))
                        THEN NULL ELSE l.leg END AS leg
  FROM legs l)"""
ROOTS_CTE = """
parents AS (SELECT DISTINCT actor_session_uid AS s, delegation_parent_uid AS p FROM api),
walk AS (
  SELECT s, s AS root, 0 AS depth FROM parents WHERE p IS NULL
  UNION ALL
  SELECT c.s, w.root, w.depth + 1 FROM parents c JOIN walk w ON c.p = w.s WHERE w.depth < 8)"""


def session_sql(qualified, walk):
    src = "qlegs" if qualified else "legs"
    ctes = [LEGS_CTE] + ([QUAL_CTE] if qualified else []) + ([ROOTS_CTE] if walk else [])
    if walk:
        body = f"SELECT w.root AS unit FROM {src} l JOIN walk w ON w.s = l.s WHERE l.leg IS NOT NULL GROUP BY w.root"
    else:
        body = f"SELECT s AS unit FROM {src} WHERE leg IS NOT NULL GROUP BY s"
    return "WITH RECURSIVE " + ",".join(ctes) + "\n" + body + f" HAVING COUNT(DISTINCT leg) = 3 AND MAX(t) - MIN(t) <= {WINDOW_S}"


SESSION_SQL = {
    "b3_session_sql": session_sql(False, False), "b4_session_sql_qualified": session_sql(True, False),
    "c1_walk_sql": session_sql(False, True), "c2_walk_sql_qualified": session_sql(True, True),
}


def compile_yaml(path):
    return sqliteBackend().convert(SigmaCollection.from_yaml(open(os.path.join(HERE, "rules", path)).read()))


def to_api(sql):
    return sql.replace(" FROM logs", " FROM api").replace("julianday(timestamp)", "julianday(time)")


def duck_from_sqlite(path):
    con = duckdb.connect(":memory:")
    con.execute("SET threads = 4")
    s = sqlite3.connect(path)
    cols = gen_corpus.COLUMNS
    rows = s.execute(f"SELECT {', '.join(cols)} FROM api").fetchall()
    con.execute("CREATE TABLE api (" + ", ".join(f"{c} {'BIGINT' if c in gen_corpus.INT_COLS else 'VARCHAR'}" for c in cols) + ")")
    con.executemany(f"INSERT INTO api VALUES ({', '.join('?' * len(cols))})", rows)
    s.close()
    return con


def score(matched, truth):
    tp = len(matched & truth)
    prec = round(tp / len(matched), 4) if matched else 0.0
    state = "MISSED" if tp == 0 else ("NOISY" if prec < T_FLOOR else "DETECTED")
    return {"state": state, "matches": len(matched), "tp": tp, "fp": len(matched) - tp, "precision": prec,
            "recall": round(tp / len(truth), 4) if truth else None}


def timed(fn, n=3):
    ts = []
    out = None
    for _ in range(n):
        t0 = time.perf_counter()
        out = fn()
        ts.append(time.perf_counter() - t0)
    return out, {"median_s": round(statistics.median(ts), 4), "min_s": round(min(ts), 4), "max_s": round(max(ts), 4)}


def loadavg():
    return float(open("/proc/loadavg").read().split()[0])


def fp_breakdown(fps, truth):
    out = {}
    for s in fps:
        c = truth["session_class"].get(s, "unknown")
        c = re.sub(r"PLANT-(CS006[67])-(\w+)-\d+-sub", r"PLANT-\1-\2-sub", c)
        out[c] = out.get(c, 0) + 1
    return dict(sorted(out.items()))


def event_fp_breakdown(fps, uid2sess, truth):
    return fp_breakdown([uid2sess[u] for u in fps], truth)


def run_seed(seed, n_sessions, timings, sql_only=False):
    out = os.path.join(HERE, "corpus", f"{seed}-{n_sessions}")
    rows, truth = gen_corpus.gen(seed, n_sessions)
    db = gen_corpus.write(rows, truth, out)
    uid2sess = {r["metadata_uid"]: r["actor_session_uid"] for r in rows}
    # supplementary (not pre-registered) truth views: leg events per chain shape, and the plant's Action-log channel
    leg_by_shape = {}
    channel_uids = set()
    for r in rows:
        if r["truth_leg"]:
            leg_by_shape.setdefault((str(r["truth_leg"]), r["truth_chain"][:6]), set()).add(r["metadata_uid"])
        if r["is_planted"] and r["api_operation"] == "bash.exec":
            channel_uids.add(r["metadata_uid"])
    sq = sqlite3.connect(db)
    dk = duck_from_sqlite(db)
    rid2uid = dict(sq.execute("SELECT CAST(rowid AS TEXT), metadata_uid FROM api").fetchall())
    leg_truth = {k: set(v) for k, v in truth["legs"].items()}
    chain_roots = {c["root"] for c in truth["chains"].values()}
    strata = {}
    for cid, c in truth["chains"].items():
        strata.setdefault(f"{c['chain']}-{'delegated' if c['delegated'] else 'direct'}", set()).add(c["root"])
    res = {"n_events": len(rows), "n_sessions": len(truth["session_class"]), "rules": {}}
    tm = timings.setdefault(str(seed), {})

    # background leg prevalence among benign (non-plant) sessions
    prev = {}
    for (s, k, n) in dk.execute("WITH RECURSIVE" + LEGS_CTE + " SELECT s, GROUP_CONCAT(DISTINCT CAST(leg AS VARCHAR)) AS k, COUNT(*) FROM legs WHERE leg IS NOT NULL GROUP BY s").fetchall():
        if truth["session_class"].get(s, "").startswith("PLANT"):
            continue
        key = "+".join(sorted(k.split(",")))
        prev[key] = prev.get(key, 0) + 1
    n_benign = sum(1 for c in truth["session_class"].values() if not c.startswith("PLANT"))
    res["benign_leg_prevalence"] = {"n_benign_sessions": n_benign, "sessions_by_leg_set": dict(sorted(prev.items()))}
    res["lookalike_counts"] = dict(sorted((c, list(truth["session_class"].values()).count(c)) for c in set(truth["session_class"].values()) if not c.startswith("PLANT")))

    # tier (a): single-step Sigma rules, both engines, event-level
    for name, (f, leg) in TIER_A.items():
        sql = to_api(compile_yaml(f)[-1]).replace("SELECT *", "SELECT metadata_uid", 1)
        row = {"tier": "a", "unit": "event", "leg": leg, "sql": sql}
        sets = {}
        for eng, con in (("sqlite", sq), ("duckdb", dk)):
            la = loadavg()
            try:
                m, t = timed(lambda: {r[0] for r in con.execute(sql).fetchall()})
                sets[eng] = m
                row[eng] = score(m, leg_truth[str(leg)])
                row[eng]["fp_by_session_class"] = event_fp_breakdown(m - leg_truth[str(leg)], uid2sess, truth)
            except Exception as e:
                row[eng] = {"state": "MISSED", "matches": 0, "tp": 0, "fp": 0, "precision": 0.0, "recall": 0.0,
                            "miss_reason": "exec_error: " + re.sub(r"\s+", " ", str(e))[:160]}
                t = None
            tm.setdefault(name, {})[eng] = {"timing": t, "loadavg_1m_before": la}
        row["engines_agree"] = (sets.get("sqlite") == sets.get("duckdb")) if len(sets) == 2 else None
        # supplementary views (not pre-registered; labelled): per-shape recall, session-level scoring with sessions
        # mapped to their chain root by ground truth (an oracle walk, so an upper bound for a session view), and for a6
        # a re-score that counts the plant's bash.exec Action-log channel as leg-3 truth.
        m = sets.get("duckdb", sets.get("sqlite", set()))
        supp = {"recall_by_shape": {sh: round(len(m & leg_by_shape[(str(leg), sh)]) / len(leg_by_shape[(str(leg), sh)]), 4)
                                    for (lg, sh) in sorted(leg_by_shape) if lg == str(leg)}}
        sess_hits = {truth["session_root"].get(uid2sess[u], uid2sess[u]) for u in m}
        sc = score(sess_hits, chain_roots)
        sc["fp_by_session_class"] = fp_breakdown(sess_hits - chain_roots, truth)
        supp["session_level_oracle_root"] = sc
        if name == "a6_credential_shape":
            supp["rescored_with_channel_events_as_truth"] = score(m, leg_truth["3"] | channel_uids)
        row["supplementary"] = supp
        res["rules"][name] = row

    if sql_only:
        return _finish(res, sq, dk, truth, chain_roots, strata, timings, tm)
    # a7: Sigma event_count burst, SQLite-dialect; attempt on DuckDB too (expected to fail)
    sql = to_api(compile_yaml("a7_url_burst.yml")[-1])
    row = {"tier": "a", "unit": "event", "leg": 3, "sql": sql}
    for eng, con in (("sqlite", sq), ("duckdb", dk)):
        la = loadavg()
        try:
            alerts, t = timed(lambda: con.execute(sql).fetchall())
            m = set()
            for a in alerts:
                for eid in json.loads(a[-2]):
                    m.add(rid2uid[eid.split(":")[-1]])
            row[eng] = score(m, leg_truth["3"])
            row[eng]["alerts"] = len(alerts)
            row[eng]["fp_by_session_class"] = event_fp_breakdown(m - leg_truth["3"], uid2sess, truth)
            row[eng]["note"] = "scored against all leg-3 events; CS0067 leg-3 events are single calls, so recall < 1 by design"
        except Exception as e:
            row[eng] = {"state": "MISSED", "matches": 0, "tp": 0, "fp": 0, "precision": 0.0, "recall": 0.0,
                        "miss_reason": "exec_error: " + re.sub(r"\s+", " ", str(e))[:160]}
            t = None
        tm.setdefault("a7_url_burst", {})[eng] = {"timing": t, "loadavg_1m_before": la}
    res["rules"]["a7_url_burst"] = row

    # b1/b2: pySigma temporal correlations, SQLite-dialect; attempt on DuckDB too
    outs = compile_yaml("b_session_temporal.yml")
    corr = {("b1_session_temporal" if "'temporal' AS metric_name" in q else "b2_session_temporal_ordered"): to_api(q)
            for q in outs if " AS metric_name" in q}
    assert len(corr) == 2, "expected two correlation queries"

    for name, sql in corr.items():
        row = {"tier": "b", "unit": "session", "sql": sql}
        for eng, con in (("sqlite", sq), ("duckdb", dk)):
            la = loadavg()
            try:
                alerts, t = timed(lambda: con.execute(sql).fetchall())
                m = {json.loads(a[1])["actor_session_uid"] for a in alerts}
                _score_sessions(m, row, eng, chain_roots, strata, truth)
                row[eng]["alerts"] = len(alerts)
            except Exception as e:
                row[eng] = {"state": "MISSED", "matches": 0, "tp": 0, "fp": 0, "precision": 0.0, "recall": 0.0,
                            "miss_reason": "exec_error: " + re.sub(r"\s+", " ", str(e))[:160]}
                t = None
            tm.setdefault(name, {})[eng] = {"timing": t, "loadavg_1m_before": la}
        res["rules"][name] = row
    return _finish(res, sq, dk, truth, chain_roots, strata, timings, tm)


def _score_sessions(matched, row, eng, chain_roots, strata, truth):
    row[eng] = score(matched, chain_roots)
    row[eng]["fp_by_session_class"] = fp_breakdown(matched - chain_roots, truth)
    row[eng]["recall_by_stratum"] = {k: round(len(matched & v) / len(v), 2) for k, v in sorted(strata.items())}


def _finish(res, sq, dk, truth, chain_roots, strata, timings, tm):
    # b3/b4/c1/c2: hand SQL, both engines
    for name, sql in SESSION_SQL.items():
        row = {"tier": name[0], "unit": "root session" if name[0] == "c" else "session", "sql": sql}
        sets = {}
        for eng, con in (("sqlite", sq), ("duckdb", dk)):
            la = loadavg()
            try:
                m, t = timed(lambda: {r[0] for r in con.execute(sql).fetchall()})
                sets[eng] = m
                _score_sessions(m, row, eng, chain_roots, strata, truth)
            except Exception as e:
                row[eng] = {"state": "MISSED", "matches": 0, "tp": 0, "fp": 0, "precision": 0.0, "recall": 0.0,
                            "miss_reason": "exec_error: " + re.sub(r"\s+", " ", str(e))[:160]}
                t = None
            tm.setdefault(name, {})[eng] = {"timing": t, "loadavg_1m_before": la}
        row["engines_agree"] = (sets.get("sqlite") == sets.get("duckdb")) if len(sets) == 2 else None
        res["rules"][name] = row

    sq.close()
    dk.close()
    return res


def summarize(per_seed, seeds):
    names = list(per_seed[str(seeds[0])]["rules"])
    summary = {}
    for n in names:
        row = {}
        for eng in ("sqlite", "duckdb"):
            cells = [per_seed[str(s)]["rules"][n][eng] for s in seeds]
            precs = [c["precision"] for c in cells if "precision" in c]
            recs = [c["recall"] for c in cells if c.get("recall") is not None]
            row[eng] = {"states": [c["state"] for c in cells],
                        "precision_min_median_max": [min(precs), statistics.median(precs), max(precs)] if precs else None,
                        "recall_min_median_max": [min(recs), statistics.median(recs), max(recs)] if recs else None,
                        "fp_per_seed": [c.get("fp") for c in cells]}
            mr = sorted({c.get("miss_reason") for c in cells} - {None})
            if mr:
                row[eng]["miss_reason"] = mr
            if any("recall_by_stratum" in c for c in cells):
                row[eng]["recall_by_stratum_per_seed"] = [c.get("recall_by_stratum") for c in cells]
        ea = [per_seed[str(s)]["rules"][n].get("engines_agree") for s in seeds]
        if any(e is not None for e in ea):
            row["engines_agree_per_seed"] = ea
        summary[n] = row
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=int, default=gen_corpus.N_SESSIONS_DEFAULT)
    ap.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    ap.add_argument("--out", default="results/coverage.json")
    ap.add_argument("--sql-only", action="store_true", help="skip the pySigma correlation queries (a7, b1, b2)")
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",")]
    timings = {}
    per_seed = {}
    for s in seeds:
        t0 = time.perf_counter()
        per_seed[str(s)] = run_seed(s, a.scale, timings, a.sql_only)
        timings[str(s)]["_seed_wall_s"] = round(time.perf_counter() - t0, 2)
        print(f"seed {s} done in {timings[str(s)]['_seed_wall_s']} s, loadavg {loadavg()}", file=sys.stderr)
    obj = {"benchmark": "t8c-trifecta-detection", "precision_floor_T": T_FLOOR, "seeds": seeds, "n_sessions": a.scale,
           "window_s": WINDOW_S, "burst": {"n": BURST_N, "span_s": BURST_S},
           "versions": {"duckdb": duckdb.__version__, "sqlite": sqlite3.sqlite_version, "python": sys.version.split()[0]},
           "summary": summarize(per_seed, seeds),
           "per_seed": {s: {**{k: v for k, v in r.items() if k != "rules"},
                            "rules": {n: {k: v for k, v in rr.items() if k != "sql"} for n, rr in r["rules"].items()}}
                        for s, r in per_seed.items()},
           "sql": {n: rr["sql"] for n, rr in per_seed[str(seeds[0])]["rules"].items()}}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    json.dump(obj, open(os.path.join(HERE, a.out), "w"), indent=1, sort_keys=True)
    json.dump({"note": "perf_counter medians of 3, under host contention, taskset 0-3 nice 10, duckdb threads=4",
               "versions": obj["versions"], "timings": timings},
              open(os.path.join(HERE, a.out.replace("coverage", "timings")), "w"), indent=1, sort_keys=True)
    for n, s in obj["summary"].items():
        print(f"{n:28} sqlite={s['sqlite']['states']} p={s['sqlite']['precision_min_median_max']} r={s['sqlite']['recall_min_median_max']}"
              f" | duckdb={s['duckdb']['states']} p={s['duckdb']['precision_min_median_max']}")


if __name__ == "__main__":
    main()

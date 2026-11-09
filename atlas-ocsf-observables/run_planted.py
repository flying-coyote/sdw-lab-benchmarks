"""R1 planted bench: does a Sigma rule over the mapped OCSF field fire on a planted event?

For each seed: build the corpus (gen_corpus.py), compile each rule with pySigma's sqlite backend, run the
SQL in SQLite (the backend's target) and in DuckDB 1.5.3 (the ocsf-attack-coverage engine), and score
DETECTED / NOISY / MISSED at precision floor T = 0.9, per arm (core, profile).

  .venv/bin/python -I run_planted.py            # three seeds, writes results/coverage.json
"""
import glob, json, os, re, sqlite3, statistics, sys
import duckdb
from sigma.backends.sqlite import sqliteBackend
from sigma.collection import SigmaCollection

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_corpus  # noqa: E402

T_FLOOR = 0.9
SEEDS = [20261109, 20261110, 20261111]
RULES = {  # technique -> (rule file, table)
    "AML.T0012": ("T0012_default_account_external.yml", "authentication"),
    "AML.T0055": ("T0055_imds_credentials.yml", "process"),
    "AML.T0049": ("T0049_sqli_union.yml", "datastore"),
    "AML.T0050": ("T0050_python_exec_b64.yml", "process"),
    "AML.T0089": ("T0089_process_discovery.yml", "process"),
    "AML.T0024": ("T0024_llm_api_call.yml", "api"),
    "AML.T0025": ("T0025_large_outbound.yml", "network"),
    "AML.T0051.000": ("T0051_000_prompt_injection.yml", "api"),
}
SUPP = {"AML.T0024": ("supplementary/T0024_llm_api_burst_correlation.yml", "api")}


def compile_rule(path):
    return sqliteBackend().convert(SigmaCollection.from_yaml(open(os.path.join(HERE, "rules", path)).read()))[-1]


def single_sql(sql, table):
    return sql.replace("SELECT *", "SELECT event_uid", 1).replace(" FROM logs", f" FROM {table}")


def duck_from_sqlite(path):
    con = duckdb.connect(":memory:")
    s = sqlite3.connect(path)
    for (name,) in s.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        cols = [r[1] for r in s.execute(f"PRAGMA table_info({name})")]
        rows = s.execute(f"SELECT {', '.join(cols)} FROM {name}").fetchall()
        types = ["BIGINT" if isinstance(rows[0][i], int) else "VARCHAR" for i in range(len(cols))]
        con.execute(f"CREATE TABLE {name} ({', '.join(f'{c} {t}' for c, t in zip(cols, types))})")
        con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})", rows)
    s.close()
    return con


def score(matched, truth):
    tp = len(matched & truth)
    prec = round(tp / len(matched), 4) if matched else 0.0
    if tp == 0:
        state = "MISSED"
    elif prec < T_FLOOR:
        state = "NOISY"
    else:
        state = "DETECTED"
    return {"state": state, "matches": len(matched), "tp": tp, "fp": len(matched) - tp,
            "precision": prec, "recall": round(tp / len(truth), 4)}


def run_seed(seed):
    out = os.path.join(HERE, "corpus", str(seed))
    T, truth = gen_corpus.gen(seed)
    gen_corpus.write(T, truth, out)
    res = {}
    for arm in ("core", "profile"):
        db = os.path.join(out, f"corpus_{arm}.sqlite")
        sq = sqlite3.connect(db)
        dk = duck_from_sqlite(db)
        for tid, (rule, table) in sorted(RULES.items()):
            sql = single_sql(compile_rule(rule), table)
            tr = set(truth[tid])
            row = {"rule": rule, "table": table, "sql": sql}
            for eng, con in (("sqlite", sq), ("duckdb", dk)):
                try:
                    m = {r[0] for r in con.execute(sql).fetchall()}
                    row[eng] = score(m, tr)
                except Exception as e:
                    row[eng] = {"state": "MISSED", "matches": 0, "tp": 0, "fp": 0, "precision": 0.0, "recall": 0.0,
                                "miss_reason": "exec_error: " + re.sub(r"\s+", " ", str(e))[:120]}
            res[f"{arm}|{tid}"] = row
        for tid, (rule, table) in SUPP.items():
            sql = compile_rule(rule).replace(" FROM logs", f" FROM {table}")
            rid2uid = dict(sq.execute(f"SELECT CAST(rowid AS TEXT), event_uid FROM {table}").fetchall())
            # correlation SQL reads a `timestamp` column
            sql = sql.replace("julianday(timestamp)", "julianday(time)")
            try:
                alerts = sq.execute(sql).fetchall()
                m = set()
                for a in alerts:
                    for eid in json.loads(a[-2]):
                        m.add(rid2uid[eid.split(":")[-1]])
                r = score(m, set(truth[tid]))
                r["alerts"] = len(alerts)
            except Exception as e:
                r = {"state": "MISSED", "miss_reason": "exec_error: " + str(e)[:120]}
            res[f"{arm}|{tid}|correlation"] = {"rule": rule, "table": table, "sqlite": r, "duckdb": {"state": "n/a (sqlite-specific SQL)"}}
        sq.close()
        dk.close()
    return res


def main():
    per_seed = {s: run_seed(s) for s in SEEDS}
    keys = sorted(per_seed[SEEDS[0]])
    summary = {}
    for k in keys:
        row = {}
        for eng in ("sqlite", "duckdb"):
            states = [per_seed[s][k][eng].get("state") for s in SEEDS]
            precs = [per_seed[s][k][eng].get("precision") for s in SEEDS if isinstance(per_seed[s][k][eng].get("precision"), float)]
            row[eng] = {"states": states,
                        "precision_min_median_max": [min(precs), statistics.median(precs), max(precs)] if precs else None,
                        "fp_per_seed": [per_seed[s][k][eng].get("fp") for s in SEEDS]}
            mr = {per_seed[s][k][eng].get("miss_reason") for s in SEEDS} - {None}
            if mr:
                row[eng]["miss_reason"] = sorted(mr)
        summary[k] = row
    obj = {"benchmark": "atlas-ocsf-observables / planted", "precision_floor_T": T_FLOOR, "seeds": SEEDS,
           "versions": {"duckdb": duckdb.__version__}, "summary": summary,
           "per_seed": {str(s): {k: {e: v for e, v in r.items() if e != "sql"} for k, r in per_seed[s].items()} for s in SEEDS},
           "compiled_sql": {k: per_seed[SEEDS[0]][k].get("sql") for k in keys if "sql" in per_seed[SEEDS[0]][k]}}
    json.dump(obj, open(os.path.join(HERE, "results", "coverage.json"), "w"), indent=1, sort_keys=True)
    for k in keys:
        s = summary[k]
        print(f"{k:34} sqlite={s['sqlite']['states']} p={s['sqlite']['precision_min_median_max']}  duckdb={s['duckdb']['states']}")


if __name__ == "__main__":
    main()

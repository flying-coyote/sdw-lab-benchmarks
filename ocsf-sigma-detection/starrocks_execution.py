"""H-SIGMA-01 lakehouse leg (backend 6 — StarRocks, GENERIC SQL path): does the window-drop persist on an
MPP OLAP engine (C++/MPP, MySQL wire protocol) reached through the generic pySigma path?

No dedicated `pySigma-backend-starrocks` on PyPI (checked 2026-06-23 — 404), so StarRocks falls to the
generic SQL backend. StarRocks is MySQL-dialect, so unlike Trino it ACCEPTS the alias-in-HAVING the generic
backend emits — the emitted windowless SQL runs verbatim. A fifth architecturally-distinct engine class
(MPP OLAP). Reuses the EXACT planted corpus + scoring. Tier B, single host, synthetic. StarRocks reached
over the MySQL protocol at :9031 (moar stack; root, no password). Native OLAP table (no S3 dependency).
"""
import json, os
import pymysql
import ppl_execution as P
from sigma.collection import SigmaCollection
from sigma.backends.sqlite import sqliteBackend  # generic SQL path (no dedicated StarRocks backend)

HERE = os.path.dirname(os.path.abspath(__file__))
from sqlite_execution import EVENT_COUNT_RULE, VALUE_COUNT_RULE, TEMPORAL_RULE

SR_HOST = os.environ.get("SR_HOST", "127.0.0.1")
SR_PORT = int(os.environ.get("SR_PORT", "9031"))


def compile_sql(rule_yaml):
    try:
        out = sqliteBackend().convert(SigmaCollection.from_yaml(rule_yaml))
        return out[0], None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:160]}"


def main():
    docs, truth = P.gen_corpus()
    true_set, decoy_set, benign_set = set(truth["true"]), set(truth["decoy"]), set(truth["benign"])
    conn = pymysql.connect(host=SR_HOST, port=SR_PORT, user="root", password="")
    cur = conn.cursor()
    cur.execute("SELECT current_version()"); print(f"  StarRocks {cur.fetchone()[0]} (generic SQL pySigma path)", flush=True)
    cur.execute("CREATE DATABASE IF NOT EXISTS sigma")
    cur.execute("DROP TABLE IF EXISTS sigma.logs")
    cur.execute("CREATE TABLE sigma.logs (`timestamp` BIGINT, actor_user VARCHAR(64), outcome VARCHAR(16)) "
                "ENGINE=OLAP DUPLICATE KEY(`timestamp`) DISTRIBUTED BY HASH(actor_user) BUCKETS 4 "
                "PROPERTIES (\"replication_num\"=\"1\")")
    cur.execute("USE sigma")
    # chunked multi-row INSERT (keep statements well under any size cap)
    B = 1000
    for i in range(0, len(docs), B):
        chunk = docs[i:i + B]
        vals = ",".join(f"({int(ts)},'{u}','{o}')" for ts, u, o in chunk)
        cur.execute(f"INSERT INTO sigma.logs VALUES {vals}")
    conn.commit()
    cur.execute("SELECT count(*) FROM sigma.logs"); n = cur.fetchone()[0]
    print(f"  loaded {n} synthetic auth events into StarRocks ({len(true_set)} true, {len(decoy_set)} decoy, {len(benign_set)} benign)", flush=True)

    def users(sql):
        cur.execute(sql); return {r[0] for r in cur.fetchall()}

    # 1) the pySigma-EMITTED query (generic sqlite backend), executed verbatim (StarRocks = MySQL dialect, alias-in-HAVING OK)
    emitted, err = compile_sql(EVENT_COUNT_RULE)
    print(f"  event_count emitted SQL (generic backend, run on StarRocks): {emitted}", flush=True)
    wl = users(emitted) if emitted else set()

    # 2) the CORRECT WINDOWED control (10-min tumbling bucket) — StarRocks/MySQL integer division `DIV`
    windowed_sql = ("SELECT actor_user FROM (SELECT actor_user, count(*) c FROM sigma.logs WHERE outcome='FAILURE' "
                    "GROUP BY actor_user, (`timestamp` DIV 600) HAVING count(*) >= 10) t GROUP BY actor_user")
    wd = users(windowed_sql)

    def score(flagged):
        tp = len(flagged & true_set); fp_d = len(flagged & decoy_set); fp_b = len(flagged & benign_set)
        return {"flagged": len(flagged), "tp": tp, "fp_total": fp_d + fp_b, "fp_decoy": fp_d, "fp_benign": fp_b,
                "recall": round(tp / max(len(true_set), 1), 3), "precision": round(tp / max(len(flagged), 1), 3)}

    windowless_emit = bool(emitted) and "600" not in (emitted or "") and "timestamp" not in (emitted or "")
    res = {
        "benchmark": "ocsf-sigma-detection / StarRocks execution (H-SIGMA-01 lakehouse leg, backend 6 — GENERIC path)",
        "evidence_tier": "B (single host; synthetic planted corpus; StarRocks + generic pySigma SQLite backend, no dedicated StarRocks backend)",
        "assumption_tested": "does the generic-path window-drop persist on an MPP OLAP engine (StarRocks)?",
        "compile_path": "generic pySigma SQLite backend (no dedicated StarRocks backend), executed verbatim on StarRocks (MySQL dialect accepts alias-in-HAVING)",
        "emit_classification": "WINDOWLESS (timespan dropped)" if windowless_emit else "WINDOWED",
        "emitted_sql": emitted,
        "event_count": {"correct_windowed_sql": windowed_sql,
                        "emitted_run": score(wl), "windowed_control": score(wd)},
        "three_band": ("SILENTLY-DEGRADES (windowless emit + over-fire despite window-function capability)"
                       if windowless_emit and score(wl)["fp_decoy"] > 0 else
                       ("SURVIVES (windowed emit + correct fire)" if not windowless_emit and score(wl)["fp_total"] == 0
                        else "see emitted_run")),
        "events": n,
    }
    e = res["event_count"]
    print(f"  EMITTED  (generic on StarRocks): flagged {e['emitted_run']['flagged']} tp {e['emitted_run']['tp']}/{len(true_set)} "
          f"precision {e['emitted_run']['precision']} FP-decoy {e['emitted_run']['fp_decoy']}", flush=True)
    print(f"  WINDOWED (correct StarRocks):    flagged {e['windowed_control']['flagged']} tp {e['windowed_control']['tp']}/{len(true_set)} "
          f"precision {e['windowed_control']['precision']} FP {e['windowed_control']['fp_total']}", flush=True)
    print(f"  emit={res['emit_classification']} -> three-band: {res['three_band']}", flush=True)
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "starrocks_execution.json"), "w"), indent=2, sort_keys=True)
    print("  wrote results/starrocks_execution.json", flush=True)


if __name__ == "__main__":
    main()

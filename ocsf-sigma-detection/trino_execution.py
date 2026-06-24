"""H-SIGMA-01 lakehouse leg (backend 5 — Trino, GENERIC SQL path): does the window-drop persist on a
distributed MPP-JVM SQL engine reached through the generic pySigma path (no dedicated Trino backend exists)?

No `pySigma-backend-trino` / `-presto` on PyPI (checked 2026-06-23 — 404), so Trino falls to the generic
SQL backend, exactly as the pre-reg (PRE-REG-lakehouse-engines-2026-06-22.md) frames the generic case. The
generic emit dropped the event_count `timespan: 10m` for SQLite and DuckDB; this leg confirms the same
emitted windowless SQL over-fires on Trino (a fourth architecturally-distinct engine class: distributed,
JVM, columnar). Reuses the EXACT planted corpus + scoring (apples-to-apples). Loaded into Trino's `memory`
catalog (no S3 dependency). Tier B, single host, synthetic planted corpus. Trino reached at :8081 (moar).
"""
import json, os
import trino
import ppl_execution as P
from sigma.collection import SigmaCollection
from sigma.backends.sqlite import sqliteBackend  # generic SQL path (no dedicated Trino backend)

HERE = os.path.dirname(os.path.abspath(__file__))
from sqlite_execution import EVENT_COUNT_RULE, VALUE_COUNT_RULE, TEMPORAL_RULE

TR_HOST = os.environ.get("TR_HOST", "localhost")
TR_PORT = int(os.environ.get("TR_PORT", "8081"))


def compile_sql(rule_yaml):
    try:
        out = sqliteBackend().convert(SigmaCollection.from_yaml(rule_yaml))
        return out[0], None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:160]}"


def main():
    docs, truth = P.gen_corpus()
    true_set, decoy_set, benign_set = set(truth["true"]), set(truth["decoy"]), set(truth["benign"])
    conn = trino.dbapi.connect(host=TR_HOST, port=TR_PORT, user="bench", catalog="memory", schema="default")
    cur = conn.cursor()
    cur.execute("SELECT version()"); print(f"  Trino {cur.fetchone()[0]} (generic SQL pySigma path)", flush=True)
    cur.execute("CREATE SCHEMA IF NOT EXISTS memory.default"); cur.fetchall()
    cur.execute("DROP TABLE IF EXISTS memory.default.logs"); cur.fetchall()
    cur.execute("CREATE TABLE memory.default.logs (timestamp BIGINT, actor_user VARCHAR, outcome VARCHAR)"); cur.fetchall()
    # one multi-row INSERT (memory connector handles 4k rows fine)
    vals = ",".join(f"({int(ts)},'{u}','{o}')" for ts, u, o in docs)
    cur.execute(f"INSERT INTO memory.default.logs VALUES {vals}"); cur.fetchall()
    cur.execute("SELECT count(*) FROM logs"); n = cur.fetchone()[0]
    print(f"  loaded {n} synthetic auth events into Trino memory ({len(true_set)} true, {len(decoy_set)} decoy, {len(benign_set)} benign)", flush=True)

    def users(sql):
        cur.execute(sql); return {r[0] for r in cur.fetchall()}

    # 1) the pySigma-EMITTED query (generic sqlite backend), executed verbatim on Trino
    emitted, err = compile_sql(EVENT_COUNT_RULE)
    print(f"  event_count emitted SQL (generic backend, run on Trino): {emitted}", flush=True)
    emitted_run_sql, alias_note = emitted, None
    try:
        wl = users(emitted) if emitted else set()
    except Exception as ex:
        # Trino disallows referencing the SELECT alias in HAVING — run the semantically-identical windowless
        # form (aggregate in HAVING). Same windowless query, Trino-legal; labelled so it's not asserted as verbatim.
        alias_note = f"verbatim emit rejected by Trino ({type(ex).__name__}: {str(ex)[:80]}); ran windowless-equivalent (count(*) in HAVING)"
        emitted_run_sql = ("SELECT actor_user, count(*) AS event_count FROM (SELECT * FROM logs WHERE outcome='FAILURE') "
                           "AS subquery GROUP BY actor_user HAVING count(*) >= 10")
        print(f"  [note] {alias_note}", flush=True)
        wl = users(emitted_run_sql)

    # 2) the CORRECT WINDOWED control (10-min tumbling bucket) — Trino integer-division bucket
    windowed_sql = ("SELECT actor_user FROM (SELECT actor_user, count(*) c FROM logs WHERE outcome='FAILURE' "
                    "GROUP BY actor_user, (timestamp / 600) HAVING count(*) >= 10) GROUP BY actor_user")
    wd = users(windowed_sql)

    def score(flagged):
        tp = len(flagged & true_set); fp_d = len(flagged & decoy_set); fp_b = len(flagged & benign_set)
        return {"flagged": len(flagged), "tp": tp, "fp_total": fp_d + fp_b, "fp_decoy": fp_d, "fp_benign": fp_b,
                "recall": round(tp / max(len(true_set), 1), 3), "precision": round(tp / max(len(flagged), 1), 3)}

    windowless_emit = bool(emitted) and "600" not in (emitted or "") and "timestamp" not in (emitted or "")
    res = {
        "benchmark": "ocsf-sigma-detection / Trino execution (H-SIGMA-01 lakehouse leg, backend 5 — GENERIC path)",
        "evidence_tier": "B (single host; synthetic planted corpus; Trino + generic pySigma SQLite backend, no dedicated Trino backend)",
        "assumption_tested": "does the generic-path window-drop persist on a distributed MPP-JVM engine (Trino) with full window functions?",
        "compile_path": "generic pySigma SQLite backend (no dedicated Trino/Presto backend on PyPI), executed on Trino memory catalog",
        "emit_classification": "WINDOWLESS (timespan dropped)" if windowless_emit else "WINDOWED",
        "emitted_verbatim_sql": emitted,
        "emitted_executed_sql": emitted_run_sql,
        "emit_dialect_note": alias_note,
        "event_count": {"correct_windowed_sql": windowed_sql,
                        "emitted_run": score(wl), "windowed_control": score(wd)},
        "three_band": ("SILENTLY-DEGRADES (windowless emit + over-fire despite window-function capability)"
                       if windowless_emit and score(wl)["fp_decoy"] > 0 else
                       ("SURVIVES (windowed emit + correct fire)" if not windowless_emit and score(wl)["fp_total"] == 0
                        else "see emitted_run")),
        "events": n,
    }
    e = res["event_count"]
    print(f"  EMITTED  (generic on Trino):   flagged {e['emitted_run']['flagged']} tp {e['emitted_run']['tp']}/{len(true_set)} "
          f"precision {e['emitted_run']['precision']} FP-decoy {e['emitted_run']['fp_decoy']}", flush=True)
    print(f"  WINDOWED (correct Trino):      flagged {e['windowed_control']['flagged']} tp {e['windowed_control']['tp']}/{len(true_set)} "
          f"precision {e['windowed_control']['precision']} FP {e['windowed_control']['fp_total']}", flush=True)
    print(f"  emit={res['emit_classification']} -> three-band: {res['three_band']}", flush=True)
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "trino_execution.json"), "w"), indent=2, sort_keys=True)
    print("  wrote results/trino_execution.json", flush=True)


if __name__ == "__main__":
    main()

"""H-SIGMA-01 lakehouse leg (backend 3 — DuckDB): does the dropped correlation window generalize to a
columnar/lakehouse SQL engine that HAS window functions?

Pre-reg: PRE-REG-lakehouse-engines-2026-06-22.md. The pivotal question is whether the window-drop is a
BACKEND-CAPABILITY property (engines with window functions preserve it) or a pySigma-SQL-EMISSION property
(the available backend emits `GROUP BY … HAVING count >= N` with `timespan` dropped regardless of target).
DuckDB has full window functions, so if it still over-fires it's because the EMITTED SQL is windowless —
which would make survivability a property of pySigma-backend maturity, not engine capability (refining
Move #3). Compile path: the pySigma SQLite backend (no dedicated DuckDB backend exists), executed verbatim
on DuckDB — exactly the generic-SQL path the pre-reg names. Reuses the PPL/SQLite leg's EXACT gen_corpus +
scoring (apples-to-apples). Tier B, single host, synthetic planted corpus.
"""
import json, os, duckdb
import ppl_execution as P   # reuse the EXACT planted corpus + ground truth
from sigma.collection import SigmaCollection
from sigma.backends.sqlite import sqliteBackend

HERE = os.path.dirname(os.path.abspath(__file__))

# Same correlation rules as the SQLite leg (identical ground truth across backends).
from sqlite_execution import EVENT_COUNT_RULE, VALUE_COUNT_RULE, TEMPORAL_RULE


def compile_sql(rule_yaml):
    try:
        out = sqliteBackend().convert(SigmaCollection.from_yaml(rule_yaml))
        return out[0], None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:120]}"


def main():
    docs, truth = P.gen_corpus()
    true_set, decoy_set, benign_set = set(truth["true"]), set(truth["decoy"]), set(truth["benign"])
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE logs (timestamp BIGINT, actor_user VARCHAR, outcome VARCHAR)")
    con.executemany("INSERT INTO logs VALUES (?,?,?)", [(ts, u, o) for ts, u, o in docs])
    n = con.execute("SELECT count(*) FROM logs").fetchone()[0]
    print(f"  loaded {n} synthetic auth events into DuckDB ({len(true_set)} true, {len(decoy_set)} decoy, {len(benign_set)} benign)", flush=True)

    def users(sql):
        return {r[0] for r in con.execute(sql).fetchall()}

    # 1) the pySigma-EMITTED query (the available SQLite backend), executed verbatim on DuckDB
    emitted, err = compile_sql(EVENT_COUNT_RULE)
    print(f"  event_count emitted SQL (sqlite backend, run on DuckDB): {emitted}", flush=True)
    wl = users(emitted) if emitted else set()

    # 2) the CORRECT WINDOWED control (10-min tumbling bucket) — DuckDB integer-division bucket
    windowed_sql = ("SELECT actor_user FROM (SELECT actor_user, COUNT(*) c FROM logs WHERE outcome='FAILURE' "
                    "GROUP BY actor_user, CAST(timestamp // 600 AS BIGINT) HAVING c >= 10) GROUP BY actor_user")
    wd = users(windowed_sql)

    def score(flagged):
        tp = len(flagged & true_set); fp_d = len(flagged & decoy_set); fp_b = len(flagged & benign_set)
        return {"flagged": len(flagged), "tp": tp, "fp_total": fp_d + fp_b, "fp_decoy": fp_d, "fp_benign": fp_b,
                "recall": round(tp / max(len(true_set), 1), 3), "precision": round(tp / max(len(flagged), 1), 3)}

    vc_sql, vc_err = compile_sql(VALUE_COUNT_RULE)
    tmp_sql, tmp_err = compile_sql(TEMPORAL_RULE)
    windowless_emit = bool(emitted) and "600" not in (emitted or "") and "timestamp" not in (emitted or "")

    res = {
        "benchmark": "ocsf-sigma-detection / DuckDB execution (H-SIGMA-01 lakehouse leg, backend 3)",
        "evidence_tier": "B (single host; synthetic planted corpus; DuckDB + pySigma SQLite backend = generic path)",
        "assumption_tested": "does the silent window-drop persist on a window-function-capable lakehouse engine (DuckDB)?",
        "compile_path": "pySigma SQLite backend (no dedicated DuckDB backend), executed verbatim on DuckDB",
        "emit_classification": "WINDOWLESS (timespan dropped)" if windowless_emit else "WINDOWED",
        "event_count": {"emitted_sql": emitted, "correct_windowed_sql": windowed_sql,
                        "emitted_run": score(wl), "windowed_control": score(wd)},
        "three_band": ("SILENTLY-DEGRADES (windowless emit + over-fire despite window-function capability)"
                       if windowless_emit and score(wl)["fp_decoy"] > 0 else
                       ("SURVIVES (windowed emit + correct fire)" if not windowless_emit and score(wl)["fp_total"] == 0
                        else "see emitted_run")),
        "correlation_coverage": {
            "event_count": "compiled WINDOWLESS (timespan dropped)" if windowless_emit else ("compiled" if emitted else f"refused: {err}"),
            "value_count": ("compiled WINDOWLESS" if vc_sql and "timestamp" not in vc_sql else (f"refused: {vc_err}" if vc_err else "compiled")),
            "temporal_ordered": (f"refused: {tmp_err}" if tmp_err else "compiled"),
        },
        "events": n,
    }
    e = res["event_count"]
    print(f"  EMITTED  (sqlite-backend on DuckDB): flagged {e['emitted_run']['flagged']} tp {e['emitted_run']['tp']}/{len(true_set)} "
          f"precision {e['emitted_run']['precision']} FP-decoy {e['emitted_run']['fp_decoy']}", flush=True)
    print(f"  WINDOWED (correct DuckDB control):   flagged {e['windowed_control']['flagged']} tp {e['windowed_control']['tp']}/{len(true_set)} "
          f"precision {e['windowed_control']['precision']} FP {e['windowed_control']['fp_total']}", flush=True)
    print(f"  emit={res['emit_classification']} -> three-band: {res['three_band']}", flush=True)
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "duckdb_execution.json"), "w"), indent=2, sort_keys=True)
    print("  wrote results/duckdb_execution.json", flush=True)


if __name__ == "__main__":
    main()

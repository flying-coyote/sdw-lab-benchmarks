"""H-SIGMA-01 lakehouse leg (backend 4 — ClickHouse, via the DEDICATED pySigma backend): does the
window-drop persist when a *dedicated, engine-native* pySigma backend exists (not the generic SQL path)?

This is the pivotal case the pre-reg (PRE-REG-lakehouse-engines-2026-06-22.md) names. DuckDB/SQLite/PPL
all degraded via the GENERIC path. ClickHouse is the only one of the five lakehouse engines with a
dedicated pySigma backend (`pySigma-backend-clickhouse`, ClickhouseBackend) — and it is genuinely
engine-native (it emits ClickHouse functions like `uniqExact()` for value_count). The Move #3 "most-likely
nuance" predicted survivability is a property of *dedicated-backend maturity per engine*, so the dedicated
ClickHouse backend was the candidate to emit WINDOWED and SURVIVE.

Compile-probe result (frozen before execution):
  - event_count  -> `… GROUP BY actor_user HAVING event_count >= 10`              -> WINDOWLESS (timespan dropped)
  - value_count  -> `… uniqExact(actor_user) … HAVING value_count >= 10`         -> WINDOWLESS (CH-native fn, still windowless)
  - temporal     -> `… HAVING rule_count >= 2 AND (max(last)-min(first)) <= 600` -> WINDOWED (carries the 600s span)
So the dedicated backend drops the event_count/value_count window but DOES carry the temporal one — the
window-drop is per-correlation-type in pySigma's SQL-family conversion, not a "no dedicated backend" gap.

This harness EXECUTES the dedicated-backend-emitted event_count SQL on live ClickHouse + the correct windowed
control, scoring against the SAME planted corpus/ground truth as the PPL/SQLite/DuckDB legs (apples-to-apples).
Tier B, single host, synthetic planted corpus. ClickHouse reached over HTTP :8125 (the moar stack).
"""
import json, os
import clickhouse_connect
import ppl_execution as P   # reuse the EXACT planted corpus + ground truth
from sigma.collection import SigmaCollection
from sigma.backends.clickhouse import ClickhouseBackend

HERE = os.path.dirname(os.path.abspath(__file__))

# Same correlation rules as every other leg (identical ground truth across backends).
from sqlite_execution import EVENT_COUNT_RULE, VALUE_COUNT_RULE, TEMPORAL_RULE

CH_HOST = os.environ.get("CH_HOST", "localhost")
CH_PORT = int(os.environ.get("CH_PORT", "8125"))


def compile_sql(rule_yaml):
    try:
        out = ClickhouseBackend().convert(SigmaCollection.from_yaml(rule_yaml))
        return out[0], None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:160]}"


def main():
    docs, truth = P.gen_corpus()
    true_set, decoy_set, benign_set = set(truth["true"]), set(truth["decoy"]), set(truth["benign"])
    c = clickhouse_connect.get_client(host=CH_HOST, port=CH_PORT, username="default", password="")
    print(f"  ClickHouse {c.query('SELECT version()').result_rows[0][0]} (dedicated pySigma backend)", flush=True)
    c.command("DROP TABLE IF EXISTS logs")
    c.command("CREATE TABLE logs (timestamp Int64, actor_user String, outcome String) ENGINE = Memory")
    c.insert("logs", [(int(ts), u, o) for ts, u, o in docs], column_names=["timestamp", "actor_user", "outcome"])
    n = c.query("SELECT count(*) FROM logs").result_rows[0][0]
    print(f"  loaded {n} synthetic auth events into ClickHouse ({len(true_set)} true, {len(decoy_set)} decoy, {len(benign_set)} benign)", flush=True)

    def users(sql):
        return {r[0] for r in c.query(sql).result_rows}

    # 1) the pySigma-EMITTED query from the DEDICATED ClickHouse backend
    emitted, err = compile_sql(EVENT_COUNT_RULE)
    print(f"  event_count emitted SQL (DEDICATED ClickHouse backend): {emitted}", flush=True)
    wl = users(emitted) if emitted else set()

    # 2) the CORRECT WINDOWED control (10-min tumbling bucket) — ClickHouse integer-division bucket
    windowed_sql = ("SELECT actor_user FROM (SELECT actor_user, count(*) c FROM logs WHERE outcome='FAILURE' "
                    "GROUP BY actor_user, intDiv(timestamp, 600) HAVING c >= 10) GROUP BY actor_user")
    wd = users(windowed_sql)

    def score(flagged):
        tp = len(flagged & true_set); fp_d = len(flagged & decoy_set); fp_b = len(flagged & benign_set)
        return {"flagged": len(flagged), "tp": tp, "fp_total": fp_d + fp_b, "fp_decoy": fp_d, "fp_benign": fp_b,
                "recall": round(tp / max(len(true_set), 1), 3), "precision": round(tp / max(len(flagged), 1), 3)}

    vc_sql, vc_err = compile_sql(VALUE_COUNT_RULE)
    tmp_sql, tmp_err = compile_sql(TEMPORAL_RULE)
    windowless_emit = bool(emitted) and "600" not in (emitted or "") and "timestamp" not in (emitted or "")

    res = {
        "benchmark": "ocsf-sigma-detection / ClickHouse execution (H-SIGMA-01 lakehouse leg, backend 4 — DEDICATED backend)",
        "evidence_tier": "B (single host; synthetic planted corpus; ClickHouse + DEDICATED pySigma-backend-clickhouse 1.0.0)",
        "assumption_tested": "does a DEDICATED, engine-native pySigma backend preserve the event_count window where the generic path dropped it?",
        "compile_path": "DEDICATED pySigma ClickHouse backend (ClickhouseBackend) — engine-native (emits uniqExact for value_count)",
        "emit_classification": "WINDOWLESS (timespan dropped)" if windowless_emit else "WINDOWED",
        "event_count": {"emitted_sql": emitted, "correct_windowed_sql": windowed_sql,
                        "emitted_run": score(wl), "windowed_control": score(wd)},
        "three_band": ("SILENTLY-DEGRADES (windowless emit + over-fire from a DEDICATED backend despite engine capability)"
                       if windowless_emit and score(wl)["fp_decoy"] > 0 else
                       ("SURVIVES (windowed emit + correct fire)" if not windowless_emit and score(wl)["fp_total"] == 0
                        else "see emitted_run")),
        "correlation_coverage": {
            "event_count": "compiled WINDOWLESS (timespan dropped)" if windowless_emit else ("compiled" if emitted else f"refused: {err}"),
            "value_count": ("compiled WINDOWLESS (CH-native uniqExact, window dropped)" if vc_sql and "600" not in vc_sql and "timestamp" not in vc_sql else (f"refused: {vc_err}" if vc_err else "compiled")),
            "value_count_sql": vc_sql,
            "temporal_ordered": ("compiled WINDOWED (carries max-min <= 600 span)" if tmp_sql and "600" in tmp_sql else (f"refused: {tmp_err}" if tmp_err else "compiled")),
            "temporal_sql": tmp_sql,
        },
        "events": n,
    }
    e = res["event_count"]
    print(f"  EMITTED  (dedicated CH backend):   flagged {e['emitted_run']['flagged']} tp {e['emitted_run']['tp']}/{len(true_set)} "
          f"precision {e['emitted_run']['precision']} FP-decoy {e['emitted_run']['fp_decoy']}", flush=True)
    print(f"  WINDOWED (correct CH control):     flagged {e['windowed_control']['flagged']} tp {e['windowed_control']['tp']}/{len(true_set)} "
          f"precision {e['windowed_control']['precision']} FP {e['windowed_control']['fp_total']}", flush=True)
    print(f"  emit={res['emit_classification']} -> three-band: {res['three_band']}", flush=True)
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "clickhouse_execution.json"), "w"), indent=2, sort_keys=True)
    print("  wrote results/clickhouse_execution.json", flush=True)


if __name__ == "__main__":
    main()

"""H-SIGMA-01 lakehouse leg (backend 7 — Dremio OSS, GENERIC SQL path): does the window-drop persist on a
federation/lakehouse engine reached through the generic pySigma path?

No dedicated `pySigma-backend-dremio` on PyPI (checked 2026-06-23 — 404), so Dremio falls to the generic
SQL backend. Sixth+ architecturally-distinct engine class (federation/Arrow). Reuses the EXACT planted
corpus + scoring. Data loaded into Dremio's built-in `$scratch` writable space via CTAS-from-VALUES; queried
over the Dremio REST API (:9147) — no perf instrumentation.

SCOPE GUARD (DeWitt): this leg records ONLY firing-correctness (precision / over-fire / three-band) — it
emits NO Dremio performance numbers (latency/throughput), and it is INDEPENDENT of the answer-equality
reader-count benchmark (where Dremio is the withheld participant). The pre-reg lists Dremio as backend 7 and
firing-correctness is exactly the survivability measurement, so it is in-scope here; perf stays withheld.

Tier B, single host, synthetic planted corpus. Dremio admin bootstrap per moar config/dremio/setup-dremio.sh.
"""
import json, os, time, urllib.request, urllib.error
import ppl_execution as P
from sigma.collection import SigmaCollection
from sigma.backends.sqlite import sqliteBackend  # generic SQL path (no dedicated Dremio backend)

HERE = os.path.dirname(os.path.abspath(__file__))
from sqlite_execution import EVENT_COUNT_RULE

DREMIO = os.environ.get("DREMIO_URL", "http://localhost:9147")
DUSER = os.environ.get("DREMIO_USER", "admin")
DPASS = os.environ.get("DREMIO_PASS", "dremioAdmin123")


def _req(path, body=None, method="GET", token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"_dremio{token}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{DREMIO}{path}", data=data, method=method, headers=headers)
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.load(resp)


def login():
    return _req("/apiv2/login", {"userName": DUSER, "password": DPASS}, method="POST")["token"]


def run_sql(sql, token, want_rows=True):
    job = _req("/api/v3/sql", {"sql": sql}, method="POST", token=token)["id"]
    for _ in range(120):
        st = _req(f"/api/v3/job/{job}", token=token)
        state = st["jobState"]
        if state in ("COMPLETED", "FAILED", "CANCELED"):
            break
        time.sleep(1)
    if state != "COMPLETED":
        raise RuntimeError(f"Dremio job {state}: {st.get('errorMessage', '')[:200]}")
    if not want_rows:
        return None
    rows, offset = [], 0
    while True:
        page = _req(f"/api/v3/job/{job}/results?offset={offset}&limit=500", token=token)
        rows.extend(page.get("rows", []))
        total = page.get("rowCount", len(rows))
        offset = len(rows)
        if offset >= total or not page.get("rows"):
            break
    return rows


def compile_sql(rule_yaml):
    out = sqliteBackend().convert(SigmaCollection.from_yaml(rule_yaml))
    return out[0]


def main():
    docs, truth = P.gen_corpus()
    true_set, decoy_set, benign_set = set(truth["true"]), set(truth["decoy"]), set(truth["benign"])
    token = login()
    ver = _req("/apiv2/server_status", token=token) if False else None  # avoid extra calls; version via SQL below
    try:
        v = run_sql("SELECT version() AS v", token)
        print(f"  Dremio {v[0]['v'] if v else '?'} (generic SQL pySigma path)", flush=True)
    except Exception:
        print("  Dremio (generic SQL pySigma path)", flush=True)

    run_sql('DROP TABLE IF EXISTS $scratch.logs', token, want_rows=False)
    vals = ",".join(f"({int(ts)},'{u}','{o}')" for ts, u, o in docs)
    run_sql(f'CREATE TABLE $scratch.logs AS '
            f'SELECT * FROM (VALUES {vals}) AS t("timestamp","actor_user","outcome")', token, want_rows=False)
    n = run_sql('SELECT count(*) AS c FROM $scratch.logs', token)[0]["c"]
    print(f"  loaded {n} synthetic auth events into Dremio $scratch ({len(true_set)} true, {len(decoy_set)} decoy, {len(benign_set)} benign)", flush=True)

    def users(sql):
        return {r["actor_user"] for r in run_sql(sql, token)}

    emitted = compile_sql(EVENT_COUNT_RULE)
    # qualify the bare `logs` reference to the $scratch table
    emitted_dremio = emitted.replace("FROM logs", 'FROM $scratch.logs')
    print(f"  event_count emitted SQL (generic backend, run on Dremio): {emitted_dremio}", flush=True)
    # Dremio (Calcite) rejects alias-in-HAVING like Trino — run the windowless-equivalent (aggregate in HAVING)
    emitted_exec = ('SELECT actor_user, count(*) AS event_count FROM (SELECT * FROM $scratch.logs '
                    "WHERE outcome='FAILURE') AS subquery GROUP BY actor_user HAVING count(*) >= 10")
    try:
        wl = users(emitted_dremio)
        executed = emitted_dremio; alias_note = None
    except Exception as ex:
        alias_note = f"verbatim emit rejected by Dremio ({str(ex)[:80]}); ran windowless-equivalent (count(*) in HAVING)"
        print(f"  [note] {alias_note}", flush=True)
        wl = users(emitted_exec); executed = emitted_exec

    windowed_sql = ('SELECT actor_user FROM (SELECT actor_user, count(*) c FROM $scratch.logs '
                    "WHERE outcome='FAILURE' GROUP BY actor_user, FLOOR(\"timestamp\"/600) "
                    'HAVING count(*) >= 10) t GROUP BY actor_user')
    wd = users(windowed_sql)

    def score(flagged):
        tp = len(flagged & true_set); fp_d = len(flagged & decoy_set); fp_b = len(flagged & benign_set)
        return {"flagged": len(flagged), "tp": tp, "fp_total": fp_d + fp_b, "fp_decoy": fp_d, "fp_benign": fp_b,
                "recall": round(tp / max(len(true_set), 1), 3), "precision": round(tp / max(len(flagged), 1), 3)}

    windowless_emit = "600" not in emitted and "timestamp" not in emitted
    res = {
        "benchmark": "ocsf-sigma-detection / Dremio execution (H-SIGMA-01 lakehouse leg, backend 7 — GENERIC path)",
        "evidence_tier": "B (single host; synthetic planted corpus; Dremio OSS + generic pySigma SQLite backend, no dedicated Dremio backend)",
        "scope_guard": "firing-correctness ONLY (no Dremio perf numbers); independent of the answer-equality reader-count benchmark",
        "assumption_tested": "does the generic-path window-drop persist on a federation/Arrow engine (Dremio)?",
        "compile_path": "generic pySigma SQLite backend (no dedicated Dremio backend), executed over Dremio REST on $scratch",
        "emit_classification": "WINDOWLESS (timespan dropped)" if windowless_emit else "WINDOWED",
        "emitted_verbatim_sql": emitted,
        "emitted_executed_sql": executed,
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
    print(f"  EMITTED  (generic on Dremio):  flagged {e['emitted_run']['flagged']} tp {e['emitted_run']['tp']}/{len(true_set)} "
          f"precision {e['emitted_run']['precision']} FP-decoy {e['emitted_run']['fp_decoy']}", flush=True)
    print(f"  WINDOWED (correct Dremio):     flagged {e['windowed_control']['flagged']} tp {e['windowed_control']['tp']}/{len(true_set)} "
          f"precision {e['windowed_control']['precision']} FP {e['windowed_control']['fp_total']}", flush=True)
    print(f"  emit={res['emit_classification']} -> three-band: {res['three_band']}", flush=True)
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "dremio_execution.json"), "w"), indent=2, sort_keys=True)
    print("  wrote results/dremio_execution.json", flush=True)


if __name__ == "__main__":
    main()

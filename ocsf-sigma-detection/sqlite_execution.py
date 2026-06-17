"""H-SIGMA-01 execution leg #4 — second backend (SQLite): does the dropped correlation window generalize?

Tests whether PPL's silent correlation-window drop is a PPL-plugin quirk or a cross-backend pattern, by
EXECUTING the pySigma **SQLite** backend's emitted query on a file-based SQL engine (architecturally
distinct from OpenSearch). Reuses the PPL leg's exact `gen_corpus` + scoring (apples-to-apples). The
compile probe already showed the SQLite backend drops the `timespan: 10m` (`… GROUP BY actor_user HAVING
event_count >= 10`); this confirms the over-fire at runtime. Pre-reg: PRE-REG-sqlite-2ndbackend-2026-06-17.md.
Tier B, single host, synthetic planted corpus, pySigma 1.3.3 + pySigma-backend-sqlite 1.1.3.
"""
import json, os, sqlite3
import ppl_execution as P   # reuse the EXACT planted corpus + ground truth
from sigma.collection import SigmaCollection
from sigma.backends.sqlite import sqliteBackend

HERE = os.path.dirname(os.path.abspath(__file__))

EVENT_COUNT_RULE = """
title: failed_logins
name: failed_logins
status: test
logsource: {category: authentication}
detection: {sel: {outcome: FAILURE}, condition: sel}
---
title: brute_force
status: test
correlation:
  type: event_count
  rules: [failed_logins]
  group-by: [actor_user]
  timespan: 10m
  condition: {gte: 10}
"""

VALUE_COUNT_RULE = """
title: failed_logins_vc
name: failed_logins_vc
status: test
logsource: {category: authentication}
detection: {sel: {outcome: FAILURE}, condition: sel}
---
title: user_spray
status: test
correlation:
  type: value_count
  rules: [failed_logins_vc]
  group-by: [src_ip]
  timespan: 10m
  condition: {gte: 10, field: actor_user}
"""

TEMPORAL_RULE = """
title: a
name: a
logsource: {category: authentication}
detection: {sel: {outcome: FAILURE}, condition: sel}
---
title: b
name: b
logsource: {category: authentication}
detection: {sel: {outcome: SUCCESS}, condition: sel}
---
title: temporal_seq
status: test
correlation:
  type: temporal_ordered
  rules: [a, b]
  group-by: [actor_user]
  timespan: 10m
"""


def compile_sqlite(rule_yaml):
    try:
        out = sqliteBackend().convert(SigmaCollection.from_yaml(rule_yaml))
        return out[0], None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:120]}"


def main():
    docs, truth = P.gen_corpus()
    true_set, decoy_set, benign_set = set(truth["true"]), set(truth["decoy"]), set(truth["benign"])
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE logs (timestamp INTEGER, actor_user TEXT, outcome TEXT)")
    con.executemany("INSERT INTO logs VALUES (?,?,?)", [(ts, u, o) for ts, u, o in docs])
    con.commit()
    n = con.execute("SELECT count(*) FROM logs").fetchone()[0]
    print(f"  loaded {n} synthetic auth events into SQLite ({len(true_set)} true, {len(decoy_set)} decoy, {len(benign_set)} benign)", flush=True)

    # 1) the SQLite-backend-EMITTED windowless query (timespan dropped) — execute it
    emitted, err = compile_sqlite(EVENT_COUNT_RULE)
    print(f"  event_count emitted SQL: {emitted}", flush=True)
    def users(sql):
        return {r[0] for r in con.execute(sql).fetchall()}
    wl = users(emitted) if emitted else set()

    # 2) a CORRECT WINDOWED query (10-min tumbling bucket on the SAME engine)
    windowed_sql = ("SELECT actor_user FROM (SELECT actor_user, COUNT(*) c FROM logs WHERE outcome='FAILURE' "
                    "GROUP BY actor_user, CAST(timestamp/600 AS INT) HAVING c >= 10) GROUP BY actor_user")
    wd = users(windowed_sql)

    def score(flagged):
        tp = len(flagged & true_set); fp_d = len(flagged & decoy_set); fp_b = len(flagged & benign_set)
        return {"flagged": len(flagged), "tp": tp, "fp_total": fp_d + fp_b, "fp_decoy": fp_d, "fp_benign": fp_b,
                "recall": round(tp / max(len(true_set), 1), 3), "precision": round(tp / max(len(flagged), 1), 3)}

    # coverage of the other correlation types on this backend (compile-only)
    vc_sql, vc_err = compile_sqlite(VALUE_COUNT_RULE)
    tmp_sql, tmp_err = compile_sqlite(TEMPORAL_RULE)

    res = {
        "benchmark": "ocsf-sigma-detection / SQLite execution (H-SIGMA-01 second-backend leg)",
        "evidence_tier": "B (single host; synthetic planted corpus; SQLite + pySigma-backend-sqlite 1.1.3)",
        "assumption_tested": "is PPL's silent window-drop a PPL quirk or cross-backend?",
        "event_count": {"emitted_windowless_sql": emitted, "correct_windowed_sql": windowed_sql,
                        "windowless": score(wl), "windowed": score(wd)},
        "correlation_coverage": {
            "event_count": "compiled WINDOWLESS (timespan dropped)" if emitted and "600" not in (emitted or "") and "timestamp" not in (emitted or "") else ("compiled" if emitted else f"refused: {err}"),
            "value_count": ("compiled WINDOWLESS" if vc_sql and "timestamp" not in vc_sql else (f"refused: {vc_err}" if vc_err else "compiled")),
            "value_count_sql": vc_sql,
            "temporal_ordered": (f"refused: {tmp_err}" if tmp_err else "compiled"),
            "temporal_sql": tmp_sql,
        },
        "events": n,
    }
    e = res["event_count"]
    print(f"  WINDOWLESS (emitted SQLite): flagged {e['windowless']['flagged']} tp {e['windowless']['tp']}/{len(true_set)} "
          f"precision {e['windowless']['precision']} FP-decoy {e['windowless']['fp_decoy']}", flush=True)
    print(f"  WINDOWED  (correct SQLite): flagged {e['windowed']['flagged']} tp {e['windowed']['tp']}/{len(true_set)} "
          f"precision {e['windowed']['precision']} FP {e['windowed']['fp_total']}", flush=True)
    print(f"  coverage: event_count={res['correlation_coverage']['event_count']} | "
          f"value_count={res['correlation_coverage']['value_count']} | temporal={res['correlation_coverage']['temporal_ordered']}", flush=True)
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "sqlite_execution.json"), "w"), indent=2, sort_keys=True)
    print("  wrote results/sqlite_execution.json", flush=True)


if __name__ == "__main__":
    main()

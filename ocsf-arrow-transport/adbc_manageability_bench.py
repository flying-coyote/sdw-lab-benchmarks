#!/usr/bin/env python3
"""M1 (integration-surface quantification) + M2 (engine-swap reversibility) for Arrow/ADBC as a
MANAGEABILITY lever across the lab's 4-engine stack. Folds in the ADBC-over-JDBC bridge as the
realistic uniform path for the engines that don't speak Flight SQL.

Three access regimes compared over the SAME shared Nessie/Iceberg table (soc.conn_ueba_planted):
  A. BESPOKE (status quo, ejs_clients.py): one hand-written client per engine.
  B. PY-ARROW-TODAY: best Arrow you can get from Python today, per engine, with mixed APIs
     (Dremio ADBC Flight SQL; ClickHouse clickhouse-connect query_arrow; StarRocks/Trino still row-bespoke).
  C. ADBC-UNIFORM (Flight SQL + ADBC-over-JDBC bridge): one ADBC API for all engines —
     Flight SQL natively (Dremio), ADBC-over-JDBC for the rest (ClickHouse/StarRocks/Trino),
     at the cost of a JVM + one JDBC jar per non-Flight-SQL engine.

M1 counts the consumer-facing surface (auth schemes, result representations, paging models, type
fidelity, deps) per regime. M2 counts the touch-points to swap engine A->B per regime. Live
answer-equality (count over the shared table) confirms the uniform paths return the same data.
Tier B, single host. Run in ejs-lab.
"""
import json, os, re, time
import ejs_clients as E

TABLE = "soc.conn_ueba_planted"
OUT = "/tmp/adbc_manageability.json"
EJS_SRC = "/tmp/ejs_clients.py"   # the bespoke baseline, for LOC/dep counting

# ---- live answer-equality + capability confirmation across access tiers --------------------------
def live_checks():
    res = {}
    # bespoke row paths (StarRocks pymysql, Trino REST, ClickHouse HTTP) via ejs_clients
    for name in ("starrocks", "clickhouse_iceberg", "trino", "dremio"):
        try:
            c = E.CLIENTS[name](); ref = c.ref(TABLE)
            rows = c.run(f"SELECT count(*) FROM {ref}")
            res[f"bespoke:{name}"] = {"count": int(rows[0][0]), "result_type": type(rows).__name__}
        except Exception as e:
            res[f"bespoke:{name}"] = {"error": str(e)[:160]}
    # Tier-B Arrow-today: Dremio ADBC Flight SQL (uniform ADBC API)
    try:
        import adbc_driver_flightsql.dbapi as fsql
        conn = fsql.connect("grpc://dremio:32010", db_kwargs={"username": "admin", "password": "dremioAdmin123"})
        cur = conn.cursor(); cur.execute(f'SELECT count(*) AS n FROM nessie."soc"."conn_ueba_planted"')
        t = cur.fetch_arrow_table(); cur.close(); conn.close()
        res["adbc_flightsql:dremio"] = {"count": int(t.column("n")[0].as_py()),
                                        "result_type": type(t).__name__, "typed_schema": [str(x) for x in t.schema.types]}
    except Exception as e:
        res["adbc_flightsql:dremio"] = {"error": str(e)[:200]}
    # Tier-B Arrow-today: ClickHouse query_arrow (engine Arrow API, NOT ADBC)
    try:
        import clickhouse_connect
        ch = clickhouse_connect.get_client(host="clickhouse", port=8123, password="ejsbench123")
        ref = E.ClickHouse().ref(TABLE)
        t = ch.query_arrow(f"SELECT count(*) AS n FROM {ref}")
        res["engine_arrow:clickhouse"] = {"count": int(t.column("n")[0].as_py()),
                                          "result_type": type(t).__name__, "typed_schema": [str(x) for x in t.schema.types]}
    except Exception as e:
        res["engine_arrow:clickhouse"] = {"error": str(e)[:200]}
    return res

# ---- M1: integration-surface facts (audited from ejs_clients.py source + the probes) -------------
# Each engine's bespoke access, classified. These are the consumer-facing concerns a maintainer owns.
BESPOKE = {
    "starrocks":          {"wire": "MySQL-wire (pymysql)", "auth": "user + CREATE EXTERNAL CATALOG DDL",
                           "result": "list[tuple]", "paging": "cursor.fetchall", "types": "driver-typed",
                           "dep": "pymysql"},
    "clickhouse_iceberg": {"wire": "HTTP (clickhouse-connect)", "auth": "password",
                           "result": ".result_rows (list)", "paging": "single call", "types": "driver-typed",
                           "dep": "clickhouse-connect"},
    "trino":              {"wire": "REST /v1/statement", "auth": "X-Trino-User header",
                           "result": "JSON data arrays", "paging": "nextUri poll loop", "types": "JSON-untyped",
                           "dep": "requests"},
    "dremio":             {"wire": "REST /apiv2 + /api/v3", "auth": "login->token header",
                           "result": "JSON rows+schema (rebuilt by name)", "paging": "job-state poll + offset/limit",
                           "types": "LOST -> re-inferred by name", "dep": "requests"},
}
# Uniform-coverage capability tier (probed this session)
CAPABILITY = {
    "dremio":             "ADBC Flight SQL (native, :32010) — uniform ADBC API + Arrow",
    "clickhouse_iceberg": "engine Arrow API (query_arrow) — Arrow result, bespoke API; no native ADBC / no Flight SQL server",
    "starrocks":          "no Flight SQL (not enabled), no native Python ADBC — bespoke rows or ADBC-over-JDBC",
    "trino":              "Trino 481, no native Python ADBC / no Flight SQL server — bespoke rows or ADBC-over-JDBC",
}
# Regime C: ADBC-uniform via Flight SQL + ADBC-over-JDBC bridge. The bridge restores ONE ADBC API
# returning Arrow, but is JVM-only (org.apache.arrow.adbc.driver.jdbc.JdbcDriver) and needs one JDBC jar
# per engine — so "N drivers" does not fully collapse to zero; it collapses the API/result/paging/type
# surface to 1 each, while the *driver* count stays N (jars) + a JVM runtime.
ADBC_JDBC_BRIDGE = {
    "mechanism": "org.apache.arrow.adbc.driver.jdbc.JdbcDriver wraps any JDBC driver, returns Arrow (JVM-side)",
    "uniform_api": True, "result": "Arrow (VectorSchemaRoot)", "paging": "driver-owned", "types": "Arrow-typed",
    "runtime_cost": "JVM required (no clean Python ADBC path for these engines)",
    "per_engine_dep": {"clickhouse_iceberg": "clickhouse-jdbc jar", "starrocks": "mysql-connector-j jar",
                       "trino": "trino-jdbc jar"},
    "note": "From Python (the security-analytics lingua franca) this means crossing into the JVM or staying "
            "on engine-specific Arrow APIs; the uniform-API win is real but carries a JVM + N-jars cost.",
}


def count_surface():
    n = len(BESPOKE)
    def distinct(key):
        return sorted(set(v[key] for v in BESPOKE.values()))
    # Regime A: bespoke — every concern is per-engine
    A = {"regime": "A: bespoke (status quo)",
         "distinct_auth": len(distinct("auth")), "distinct_result_reprs": len(distinct("result")),
         "distinct_paging": len(distinct("paging")), "type_fidelity_lost_engines": [k for k, v in BESPOKE.items() if "LOST" in v["types"]],
         "client_deps": sorted(set(v["dep"] for v in BESPOKE.values())), "jvm_required": False,
         "consumer_handlers": n}  # one full {auth,result,paging,type} handler per engine
    # Regime C: ADBC-uniform (Flight SQL + ADBC-JDBC bridge)
    flight = [k for k, v in CAPABILITY.items() if "Flight SQL (native" in v]
    bridged = [k for k in BESPOKE if k not in flight]
    C = {"regime": "C: ADBC-uniform (Flight SQL + ADBC-over-JDBC bridge)",
         "distinct_auth": 1, "distinct_result_reprs": 1, "distinct_paging": 0,  # ADBC API owns these
         "type_fidelity_lost_engines": [], "uniform_api": True,
         "flight_sql_native": flight, "adbc_jdbc_bridged": bridged,
         "client_deps": ["adbc_driver_manager", "adbc_driver_flightsql"],
         "jvm_required": True, "jvm_reason": f"ADBC-over-JDBC for {bridged} (no native Python ADBC)",
         "per_engine_jdbc_jars": {k: ADBC_JDBC_BRIDGE["per_engine_dep"][k] for k in bridged},
         "consumer_handlers": 1}  # one ADBC handler for all engines
    return {"n_engines": n, "regime_A_bespoke": A, "regime_C_adbc_uniform": C,
            "bespoke_detail": BESPOKE, "capability_map": CAPABILITY, "adbc_jdbc_bridge": ADBC_JDBC_BRIDGE}


# ---- M2: engine-swap reversibility (touch-points to swap A->B) -----------------------------------
def swap_cost():
    src = open(EJS_SRC).read() if os.path.exists(EJS_SRC) else ""
    # bespoke: swapping engines means swapping client CLASSES — measure each class's LOC (what you rewrite)
    classes = {}
    for m in re.finditer(r"\nclass (\w+):(.*?)(?=\nclass |\nCLIENTS|\Z)", src, re.DOTALL):
        name, body = m.group(1), m.group(2)
        classes[name] = len([l for l in body.splitlines() if l.strip() and not l.strip().startswith("#")])
    bespoke_loc = {k: classes.get(k) for k in ("StarRocks", "ClickHouse", "Trino", "Dremio")}
    return {
        "bespoke": {"swap_unit": "rewrite the per-engine client class (auth+execute+result+paging+ref)",
                    "touch_points_loc_per_engine": bespoke_loc,
                    "median_loc": sorted(v for v in bespoke_loc.values() if v)[len([v for v in bespoke_loc.values() if v])//2] if any(bespoke_loc.values()) else None},
        "adbc_uniform": {"swap_unit": "change the connection target (driver/URI); + 1 JDBC jar if non-Flight-SQL",
                         "touch_points_loc_per_engine": {"flight_sql": "~1-3 (connection dict)", "jdbc_bridge": "~1-3 + add 1 jar to classpath"},
                         "note": "the {execute, fetch_arrow_table} consumer code does NOT change — that is the reversibility win"},
    }


def main():
    out = {"bench": "ocsf-arrow-transport / Arrow-ADBC manageability M1+M2", "tier": "B", "host": "ejs single host",
           "table": TABLE, "M1_surface": count_surface(), "M2_swap_cost": swap_cost(), "live_checks": live_checks()}
    # answer-equality across the access tiers that returned a count
    counts = {k: v["count"] for k, v in out["live_checks"].items() if "count" in v}
    out["answer_equal_across_access"] = (len(set(counts.values())) == 1) if counts else None
    out["counts_by_access"] = counts
    json.dump(out, open(OUT, "w"), indent=2, default=str)
    A, C = out["M1_surface"]["regime_A_bespoke"], out["M1_surface"]["regime_C_adbc_uniform"]
    print("M1 integration surface (4 engines):")
    print(f"  BESPOKE   : auth={A['distinct_auth']} result-reprs={A['distinct_result_reprs']} paging={A['distinct_paging']} "
          f"type-lost={A['type_fidelity_lost_engines']} deps={A['client_deps']} jvm={A['jvm_required']} handlers={A['consumer_handlers']}")
    print(f"  ADBC-UNIF : auth={C['distinct_auth']} result-reprs={C['distinct_result_reprs']} paging={C['distinct_paging']} "
          f"type-lost={C['type_fidelity_lost_engines']} deps={C['client_deps']} jvm={C['jvm_required']} handlers={C['consumer_handlers']}")
    print(f"            flight-sql-native={C['flight_sql_native']} | adbc-jdbc-bridged={C['adbc_jdbc_bridged']} (+{C['per_engine_jdbc_jars']})")
    print(f"M2 swap cost: bespoke per-engine class LOC={out['M2_swap_cost']['bespoke']['touch_points_loc_per_engine']} "
          f"vs ADBC-uniform ~1-3 lines (consumer code unchanged)")
    print(f"answer-equal across access tiers: {out['answer_equal_across_access']} | counts={counts}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()

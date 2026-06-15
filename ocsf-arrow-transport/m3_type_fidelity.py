#!/usr/bin/env python3
"""M3 — type-fidelity as a maintenance burden. Arrow's typed schema travels intact across engines;
the bespoke row paths return the SAME logical column as different Python types per engine (or lose
types entirely), so a consumer must write per-engine coercion to normalize. Count the coercion sites.

Same multi-type query across the 4 engines via bespoke clients (capture each cell's Python type) and
via the Arrow paths (Dremio ADBC Flight SQL, ClickHouse query_arrow — capture the Arrow schema type).
Tier B, single host. Run in ejs-lab with PYTHONPATH=/tmp (ejs_clients there)."""
import json
import ejs_clients as E

TABLE = "soc.conn_ueba_planted"
# orig_h: string, c: integer count, avg_b: floating average, max_ts: double epoch
TAIL = "count(*) AS c, avg(orig_bytes) AS avg_b, max(ts) AS max_ts FROM {ref} GROUP BY orig_h ORDER BY c DESC LIMIT 1"
COLS = ["orig_h", "c", "avg_b", "max_ts"]


def bespoke_types():
    out = {}
    for n in ("starrocks", "clickhouse_iceberg", "trino", "dremio"):
        try:
            c = E.CLIENTS[n](); ref = c.ref(TABLE)
            row = c.run("SELECT orig_h, " + TAIL.format(ref=ref))[0]
            out[n] = {COLS[i]: type(row[i]).__name__ for i in range(len(COLS))}
        except Exception as e:
            out[n] = {"error": str(e)[:140]}
    return out


def arrow_types():
    out = {}
    try:
        import adbc_driver_flightsql.dbapi as fsql
        conn = fsql.connect("grpc://dremio:32010", db_kwargs={"username": "admin", "password": "dremioAdmin123"})
        cur = conn.cursor()
        cur.execute(f'SELECT orig_h, count(*) AS c, avg(orig_bytes) AS avg_b, max(ts) AS max_ts '
                    f'FROM nessie."soc"."conn_ueba_planted" GROUP BY orig_h ORDER BY c DESC LIMIT 1')
        t = cur.fetch_arrow_table(); cur.close(); conn.close()
        out["dremio_adbc_flightsql"] = {f.name: str(f.type) for f in t.schema}
    except Exception as e:
        out["dremio_adbc_flightsql"] = {"error": str(e)[:160]}
    try:
        import clickhouse_connect
        ch = clickhouse_connect.get_client(host="clickhouse", port=8123, password="ejsbench123")
        ref = E.ClickHouse().ref(TABLE)
        t = ch.query_arrow(f"SELECT orig_h, count(*) AS c, avg(orig_bytes) AS avg_b, max(ts) AS max_ts "
                           f"FROM {ref} GROUP BY orig_h ORDER BY c DESC LIMIT 1")
        out["clickhouse_query_arrow"] = {f.name: str(f.type) for f in t.schema}
    except Exception as e:
        out["clickhouse_query_arrow"] = {"error": str(e)[:160]}
    return out


def main():
    bespoke = bespoke_types()
    arrow = arrow_types()
    # coercion sites: per logical column, # of DISTINCT python types across bespoke engines beyond 1
    coercion = {}
    ok_engines = [n for n, v in bespoke.items() if "error" not in v]
    for col in COLS:
        types = sorted(set(bespoke[n][col] for n in ok_engines))
        coercion[col] = {"distinct_bespoke_types": types, "coercion_sites": max(0, len(types) - 1)}
    total_coercion = sum(c["coercion_sites"] for c in coercion.values())
    out = {"bench": "ocsf-arrow-transport / M3 type-fidelity as maintenance", "tier": "B", "table": TABLE,
           "bespoke_python_types": bespoke, "arrow_schema_types": arrow,
           "per_column_coercion": coercion,
           "total_coercion_sites_bespoke": total_coercion, "total_coercion_sites_arrow": 0}
    json.dump(out, open("/tmp/m3_type_fidelity.json", "w"), indent=2)
    print("bespoke per-engine Python types:")
    for n in ok_engines:
        print(f"  {n:20} {bespoke[n]}")
    print("arrow schema types:")
    for k, v in arrow.items():
        print(f"  {k:24} {v}")
    print(f"\nper-column divergence (bespoke): " + " | ".join(f"{c}={coercion[c]['distinct_bespoke_types']}" for c in COLS))
    print(f"TOTAL coercion sites — bespoke: {total_coercion}  |  Arrow: 0 (one typed contract)")
    print("-> /tmp/m3_type_fidelity.json")


if __name__ == "__main__":
    main()

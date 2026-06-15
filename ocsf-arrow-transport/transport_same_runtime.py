# Arrow M4 — same-runtime transport isolation (closes M1's cross-runtime confound).
# Pull K rows from Dremio via (a) ADBC Flight SQL -> Arrow and (b) REST -> rows, BOTH in Python,
# isolating the runtime so the gap is the transport (columnar Arrow batches vs paginated JSON rows).
import time, json
import ejs_clients as E
K = 100000
def pull_adbc():
    import adbc_driver_flightsql.dbapi as fsql
    conn = fsql.connect("grpc://dremio:32010", db_kwargs={"username":"admin","password":"dremioAdmin123"})
    cur = conn.cursor(); t0=time.perf_counter()
    cur.execute(f'SELECT orig_h, ts, orig_bytes FROM nessie."soc"."conn_ueba_planted" LIMIT {K}')
    t = cur.fetch_arrow_table(); dt=time.perf_counter()-t0; n=t.num_rows; cur.close(); conn.close()
    return n, dt
def pull_rest():
    c = E.Dremio(); t0=time.perf_counter()
    rows = c.run(f'SELECT orig_h, ts, orig_bytes FROM nessie."soc"."conn_ueba_planted" LIMIT {K}')
    return len(rows), time.perf_counter()-t0
out={"bench":"arrow M4 same-runtime transport (Dremio, Python)","tier":"B","rows":K,"trials":3,"arms":{}}
for name,fn in (("adbc_flightsql_arrow",pull_adbc),("rest_json_rows",pull_rest)):
    ds=[]; n=0
    for _ in range(3):
        n,dt=fn(); ds.append(dt)
    ds.sort(); med=ds[1]
    out["arms"][name]={"rows":n,"median_s":round(med,2),"rows_per_s":int(n/med)}
    print(f"  {name:22} {n} rows in {med:.2f}s -> {int(n/med):,} rows/s", flush=True)
a=out["arms"]["adbc_flightsql_arrow"]["median_s"]; r=out["arms"]["rest_json_rows"]["median_s"]
out["arrow_speedup_same_runtime_x"]=round(r/a,1)
print(f"\nsame-runtime (both Python): ADBC-Arrow {out['arrow_speedup_same_runtime_x']}x faster than REST-rows for a {K}-row pull")
json.dump(out, open("/tmp/transport_same_runtime.json","w"), indent=2)

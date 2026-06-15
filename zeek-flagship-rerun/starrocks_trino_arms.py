#!/usr/bin/env python3
"""Flagship engine-chart extension: StarRocks + Trino on the SAME conn_10m corpus + the SAME
5-query suite as the flagship, so the engine-two-regime chart can carry >4 arms.

Baseline = the published OpenSearch foil avg-of-5-medians = 2.854 s (zeek-flagship RESULTS). This
loads conn_10m into the ejs Nessie catalog (iceberg.flagship.conn_10m), then runs the 5 flagship
queries on StarRocks 4.1 (iceberg ext-catalog) and Trino (iceberg connector) — 1 warmup + 7 trials,
median per query, avg-of-medians, multiple vs the foil. Tier B, single host, ejs stack. Run from the
ejs-bench-lab image on the ejs network.
"""
import json, time, sys
from pathlib import Path
import pymysql
import requests
import pyarrow.parquet as pq
from pyiceberg.catalog.rest import RestCatalog

FOIL_AVG_S = 2.854
NESSIE = "http://nessie:19120/iceberg/"
S3 = {"s3.endpoint": "http://minio:9000", "s3.access-key-id": "ejsbench",
      "s3.secret-access-key": "ejsbench123", "s3.path-style-access": "true"}
SR_CATALOG_SQL = """CREATE EXTERNAL CATALOG IF NOT EXISTS iceberg PROPERTIES (
 'type'='iceberg','iceberg.catalog.type'='rest','iceberg.catalog.uri'='http://nessie:19120/iceberg/',
 'iceberg.catalog.warehouse'='warehouse','aws.s3.endpoint'='http://minio:9000',
 'aws.s3.enable_path_style_access'='true','aws.s3.enable_ssl'='false',
 'aws.s3.access_key'='ejsbench','aws.s3.secret_key'='ejsbench123','aws.s3.region'='us-east-1')"""
PARQUET = "/repo/zeek-flagship-rerun/_work/zeek_conn_10m.parquet"
OUT = Path(__file__).parent / "results"


def queries(t):
    return {
        "count_all": f"SELECT COUNT(*) AS cnt FROM {t}",
        "top_source_ips_by_bytes": ("SELECT orig_h, SUM(COALESCE(orig_bytes,0)+COALESCE(resp_bytes,0)) "
            f"AS total_bytes FROM {t} GROUP BY orig_h ORDER BY total_bytes DESC LIMIT 10"),
        "protocol_distribution": f"SELECT proto, COUNT(*) AS cnt FROM {t} GROUP BY proto ORDER BY cnt DESC",
        "long_duration_connections": ("SELECT orig_h, resp_h, duration, orig_bytes, resp_bytes "
            f"FROM {t} WHERE duration > 60 ORDER BY duration DESC LIMIT 10"),
        "port_scan_detection": ("SELECT orig_h, COUNT(DISTINCT resp_p) AS unique_ports, "
            f"COUNT(DISTINCT resp_h) AS unique_hosts FROM {t} WHERE proto='tcp' GROUP BY orig_h "
            "HAVING COUNT(DISTINCT resp_p) > 10 ORDER BY unique_ports DESC LIMIT 10"),
    }


def median(xs):
    xs = sorted(xs); n = len(xs); return xs[n//2] if n % 2 else (xs[n//2-1]+xs[n//2])/2


def load_corpus():
    # mirror load_arms.py: flatten the nested Zeek id.* names to the flat columns the
    # flagship 5-query suite uses (id.orig_h -> orig_h, etc.)
    RENAME = {"id.orig_h": "orig_h", "id.orig_p": "orig_p", "id.resp_h": "resp_h", "id.resp_p": "resp_p"}
    cat = RestCatalog("nessie", uri=NESSIE, warehouse="warehouse", **S3)
    cat.create_namespace_if_not_exists("flagship")
    tbl_arrow = pq.read_table(PARQUET)
    if "orig_h" not in tbl_arrow.column_names:
        tbl_arrow = tbl_arrow.rename_columns([RENAME.get(c, c) for c in tbl_arrow.column_names])
    # always (re)create with the flattened schema — a prior run may have loaded the dotted names
    try:
        t = cat.load_table("flagship.conn_10m")
        if "orig_h" in [f.name for f in t.schema().as_arrow()]:
            print("flagship.conn_10m already loaded (flat schema)"); return
        cat.drop_table("flagship.conn_10m"); print("dropped wrong-schema flagship.conn_10m")
    except Exception:
        pass
    t = cat.create_table("flagship.conn_10m", schema=tbl_arrow.schema)
    t.append(tbl_arrow)
    print(f"loaded flagship.conn_10m ({tbl_arrow.num_rows} rows, flat columns)")


def run_starrocks():
    con = pymysql.connect(host="starrocks", port=9030, user="root", connect_timeout=20, read_timeout=600)
    cur = con.cursor(); cur.execute(SR_CATALOG_SQL)
    cur.execute("SET enable_materialized_view_rewrite=false")
    qs = queries("iceberg.flagship.conn_10m"); res = {}
    for name, sql in qs.items():
        cur.execute(sql); cur.fetchall()  # warmup
        xs = []
        for _ in range(7):
            t0 = time.perf_counter(); cur.execute(sql); cur.fetchall(); xs.append(time.perf_counter()-t0)
        res[name] = round(median(xs), 4)
    return res


def trino_sql(sql, cat):
    r = requests.post("http://trino:8080/v1/statement", data=sql.encode(),
                      headers={"X-Trino-User": "bench"}, timeout=300); r.raise_for_status()
    doc = r.json();
    while True:
        if doc.get("error"): raise RuntimeError(doc["error"].get("message"))
        nxt = doc.get("nextUri")
        if not nxt: return
        doc = requests.get(nxt, timeout=300).json()


def run_trino():
    # discover the iceberg catalog name
    cats = []
    r = requests.post("http://trino:8080/v1/statement", data=b"SHOW CATALOGS",
                      headers={"X-Trino-User": "bench"}, timeout=60); r.raise_for_status(); doc = r.json()
    while True:
        cats += [row[0] for row in doc.get("data", []) or []]
        nxt = doc.get("nextUri")
        if not nxt: break
        doc = requests.get(nxt, timeout=60).json()
    iceberg_cat = next((c for c in cats if "iceberg" in c.lower() or "nessie" in c.lower()), None)
    if not iceberg_cat:
        raise RuntimeError(f"no iceberg catalog in Trino: {cats}")
    t = f"{iceberg_cat}.flagship.conn_10m"
    qs = queries(t); res = {}
    for name, sql in qs.items():
        trino_sql(sql, iceberg_cat)  # warmup
        xs = []
        for _ in range(7):
            t0 = time.perf_counter(); trino_sql(sql, iceberg_cat); xs.append(time.perf_counter()-t0)
        res[name] = round(median(xs), 4)
    return {"catalog": iceberg_cat, "per_query": res}


def main():
    load_corpus()
    out = {"foil_avg_s": FOIL_AVG_S, "corpus": "flagship conn_10m", "tier": "B", "host": "ejs single host"}
    sr = run_starrocks()
    sr_avg = sum(sr.values())/len(sr)
    out["starrocks"] = {"per_query": sr, "avg_of_medians_s": round(sr_avg,4), "x_vs_foil": round(FOIL_AVG_S/sr_avg,1)}
    print(f"StarRocks avg={sr_avg:.4f}s = {FOIL_AVG_S/sr_avg:.1f}x foil", flush=True)
    try:
        tr = run_trino(); tr_avg = sum(tr["per_query"].values())/len(tr["per_query"])
        out["trino"] = {**tr, "avg_of_medians_s": round(tr_avg,4), "x_vs_foil": round(FOIL_AVG_S/tr_avg,1)}
        print(f"Trino avg={tr_avg:.4f}s = {FOIL_AVG_S/tr_avg:.1f}x foil", flush=True)
    except Exception as e:
        out["trino"] = {"error": str(e)[:200]}; print(f"Trino FAIL: {str(e)[:200]}", flush=True)
    OUT.mkdir(exist_ok=True)
    (OUT / "starrocks_trino_arms.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""#25 StarRocks async-MV freshness/acceleration on a LIVE Iceberg table (the achievable half;
the Dremio arm is blocked — see DREMIO-ARM-FINDING-2026-06-15.md).

Single-engine characterization (the Dremio-vs-StarRocks matched-freshness comparison can't run on
the open Nessie/Iceberg path). Measures the two things an async MV trades on a moving table:
  - ACCELERATION: MV-query latency vs the same aggregate on the base Iceberg table (warm, median).
  - STALENESS: after appending a batch to the base table, how far the MV lags (rows behind) and for
    how long, until the next REFRESH ASYNC EVERY (INTERVAL) cycle catches up.

Protocol (Tier B, single host, ejs StarRocks 4.1, iceberg external catalog over Nessie/MinIO):
  1. Build one async MV (per-resp_p scan-aggregate) with REFRESH ASYNC EVERY (INTERVAL 15 SECOND).
  2. Force one sync refresh; baseline: base count, MV-underlying count (equal), MV vs base latency.
  3. Append a batch (~300k rows) to iceberg.soc.conn (advances the table -> new snapshot).
  4. Poll every ~5 s: base count (live) vs MV-derived count (stale), and the lag, until the MV
     auto-refresh catches up (lag returns to 0) — record the catch-up time.
Run from the ejs-bench-lab image on the ejs network. pymysql -> starrocks:9030; pyiceberg -> Nessie.
"""
import json
import time
import sys
from pathlib import Path

import pymysql
import pyarrow.parquet as pq
from pyiceberg.catalog.rest import RestCatalog

SR = dict(host="starrocks", port=9030, user="root", connect_timeout=20, read_timeout=600)
NESSIE = "http://nessie:19120/iceberg/"
S3 = {"s3.endpoint": "http://minio:9000", "s3.access-key-id": "ejsbench",
      "s3.secret-access-key": "ejsbench123", "s3.path-style-access": "true"}
CATALOG_SQL = """CREATE EXTERNAL CATALOG IF NOT EXISTS iceberg PROPERTIES (
 'type'='iceberg','iceberg.catalog.type'='rest','iceberg.catalog.uri'='http://nessie:19120/iceberg/',
 'iceberg.catalog.warehouse'='warehouse','aws.s3.endpoint'='http://minio:9000',
 'aws.s3.enable_path_style_access'='true','aws.s3.enable_ssl'='false',
 'aws.s3.access_key'='ejsbench','aws.s3.secret_key'='ejsbench123','aws.s3.region'='us-east-1')"""
REFRESH_INTERVAL_S = 60   # StarRocks enforces a 60s minimum (materialized_view_min_refresh_interval)
APPEND_ROWS = 300_000
OUT = Path(__file__).parent / "results"


def q(cur, sql):
    cur.execute(sql)
    return cur.fetchall()


def median_latency(cur, sql, n=7):
    cur.execute(sql); cur.fetchall()  # warm
    xs = []
    for _ in range(n):
        t = time.perf_counter(); cur.execute(sql); cur.fetchall()
        xs.append(time.perf_counter() - t)
    xs.sort(); return xs[len(xs)//2]


def main():
    con = pymysql.connect(**SR); cur = con.cursor()
    cur.execute(CATALOG_SQL)
    cur.execute("CREATE DATABASE IF NOT EXISTS wi_mv"); cur.execute("USE wi_mv")
    base = "iceberg.soc.conn"
    base_agg = f"SELECT resp_p, count(*) c FROM {base} GROUP BY resp_p"
    cur.execute('DROP MATERIALIZED VIEW IF EXISTS mv_live')
    cur.execute(f"""CREATE MATERIALIZED VIEW mv_live DISTRIBUTED BY HASH(resp_p)
                    REFRESH ASYNC EVERY (INTERVAL {REFRESH_INTERVAL_S} SECOND)
                    AS SELECT resp_p AS resp_p, count(*) AS c FROM {base} GROUP BY resp_p""")
    cur.execute("REFRESH MATERIALIZED VIEW mv_live WITH SYNC MODE")
    print("MV mv_live created + sync-refreshed", flush=True)

    base_count0 = q(cur, f"SELECT count(*) FROM {base}")[0][0]
    mv_count0 = q(cur, "SELECT sum(c) FROM mv_live")[0][0]
    mv_lat = median_latency(cur, "SELECT resp_p, c FROM mv_live ORDER BY c DESC LIMIT 10")
    base_lat = median_latency(cur, f"{base_agg} ORDER BY c DESC LIMIT 10")
    accel = base_lat / mv_lat if mv_lat else None
    print(f"baseline: base_count={base_count0} mv_count={mv_count0} "
          f"mv_lat={mv_lat*1000:.1f}ms base_lat={base_lat*1000:.1f}ms accel={accel:.1f}x", flush=True)

    # append a batch to the base Iceberg table (advance it)
    cat = RestCatalog("nessie", uri=NESSIE, warehouse="warehouse", **S3)
    tbl = cat.load_table("soc.conn")
    src = pq.read_table("/repo/workload-interference/_work/soc/conn.parquet")
    batch = src.slice(0, APPEND_ROWS).cast(tbl.schema().as_arrow())
    t_append = time.time()
    tbl.append(batch)
    print(f"appended {APPEND_ROWS} rows at t=0 (table advanced)", flush=True)

    # poll staleness until the MV auto-refresh catches up
    samples = []
    deadline = time.time() + 5 * REFRESH_INTERVAL_S + 60
    caught_up_s = None
    while time.time() < deadline:
        dt = round(time.time() - t_append, 1)
        live = q(cur, f"SELECT count(*) FROM {base}")[0][0]
        mvc = q(cur, "SELECT sum(c) FROM mv_live")[0][0]
        lag = int(live) - int(mvc)
        samples.append({"t_s": dt, "live_count": int(live), "mv_count": int(mvc), "lag_rows": lag})
        print(f"  t={dt}s live={live} mv={mvc} lag={lag}", flush=True)
        if lag == 0 and dt > 1:
            caught_up_s = dt
            break
        time.sleep(5)

    result = {
        "bench": "#25 mv-rewrite-freshness — StarRocks async-MV half (Dremio arm blocked)",
        "tier": "B", "host": "ejs StarRocks 4.1, single host, iceberg ext-catalog over Nessie/MinIO",
        "refresh_interval_s": REFRESH_INTERVAL_S, "append_rows": APPEND_ROWS,
        "acceleration": {"mv_latency_ms": round(mv_lat*1000, 1), "base_latency_ms": round(base_lat*1000, 1),
                         "accel_x": round(accel, 1) if accel else None},
        "staleness": {"caught_up_after_s": caught_up_s, "max_lag_rows": max((s["lag_rows"] for s in samples), default=0),
                      "samples": samples},
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "starrocks_freshness.json").write_text(json.dumps(result, indent=2))
    print("\n" + json.dumps(result["acceleration"], indent=2))
    print(f"caught_up_after_s={caught_up_s} (refresh interval {REFRESH_INTERVAL_S}s)")
    print(f"-> results/starrocks_freshness.json")


if __name__ == "__main__":
    main()

"""The OCSF analytical workload, run identically on DuckDB and ClickHouse (chDB).

Five queries a SOC actually runs against event data, from a full-scan rollup to a
selective time-window lookup. Each is expressed in standard SQL with one honest
exception noted below, run against both engines over (a) the same Parquet file in
place and (b) each engine's native store, and the *answers* are asserted equal
before any timing is reported. Equal answers are the deterministic guarantee here;
the latencies are not — they are wall-clock medians on one machine.

On "interchangeable": four of the five queries are byte-identical text across both
engines. Only the time-bucket rollup differs, and only by one token — DuckDB's
integer-division `//` versus ClickHouse's `intDiv(...)`. That single dialect edge
is itself a small, true finding about how interchangeable the SQL really is.
"""

import csv
import io
import os
import sys

from chdb import session as chs

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from common import BASE_EPOCH, configure_duckdb, time_trials  # noqa: E402
import corpus  # noqa: E402

BASE_MS = BASE_EPOCH * 1000
# Q3 selective window: the middle six hours of the UTC day.
T0 = BASE_MS + 9 * 3600 * 1000
T1 = BASE_MS + 15 * 3600 * 1000
FAIL_THRESHOLD = 20  # Q5 HAVING bound

# Each query carries a DuckDB and a ClickHouse template with a {src} hole. They are
# identical strings except where a dialect genuinely differs (Q4).
QUERIES = [
    {
        "id": "q1_scan_rollup",
        "title": "Full-scan rollup: count + bytes by class and activity",
        "note": "wide sequential scan, tiny grouping — favours vectorised scans",
        "duckdb": "SELECT class_uid, activity_id, count(*) n, sum(bytes_in) bin, sum(bytes_out) bout "
                  "FROM {src} GROUP BY class_uid, activity_id ORDER BY class_uid, activity_id",
        "clickhouse": "SELECT class_uid, activity_id, count(*) n, sum(bytes_in) bin, sum(bytes_out) bout "
                      "FROM {src} GROUP BY class_uid, activity_id ORDER BY class_uid, activity_id",
    },
    {
        "id": "q2_top_talkers",
        "title": "Top-20 talkers: high-cardinality group-by + order/limit",
        "note": "millions of groups collapsed to 20 — hash-aggregation pressure",
        "duckdb": "SELECT src_ip, count(*) n, sum(bytes_out) bout "
                  "FROM {src} GROUP BY src_ip ORDER BY n DESC, src_ip ASC LIMIT 20",
        "clickhouse": "SELECT src_ip, count(*) n, sum(bytes_out) bout "
                      "FROM {src} GROUP BY src_ip ORDER BY n DESC, src_ip ASC LIMIT 20",
    },
    {
        "id": "q3_selective_window",
        "title": "Selective lookup: one user inside a six-hour window",
        "note": "selective time predicate — favours a time-ordered native store",
        "duckdb": "SELECT count(*) n, sum(bytes_in) bin, max(time) mx "
                  "FROM {src} WHERE user_name = 'user42' AND time BETWEEN %d AND %d" % (T0, T1),
        "clickhouse": "SELECT count(*) n, sum(bytes_in) bin, max(time) mx "
                      "FROM {src} WHERE user_name = 'user42' AND time BETWEEN %d AND %d" % (T0, T1),
    },
    {
        "id": "q4_time_buckets",
        "title": "Time-bucketed rate: events per 5-minute bucket",
        "note": "the one dialect difference — `//` vs `intDiv(...)`",
        "duckdb": "SELECT (time - %d) // 300000 AS bucket, count(*) n, sum(bytes_out) bout "
                  "FROM {src} GROUP BY bucket ORDER BY bucket" % BASE_MS,
        "clickhouse": "SELECT intDiv(time - %d, 300000) AS bucket, count(*) n, sum(bytes_out) bout "
                      "FROM {src} GROUP BY bucket ORDER BY bucket" % BASE_MS,
    },
    {
        "id": "q5_failed_auth_burst",
        "title": "Failed-auth burst: filter + group + having",
        "note": "predicate then grouped threshold — classic detection shape",
        "duckdb": "SELECT user_name, count(*) fails FROM {src} "
                  "WHERE status_id = 2 AND class_uid = 3002 GROUP BY user_name "
                  "HAVING count(*) >= %d ORDER BY fails DESC, user_name ASC LIMIT 50" % FAIL_THRESHOLD,
        "clickhouse": "SELECT user_name, count(*) fails FROM {src} "
                      "WHERE status_id = 2 AND class_uid = 3002 GROUP BY user_name "
                      "HAVING count(*) >= %d ORDER BY fails DESC, user_name ASC LIMIT 50" % FAIL_THRESHOLD,
    },
]

# ClickHouse column types matching the Parquet the generator writes.
CH_SCHEMA = (
    "row_id Int64, time Int64, activity_id Int32, class_uid Int32, severity_id Int32, "
    "src_ip String, dst_ip String, dst_port Int32, user_name String, "
    "bytes_in Int64, bytes_out Int64, status_id Int32"
)


def _norm_duck(rows):
    return [tuple(str(c) for c in r) for r in rows]


def _norm_csv(text):
    return [tuple(r) for r in csv.reader(io.StringIO(text)) if r]


def _duck_rows(con, sql):
    return _norm_duck(con.execute(sql).fetchall())


def _sess_rows(sess, sql):
    return _norm_csv(str(sess.query(sql, "CSV")))


def run_scale(n, parquet_path, warmup=2, trials=7, ingest_trials=3):
    """Generate the corpus, then for each config and engine: assert answer
    equality and time every query. Returns a results dict for one scale.

    Both engines run warm: a persistent DuckDB connection and a persistent chDB
    session, created once and reused across both configs. That is deliberate — the
    only difference between Config A and Config B is then the storage (the same
    Parquet file in place vs each engine's native store), not a cold-vs-warm
    engine. chDB's stateless `chdb.query()` re-inits the engine on every call (a
    ~40 ms floor that warmup cannot amortise), which would make Config A a startup
    benchmark rather than a query benchmark; the session removes that artifact."""
    import duckdb

    con = configure_duckdb(duckdb.connect())
    corpus.write_parquet(con, n, parquet_path)
    file_bytes = os.path.getsize(parquet_path)

    sess = chs.Session()
    sess.query("CREATE DATABASE IF NOT EXISTS b")

    scale = {"n_events": n, "parquet_bytes": file_bytes, "configs": {}}

    # ---- Config A: both engines query the same Parquet file in place (warm) ----
    cfgA = {"queries": []}
    duck_src = f"read_parquet('{parquet_path}')"
    file_src = f"file('{parquet_path}', Parquet)"
    for q in QUERIES:
        d_sql = q["duckdb"].format(src=duck_src)
        c_sql = q["clickhouse"].format(src=file_src)
        duck_ans = _duck_rows(con, d_sql)
        chdb_ans = _sess_rows(sess, c_sql)
        agree = duck_ans == chdb_ans
        d_t = time_trials(lambda s=d_sql: con.execute(s).fetchall(), warmup, trials)
        c_t = time_trials(lambda s=c_sql: sess.query(s, "CSV"), warmup, trials)
        cfgA["queries"].append(_q_record(q, agree, len(duck_ans), d_t, c_t))
    scale["configs"]["parquet_in_place"] = cfgA

    # ---- Config B: ingest into each engine's native store, then query (warm) ----
    cfgB = {"queries": []}
    duck_ingest = time_trials(
        lambda: con.execute(f"CREATE OR REPLACE TABLE events AS SELECT * FROM read_parquet('{parquet_path}')"),
        warmup=1, trials=ingest_trials,
    )
    sess.query(f"CREATE TABLE IF NOT EXISTS b.events ({CH_SCHEMA}) ENGINE = MergeTree ORDER BY time")

    def _ch_load():
        sess.query("TRUNCATE TABLE b.events")
        sess.query(f"INSERT INTO b.events SELECT * FROM file('{parquet_path}', Parquet)")

    chdb_ingest = time_trials(_ch_load, warmup=1, trials=ingest_trials)

    for q in QUERIES:
        d_sql = q["duckdb"].format(src="events")
        c_sql = q["clickhouse"].format(src="b.events")
        duck_ans = _duck_rows(con, d_sql)
        chdb_ans = _sess_rows(sess, c_sql)
        agree = duck_ans == chdb_ans
        d_t = time_trials(lambda s=d_sql: con.execute(s).fetchall(), warmup, trials)
        c_t = time_trials(lambda s=c_sql: sess.query(s, "CSV"), warmup, trials)
        cfgB["queries"].append(_q_record(q, agree, len(duck_ans), d_t, c_t))
    cfgB["ingest"] = {
        "duckdb_native_load": duck_ingest,
        "clickhouse_mergetree_load": chdb_ingest,
    }
    scale["configs"]["native_store"] = cfgB

    sess.close()
    con.close()
    return scale


def _q_record(q, agree, n_rows, d_t, c_t):
    dm, cm = d_t["median_ms"], c_t["median_ms"]
    if dm > 0 and cm > 0:
        faster = "duckdb" if dm < cm else ("clickhouse" if cm < dm else "tie")
        ratio = round(max(dm, cm) / min(dm, cm), 2)
    else:
        faster, ratio = "tie", 1.0
    return {
        "id": q["id"],
        "title": q["title"],
        "note": q["note"],
        "answers_agree": agree,
        "result_rows": n_rows,
        "duckdb": d_t,
        "clickhouse": c_t,
        "faster_engine": faster,
        "speed_ratio": ratio,
    }

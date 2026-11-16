#!/usr/bin/env python3
"""ADDENDUM B: generate Z2 only (Zipf with genuinely independent keys). Copy of gen_corpus.py; the Z generator used
hash(i, '<col>'), which DuckDB combines so that hash(i,a) XOR hash(i,b) is a constant: every Z column is a function of
hash(i). Z2 hashes a distinct integer per column, hash(i*8 + k), so no input is shared across columns or rows.
Original docstring follows.
Generate the two pinned corpora for the 2026-11-15 run, once, uncapped, outside any timed path.
Runs inside the sdw-edge-floor:duckdb-1.5.3 image (DuckDB 1.5.3). Writes /work/corpus/{U,Z}.parquet and
/work/results/corpus_stats.json.

U = the June heavy_cliff.py generator, unchanged (ts and host both derive from hash(i), so they are correlated).
Z = Zipf (s = 1, continuous inverse-CDF approximation k = floor((n+1)^u) - 1) on host, usr and process, with
    ts, host, usr, process and bytes each drawn from a separate hash of the row id, so the keys are independent.
"""
import hashlib, json, os
import duckdb

N = 10_000_000
CORPUS = "/work/corpus"
U_SQL = f"""SELECT (1781000000 + (hash(i) % 604800))::BIGINT AS ts,
  'h' || ((hash(i) % 8000))::VARCHAR AS host,
  'u' || ((hash(i+11) % 20000))::VARCHAR AS usr,
  ('proc' || (hash(i+1) % 200))::VARCHAR AS process,
  (hash(i+7) % 100000)::BIGINT AS bytes
  FROM range({N}) t(i)"""


def zipf(k, n):
    u = f"((hash(i * 8 + {k}) % 9007199254740992)::DOUBLE / 9007199254740992.0)"
    return f"least(greatest(floor(pow({n + 1}, {u}))::BIGINT - 1, 0), {n - 1})"


Z_SQL = f"""SELECT (1781000000 + (hash(i * 8 + 0) % 604800))::BIGINT AS ts,
  'h' || {zipf(1, 8000)}::VARCHAR AS host,
  'u' || {zipf(2, 20000)}::VARCHAR AS usr,
  'proc' || {zipf(3, 200)}::VARCHAR AS process,
  (hash(i * 8 + 4) % 100000)::BIGINT AS bytes
  FROM range({N}) t(i)"""


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    con = duckdb.connect()
    con.execute("SET threads=1")  # single-threaded write so the file bytes are reproducible
    stats = {"duckdb": duckdb.__version__, "n_rows": N, "corpora": {}}
    for name, sql in (("Z2", Z_SQL),):
        path = f"{CORPUS}/{name}.parquet"
        con.execute(f"COPY ({sql}) TO '{path}' (FORMAT parquet, COMPRESSION zstd)")
        con.execute("SET threads=8")
        v = f"read_parquet('{path}')"
        q = lambda s: con.execute(s).fetchone()
        st = {"generator_sql": sql, "file_bytes": os.path.getsize(path), "file_sha256": sha256(path)}
        st["rows"], st["logical_xor"] = q(f"SELECT count(*), bit_xor(hash(ts, host, usr, process, bytes))::VARCHAR FROM {v}")
        st["distinct_hosts"], st["distinct_usr"], st["distinct_process"] = q(
            f"SELECT count(DISTINCT host), count(DISTINCT usr), count(DISTINCT process) FROM {v}")
        st["H_groups"] = q(f"SELECT count(*) FROM (SELECT 1 FROM {v} GROUP BY host, usr, process, ts // 60)")[0]
        st["S_host_hours"] = q(f"SELECT count(*) FROM (SELECT 1 FROM {v} GROUP BY host, ts // 3600)")[0]
        st["J_host_minutes"], st["J_pair_rows_upper"] = q(
            f"SELECT count(*), sum(c * (c - 1) // 2)::BIGINT FROM (SELECT count(*) c FROM {v} GROUP BY host, ts // 60)")
        st["top_host_share"], st["top10_host_share"] = q(
            f"""SELECT max(c)::DOUBLE / {N}, (SELECT sum(c) FROM (SELECT c FROM (SELECT count(*) c FROM {v} GROUP BY host)
            ORDER BY c DESC LIMIT 10))::DOUBLE / {N} FROM (SELECT count(*) c FROM {v} GROUP BY host)""")
        st["top_process_share"] = q(f"SELECT max(c)::DOUBLE / {N} FROM (SELECT count(*) c FROM {v} GROUP BY process)")[0]
        st["h0_distinct_process"], st["h0_distinct_usr"], st["h0_distinct_minutes"] = q(
            f"SELECT count(DISTINCT process), count(DISTINCT usr), count(DISTINCT ts // 60) FROM {v} WHERE host = 'h0'")
        st["distinct_host_process"] = q(f"SELECT count(DISTINCT (host, process)) FROM {v}")[0]
        st["corr_ts_hostnum"] = q(
            f"SELECT corr(ts::DOUBLE, substr(host, 2)::DOUBLE) FROM {v}")[0]
        stats["corpora"][name] = st
        con.execute("SET threads=1")
    json.dump(stats, open("/work/results/corpus_stats_z2.json", "w"), indent=1)
    print(json.dumps({k: {kk: vv for kk, vv in s.items() if kk != "generator_sql"} for k, s in stats["corpora"].items()}, indent=1))


if __name__ == "__main__":
    main()

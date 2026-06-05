"""Diagnostic: what Parquet config does each write path actually use?

The large-scan arm found Iceberg storage (13.3 GB) smaller than DuckLake (21.6 GB) at 1B rows, while
DuckLake read faster. Before crediting the read-latency gap to the *format*, confirm whether the two
write paths differ in Parquet COMPRESSION codec / row-group sizing — a codec difference (Snappy vs
ZSTD) would confound the comparison, because Snappy decompresses faster than ZSTD at the cost of a
larger file. This writes the same seeded corpus several ways and dumps each Parquet file's footer:
compression codec, row-group count, rows per row group, and on-disk bytes. No claims, just the config
each path actually emitted.

    python config_probe.py --rows 5000000
"""
import argparse
import glob
import os
import shutil
import sys
import tempfile

import duckdb
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import BASE_EPOCH, configure_duckdb  # noqa: E402

PORTS = "[80, 443, 22, 53, 3389, 445, 8080, 3306]"


def gen(con, n):
    return con.execute(f"""
        SELECT i AS id, {BASE_EPOCH*1000} + i AS time,
               '10.' || (hash(i::VARCHAR||'a')%256) || '.' || (hash(i::VARCHAR||'b')%256) || '.' || (hash(i::VARCHAR||'c')%256) AS src_ip,
               {PORTS}[(1 + hash(i::VARCHAR||'p')%8)::BIGINT]::INTEGER AS dst_port,
               (hash(i::VARCHAR||'bo')%5000000)::BIGINT AS bytes_out
        FROM range(0,{n}) t(i)""").fetch_arrow_table()


def footer(path):
    m = pq.ParquetFile(path).metadata
    rg0 = m.row_group(0)
    codecs = sorted({rg0.column(i).compression for i in range(rg0.num_columns)})
    rpg = [m.row_group(i).num_rows for i in range(m.num_row_groups)]
    return {"codec": "/".join(codecs), "row_groups": m.num_row_groups,
            "rows": m.num_rows, "rows_per_group_max": max(rpg) if rpg else 0,
            "file_bytes": os.path.getsize(path)}


def biggest_parquet(root):
    files = [os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in fs if f.endswith(".parquet")]
    return max(files, key=os.path.getsize) if files else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--rows", type=int, default=5_000_000)
    args = ap.parse_args()
    work = tempfile.mkdtemp(prefix="cfg_probe_")
    rows = {}
    try:
        con = configure_duckdb(duckdb.connect())
        con.execute("INSTALL iceberg; LOAD iceberg; INSTALL ducklake; LOAD ducklake")
        arrow = gen(con, args.rows)
        con.register("src", arrow)

        # 1) Iceberg via pyiceberg (the benchmark's Iceberg write path)
        from pyiceberg.catalog.sql import SqlCatalog
        wh = os.path.join(work, "ice"); os.makedirs(wh)
        cat = SqlCatalog("e", uri=f"sqlite:///{work}/ice.db", warehouse=f"file://{wh}")
        cat.create_namespace("b")
        t = cat.create_table("b.events", schema=arrow.schema); t.append(arrow)
        rows["iceberg (pyiceberg.append)"] = footer(biggest_parquet(wh))

        # 2) DuckLake via DuckDB (the benchmark's DuckLake write path)
        dpath = os.path.join(work, "dl"); os.makedirs(dpath)
        con.execute(f"ATTACH 'ducklake:{work}/dl.ducklake' AS dl (DATA_PATH '{dpath}')")
        con.execute("CREATE TABLE dl.events AS SELECT * FROM src")
        rows["ducklake (DuckDB default)"] = footer(biggest_parquet(dpath))

        # 3) plain DuckDB COPY — default, and a few explicit codecs, to show the knob exists
        for tag, opt in (("duckdb COPY default", "FORMAT parquet"),
                         ("duckdb COPY snappy", "FORMAT parquet, COMPRESSION snappy"),
                         ("duckdb COPY zstd", "FORMAT parquet, COMPRESSION zstd"),
                         ("duckdb COPY zstd lvl22", "FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 22")):
            p = os.path.join(work, f"{tag.replace(' ', '_')}.parquet")
            try:
                con.execute(f"COPY (SELECT * FROM src) TO '{p}' ({opt})")
                rows[tag] = footer(p)
            except Exception as e:
                rows[tag] = {"error": str(e)[:80]}

        # report
        cols = ["codec", "row_groups", "rows_per_group_max", "file_bytes"]
        w = max(len(k) for k in rows)
        print(f"\n{args.rows:,}-row sample — Parquet footer per write path\n")
        print(f"{'path'.ljust(w)}  {'codec':<14} {'row_grps':>8} {'rows/grp':>10} {'MB':>8}")
        for k, v in rows.items():
            if "error" in v:
                print(f"{k.ljust(w)}  ERROR {v['error']}"); continue
            print(f"{k.ljust(w)}  {v['codec']:<14} {v['row_groups']:>8} "
                  f"{v['rows_per_group_max']:>10,} {v['file_bytes']/1e6:>8.1f}")
    finally:
        con.close()
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()

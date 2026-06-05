"""Why do two 'same-codec' Parquet writers produce different sizes? Per-column diagnostic.

The parity arm held codec (zstd) and row-group (~123k rows) equal, yet Iceberg was 1.93 GB and DuckLake
1.14 GB at 1B. "Same codec name" is not "same compression": DuckDB's Parquet writer and PyArrow's (which
pyiceberg uses) pick different compression levels, dictionary-encoding, page sizes, and column encodings.
This writes ONE logical table several ways and dumps, per column, the compressed bytes and the encodings
each writer chose — so we can see exactly where the gap lives (dictionary? level? a specific column?) and
which knobs would converge them.

    python compression_probe.py --rows 10000000
"""
import argparse
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


def col_stats(path):
    m = pq.ParquetFile(path).metadata
    cols = {}
    for rg in range(m.num_row_groups):
        g = m.row_group(rg)
        for ci in range(g.num_columns):
            c = g.column(ci)
            d = cols.setdefault(c.path_in_schema, {"comp": 0, "uncomp": 0, "enc": set()})
            d["comp"] += c.total_compressed_size
            d["uncomp"] += c.total_uncompressed_size
            for e in (c.encodings or ()):
                d["enc"].add(str(e).split(".")[-1])
    return cols, os.path.getsize(path)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--rows", type=int, default=10_000_000)
    args = ap.parse_args()
    work = tempfile.mkdtemp(prefix="comp_probe_")
    con = configure_duckdb(duckdb.connect())
    con.execute(f"""CREATE TABLE mem AS
        SELECT i AS id, {BASE_EPOCH*1000} + i AS time,
               '10.' || (hash(i::VARCHAR||'a')%256) || '.' || (hash(i::VARCHAR||'b')%256) || '.' || (hash(i::VARCHAR||'c')%256) AS src_ip,
               {PORTS}[(1 + hash(i::VARCHAR||'p')%8)::BIGINT]::INTEGER AS dst_port,
               (hash(i::VARCHAR||'bo')%5000000)::BIGINT AS bytes_out
        FROM range(0,{args.rows}) t(i)""")
    at = con.execute("SELECT * FROM mem").fetch_arrow_table()

    paths = {}
    # DuckLake's writer (DuckDB), zstd level 3
    p = os.path.join(work, "duckdb_zstd3.parquet")
    con.execute(f"COPY mem TO '{p}' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 3, ROW_GROUP_SIZE 122880)")
    paths["duckdb_zstd3"] = p
    # PyArrow (pyiceberg's writer) — default dictionary behaviour, zstd level 3
    p = os.path.join(work, "pyarrow_zstd3.parquet")
    pq.write_table(at, p, compression="zstd", compression_level=3, row_group_size=122880)
    paths["pyarrow_zstd3"] = p
    # PyArrow with dictionary forced on every column + a DuckDB-like page size
    p = os.path.join(work, "pyarrow_zstd3_dict.parquet")
    pq.write_table(at, p, compression="zstd", compression_level=3, row_group_size=122880,
                   use_dictionary=True, data_page_size=1024 * 1024)
    paths["pyarrow_zstd3_dict"] = p
    # pyiceberg's actual append path
    try:
        from pyiceberg.catalog.sql import SqlCatalog
        wh = os.path.join(work, "ice"); os.makedirs(wh)
        cat = SqlCatalog("c", uri=f"sqlite:///{work}/ice.db", warehouse=f"file://{wh}")
        cat.create_namespace("b")
        t = cat.create_table("b.e", schema=at.schema, properties={
            "write.parquet.compression-codec": "zstd", "write.parquet.compression-level": "3",
            "write.parquet.row-group-limit": "122880"})
        t.append(at)
        files = [os.path.join(dp, f) for dp, _, fs in os.walk(wh) for f in fs if f.endswith(".parquet")]
        paths["pyiceberg_zstd3"] = max(files, key=os.path.getsize)
    except Exception as e:
        print("pyiceberg arm failed:", str(e)[:100])

    stats = {k: col_stats(v) for k, v in paths.items()}
    con.close(); shutil.rmtree(work, ignore_errors=True)

    cols = list(next(iter(stats.values()))[0].keys())
    print(f"\n{args.rows:,} rows — compressed MB per column (and encodings), by writer\n")
    hdr = "column".ljust(10) + "".join(k.rjust(20) for k in stats)
    print(hdr)
    for col in cols:
        line = col.ljust(10) + "".join(f"{stats[k][0][col]['comp']/1e6:>8.1f} MB".rjust(20) for k in stats)
        print(line)
    print("\ntotal MB:".ljust(10) + "".join(f"{stats[k][1]/1e6:>8.1f} MB".rjust(20) for k in stats))
    print("\nencodings per column:")
    for col in cols:
        print(f"  {col:10}: " + " | ".join(f"{k}={'+'.join(sorted(stats[k][0][col]['enc']))}" for k in stats))


if __name__ == "__main__":
    main()

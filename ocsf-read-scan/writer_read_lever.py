"""T2.6 — the Parquet writer as a READ lever: size AND read latency across writers on identical data.

compression_probe.py already showed the three writers (DuckDB, PyArrow/pyiceberg) pick different
encodings and so produce different FILE SIZES on identical data ("same codec ≠ same compression"). The
open half is whether that encoding choice also moves READ latency — the "encoder is the read lever" claim.
This writes one logical OCSF table several ways at a matched codec+level+row-group, then reads each
writer's output with the SAME engine (DuckDB `read_parquet`) and reports size next to read latency for a
filter, a high-cardinality group-by, and a full-scan aggregate. The variable is the writer's encoding
alone; the reader and the logical data are held constant.

    python writer_read_lever.py --rows 20000000
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

import duckdb
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import BASE_EPOCH, configure_duckdb  # noqa: E402
from same_files_scan import timed  # noqa: E402

PORTS = "[80, 443, 22, 53, 3389, 445, 8080, 3306]"
RG = 122_880
QUERIES = {
    "filter_count":  "SELECT count(*) FROM {t} WHERE dst_port = 443",
    "topn_src":      "SELECT src_ip, count(*) c FROM {t} GROUP BY 1 ORDER BY c DESC, src_ip LIMIT 20",
    "scan_sum":      "SELECT sum(bytes_out) FROM {t}",
}


def _encodings(path):
    m = pq.ParquetFile(path).metadata
    enc = {}
    g = m.row_group(0)
    for ci in range(g.num_columns):
        c = g.column(ci)
        enc[c.path_in_schema] = "+".join(sorted({str(e).split(".")[-1] for e in (c.encodings or ())}))
    return enc


def run(rows, warmup, trials):
    work = tempfile.mkdtemp(prefix="read_lever_")
    try:
        con = configure_duckdb(duckdb.connect())
        con.execute(f"""CREATE TABLE mem AS
            SELECT i AS id, {BASE_EPOCH*1000} + i AS time,
                   '10.' || (hash(i::VARCHAR||'a')%256) || '.' || (hash(i::VARCHAR||'b')%256) || '.' || (hash(i::VARCHAR||'c')%256) AS src_ip,
                   {PORTS}[(1 + hash(i::VARCHAR||'p')%8)::BIGINT]::INTEGER AS dst_port,
                   (hash(i::VARCHAR||'bo')%5000000)::BIGINT AS bytes_out
            FROM range(0,{rows}) t(i)""")
        at = con.execute("SELECT * FROM mem").fetch_arrow_table()

        writers = {}
        p = os.path.join(work, "duckdb.parquet")
        con.execute(f"COPY mem TO '{p}' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 3, ROW_GROUP_SIZE {RG})")
        writers["duckdb"] = p
        p = os.path.join(work, "pyarrow_default.parquet")
        pq.write_table(at, p, compression="zstd", compression_level=3, row_group_size=RG)
        writers["pyarrow_default"] = p
        p = os.path.join(work, "pyarrow_dict.parquet")
        pq.write_table(at, p, compression="zstd", compression_level=3, row_group_size=RG,
                       use_dictionary=True, data_page_size=1024 * 1024)
        writers["pyarrow_dict"] = p
        try:
            from pyiceberg.catalog.sql import SqlCatalog
            wh = os.path.join(work, "ice"); os.makedirs(wh)
            cat = SqlCatalog("c", uri=f"sqlite:///{work}/ice.db", warehouse=f"file://{wh}")
            cat.create_namespace("b")
            t = cat.create_table("b.e", schema=at.schema, properties={
                "write.parquet.compression-codec": "zstd", "write.parquet.compression-level": "3",
                "write.parquet.row-group-limit": str(RG)})
            t.append(at)
            files = [os.path.join(dp, f) for dp, _, fs in os.walk(wh) for f in fs if f.endswith(".parquet")]
            writers["pyiceberg"] = max(files, key=os.path.getsize)
        except Exception as e:  # noqa: BLE001
            print("pyiceberg arm failed:", str(e)[:100])

        out = {}
        for w, path in writers.items():
            reader = lambda q, pp=path: q.format(t=f"read_parquet('{pp}')")
            qres = {qid: timed(con, reader(sql), warmup, trials) for qid, sql in QUERIES.items()}
            out[w] = {"file_mb": round(os.path.getsize(path) / 1e6, 1),
                      "src_ip_encoding": _encodings(path).get("src_ip", "?"),
                      "queries": {qid: qres[qid]["median_ms"] for qid in QUERIES},
                      "cv": {qid: qres[qid]["cv_pct"] for qid in QUERIES}}
            print(f"  {w:16} {out[w]['file_mb']:>7.1f} MB  src_ip={out[w]['src_ip_encoding']:14}  " +
                  "  ".join(f"{qid}={out[w]['queries'][qid]:.0f}ms" for qid in QUERIES), flush=True)
        con.close()

        base = "duckdb"
        rel = {w: {"size_x_vs_duckdb": round(out[w]["file_mb"] / out[base]["file_mb"], 2),
                   "read_x_vs_duckdb": {qid: round(out[w]["queries"][qid] / max(out[base]["queries"][qid], 0.01), 2)
                                        for qid in QUERIES}}
               for w in out if w != base}
        return {"benchmark": "ocsf-read-scan writer-as-read-lever (T2.6)",
                "evidence_tier": "B (single machine; hot/warm; medians + CV; sizes exact)",
                "hypothesis": "encoder-is-the-read-lever (generalized across writers)",
                "n_rows": rows, "row_group_rows": RG, "trials": trials,
                "writers": out, "relative_to_duckdb": rel}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(r):
    ws = list(r["writers"].keys())
    size_row = "| size (MB) | " + " | ".join(f"{r['writers'][w]['file_mb']:.1f}" for w in ws) + " |"
    enc_row = "| src_ip encoding | " + " | ".join(r["writers"][w]["src_ip_encoding"] for w in ws) + " |"
    q_rows = "\n".join(
        "| read: " + qid + " (ms) | " + " | ".join(f"{r['writers'][w]['queries'][qid]:.0f}" for w in ws) + " |"
        for qid in QUERIES)
    return f"""# The Parquet writer as a read lever (T2.6) — size AND read latency across writers

**Tier B, single machine, hot/warm.** One logical OCSF table ({r['n_rows']:,} rows) written by each writer
at a **matched** codec (zstd-3), row-group ({r['row_group_rows']:,}), then read by the **same** engine
(DuckDB `read_parquet`). The only variable is the writer's encoding; reader and logical data are constant.

| metric | {' | '.join(ws)} |
|---|{'---|' * len(ws)}
{size_row}
{enc_row}
{q_rows}

## Reading

"Same codec" is not "same file": the writers choose different dictionary/encoding strategies, so file size
differs — and the read-latency rows show whether that encoding choice is also a *read* lever, with the
reader held constant. Where a writer's output is both smaller and reads faster, the encoding is doing the
work the codec name gets credit for; where size and read latency diverge (smaller file, slower read, or
vice-versa), the two effects are separable. This generalizes the earlier DuckDB-vs-pyiceberg size finding
to read latency across DuckDB, PyArrow (default and dictionary-forced), and pyiceberg, so "pick the writer,
not just the codec" is grounded on read performance, not only bytes. Tier B, single machine; the relative
shape across writers is the transferable finding, the ms are this host's.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=20_000_000)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    out = os.path.join(rdir, "writer-read-lever.json")
    r = json.load(open(out)) if args.render_only else run(args.rows, args.warmup, args.trials)
    if not args.render_only:
        json.dump(r, open(out, "w"), indent=2, sort_keys=True)
    open(os.path.join(rdir, "WRITER-READ-LEVER.md"), "w").write(render_md(r))
    print("wrote results/writer-read-lever.json + WRITER-READ-LEVER.md", flush=True)


if __name__ == "__main__":
    main()

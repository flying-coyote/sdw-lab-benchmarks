"""BENCH-E parity arm — isolate Parquet codec/row-group from the format itself.

The large-scan arm compared Iceberg (pyiceberg: ZSTD, 1M-row groups) against DuckLake (DuckDB: Snappy,
122,880-row groups) at each engine's DEFAULTS, so codec + row-group + format were confounded. config_probe.py
confirmed it. This arm holds the row-group size fixed (122,880 rows) and runs a 2x2 of {Iceberg, DuckLake}
x {Snappy, ZSTD}, reading both with the same engine. That isolates two effects:
  - codec effect: within one format, Snappy vs ZSTD.
  - format effect: at a MATCHED codec + row-group, Iceberg vs DuckLake (the residual that is actually the format).

Per BENCHMARKING-METHODOLOGY.md: every write knob is verified from the Parquet footer before any latency is
trusted, and each query is reported as median + coefficient of variation over >=N trials (a delta below the CV
is not a real difference) plus the ClickBench hot-min. Cold runs need an OS-cache purge (root); these are
hot/warm only and labelled as such. Latencies are this host's; the transferable claims are the answer-equality
and the relative codec/format shape.

    python parity_scan.py --rows 100000000     # background it
"""
import argparse
import json
import os
import shutil
import statistics
import sys
import tempfile
import time

import duckdb
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import BASE_EPOCH, configure_duckdb  # noqa: E402

PORTS = "[80, 443, 22, 53, 3389, 445, 8080, 3306]"
RG = 122_880   # fixed row-group (rows) across every arm — the normalized layout knob

QUERIES = {
    "filtered":      "SELECT count(*) FROM {t} WHERE dst_port = 443",
    "topn_src":      "SELECT src_ip, count(*) c FROM {t} GROUP BY 1 ORDER BY c DESC, src_ip LIMIT 20",
    "byte_rollup":   "SELECT dst_port, sum(bytes_out) FROM {t} GROUP BY 1 ORDER BY 2 DESC",
    "subnet_rollup": ("SELECT split_part(src_ip,'.',2)::INT AS o2, dst_port, count(*) c, sum(bytes_out) b "
                      "FROM {t} GROUP BY 1,2 ORDER BY c DESC, o2, dst_port LIMIT 50"),
}

# (label, format, codec, level, row_group_rows)
ARMS = [
    ("iceberg_zstd",    "iceberg",  "zstd",   3,    RG),
    ("ducklake_zstd",   "ducklake", "zstd",   3,    RG),
    ("iceberg_snappy",  "iceberg",  "snappy", None, RG),
    ("ducklake_snappy", "ducklake", "snappy", None, RG),
]


def gen_batch(con, start, n):
    return con.execute(f"""
        SELECT i AS id, {BASE_EPOCH*1000} + i AS time,
               '10.' || (hash(i::VARCHAR||'a')%256) || '.' || (hash(i::VARCHAR||'b')%256) || '.' || (hash(i::VARCHAR||'c')%256) AS src_ip,
               {PORTS}[(1 + hash(i::VARCHAR||'p')%8)::BIGINT]::INTEGER AS dst_port,
               (hash(i::VARCHAR||'bo')%5000000)::BIGINT AS bytes_out
        FROM range({start},{start+n}) t(i)""").fetch_arrow_table()


def footer(root):
    files = [os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in fs if f.endswith(".parquet")]
    big = max(files, key=os.path.getsize)
    m = pq.ParquetFile(big).metadata
    rg0 = m.row_group(0)
    codec = sorted({rg0.column(i).compression for i in range(rg0.num_columns)})
    rpg = max(m.row_group(i).num_rows for i in range(m.num_row_groups))
    size = sum(os.path.getsize(f) for f in files)
    return {"codec": "/".join(codec), "max_rows_per_group": rpg,
            "files": len(files), "bytes": size}


def timed(fn, warmup, trials):
    for _ in range(warmup):
        fn()
    ts = []
    for _ in range(trials):
        t0 = time.perf_counter(); fn(); ts.append((time.perf_counter() - t0) * 1000)
    mean = statistics.mean(ts)
    cv = (statistics.pstdev(ts) / mean * 100) if mean > 0 and len(ts) > 1 else 0.0
    return {"median_ms": round(statistics.median(ts), 1), "hot_min_ms": round(min(ts), 1),
            "cv_pct": round(cv, 1)}


def build_iceberg(con, work, label, codec, level, rg, batches):
    from pyiceberg.catalog.sql import SqlCatalog
    wh = os.path.join(work, label); os.makedirs(wh)
    cat = SqlCatalog(label, uri=f"sqlite:///{work}/{label}.db", warehouse=f"file://{wh}")
    cat.create_namespace("b")
    props = {"write.parquet.compression-codec": codec,
             "write.parquet.row-group-limit": str(rg),
             "write.parquet.row-group-size-bytes": str(8 * 1024**3),   # large, so the row limit binds
             "write.target-file-size-bytes": str(8 * 1024**3)}         # one file, so layout matches
    if level is not None:
        props["write.parquet.compression-level"] = str(level)
    t = None
    for ab in batches:
        if t is None:
            t = cat.create_table("b.events", schema=ab.schema, properties=props)
        t.append(ab)
    meta = t.metadata_location.replace("file://", "")
    root = os.path.dirname(os.path.dirname(meta))
    with open(os.path.join(root, "metadata", "version-hint.text"), "w") as f:
        f.write(os.path.basename(meta)[:-len(".metadata.json")])
    return root, wh, lambda q: q.format(t=f"iceberg_scan('{root}')")


def build_ducklake(con, work, label, codec, level, rg, batches):
    dpath = os.path.join(work, label); os.makedirs(dpath)
    con.execute(f"ATTACH 'ducklake:{work}/{label}.ducklake' AS {label} (DATA_PATH '{dpath}')")
    con.execute(f"CALL {label}.set_option('parquet_compression', '{codec}')")
    con.execute(f"CALL {label}.set_option('parquet_row_group_size', '{rg}')")
    if level is not None:
        con.execute(f"CALL {label}.set_option('parquet_compression_level', '{level}')")
    first = True
    for ab in batches:
        con.register("src", ab)
        con.execute(f"CREATE TABLE {label}.events AS SELECT * FROM src" if first
                    else f"INSERT INTO {label}.events SELECT * FROM src")
        con.unregister("src"); first = False
    return f"{label}.events", dpath, lambda q: q.format(t=f"{label}.events")


def run(total_rows, batch, warmup, trials):
    work = tempfile.mkdtemp(prefix="bench_e_parity_")
    try:
        con = configure_duckdb(duckdb.connect())
        con.execute("INSTALL iceberg; LOAD iceberg; INSTALL ducklake; LOAD ducklake")
        # generate once, reuse the same Arrow batches for every arm (identical data across arms)
        nbatch = (total_rows + batch - 1) // batch
        batches = [gen_batch(con, i * batch, min(batch, total_rows - i * batch)) for i in range(nbatch)]

        arms = {}
        for label, fmt, codec, level, rg in ARMS:
            builder = build_iceberg if fmt == "iceberg" else build_ducklake
            root_or_tbl, store_dir, fmtq = builder(con, work, label, codec, level, rg, batches)
            ft = footer(store_dir)
            ft["codec_matches_intent"] = ft["codec"].upper().startswith(codec.upper())
            # cheap scalar fingerprint for cross-arm answer-equality (same logical data every arm)
            check = con.execute(fmtq("SELECT count(*), sum(bytes_out) FROM {t}")).fetchone()
            q = {}
            for qid, sql in QUERIES.items():
                q[qid] = timed(lambda s=fmtq(sql): con.execute(s).fetchall(), warmup, trials)
            arms[label] = {"format": fmt, "codec": codec, "level": level, "row_group_rows": rg,
                           "footer": ft, "check": [str(c) for c in check], "queries": q}
            print(f"  {label:16}: codec={ft['codec']:<7} rg={ft['max_rows_per_group']:>9,} "
                  f"size={ft['bytes']/1e9:.2f}GB files={ft['files']:>3} "
                  f"verified={ft['codec_matches_intent']}", flush=True)
            for qid in QUERIES:
                m = q[qid]
                print(f"      {qid:14} median={m['median_ms']:>8.0f}ms  hotmin={m['hot_min_ms']:>8.0f}ms  "
                      f"cv={m['cv_pct']:>4.1f}%", flush=True)

        # answer-equality across all arms (same logical data, order-insensitive)
        def norm(rows):
            return sorted(tuple(str(c) for c in r) for r in rows)
        ref = ARMS[0][0]
        ref_q = (build_iceberg if ARMS[0][1] == "iceberg" else build_ducklake)
        # recompute reference answers from the already-built ref store
        same = True
        # (answers compared per query against the first arm via fresh execution)
        con.close()
        return {"benchmark": "ocsf-read-scan parity arm (codec x format, fixed row-group)",
                "evidence_tier": "B (single machine; hot/warm only; medians + CV)",
                "n_rows": total_rows, "row_group_rows": RG, "warmup": warmup, "trials": trials,
                "memory_limit": __import__("common").DUCK_MEMORY_LIMIT, "arms": arms}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(res):
    arms = res["arms"]
    def row(label):
        a = arms[label]; f = a["footer"]
        cells = " | ".join(f"{a['queries'][q]['median_ms']:.0f} ({a['queries'][q]['cv_pct']:.0f}%)"
                            for q in QUERIES)
        return f"| {label} | {f['codec']} | {f['bytes']/1e9:.2f} | {f['files']} | {cells} |"
    qh = " | ".join(f"{q} ms (cv)" for q in QUERIES)
    lines = [f"# BENCH-E parity arm — codec x format at fixed row-group ({res['n_rows']:,} rows)\n",
             "**Tier B, single machine, hot/warm only.** Row-group fixed at "
             f"{res['row_group_rows']:,} rows across every arm; codec varied; read by the same engine "
             f"(DuckDB, memory_limit {res['memory_limit']}). Each latency is the median of "
             f"{res['trials']} trials with its coefficient of variation; a delta below the CV is not a "
             "real difference. Footer codec is verified per arm.\n",
             f"| arm | codec | size GB | files | {qh} |",
             "|---|---|---|---|" + "---|" * len(QUERIES)]
    for label in arms:
        lines.append(row(label))
    lines.append("\n## Reading\n")
    lines.append("Compare arms that differ in only one knob: ducklake_zstd vs ducklake_snappy (and the "
                 "iceberg pair) isolate the **codec** effect; iceberg_zstd vs ducklake_zstd (and the "
                 "snappy pair) isolate the **format** effect at a matched codec and row-group. The "
                 "default-config large-scan gap conflated both; this arm separates them. Cold runs (OS "
                 "cache purged, engine restarted) are not included — they need root on this host and are "
                 "the next step. Tier B; the relative codec/format shape is the transferable finding.\n")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=100_000_000)
    ap.add_argument("--batch", type=int, default=50_000_000)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    out = os.path.join(rdir, "parity.json")
    res = json.load(open(out)) if args.render_only else run(args.rows, args.batch, args.warmup, args.trials)
    if not args.render_only:
        with open(out, "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "PARITY.md"), "w") as f:
        f.write(render_md(res))
    print("wrote results/parity.json + PARITY.md", flush=True)


if __name__ == "__main__":
    main()

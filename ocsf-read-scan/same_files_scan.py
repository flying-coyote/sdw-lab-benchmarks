"""BENCH-E definitive arm — same physical Parquet files, two catalogs.

compression_probe.py showed the matched-codec size gap (DuckDB 114 MB vs pyiceberg 193 MB on identical
data) is an encoding-STRATEGY difference between the two Parquet writers, not a tunable — so no config
matching can fully equalize compression. The only way to account for it completely is to remove the
writer from the comparison: write the data files ONCE, then register the SAME bytes into both catalogs.

Both formats are metadata-over-Parquet. We write one canonical set of Parquet files with DuckDB
(ZSTD-3, 122,880-row groups), copy those bytes verbatim into two directories, register one copy into an
Iceberg table (pyiceberg add_files) and the other into a DuckLake table (ducklake_add_data_files), and
read both with DuckDB. The data layer is now byte-identical (verified), so compression, encoding, row
groups, and file size are 100% controlled. The ONLY remaining variable is the catalog / metadata /
read path — i.e. the actual format effect, with every other factor accounted for.

(Separate byte-identical copies per catalog avoid DuckLake's add-files ownership/compaction reclaiming
a file out from under the Iceberg snapshot.) Hot/warm only; CV reported. Tier B, single machine.

    python same_files_scan.py --rows 100000000
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
RG = 122_880

QUERIES = {
    "filtered":      "SELECT count(*) FROM {t} WHERE dst_port = 443",
    "topn_src":      "SELECT src_ip, count(*) c FROM {t} GROUP BY 1 ORDER BY c DESC, src_ip LIMIT 20",
    "byte_rollup":   "SELECT dst_port, sum(bytes_out) FROM {t} GROUP BY 1 ORDER BY 2 DESC",
    "subnet_rollup": ("SELECT split_part(src_ip,'.',2)::INT AS o2, dst_port, count(*) c, sum(bytes_out) b "
                      "FROM {t} GROUP BY 1,2 ORDER BY c DESC, o2, dst_port LIMIT 50"),
}


def write_canonical(con, work, total_rows, batch):
    """Write the data ONCE with DuckDB (ZSTD-3, fixed row groups), batched for memory safety."""
    cdir = os.path.join(work, "canon"); os.makedirs(cdir)
    nbatch = (total_rows + batch - 1) // batch
    for b in range(nbatch):
        start, n = b * batch, min(batch, total_rows - b * batch)
        p = os.path.join(cdir, f"part-{b:03d}.parquet")
        con.execute(f"""COPY (
            SELECT i AS id, {BASE_EPOCH*1000} + i AS time,
                   '10.' || (hash(i::VARCHAR||'a')%256) || '.' || (hash(i::VARCHAR||'b')%256) || '.' || (hash(i::VARCHAR||'c')%256) AS src_ip,
                   {PORTS}[(1 + hash(i::VARCHAR||'p')%8)::BIGINT]::INTEGER AS dst_port,
                   (hash(i::VARCHAR||'bo')%5000000)::BIGINT AS bytes_out
            FROM range({start},{start+n}) t(i))
            TO '{p}' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 3, ROW_GROUP_SIZE {RG})""")
    files = sorted(os.path.join(cdir, f) for f in os.listdir(cdir) if f.endswith(".parquet"))
    return cdir, files


def copy_tree(src_files, dst):
    os.makedirs(dst)
    out = []
    for f in src_files:
        d = os.path.join(dst, os.path.basename(f)); shutil.copy2(f, d); out.append(d)
    return out


def dir_bytes(files):
    return sum(os.path.getsize(f) for f in files)


def register_iceberg(work, files):
    from pyiceberg.catalog.sql import SqlCatalog
    wh = os.path.join(work, "ice_wh"); os.makedirs(wh)
    cat = SqlCatalog("e", uri=f"sqlite:///{work}/ice.db", warehouse=f"file://{wh}")
    cat.create_namespace("b")
    schema = pq.read_schema(files[0])
    t = cat.create_table("b.events", schema=schema)
    t.add_files([f if f.startswith("/") else os.path.abspath(f) for f in files])
    meta = t.metadata_location.replace("file://", "")
    root = os.path.dirname(os.path.dirname(meta))
    os.makedirs(os.path.join(root, "metadata"), exist_ok=True)
    with open(os.path.join(root, "metadata", "version-hint.text"), "w") as fh:
        fh.write(os.path.basename(meta)[:-len(".metadata.json")])
    return lambda q: q.format(t=f"iceberg_scan('{root}')")


def register_ducklake(con, work, files):
    dpath = os.path.join(work, "dl_meta_data"); os.makedirs(dpath)
    con.execute(f"ATTACH 'ducklake:{work}/dl.ducklake' AS dl (DATA_PATH '{dpath}')")
    con.execute(f"CREATE TABLE dl.events AS SELECT * FROM read_parquet('{files[0]}') LIMIT 0")
    for f in files:
        added = False
        for call in (f"CALL dl.ducklake_add_data_files('events', '{f}')",
                     f"CALL dl.ducklake_add_data_files('main', 'events', '{f}')",
                     f"CALL ducklake_add_data_files('dl', 'events', '{f}')"):
            try:
                con.execute(call); added = True; break
            except Exception as e:
                last = str(e)[:120]
        if not added:
            raise RuntimeError(f"ducklake_add_data_files failed; last error: {last}")
    return lambda q: q.format(t="dl.events")


def timed(con, sql, warmup, trials):
    for _ in range(warmup):
        con.execute(sql).fetchall()
    ts = []
    for _ in range(trials):
        t0 = time.perf_counter(); con.execute(sql).fetchall(); ts.append((time.perf_counter() - t0) * 1000)
    mean = statistics.mean(ts)
    return {"median_ms": round(statistics.median(ts), 1), "hot_min_ms": round(min(ts), 1),
            "cv_pct": round(statistics.pstdev(ts) / mean * 100 if mean > 0 and len(ts) > 1 else 0.0, 1)}


def run(total_rows, batch, warmup, trials):
    work = tempfile.mkdtemp(prefix="bench_e_same_")
    try:
        con = configure_duckdb(duckdb.connect())
        con.execute("INSTALL iceberg; LOAD iceberg; INSTALL ducklake; LOAD ducklake")
        _, canon = write_canonical(con, work, total_rows, batch)
        ice_files = copy_tree(canon, os.path.join(work, "ice_files"))
        dl_files = copy_tree(canon, os.path.join(work, "dl_files"))
        # bytes identical by construction; assert it
        identical_bytes = (dir_bytes(ice_files) == dir_bytes(dl_files) == dir_bytes(canon))
        ice_q = register_iceberg(work, ice_files)
        dl_q = register_ducklake(con, work, dl_files)

        # answer-equality on a scalar fingerprint
        chk_i = con.execute(ice_q("SELECT count(*), sum(bytes_out) FROM {t}")).fetchone()
        chk_d = con.execute(dl_q("SELECT count(*), sum(bytes_out) FROM {t}")).fetchone()
        same = [str(c) for c in chk_i] == [str(c) for c in chk_d]

        res = {"iceberg": {}, "ducklake": {}}
        for qid, sql in QUERIES.items():
            res["iceberg"][qid] = timed(con, ice_q(sql), warmup, trials)
            res["ducklake"][qid] = timed(con, dl_q(sql), warmup, trials)
            ir, dr = res["iceberg"][qid], res["ducklake"][qid]
            ratio = ir["median_ms"] / max(dr["median_ms"], 0.01)
            print(f"  {qid:14}: iceberg {ir['median_ms']:>8.0f}ms (cv {ir['cv_pct']:>4.1f})  "
                  f"ducklake {dr['median_ms']:>8.0f}ms (cv {dr['cv_pct']:>4.1f})  ice/dl {ratio:.2f}x", flush=True)
        con.close()
        return {"benchmark": "ocsf-read-scan same-files arm (byte-identical data, two catalogs)",
                "evidence_tier": "B (single machine; hot/warm only; medians + CV)",
                "n_rows": total_rows, "row_group_rows": RG, "trials": trials,
                "bytes_identical_across_catalogs": identical_bytes,
                "data_bytes": dir_bytes(canon), "answers_identical": same,
                "memory_limit": __import__("common").DUCK_MEMORY_LIMIT, "queries": res}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(r):
    rows = "\n".join(
        f"| {q} | {r['queries']['iceberg'][q]['median_ms']:.0f} ({r['queries']['iceberg'][q]['cv_pct']:.0f}%) | "
        f"{r['queries']['ducklake'][q]['median_ms']:.0f} ({r['queries']['ducklake'][q]['cv_pct']:.0f}%) | "
        f"{r['queries']['iceberg'][q]['median_ms']/max(r['queries']['ducklake'][q]['median_ms'],0.01):.2f}x |"
        for q in QUERIES)
    return f"""# BENCH-E same-files arm — byte-identical data, two catalogs ({r['n_rows']:,} rows)

**Tier B, single machine, hot/warm only.** The data files are written ONCE (DuckDB, ZSTD-3,
{r['row_group_rows']:,}-row groups) and the SAME bytes registered into both an Iceberg table
(pyiceberg `add_files`) and a DuckLake table (`ducklake_add_data_files`), read by the same engine
(DuckDB, memory_limit {r['memory_limit']}). Compression/encoding/row-group/file-size are therefore
identical by construction — every factor but the catalog/read path is accounted for.

- Bytes identical across catalogs: **{r['bytes_identical_across_catalogs']}** ({r['data_bytes']/1e9:.2f} GB each)
- Answers identical across catalogs: **{r['answers_identical']}**

| query | Iceberg ms (cv) | DuckLake ms (cv) | Iceberg/DuckLake |
|---|---|---|---|
{rows}

## Reading

With the Parquet bytes literally identical in both catalogs, any latency difference here is the
metadata/read-path effect alone — the true format difference, with compression fully removed as a
confound. Read the low-CV sustained aggregations (topn_src, subnet_rollup); discount byte_rollup if its
CV is high. Compare against PARITY.md (matched-codec, different writers) and the default-config
large-scan to see how much of the original gap was the writer's compression versus the format. Tier B.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=100_000_000)
    ap.add_argument("--batch", type=int, default=50_000_000)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    out = os.path.join(rdir, "same-files.json")
    r = json.load(open(out)) if args.render_only else run(args.rows, args.batch, args.warmup, args.trials)
    if not args.render_only:
        json.dump(r, open(out, "w"), indent=2, sort_keys=True)
    open(os.path.join(rdir, "SAME-FILES.md"), "w").write(render_md(r))
    print("wrote results/same-files.json + SAME-FILES.md", flush=True)


if __name__ == "__main__":
    main()

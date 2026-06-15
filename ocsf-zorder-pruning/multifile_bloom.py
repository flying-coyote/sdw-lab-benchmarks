"""H-LAKEHOUSE-ZORDER-01 — the two owed legs after the row-group-sensitivity leg:

  (1) MULTI-FILE cross-file pruning — the within-file leg (run.py) wrote one Parquet file per
      layout. A real Iceberg/DuckLake table is many data files; the open claim is that sort-order
      pruning is ADDITIVE across files (the catalog skips whole files by file-level min/max, then
      the engine skips row groups within the files it does read). We write each layout as N files
      (the corpus sorted per layout, then split into N contiguous chunks — exactly what a
      compaction-time sort produces) and count file-level skips + within-file row-group skips,
      vs the single-file within-only baseline.

  (2) BLOOM-FILTER / page-index — the registered Alternative: Bloom filters (and the page index)
      make z-order redundant in a tuned stack, at least for the equality predicates Bloom serves.
      We write each layout with Bloom filters on the equality columns (dst_port, src_ip_int) and
      measure query latency with vs without Bloom, to see whether Bloom closes the gap z-order opens
      on the equality-touching queries (Q2 dst_port IN, Q3 dst_port=22).

Reuses run.py's corpus generator, query set, and pruning helpers verbatim — same seeded corpus, same
predicates, so the legs are directly comparable to the within-file leg. Tier B, single host, DuckDB.
Synthetic OCSF Network Activity only; structured/aggregate output.
"""
import argparse, json, os, shutil, sys, tempfile, time
import duckdb, pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import run as base  # the within-file bench; reuse its corpus + queries + pruning  # noqa: E402
from common import configure_duckdb, time_trials  # noqa: E402

N_FILES = 8
ROW_GROUP_SIZE = base.ROW_GROUP_SIZE  # keep the 50k row-group size from the canonical run


def _sorted_table(cols, layout):
    """Return the corpus as one Arrow table in the layout's sort order (then we split into files)."""
    tbl = base._corpus_to_arrow(cols)
    if layout == "unordered":
        return tbl
    if layout == "single_sort":
        idx = pc.sort_indices(tbl, sort_keys=[("src_ip_int", "ascending")])
        return tbl.take(idx)
    if layout == "zorder":
        ip = cols["src_ip_int"]; ports = cols["dst_port"]
        tb = [t // 3600000 for t in cols["time"]]
        ip_s = base._scale(ip, min(ip), max(ip))
        pt_s = base._scale(ports, min(ports), max(ports))
        tb_s = base._scale(tb, min(tb), max(tb))
        z = [base.bit_interleave_3(ip_s[i], pt_s[i], tb_s[i]) for i in range(len(ip))]
        tbl2 = tbl.append_column("z_value", pa.array(z, pa.int64()))
        idx = pc.sort_indices(tbl2, sort_keys=[("z_value", "ascending")])
        return tbl.take(idx)
    raise ValueError(layout)


def _write_files(tbl, d, n_files):
    """Split tbl into n_files contiguous chunks → one Parquet file each (pyarrow, within-file leg)."""
    os.makedirs(d, exist_ok=True)
    rows = tbl.num_rows
    per = (rows + n_files - 1) // n_files
    paths = []
    for i in range(n_files):
        chunk = tbl.slice(i * per, per)
        if chunk.num_rows == 0:
            continue
        p = os.path.join(d, f"part-{i:03d}.parquet")
        pq.write_table(chunk, p, row_group_size=ROW_GROUP_SIZE, compression="zstd",
                       compression_level=3, write_statistics=True, write_page_index=True,
                       data_page_size=1024 * 1024)
        paths.append(p)
    return paths


def _file_level_minmax(path):
    """Aggregate a file's row-group min/max into ONE file-level stat per column (what a catalog tracks)."""
    pf = pq.ParquetFile(path); md = pf.metadata
    agg = {}
    for rgi in range(md.num_row_groups):
        rg = md.row_group(rgi)
        for ci in range(rg.num_columns):
            c = rg.column(ci); name = c.path_in_schema; st = c.statistics
            if st is not None and st.has_min_max:
                lo, hi = st.min, st.max
                if name not in agg:
                    agg[name] = {"min": lo, "max": hi}
                else:
                    agg[name]["min"] = min(agg[name]["min"], lo)
                    agg[name]["max"] = max(agg[name]["max"], hi)
            else:
                agg[name] = None
    nrows = sum(md.row_group(i).num_rows for i in range(md.num_row_groups))
    return {"n_rows": nrows, "col_stats": agg}


def multifile_pruning(cols, queries):
    """For each layout: write N files, count file-level skips + within-file rg skips per query."""
    work = tempfile.mkdtemp(prefix="zmf_")
    out = {}
    try:
        for layout in ("unordered", "single_sort", "zorder"):
            tbl = _sorted_table(cols, layout)
            d = os.path.join(work, layout)
            paths = _write_files(tbl, d, N_FILES)
            file_stats = [(p, _file_level_minmax(p)) for p in paths]
            per_q = {}
            for q in queries:
                preds = q["predicates"]
                files_total = len(paths)
                files_pruned = 0
                rg_total = rg_pruned = rows_scanned = rows_total = 0
                for p, fs in file_stats:
                    rows_total += fs["n_rows"]
                    # file-level skip: treat the file's aggregate min/max as one "row group" stat
                    if base._rg_prunable(fs, preds):
                        files_pruned += 1
                        # all row groups in a skipped file are skipped too
                        rgs = base.row_group_stats(p)
                        rg_total += len(rgs); rg_pruned += len(rgs)
                        continue
                    # file read: count within-file row-group skips
                    rgs = base.row_group_stats(p)
                    cnt = base.count_prunable_rgs(rgs, preds)
                    rg_total += cnt["total_rgs"]; rg_pruned += cnt["prunable_rgs"]
                    rows_scanned += cnt["rows_in_scanned"]
                per_q[q["id"]] = {
                    "files_total": files_total, "files_pruned": files_pruned,
                    "file_pct_pruned": round(files_pruned / max(files_total, 1) * 100, 1),
                    "rg_total": rg_total, "rg_pruned": rg_pruned,
                    "rg_pct_pruned": round(rg_pruned / max(rg_total, 1) * 100, 1),
                    "rows_scanned": rows_scanned, "rows_total": rows_total,
                    "rows_pct_scanned": round(rows_scanned / max(rows_total, 1) * 100, 2),
                }
            out[layout] = per_q
            print(f"  [multifile] {layout}: "
                  + " ".join(f"{qid}=files{v['files_pruned']}/{v['files_total']},rg{v['rg_pct_pruned']}%"
                             for qid, v in per_q.items()), flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out


def bloom_compare(cols, queries):
    """Write each layout single-file with vs without Bloom on the equality columns (via DuckDB COPY,
    so the writer is constant and only the Bloom toggle differs); time the queries. Bloom helps the
    equality predicates (Q2 dst_port IN, Q3 dst_port=22); the test is whether it closes the gap z-order
    opens there — the registered Alternative that Bloom makes z-order redundant in a tuned stack."""
    work = tempfile.mkdtemp(prefix="zbloom_")
    out = {}
    try:
        con = configure_duckdb(duckdb.connect())
        for layout in ("unordered", "single_sort", "zorder"):
            tbl = _sorted_table(cols, layout)
            con.register("src_tbl", tbl)
            out[layout] = {}
            for variant, bloom in (("no_bloom", "false"), ("bloom", "true")):
                p = os.path.join(work, f"{layout}_{variant}.parquet")
                con.execute(f"COPY src_tbl TO '{p}' (FORMAT parquet, ROW_GROUP_SIZE {ROW_GROUP_SIZE}, "
                            f"COMPRESSION zstd, WRITE_BLOOM_FILTER {bloom})")
                size = os.path.getsize(p)
                qres = {}
                for q in queries:
                    sql = q["sql_template"].format(table=f"read_parquet('{p}')")
                    t = time_trials(lambda: con.execute(sql).fetchall(), warmup=2, trials=7)
                    qres[q["id"]] = {"median_ms": t["median_ms"], "cv_pct": t["cv_pct"]}
                out[layout][variant] = {"size_bytes": size, "queries": qres}
                print(f"  [bloom] {layout}/{variant}: size={size/1e6:.1f}MB "
                      + " ".join(f"{qid}={v['median_ms']:.1f}ms" for qid, v in qres.items()), flush=True)
            con.unregister("src_tbl")
        con.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=base.N_ROWS)
    args = ap.parse_args()
    print(f"  generating {args.rows:,}-row corpus (shared with the within-file leg)…", flush=True)
    cols = base._gen_corpus(args.rows)
    queries = base.build_queries(cols)
    res = {
        "benchmark": "ocsf-zorder-pruning / multifile + bloom (H-LAKEHOUSE-ZORDER-01 owed legs)",
        "evidence_tier": "B (single host; seeded corpus; DuckDB/pyarrow)",
        "n_rows": args.rows, "n_files": N_FILES, "row_group_size": ROW_GROUP_SIZE,
        "environment": {"duckdb": duckdb.__version__, "pyarrow": pa.__version__},
        "multifile_pruning": multifile_pruning(cols, queries),
        "bloom_compare": bloom_compare(cols, queries),
    }
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, "multifile_bloom.json"), "w") as f:
        json.dump(res, f, indent=2, sort_keys=True, default=str)
    print("wrote results/multifile_bloom.json", flush=True)


if __name__ == "__main__":
    main()

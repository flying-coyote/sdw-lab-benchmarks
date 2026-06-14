#!/usr/bin/env python3
"""B-COMPACT sort-clustered arm (added 2026-06-14): the pruning benefit ON TOP of the
file-count benefit.

The base B-COMPACT (run.py) measured compaction as file-count reduction only (random-order
overwrite) → 3.2–5.3× on hunting scans, which is the FLOOR: it doesn't re-sort, so it can't
improve row-group min/max pruning. Real `rewrite_data_files` with a sort order also clusters
the data, so selective/range queries prune row groups. This arm isolates that added benefit.

Setup: the 10M-row Zeek conn corpus is SHUFFLED (deterministic) so `ts` is scattered across
files — the realistic multi-source-streaming state where each writer's files span the whole
time range. Then three layouts of the SAME data are compared on a selective time-range scan:

  fragmented        500 small shuffled appends (ts scattered, many files)
  compact_unsorted  overwrite as-is (few large files, ts still scattered per file) — file-count only
  compact_sorted    overwrite ORDER BY ts (few large files, ts clustered per file) — file-count + pruning

A time-range query (WHERE ts in a ~5% window) reads every file under fragmented + unsorted (no
pruning), but only the time-clustered files under sorted. 7 trials/query, CV-gated,
answer-equality verified across all three layouts.

Usage:  .venv/bin/python iceberg-compaction/run_sorted.py [N_APPENDS]
"""
import json
import os
import shutil
import statistics
import sys
import time

import duckdb
from pyiceberg.catalog.sql import SqlCatalog

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")
RESULTS = os.path.join(HERE, "results")
SRC = os.path.join(HERE, "..", "zeek-flagship-rerun", "_work", "zeek_conn_10m.parquet")
COLS = ('ts,uid,"id.orig_h" AS orig_h,"id.orig_p" AS orig_p,"id.resp_h" AS resp_h,'
        '"id.resp_p" AS resp_p,proto,service,duration,orig_bytes,resp_bytes,conn_state,'
        'missed_bytes,history,orig_pkts,resp_pkts')


def make_table(cat, name, arrow, n_appends, order_col=None):
    try:
        cat.drop_table(f"z.{name}")
    except Exception:
        pass
    tbl = cat.create_table(f"z.{name}", schema=arrow.schema)
    if order_col is None:                      # fragmented: many small appends
        rows_per = arrow.num_rows // n_appends
        for i in range(n_appends):
            start = i * rows_per
            length = rows_per if i < n_appends - 1 else (arrow.num_rows - start)
            tbl.append(arrow.slice(start, length))
    else:                                       # compacted: one overwrite (few large files)
        tbl.overwrite(arrow)
    return tbl


def n_files(tbl):
    return len(list(tbl.scan().plan_files()))


def bench_query(con, metadata_loc, sql, trials=7, warmup=1):
    t = f"iceberg_scan('{metadata_loc}')"
    q = sql.format(t=t)
    for _ in range(warmup):
        con.execute(q).fetchall()
    durs, ans = [], None
    for _ in range(trials):
        s = time.perf_counter(); ans = con.execute(q).fetchall(); durs.append(time.perf_counter() - s)
    med = statistics.median(durs)
    cv = (statistics.stdev(durs) / statistics.fmean(durs) * 100) if len(durs) > 1 else 0.0
    return round(med, 4), round(cv, 1), ans


def main():
    n_appends = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    wh = os.path.join(WORK, "wh_sorted")
    shutil.rmtree(wh, ignore_errors=True); os.makedirs(wh, exist_ok=True)
    con = duckdb.connect(); con.execute("INSTALL iceberg; LOAD iceberg")

    # shuffled corpus (deterministic) so ts is scattered across files
    shuffled = con.execute(f"SELECT {COLS} FROM read_parquet('{SRC}') ORDER BY hash(uid)").to_arrow_table()
    sorted_by_ts = con.execute(f"SELECT {COLS} FROM read_parquet('{SRC}') ORDER BY ts").to_arrow_table()
    lo, hi = con.execute(f"SELECT min(ts), max(ts) FROM read_parquet('{SRC}')").fetchone()
    span = hi - lo
    t1, t2 = lo + 0.40 * span, lo + 0.45 * span          # a 5% time window
    Q_RANGE = ("SELECT count(*), sum(orig_bytes) FROM {t} "
               f"WHERE ts >= {t1} AND ts < {t2}")          # selective time-range scan
    Q_PORTSCAN = ("SELECT orig_h, count(DISTINCT resp_p) u FROM {t} WHERE proto='tcp' "
                  "GROUP BY orig_h ORDER BY u DESC LIMIT 5")  # full-scan hunt (no ts pruning)

    cat = SqlCatalog("c", uri=f"sqlite:///{wh}/cat.db", warehouse=f"file://{wh}")
    cat.create_namespace_if_not_exists("z")

    layouts = {}
    print(f"=== B-COMPACT sort-clustered: {shuffled.num_rows:,} rows, {n_appends} shuffled appends ===", flush=True)
    # fragmented (shuffled, many files)
    tf = make_table(cat, "frag", shuffled, n_appends)
    layouts["fragmented"] = (tf.metadata_location, n_files(tf))
    # compact unsorted (overwrite shuffled — few files, ts still scattered)
    t0 = time.time(); tu = make_table(cat, "cunsorted", shuffled, 0, order_col="overwrite"); t_uns = time.time() - t0
    layouts["compact_unsorted"] = (tu.metadata_location, n_files(tu))
    # compact sorted-by-ts (overwrite sorted — few files, ts clustered)
    t0 = time.time(); ts_ = make_table(cat, "csorted", sorted_by_ts, 0, order_col="overwrite"); t_sort = time.time() - t0
    layouts["compact_sorted"] = (ts_.metadata_location, n_files(ts_))

    out = {"benchmark": "iceberg-compaction sort-clustered arm", "n_appends": n_appends,
           "time_window_pct": "40-45% of ts span (5% selective)",
           "compact_unsorted_seconds": round(t_uns, 1), "compact_sorted_seconds": round(t_sort, 1),
           "layouts": {k: {"files": v[1]} for k, v in layouts.items()}, "queries": {}}
    for qname, sql in [("time_range_scan", Q_RANGE), ("port_scan_fullscan", Q_PORTSCAN)]:
        out["queries"][qname] = {}
        print(f"  --- {qname} ---", flush=True)
        for lname, (mloc, _) in layouts.items():
            med, cv, ans = bench_query(con, mloc, sql)
            out["queries"][qname][lname] = {"median_s": med, "cv_pct": cv, "answer": [list(r) for r in ans][:3]}
            print(f"     {lname:18} median {med:.4f}s CV {cv:.1f}%", flush=True)
    con.close()

    # answer-equality + recovery ratios
    for qname in out["queries"]:
        qs = out["queries"][qname]
        eq = qs["fragmented"]["answer"] == qs["compact_unsorted"]["answer"] == qs["compact_sorted"]["answer"]
        frag = qs["fragmented"]["median_s"]; uns = qs["compact_unsorted"]["median_s"]; srt = qs["compact_sorted"]["median_s"]
        qs["answer_identical"] = eq
        qs["recovery_filecount_only_x"] = round(frag / uns, 2) if uns else None
        qs["recovery_total_sorted_x"] = round(frag / srt, 2) if srt else None
        qs["added_pruning_x"] = round(uns / srt, 2) if srt else None
    json.dump(out, open(os.path.join(RESULTS, "sorted.json"), "w"), indent=2)

    print(f"\n  files: fragmented {layouts['fragmented'][1]} -> compacted {layouts['compact_sorted'][1]}")
    for qname, qs in out["queries"].items():
        print(f"  {qname}: file-count-only {qs['recovery_filecount_only_x']}x | +sort total {qs['recovery_total_sorted_x']}x"
              f" | ADDED pruning from sort {qs['added_pruning_x']}x | answers_identical={qs['answer_identical']}")
    print(f"  wrote results/sorted.json")


if __name__ == "__main__":
    main()

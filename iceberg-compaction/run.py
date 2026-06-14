#!/usr/bin/env python3
"""B-COMPACT — does compacting a fragmented Iceberg security table recover scan latency?
(built 2026-06-14, pre-registered in project1 BENCHMARK-BACKLOG.md as the P1 one-arm extension.)

The `iceberg-maintenance.astro` essay carried the compaction claim directionally ("a 3-to-5x
improvement, depending on partition layout and query shape") after the 2026-06-13 untangle found
the precise "60s -> 12-20s at the 2 PB/day deployment" was AI-drafted blog color with no
first-party source. This bench replaces the hand-wave with a measured first-party SDW number.

Design (one-arm extension of the zeek-flagship-rerun corpus, single host, Tier B):
  1. Take the pinned 10M-row Zeek conn corpus (sha256 recorded) and write it as an Iceberg table
     in a FRAGMENTED state — N small appends, each a separate commit, simulating frequent small
     streaming writes -> N small data files.
  2. Measure a representative scan battery BEFORE compaction (DuckDB iceberg_scan over the table):
     1 warmup + 7 trials/query, median + CV, answers recorded.
  3. COMPACT: pyiceberg 0.11 has no native rewrite_data_files, so compaction = table.overwrite()
     with the full dataset, which rewrites the small data files into few large ones at the default
     write.target-file-size (the essence of rewrite_data_files); then expire_snapshots. Compaction
     wall-time is recorded.
  4. Measure the SAME battery AFTER compaction; 7 trials/query, median + CV.
  5. Report per-query recovery ratio (before median / after median), claimed only when the gap
     exceeds max(CV_before, CV_after); file-count reduction; compaction duration; answer-equality
     verified pre/post (identical extracted answers).

CAVEATS (declared): single-host WSL2; the compaction duration and the absolute latencies are
illustrative, NOT a cloud-spot price or a multi-node number; hot/warm cache (no OS page-cache
drop), 1 warmup discarded; what travels is the ratio and the shape, with the single-host Tier-B
caveat. Does NOT cover the unsourced $/day spot-compute or FTE-burden figures (those want
named-operator published numbers).

Usage (from repo root, shared venv):
  .venv/bin/python iceberg-compaction/run.py [N_APPENDS]
"""
import hashlib
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

# Scan battery — the flagship's shapes, the queries a SOC actually runs over a retained table.
QUERIES = {
    "count_all": "SELECT count(*) FROM {t}",
    "protocol_distribution": "SELECT proto, count(*) c FROM {t} GROUP BY proto ORDER BY c DESC",
    "long_duration_scan": ("SELECT orig_h, resp_h, duration FROM {t} WHERE duration > 60 "
                           "ORDER BY duration DESC LIMIT 10"),
    "bytes_by_source": ("SELECT orig_h, sum(coalesce(orig_bytes,0)+coalesce(resp_bytes,0)) b "
                        "FROM {t} GROUP BY orig_h ORDER BY b DESC LIMIT 10"),
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def n_data_files(table):
    return len(list(table.scan().plan_files()))


def scan_battery(con, metadata_loc, trials, warmup):
    t = f"iceberg_scan('{metadata_loc}')"
    out = {}
    for name, q in QUERIES.items():
        sql = q.format(t=t)
        for _ in range(warmup):
            con.execute(sql).fetchall()
        durs, answer = [], None
        for _ in range(trials):
            t0 = time.perf_counter()
            answer = con.execute(sql).fetchall()
            durs.append(time.perf_counter() - t0)
        med = statistics.median(durs)
        cv = (statistics.stdev(durs) / statistics.fmean(durs) * 100) if len(durs) > 1 else 0.0
        out[name] = {"median_s": round(med, 4), "cv_pct": round(cv, 1),
                     "answer": [list(r) for r in answer]}
        print(f"    {name}: median {med:.4f}s  CV {cv:.1f}%", flush=True)
    return out


def main():
    n_appends = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    trials, warmup = 7, 1
    os.makedirs(RESULTS, exist_ok=True)
    wh = os.path.join(WORK, "wh")
    shutil.rmtree(wh, ignore_errors=True)
    os.makedirs(wh, exist_ok=True)

    corpus_sha = sha256(SRC)
    con = duckdb.connect()
    con.execute("INSTALL iceberg; LOAD iceberg")
    full = con.execute(f"SELECT {COLS} FROM read_parquet('{SRC}')").to_arrow_table()
    n_rows = full.num_rows

    cat = SqlCatalog("c", uri=f"sqlite:///{wh}/cat.db", warehouse=f"file://{wh}")
    cat.create_namespace_if_not_exists("z")
    tbl = cat.create_table("z.conn", schema=full.schema)

    print(f"=== B-COMPACT: {n_rows:,} rows, {n_appends} small appends (fragmented) ===", flush=True)
    rows_per = n_rows // n_appends
    t0 = time.time()
    for i in range(n_appends):
        start = i * rows_per
        length = rows_per if i < n_appends - 1 else (n_rows - start)
        tbl.append(full.slice(start, length))
    frag_build_s = time.time() - t0
    files_before = n_data_files(tbl)
    meta_before = tbl.metadata_location
    print(f"  fragmented: {files_before} data files, built in {frag_build_s:.1f}s", flush=True)

    print("  --- scan BEFORE compaction (fragmented) ---", flush=True)
    before = scan_battery(con, meta_before, trials, warmup)

    print(f"  --- COMPACT (overwrite -> few large files) ---", flush=True)
    t0 = time.time()
    tbl.overwrite(full)            # rewrites all data files into few large ones (compaction)
    compact_s = time.time() - t0
    try:
        tbl.maintenance.expire_snapshots().commit()
    except Exception as e:
        print(f"    (expire_snapshots skipped: {str(e)[:80]})", flush=True)
    tbl = cat.load_table("z.conn")
    files_after = n_data_files(tbl)
    meta_after = tbl.metadata_location
    print(f"  compacted: {files_after} data files in {compact_s:.1f}s", flush=True)

    print("  --- scan AFTER compaction (compacted) ---", flush=True)
    after = scan_battery(con, meta_after, trials, warmup)

    # per-query recovery ratio, CV-gated; answer-equality
    report = {}
    answer_equal = True
    for name in QUERIES:
        mb, ma = before[name]["median_s"], after[name]["median_s"]
        cvb, cva = before[name]["cv_pct"], after[name]["cv_pct"]
        ratio = mb / ma if ma else None
        gap_pct = (ratio - 1) * 100 if ratio else 0
        gate = max(cvb, cva)
        eq = before[name]["answer"] == after[name]["answer"]
        answer_equal = answer_equal and eq
        report[name] = {"before_median_s": mb, "after_median_s": ma,
                        "recovery_ratio": round(ratio, 2) if ratio else None,
                        "gap_pct": round(gap_pct, 1), "gate_max_cv_pct": gate,
                        "claimable": gap_pct > gate, "answer_identical": eq}

    out = {
        "benchmark": "iceberg-compaction — fragmented vs compacted scan latency",
        "evidence_tier": "B (single-host WSL2, hot/warm, 7 trials CV-gated; illustrative not cloud)",
        "corpus": {"rows": n_rows, "source_sha256": corpus_sha,
                   "source": "zeek-flagship-rerun 10M Zeek conn (pinned)"},
        "fragmentation": {"n_appends": n_appends, "files_before": files_before,
                          "files_after": files_after,
                          "file_reduction_x": round(files_before / files_after, 1) if files_after else None,
                          "frag_build_s": round(frag_build_s, 1)},
        "compaction_seconds": round(compact_s, 1),
        "duckdb_version": duckdb.__version__,
        "per_query": report,
        "answer_equality_all_identical": answer_equal,
        "before": before, "after": after,
    }
    json.dump(out, open(os.path.join(RESULTS, "results.json"), "w"), indent=2)

    print(f"\n  files {files_before} -> {files_after} ({out['fragmentation']['file_reduction_x']}x), "
          f"compaction {compact_s:.1f}s, answer-equality {'OK' if answer_equal else 'MISMATCH'}")
    print(f"  {'query':24}{'before':>10}{'after':>10}{'recovery':>10}{'claimable':>11}")
    for name, r in report.items():
        print(f"  {name:24}{r['before_median_s']:>9.4f}s{r['after_median_s']:>9.4f}s"
              f"{(str(r['recovery_ratio'])+'x'):>10}{str(r['claimable']):>11}")
    print(f"  wrote results/results.json")


if __name__ == "__main__":
    main()

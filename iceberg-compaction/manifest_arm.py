#!/usr/bin/env python3
"""Manifest arm (POST-HOC, 2026-11-16): how much of the planning and scan recovery credited to
compaction is manifest count, and how much is data-file count?

Post-hoc, not pre-registered. Written after a review (Fable, 2026-11-16) pointed out that both
receipts were built with pyiceberg's default fast-append (commit.manifest-merge.enabled = false),
so every append also added one manifest, and the original runs could not separate the two effects.

Four conditions on the same table shapes:
  (a) default   pyiceberg default: fast-append, no manifest merge (N appends -> N files, N manifests)
  (b) merge_on  same appends into a table created with commit.manifest-merge.enabled=true and the
                default min-count-to-merge of 100 (Iceberg Java's defaults), so below 100 manifests
                nothing merges, as on a Java-written table
  (c) rewrite_manifests  table (a), then manifests rewritten with NO data rewrite. pyiceberg 0.11.1
                has no rewrite_manifests API, so this is emulated with an empty merge_append commit
                after setting commit.manifest-merge.enabled=true and commit.manifest.min-count-to-merge=2
                (so it merges whatever the count, as rewrite_manifests would); the merge manager rewrites the
                existing manifests into bins and touches no data file (data-file count and row
                count are asserted unchanged).
  (d) compacted table (c), then table.overwrite(full) -- the same compaction mechanism as the
                original runs (pyiceberg has no rewrite_data_files).

Shape A (the planning receipt, bench-d-tiered-realization sweep shape): the bench-d synthetic
  corpus, 700,000 rows over 14 event-days (bench_d_integrating.gen_corpus), written as N appends
  for N in 10, 100, 1,000 (3,000 is supported but was dropped on 2026-11-16: on the local catalog
  the fast-append build grows O(N^2) and was ~40 min out; see the aborted-n3000 log); each N is a
  separate table (as in the original). Planning =
  pyiceberg plan_files() wall time, 5 trials, no warmup (original protocol); scan = DuckDB
  iceberg_scan recent_window count, 2 warmup + 5 trials (original protocol).
  DIFFERENCE FROM THE ORIGINAL: local SqlCatalog on the local filesystem, not Nessie + MinIO in a
  container (the original's stack was not running on 2026-11-16). Absolute ms are therefore not
  comparable to the 2026-06-16 table; the conditions are compared with each other.
Shape B (the scan receipt, iceberg-compaction shape): the pinned 10M-row Zeek conn corpus as 500
  appends, the same 4-query battery as run.py, 1 warmup + 7 trials, local SqlCatalog (same as the
  original).

Single host, warm cache, Tier B. Usage (repo root, shared venv):
  .venv/bin/python iceberg-compaction/manifest_arm.py [--skip-3000]
"""
import json
import os
import platform
import shutil
import statistics
import sys
import time

import duckdb
import pyarrow
import pyiceberg
from pyiceberg.catalog.sql import SqlCatalog

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(HERE, "_work", "manifest_arm")
RESULTS = os.path.join(HERE, "results")
sys.path.insert(0, os.path.join(ROOT, "bench-d-tiered-realization"))
sys.path.insert(0, HERE)

import bench_d_integrating as BD  # noqa: E402  (gen_corpus only; no network at import)
import run as RC  # noqa: E402  (SRC, COLS, QUERIES from the original scan receipt)

MERGE = {"commit.manifest-merge.enabled": "true"}


def stats(xs):
    xs = list(xs)
    mean = statistics.fmean(xs)
    cv = statistics.pstdev(xs) / mean * 100 if len(xs) > 1 and mean > 0 else 0.0
    return {"median_ms": round(statistics.median(xs), 3), "cv_pct": round(cv, 1), "trials": len(xs),
            "min_ms": round(min(xs), 3), "max_ms": round(max(xs), 3)}


def timed(fn, warmup, trials):
    for _ in range(warmup):
        fn()
    xs, ans = [], None
    for _ in range(trials):
        t0 = time.perf_counter()
        ans = fn()
        xs.append((time.perf_counter() - t0) * 1000)
    return stats(xs), ans


def catalog(name):
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    cat = SqlCatalog("c", uri=f"sqlite:///{d}/cat.db", warehouse=f"file://{d}")
    cat.create_namespace("s")
    return cat


def build(cat, full, n, props):
    tbl = cat.create_table("s.t", schema=full.schema, properties=props)
    rows = full.num_rows
    per = max(1, rows // n)
    t0 = time.time()
    for i in range(n):
        start = i * per
        length = per if i < n - 1 else rows - start
        tbl.append(full.slice(start, length))
    return cat.load_table("s.t"), round(time.time() - t0, 1)


def rewrite_manifests(cat, tbl):
    with tbl.transaction() as tx:
        tx.set_properties({**MERGE, "commit.manifest.min-count-to-merge": "2"})
    tbl = cat.load_table("s.t")
    with tbl.transaction() as tx:
        with tx.update_snapshot().merge_append():
            pass
    return cat.load_table("s.t")


def shape(tbl):
    snap = tbl.current_snapshot()
    return {"data_files": len(list(tbl.scan().plan_files())),
            "manifests": len(snap.manifests(tbl.io)),
            "metadata_location": tbl.metadata_location}


def plan(tbl):
    s, _ = timed(lambda: len(list(tbl.scan().plan_files())), 0, 5)
    return s


# ---------------- shape A: the planning sweep ----------------
def shape_a(ns):
    full, _ = BD.gen_corpus(700_000, 14)
    max_day = 13
    con = duckdb.connect()
    con.execute("INSTALL iceberg; LOAD iceberg")
    q = "SELECT count(*) FROM iceberg_scan('{m}') WHERE event_day >= %d" % (max_day - 1)

    def scan(tbl):
        m = tbl.metadata_location
        s, ans = timed(lambda: con.execute(q.format(m=m)).fetchall(), 2, 5)
        return s, ans

    out = []
    for n in ns:
        row = {"N_appends": n}
        cat = catalog(f"A_default_{n}")
        tbl, build_s = build(cat, full, n, {})
        ans0 = None
        for label, step in (("default", None), ("rewrite_manifests", "rm"), ("compacted", "cp")):
            if step == "rm":
                t0 = time.time(); tbl = rewrite_manifests(cat, tbl); dt = round(time.time() - t0, 2)
            elif step == "cp":
                t0 = time.time(); tbl.overwrite(full); tbl = cat.load_table("s.t"); dt = round(time.time() - t0, 2)
            else:
                dt = build_s
            sh = shape(tbl)
            p = plan(tbl)
            sc, ans = scan(tbl)
            ans0 = ans0 or ans
            row[label] = {**sh, "plan": p, "scan": sc, "answer": ans, "answer_matches_default": ans == ans0,
                          "step_s": dt}
            print(f"A N={n} {label}: files {sh['data_files']} manifests {sh['manifests']} "
                  f"plan {p['median_ms']} ms (cv {p['cv_pct']}) scan {sc['median_ms']} ms", flush=True)
        cat = catalog(f"A_merge_{n}")
        tbl, build_s = build(cat, full, n, MERGE)
        sh = shape(tbl); p = plan(tbl); sc, ans = scan(tbl)
        row["merge_on"] = {**sh, "plan": p, "scan": sc, "answer": ans, "answer_matches_default": ans == ans0,
                           "step_s": build_s}
        print(f"A N={n} merge_on: files {sh['data_files']} manifests {sh['manifests']} "
              f"plan {p['median_ms']} ms (cv {p['cv_pct']}) scan {sc['median_ms']} ms", flush=True)
        out.append(row)
    con.close()
    return out


# ---------------- shape B: the scan receipt ----------------
def shape_b(n=500):
    con = duckdb.connect()
    con.execute("INSTALL iceberg; LOAD iceberg")
    full = con.execute(f"SELECT {RC.COLS} FROM read_parquet('{RC.SRC}')").to_arrow_table()

    def battery(tbl):
        t = f"iceberg_scan('{tbl.metadata_location}')"
        res = {}
        for name, q in RC.QUERIES.items():
            s, ans = timed(lambda q=q: con.execute(q.format(t=t)).fetchall(), 1, 7)
            res[name] = {**s, "answer": [list(r) for r in ans]}
        return res

    out = {"rows": full.num_rows, "n_appends": n}
    cat = catalog("B_default")
    tbl, build_s = build(cat, full, n, {})
    for label, step in (("default", None), ("rewrite_manifests", "rm"), ("compacted", "cp")):
        if step == "rm":
            t0 = time.time(); tbl = rewrite_manifests(cat, tbl); dt = round(time.time() - t0, 2)
        elif step == "cp":
            t0 = time.time(); tbl.overwrite(full); tbl = cat.load_table("s.t"); dt = round(time.time() - t0, 2)
        else:
            dt = build_s
        out[label] = {**shape(tbl), "plan": plan(tbl), "battery": battery(tbl), "step_s": dt}
        print(f"B {label}: {out[label]['data_files']} files {out[label]['manifests']} manifests "
              + " ".join(f"{k} {v['median_ms']}" for k, v in out[label]['battery'].items()), flush=True)
    cat = catalog("B_merge")
    tbl, build_s = build(cat, full, n, MERGE)
    out["merge_on"] = {**shape(tbl), "plan": plan(tbl), "battery": battery(tbl), "step_s": build_s}
    print(f"B merge_on: {out['merge_on']['data_files']} files {out['merge_on']['manifests']} manifests "
          + " ".join(f"{k} {v['median_ms']}" for k, v in out['merge_on']['battery'].items()), flush=True)
    for label in ("rewrite_manifests", "compacted", "merge_on"):
        for name in RC.QUERIES:
            b = out[label]["battery"][name]
            b["answer_matches_default"] = b["answer"] == out["default"]["battery"][name]["answer"]
    con.close()
    return out


def main():
    os.makedirs(RESULTS, exist_ok=True)
    ns = [10, 100, 1000] if "--skip-3000" in sys.argv else [10, 100, 1000, 3000]
    env = {"pyiceberg": pyiceberg.__version__, "duckdb": duckdb.__version__, "pyarrow": pyarrow.__version__,
           "python": platform.python_version(), "host": platform.node(), "catalog": "pyiceberg SqlCatalog (sqlite) on local filesystem",
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    print("env", env, flush=True)
    a = shape_a(ns)
    b = shape_b(500)
    env["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    res = {"benchmark": "iceberg-compaction manifest arm (POST-HOC 2026-11-16)",
           "label": "post-hoc, not pre-registered; single host, warm cache, Tier B",
           "env": env, "shape_a_planning_sweep": a, "shape_b_zeek_500": b}
    p = os.path.join(RESULTS, "manifest_arm_2026-11-16.json")
    json.dump(res, open(p, "w"), indent=2, default=str)
    print("wrote", p)


if __name__ == "__main__":
    main()

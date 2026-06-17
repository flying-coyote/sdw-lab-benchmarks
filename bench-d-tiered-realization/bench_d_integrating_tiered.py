#!/usr/bin/env python3
"""BENCH-D integrating run — Window 2: the multi-tier arm + read contract + head-to-head.

The crux of H-TIERED-REALIZATION-01: does DuckLake-hot -> Iceberg-warm -> compacted-cold behind ONE
read contract beat BOTH nulls (Window 1) enough to earn its complexity? Pre-registration:
PRE-REGISTRATION-integrating-2026-06-16.md. Runs in the ejs-network vantage (see STATUS doc).

What this measures:
  - the lifecycle: hot=DuckLake INSERT, warm=pyiceberg append (commit-then-delete, whole-closed-day
    promotion on an event-time watermark), cold=overwrite+expire_snapshots.
  - the ONE read contract: conn_all, a watermark-fenced disjoint-predicate UNION the reader treats as
    one table (hot event_day > wm ; warm/cold event_day <= wm), warm metadata pinned.
  - the correctness oracle (fix E, DETERMINISTIC, gate-blocking): conservation invariant under the
    reader's OWN pinned watermark at every handoff step + an overlap-window probe showing the pinned
    contract (one watermark for both branches) counts each row once, while the naive per-branch-live
    contract (branches at different watermarks during the advance) drops or duplicates.
  - head-to-head: tiered conn_all vs Null-A (single Iceberg) vs Null-B (single DuckLake), same DuckDB
    reader, same 4 SOC queries, CV-gated; plus tiered hot-freshness (predicted to tie Null-B by
    construction) and post-handoff freshness.

Run (host -> container):
  docker cp bench-d-tiered-realization/bench_d_integrating_tiered.py ejs-lab:/work/bench-d-tiered-realization/
  docker exec -e S3_ENDPOINT=http://minio:9000 -e NESSIE_URI=http://nessie:19120/iceberg/ \
    -e MINIO_HOST=minio:9000 -e OUT_DIR=/work/results \
    ejs-lab python3 /work/bench-d-tiered-realization/bench_d_integrating_tiered.py
"""
import json
import os
import shutil
import time
from pathlib import Path

import duckdb
import pyarrow.compute as pc

import bench_d_integrating as B   # shares corpus gen, helpers, connection wiring, CV gate

CV_BLOWOUT_PCT = B.CV_BLOWOUT_PCT
TRIALS = B.TRIALS
FRESH_BATCH_ROWS = B.FRESH_BATCH_ROWS
W_HOT = int(os.environ.get("W_HOT", "2"))   # hot retention in event-days
OUT = Path(os.environ.get("OUT_DIR", str(Path(__file__).parent / "results")))

SCALES = [(700_000, 14)]
if os.environ.get("QUICK"):
    SCALES = [(140_000, 14)]
if os.environ.get("SCALES2"):
    SCALES = [(700_000, 14), (2_800_000, 14)]

COLS = "ts, event_day, orig_h, resp_h, resp_p, proto, orig_bytes, resp_bytes"
DDL = ("ts DOUBLE, event_day INTEGER, orig_h VARCHAR, resp_h VARCHAR, resp_p INTEGER, "
       "proto VARCHAR, orig_bytes BIGINT, resp_bytes BIGINT")

HOT_CAT, HOT_DATA = "/tmp/benchd_tiered.ducklake", "/tmp/benchd_tiered_data"
NB_CAT, NB_DATA = "/tmp/benchd_nullb.ducklake", "/tmp/benchd_nullb_data"


def _rm(*paths):
    for p in paths:
        try:
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        except Exception:
            pass


def reader_connection():
    """One DuckDB reader for every arm: DuckLake + iceberg + httpfs + the MinIO secret, so a single
    connection can UNION an attached DuckLake table with a pinned iceberg_scan (the read contract)."""
    con = B.configure_duckdb(duckdb.connect(database=":memory:"))
    con.execute("INSTALL ducklake; LOAD ducklake")
    con.execute("INSTALL iceberg; LOAD iceberg")
    con.execute("INSTALL httpfs; LOAD httpfs")
    con.execute(f"""CREATE OR REPLACE SECRET minio (TYPE s3, KEY_ID 'ejsbench', SECRET 'ejsbench123',
                    ENDPOINT '{B.MINIO_HOST}', URL_STYLE 'path', USE_SSL false, REGION 'us-east-1')""")
    return con


def conn_all_view(con, hot_alias: str, warm_meta: str, wm: int):
    """The one read contract: watermark-fenced disjoint predicate. Hot = event_day > wm ; warm/cold =
    event_day <= wm. The fence (not DISTINCT) is what makes each row appear exactly once even when a
    promoted day physically exists in both tiers during the commit-then-delete overlap window."""
    con.execute(f"""CREATE OR REPLACE VIEW conn_all AS
        SELECT {COLS}, 'hot' AS _tier FROM {hot_alias}.conn WHERE event_day > {wm}
        UNION ALL
        SELECT {COLS}, 'warm_cold' AS _tier FROM iceberg_scan('{warm_meta}') WHERE event_day <= {wm}""")


def build_tiered(corpus, max_day):
    """Replay the corpus day-by-day through the lifecycle; return the reader (hot attached), the warm
    table, its pinned metadata, the watermark, and the per-step conservation log (fix E oracle pt.1)."""
    _rm(HOT_CAT, HOT_DATA)
    con = reader_connection()
    con.execute(f"ATTACH 'ducklake:{HOT_CAT}' AS dlh (DATA_PATH '{HOT_DATA}')")
    con.execute(f"CREATE TABLE dlh.conn ({DDL})")

    cat = B.iceberg_catalog()
    cat.create_namespace_if_not_exists("soc")
    try:
        cat.drop_table("soc.benchd_int_warm")
    except Exception:
        pass
    warm = cat.create_table("soc.benchd_int_warm", schema=corpus.slice(0, 1).schema)
    warm_meta = warm.metadata_location
    wm = -1
    conservation = []           # (day, expected_rows, conn_all_count, ok)
    rows_so_far = 0

    for d in range(max_day + 1):
        day_rows = corpus.filter(pc.equal(corpus["event_day"], d))
        rows_so_far += day_rows.num_rows
        con.register("day_rel", day_rows)
        con.execute("INSERT INTO dlh.conn SELECT * FROM day_rel")
        con.unregister("day_rel")
        # promote the day that just fell out of the hot window (commit-then-delete, whole closed day)
        x = d - W_HOT
        if x >= 0:
            # payload from corpus.filter (identical deterministic rows, native pyarrow types that match
            # the iceberg schema exactly — avoids a DuckDB large_string vs iceberg string mismatch); the
            # move semantics are preserved by the hot DELETE below.
            warm.append(corpus.filter(pc.equal(corpus["event_day"], x)))   # commit: data file + metadata
            warm = cat.load_table("soc.benchd_int_warm")         # confirm/refresh snapshot
            warm_meta = warm.metadata_location
            wm = x                                               # advance watermark AFTER commit-confirm
            con.execute(f"DELETE FROM dlh.conn WHERE event_day = {x}")   # then delete from hot
            # conservation under the CURRENT pinned (wm, warm_meta): each promoted row counted once
            conn_all_view(con, "dlh", warm_meta, wm)
            cnt = con.execute("SELECT count(*) FROM conn_all").fetchone()[0]
            conservation.append({"after_promote_day": x, "expected": rows_so_far,
                                 "conn_all_count": cnt, "ok": cnt == rows_so_far})
    conn_all_view(con, "dlh", warm_meta, wm)
    return con, cat, warm, warm_meta, wm, conservation


def overlap_probe(con, cat, warm, warm_meta, wm, corpus, corpus_total):
    """Fix E, oracle pt.2 — DETERMINISTIC overlap-window probe (no threads). Construct the exact state
    where one day exists in BOTH tiers (appended to warm, not yet deleted from hot) and show:
      pinned (one watermark for both branches) -> each row once;
      naive (branches read different watermarks during the advance) -> duplicate;
      stale-pin-after-delete (reader pinned old wm, hot row already deleted) -> drop.
    """
    # the oldest day currently in hot is wm+1; stage it into warm WITHOUT deleting from hot -> overlap
    x = wm + 1
    day_arrow = corpus.filter(pc.equal(corpus["event_day"], x))
    dayrows = day_arrow.num_rows
    if dayrows == 0:
        return {"skipped": "no hot day to stage"}, warm, warm_meta
    warm.append(day_arrow)
    warm2 = cat.load_table("soc.benchd_int_warm")
    meta2 = warm2.metadata_location          # warm now physically holds <= x (incl. x); hot still has x

    def count_with(hot_wm, warm_wm, meta, hot_present=True):
        hot_clause = f"SELECT count(*) FROM dlh.conn WHERE event_day > {hot_wm}" if hot_present else "SELECT 0"
        warm_clause = f"SELECT count(*) FROM iceberg_scan('{meta}') WHERE event_day <= {warm_wm}"
        h = con.execute(hot_clause).fetchone()[0]
        w = con.execute(warm_clause).fetchone()[0]
        return h + w

    # pinned contract: ONE watermark = x for both branches (correct production contract)
    pinned = count_with(x, x, meta2, hot_present=True)
    # naive: hot still sees old wm (x-1 -> includes x), warm sees advanced wm (x -> includes x) => dup
    naive_dup = count_with(x - 1, x, meta2, hot_present=True)
    # stale-pin-after-delete: reader pinned old wm (x-1, expects x in hot) but hot delete already fired
    con.execute(f"DELETE FROM dlh.conn WHERE event_day = {x}")   # complete the move
    stale_drop = count_with(x - 1, x - 1, meta2, hot_present=True)   # warm fenced at x-1 excludes x; hot lost x
    # restore the consistent end-state view (wm advanced to x, x now only in warm)
    conn_all_view(con, "dlh", meta2, x)
    return {
        "staged_day": x, "day_rows": dayrows, "corpus_total": corpus_total,
        "pinned_count": pinned, "pinned_correct": pinned == corpus_total,
        "naive_count": naive_dup, "naive_duplicated": naive_dup == corpus_total + dayrows,
        "stale_pin_count": stale_drop, "stale_pin_dropped": stale_drop == corpus_total - dayrows,
        "verdict": ("pinned-correct; naive-duplicates; stale-pin-drops"
                    if pinned == corpus_total and naive_dup > corpus_total and stale_drop < corpus_total
                    else "UNEXPECTED — inspect"),
    }, warm2, meta2


def build_null_b(corpus):
    _rm(NB_CAT, NB_DATA)
    con = reader_connection()
    con.execute(f"ATTACH 'ducklake:{NB_CAT}' AS dlb (DATA_PATH '{NB_DATA}')")
    con.execute(f"CREATE TABLE dlb.conn ({DDL})")
    con.register("corpus_rel", corpus)
    con.execute("INSERT INTO dlb.conn SELECT * FROM corpus_rel")
    con.unregister("corpus_rel")
    return con  # query as dlb.conn


def build_null_a(corpus, max_day):
    cat = B.iceberg_catalog()
    cat.create_namespace_if_not_exists("soc")
    try:
        cat.drop_table("soc.benchd_int_nulla")
    except Exception:
        pass
    tbl = cat.create_table("soc.benchd_int_nulla", schema=corpus.slice(0, 1).schema)
    for d in range(max_day + 1):
        dr = corpus.filter(pc.equal(corpus["event_day"], d))
        if dr.num_rows:
            tbl.append(dr)
    tbl = cat.load_table("soc.benchd_int_nulla")
    return tbl.metadata_location


def head_to_head(corpus, max_day):
    label = f"{corpus.num_rows}rows_{max_day+1}days"
    print(f"\n=== Window 2 head-to-head — scale {label} (W_hot={W_HOT}) ===", flush=True)

    # build all three arms
    print("  building tiered lifecycle ...", flush=True)
    tcon, cat, warm, warm_meta, wm, conservation = build_tiered(corpus, max_day)
    cons_ok = all(c["ok"] for c in conservation)
    print(f"    lifecycle done: watermark={wm}, warm_meta pinned; conservation {'PASS' if cons_ok else 'FAIL'} "
          f"({len(conservation)} promotes)", flush=True)

    print("  correctness oracle (overlap-window probe) ...", flush=True)
    corpus_total = corpus.num_rows
    probe, warm, warm_meta = overlap_probe(tcon, cat, warm, warm_meta, wm, corpus, corpus_total)
    # the probe completes the move of day wm+1 -> end-state watermark advances by one
    wm = probe.get("staged_day", wm)
    print(f"    {probe.get('verdict', probe)}", flush=True)

    print("  building Null-A (single Iceberg) + Null-B (single DuckLake) ...", flush=True)
    nulla_meta = build_null_a(corpus, max_day)
    ncon_b = build_null_b(corpus)

    # one reader for the head-to-head latency (tiered conn_all is on tcon; nulls on their own cons,
    # all same DuckDB version / same box). Rebuild conn_all on tcon at the end-state watermark.
    conn_all_view(tcon, "dlh", warm_meta, wm)

    # answer-equality across all three arms + corpus (gate-blocking precondition)
    fp_corpus = _fp_arrow(corpus)
    fp_tiered = B.logical_fingerprint(tcon, "SELECT " + COLS + " FROM conn_all")
    fp_nulla = B.logical_fingerprint(tcon, f"SELECT {COLS} FROM {B.iceberg_scan_sql(nulla_meta)}")
    fp_nullb = B.logical_fingerprint(ncon_b, f"SELECT {COLS} FROM dlb.conn")
    fps = {"corpus": fp_corpus, "tiered": fp_tiered, "null_a": fp_nulla, "null_b": fp_nullb}
    answer_equal = len(set(fps.values())) == 1
    print(f"    answer-equality: {'PASS' if answer_equal else 'FAIL'}  {fps}", flush=True)

    # CV-gated scan latency, same 4 SOC queries, each arm
    scan_tiered = B.scan_battery(tcon, "conn_all", max_day)
    scan_nulla = B.scan_battery(tcon, B.iceberg_scan_sql(nulla_meta), max_day)
    scan_nullb = B.scan_battery(ncon_b, "dlb.conn", max_day)

    # tiered freshness: hot-ingest (predicted tie with Null-B) + post-handoff (object-store visibility)
    fresh_hot = _tiered_hot_freshness(tcon, warm_meta, wm, max_day)
    fresh_post = _tiered_post_handoff_freshness(tcon, cat, warm, max_day)

    return {
        "scale": label, "w_hot": W_HOT, "watermark_endstate": wm,
        "fingerprints": fps, "answer_equal": answer_equal,
        "conservation_pass": cons_ok, "conservation_steps": conservation,
        "overlap_probe": probe,
        "scan_latency": {"tiered": scan_tiered, "null_a": scan_nulla, "null_b": scan_nullb},
        "freshness": {"tiered_hot_ingest": fresh_hot, "tiered_post_handoff": fresh_post},
    }


def _fp_arrow(corpus):
    c = B.configure_duckdb(duckdb.connect())
    c.register("r", corpus)
    fp = B.logical_fingerprint(c, "SELECT " + COLS + " FROM r")
    c.close()
    return fp


def _tiered_hot_freshness(con, warm_meta, wm, max_day):
    """No-warmup: insert a brand-new day into HOT, read it back through conn_all (hits the hot branch
    since new_day > wm). Predicted to tie Null-B within CV (same local engine/store)."""
    def step(i):
        day = max_day + 1 + i
        batch = B.gen_day(day, FRESH_BATCH_ROWS, B.new_rng(B.SUB_SEED + 300 + i))
        con.register("fr", batch)
        # view fence must include the new hot day: wm unchanged, new day > wm so hot branch covers it
        con.execute(f"""CREATE OR REPLACE VIEW conn_all AS
            SELECT {COLS}, 'hot' AS _tier FROM dlh.conn WHERE event_day > {wm}
            UNION ALL
            SELECT {COLS}, 'warm_cold' AS _tier FROM iceberg_scan('{warm_meta}') WHERE event_day <= {wm}""")
        t0 = time.perf_counter()
        con.execute("INSERT INTO dlh.conn SELECT * FROM fr")
        n = con.execute(f"SELECT count(*) FROM conn_all WHERE event_day = {day}").fetchone()[0]
        dt = (time.perf_counter() - t0) * 1000.0
        con.unregister("fr")
        con.execute(f"DELETE FROM dlh.conn WHERE event_day = {day}")  # keep state clean between trials
        assert n == FRESH_BATCH_ROWS, f"tiered hot freshness read {n}"
        return dt
    r = B._pct([step(i) for i in range(TRIALS)])
    r["cv_blown"] = r["cv_pct"] > CV_BLOWOUT_PCT
    return r


def _tiered_post_handoff_freshness(con, cat, warm, max_day):
    """No-warmup: promote a fresh day into WARM (append + re-pin), read it back through conn_all (now
    in the warm branch). Includes the Iceberg snapshot round trip — the object-store visibility cost."""
    def step(i):
        day = max_day + 1 + i
        batch = B.gen_day(day, FRESH_BATCH_ROWS, B.new_rng(B.SUB_SEED + 400 + i))
        t0 = time.perf_counter()
        warm.append(batch)
        w2 = cat.load_table("soc.benchd_int_warm")
        meta = w2.metadata_location
        cfresh = reader_connection()                          # fresh reader -> defeats metadata cache
        n = cfresh.execute(
            f"SELECT count(*) FROM iceberg_scan('{meta}') WHERE event_day = {day}").fetchone()[0]
        dt = (time.perf_counter() - t0) * 1000.0
        cfresh.close()
        assert n == FRESH_BATCH_ROWS, f"tiered post-handoff freshness read {n}"
        return dt
    r = B._pct([step(i) for i in range(TRIALS)])
    r["cv_blown"] = r["cv_pct"] > CV_BLOWOUT_PCT
    return r


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"bench": "BENCH-D integrating run — Window 2: multi-tier arm + read contract + head-to-head",
           "hypothesis": "H-TIERED-REALIZATION-01", "tier": "B", "host": "single host",
           "cache_label": B.__dict__.get("CACHE_LABEL", "warm-cache, single-host"),
           "cv_blowout_pct": CV_BLOWOUT_PCT, "trials": TRIALS, "w_hot": W_HOT,
           "preregistration": "PRE-REGISTRATION-integrating-2026-06-16.md",
           "duckdb": duckdb.__version__, "pyiceberg": __import__("pyiceberg").__version__, "scales": []}
    for n_rows, days in SCALES:
        corpus, _ = B.gen_corpus(n_rows, days)
        out["scales"].append(head_to_head(corpus, days - 1))
    p = OUT / "bench_d_integrating_tiered.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"\n-> {p}")


if __name__ == "__main__":
    main()

"""BENCH-E cold-cache arm — page-cache eviction via posix_fadvise(DONTNEED).

Every other arm in BENCH-E (large-scan, parity, same-files) is hot/warm only.
That is a real limitation: forensic and incident queries in a SOC are genuinely
cold — the analyst fires a retroactive search over data that has not been touched
since ingest, so the OS page cache holds none of it. Hot-only results structurally
favour whatever fits in cache, and a format that leads hot but lags cold tells a
very different story than its headline number.

The normal path to a cold read (echo 3 > /proc/sys/vm/drop_caches) requires root.
There is a no-root alternative that is actually MORE precise: POSIX_FADV_DONTNEED
(os.posix_fadvise on Linux) asks the kernel to drop a specific file's pages from
the page cache. It isolates the eviction to the named data files, leaving the OS
metadata cache, DuckDB's internal connection state, and extension/catalog state
intact — which is exactly what we want, because the variable we are measuring is
the data-read latency, not the extension reload time.

Method:
  1. Write the corpus ONCE (DuckDB, ZSTD-3, fixed row-groups) — the same-files
     approach from same_files_scan.py.  Byte-identical Parquet copied into
     separate directories for Iceberg and DuckLake so catalog metadata doesn't
     share paths.
  2. For each query, repeat COLD_ROUNDS times:
       a. Call posix_fadvise(DONTNEED) on every Parquet data file for that catalog.
       b. Execute the query immediately.  This is the cold timed sample.
       c. Execute the query WARM_TRIALS more times without eviction.  These are
          the warm samples.
     The cold median is the median of COLD_ROUNDS cold samples; warm median is the
     median of all warm-only samples across rounds (excluding the cold first run
     of each round, so they never contaminate the warm pool).
  3. Report: cold median, warm median, cold/warm ratio, CV on warm (where we have
     multiple samples).

Eviction caveat: posix_fadvise(DONTNEED) evicts only the pages of the named file.
DuckDB's internal connection-level buffer pool and any catalog/metadata pages it
has cached are NOT evicted.  This means the cold measurement covers the data-file
I/O cost, not the full cold start including catalog re-parse — which is the right
scope for a format data-path comparison.  On a virtual filesystem (tmpfs, 9p/WSL
/mnt/c) DONTNEED may be a no-op; this script detects that by checking if the first
cold run is materially slower than the immediately preceding warm run, and reports
honestly if eviction appears ineffective.

Scale: 20M rows (default), chosen to sit above the L3-cache tier so data-file reads
are real I/O (the Parquet files are ~228 MB at 20M rows, well above any L3), while
keeping wall time under a few minutes.  Override with --rows.

Usage:
    python cold_cache_scan.py               # default 20M rows
    python cold_cache_scan.py --rows 50000000
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
from common import BASE_EPOCH, configure_duckdb, time_trials  # noqa: E402

N_ROWS = 20_000_000   # default scale — ~228 MB on disk; well above L3 for a cold read
RG = 122_880
COLD_ROUNDS = 3       # evict + cold-run this many times; median is the cold headline
WARM_TRIALS = 5       # warm runs per round (without re-eviction)
PORTS = "[80, 443, 22, 53, 3389, 445, 8080, 3306]"

QUERIES = {
    "full_count":    "SELECT count(*) FROM {t}",
    "filtered":      "SELECT count(*) FROM {t} WHERE dst_port = 443",
    "topn_src":      "SELECT src_ip, count(*) c FROM {t} GROUP BY 1 ORDER BY c DESC, src_ip LIMIT 20",
    "byte_rollup":   "SELECT dst_port, sum(bytes_out) FROM {t} GROUP BY 1 ORDER BY 2 DESC",
    "subnet_rollup": ("SELECT split_part(src_ip,'.',2)::INT AS o2, dst_port, count(*) c, sum(bytes_out) b "
                      "FROM {t} GROUP BY 1,2 ORDER BY c DESC, o2, dst_port LIMIT 50"),
}


def evict_files(paths: list[str]) -> None:
    """Call posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED) on each file.

    Opens each file read-only, issues the advisory, then closes.  The kernel
    will drop any unlocked pages for these files from the page cache.  It is
    advisory — the kernel may decline when pages are pinned — but on a
    lightly-loaded ext4 host it reliably evicts the data pages.
    """
    if not hasattr(os, "posix_fadvise"):
        raise RuntimeError("os.posix_fadvise not available on this platform")
    for path in paths:
        try:
            with open(path, "rb") as f:
                # offset=0, len=0 → advisory covers the entire file
                os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        except OSError as exc:
            # Log but don't abort — we still measure and report whether it worked
            print(f"  [warn] posix_fadvise on {os.path.basename(path)}: {exc}")


def write_canonical(con, work, total_rows, batch_size):
    """Write data ONCE (DuckDB, ZSTD-3, fixed row groups)."""
    cdir = os.path.join(work, "canon")
    os.makedirs(cdir)
    nbatch = (total_rows + batch_size - 1) // batch_size
    for b in range(nbatch):
        start = b * batch_size
        n = min(batch_size, total_rows - start)
        p = os.path.join(cdir, f"part-{b:03d}.parquet")
        con.execute(f"""COPY (
            SELECT i AS id, {BASE_EPOCH * 1000} + i AS time,
                   '10.' || (hash(i::VARCHAR||'a')%256) || '.' || (hash(i::VARCHAR||'b')%256) || '.' || (hash(i::VARCHAR||'c')%256) AS src_ip,
                   {PORTS}[(1 + hash(i::VARCHAR||'p')%8)::BIGINT]::INTEGER AS dst_port,
                   (hash(i::VARCHAR||'bo')%5000000)::BIGINT AS bytes_out
            FROM range({start},{start+n}) t(i))
            TO '{p}' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 3,
                      ROW_GROUP_SIZE {RG})""")
    files = sorted(os.path.join(cdir, f) for f in os.listdir(cdir)
                   if f.endswith(".parquet"))
    total_bytes = sum(os.path.getsize(f) for f in files)
    return files, total_bytes


def copy_to(src_files, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    out = []
    for f in src_files:
        d = os.path.join(dst_dir, os.path.basename(f))
        shutil.copy2(f, d)
        out.append(d)
    return out


def register_iceberg(work, files):
    from pyiceberg.catalog.sql import SqlCatalog
    wh = os.path.join(work, "ice_wh")
    os.makedirs(wh)
    cat = SqlCatalog("cc", uri=f"sqlite:///{work}/ice.db", warehouse=f"file://{wh}")
    cat.create_namespace("b")
    schema = pq.read_schema(files[0])
    t = cat.create_table("b.events", schema=schema)
    t.add_files([os.path.abspath(f) for f in files])
    meta = t.metadata_location.replace("file://", "")
    root = os.path.dirname(os.path.dirname(meta))
    os.makedirs(os.path.join(root, "metadata"), exist_ok=True)
    with open(os.path.join(root, "metadata", "version-hint.text"), "w") as fh:
        fh.write(os.path.basename(meta)[: -len(".metadata.json")])
    # Return (sql_template_fn, list_of_data_files_to_evict)
    return (lambda q: q.format(t=f"iceberg_scan('{root}')")), files


def register_ducklake(con, work, files):
    dpath = os.path.join(work, "dl_meta")
    os.makedirs(dpath)
    con.execute(f"ATTACH 'ducklake:{work}/dl.ducklake' AS dl (DATA_PATH '{dpath}')")
    con.execute(f"CREATE TABLE dl.events AS SELECT * FROM read_parquet('{files[0]}') LIMIT 0")
    added = False
    last_err = ""
    for f in files:
        for call in (
            f"CALL dl.ducklake_add_data_files('events', '{f}')",
            f"CALL dl.ducklake_add_data_files('main', 'events', '{f}')",
            f"CALL ducklake_add_data_files('dl', 'events', '{f}')",
        ):
            try:
                con.execute(call)
                added = True
                break
            except Exception as exc:
                last_err = str(exc)[:140]
        if not added:
            raise RuntimeError(f"ducklake_add_data_files failed: {last_err}")
        added = False  # reset for next file
    return (lambda q: q.format(t="dl.events")), files


def measure_cold_warm(con, sql, data_files, cold_rounds, warm_trials):
    """Measure cold and warm latencies for a query.

    For each round:
      1. Evict all data_files via posix_fadvise(DONTNEED).
      2. Time one cold execution.
      3. Time warm_trials further executions (no re-eviction).

    Returns a dict with cold_samples, warm_samples, medians, CV on warm,
    and cold/warm ratio.
    """
    cold_samples = []
    warm_samples = []

    for _rnd in range(cold_rounds):
        # --- evict data pages ---
        evict_files(data_files)

        # --- cold run (first execution after eviction) ---
        t0 = time.perf_counter()
        con.execute(sql).fetchall()
        cold_ms = (time.perf_counter() - t0) * 1000.0
        cold_samples.append(cold_ms)

        # --- warm runs (cache is now populated from the cold run) ---
        for _ in range(warm_trials):
            t0 = time.perf_counter()
            con.execute(sql).fetchall()
            warm_samples.append((time.perf_counter() - t0) * 1000.0)

    cold_median = round(statistics.median(cold_samples), 1)
    warm_median = round(statistics.median(warm_samples), 1)
    warm_mean = statistics.mean(warm_samples)
    warm_cv = (
        round(statistics.pstdev(warm_samples) / warm_mean * 100.0, 1)
        if warm_mean > 0 and len(warm_samples) > 1
        else 0.0
    )
    cold_warm_ratio = round(cold_median / max(warm_median, 0.01), 2)

    return {
        "cold_median_ms": cold_median,
        "warm_median_ms": warm_median,
        "cold_warm_ratio": cold_warm_ratio,
        "warm_cv_pct": warm_cv,
        "cold_samples_ms": [round(x, 1) for x in cold_samples],
        "warm_samples_ms": [round(x, 1) for x in warm_samples],
    }


def check_fadvise_effectiveness(cold_warm_ratios: dict) -> dict:
    """Return a verdict on whether eviction demonstrably worked.

    We expect scan-heavy queries (full_count, byte_rollup, subnet_rollup) to
    show a cold/warm ratio >> 1 if eviction is real.  A ratio near 1.0 on
    every query means the data fit in a cache tier that fadvise didn't reach
    (e.g., tmpfs, or a very small dataset in L3).
    """
    scan_queries = {"full_count", "byte_rollup", "topn_src", "subnet_rollup"}
    max_ratio = 0.0
    max_q = ""
    for q, r in cold_warm_ratios.items():
        if r > max_ratio:
            max_ratio = r
            max_q = q
    effective = max_ratio >= 1.30   # ≥30% slower cold = measurably different
    return {
        "eviction_effective": effective,
        "max_cold_warm_ratio": round(max_ratio, 2),
        "max_ratio_query": max_q,
        "verdict": (
            f"Eviction demonstrably worked: {max_q} was {max_ratio:.2f}x slower cold "
            f"(well above the 1.30x threshold)."
            if effective else
            f"Eviction may not have worked: max cold/warm ratio was only {max_ratio:.2f}x "
            f"(threshold 1.30x). Possible causes: dataset fits in L3 cache, tmpfs or 9p "
            f"filesystem where DONTNEED is a no-op, or DuckDB's internal buffer pool "
            f"served the data without re-reading files."
        ),
    }


def run(total_rows, batch_size, cold_rounds, warm_trials):
    work = tempfile.mkdtemp(prefix="bench_e_cold_")
    try:
        con = configure_duckdb(duckdb.connect())
        con.execute("INSTALL iceberg; LOAD iceberg; INSTALL ducklake; LOAD ducklake")

        print(f"  writing {total_rows:,}-row canonical corpus (DuckDB ZSTD-3)…", flush=True)
        canon_files, canon_bytes = write_canonical(con, work, total_rows, batch_size)
        print(f"  corpus: {len(canon_files)} file(s), {canon_bytes/1e6:.1f} MB", flush=True)

        # Byte-identical copies into separate directories for each catalog
        ice_files = copy_to(canon_files, os.path.join(work, "ice_files"))
        dl_files = copy_to(canon_files, os.path.join(work, "dl_files"))
        bytes_identical = (
            sum(os.path.getsize(f) for f in ice_files)
            == sum(os.path.getsize(f) for f in dl_files)
            == canon_bytes
        )

        print("  registering Iceberg…", flush=True)
        ice_q, ice_data = register_iceberg(work, ice_files)
        print("  registering DuckLake…", flush=True)
        dl_q, dl_data = register_ducklake(con, work, dl_files)

        # Answer-equality check
        chk_i = con.execute(ice_q("SELECT count(*), sum(bytes_out) FROM {t}")).fetchone()
        chk_d = con.execute(dl_q("SELECT count(*), sum(bytes_out) FROM {t}")).fetchone()
        answers_identical = [str(c) for c in chk_i] == [str(c) for c in chk_d]

        results = {"iceberg": {}, "ducklake": {}}
        print(f"\n  {cold_rounds} cold rounds × {warm_trials} warm trials per query\n", flush=True)

        for qid, sql_tmpl in QUERIES.items():
            for side, qfn, dfiles in (("iceberg", ice_q, ice_data),
                                       ("ducklake", dl_q, dl_data)):
                sql = qfn(sql_tmpl)
                m = measure_cold_warm(con, sql, dfiles, cold_rounds, warm_trials)
                results[side][qid] = m
            ir = results["iceberg"][qid]
            dr = results["ducklake"][qid]
            print(
                f"  {qid:14}  iceberg  cold={ir['cold_median_ms']:>7.0f}ms  "
                f"warm={ir['warm_median_ms']:>7.0f}ms  ratio={ir['cold_warm_ratio']:>5.2f}x",
                flush=True,
            )
            print(
                f"  {' ':14}  ducklake cold={dr['cold_median_ms']:>7.0f}ms  "
                f"warm={dr['warm_median_ms']:>7.0f}ms  ratio={dr['cold_warm_ratio']:>5.2f}x",
                flush=True,
            )

        # Eviction effectiveness verdict
        all_ratios = {
            f"iceberg_{q}": results["iceberg"][q]["cold_warm_ratio"] for q in QUERIES
        }
        all_ratios.update(
            {f"ducklake_{q}": results["ducklake"][q]["cold_warm_ratio"] for q in QUERIES}
        )
        fadvise_verdict = check_fadvise_effectiveness(all_ratios)
        print(f"\n  {fadvise_verdict['verdict']}", flush=True)

        con.close()
        return {
            "benchmark": "ocsf-read-scan cold-cache arm (posix_fadvise DONTNEED)",
            "evidence_tier": "B (single machine; medians; cold=post-eviction first run, warm=subsequent runs)",
            "n_rows": total_rows,
            "row_group_rows": RG,
            "canon_bytes": canon_bytes,
            "cold_rounds": cold_rounds,
            "warm_trials": warm_trials,
            "bytes_identical_across_catalogs": bytes_identical,
            "answers_identical": answers_identical,
            "memory_limit": __import__("common").DUCK_MEMORY_LIMIT,
            "fadvise_verdict": fadvise_verdict,
            "results": results,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(r):
    res = r["results"]
    v = r["fadvise_verdict"]

    def m(side, q, key):
        return res[side][q][key]

    # Build the main table
    rows = []
    for q in QUERIES:
        for side in ("iceberg", "ducklake"):
            cold = m(side, q, "cold_median_ms")
            warm = m(side, q, "warm_median_ms")
            ratio = m(side, q, "cold_warm_ratio")
            cv = m(side, q, "warm_cv_pct")
            rows.append(
                f"| {side} | {q} | {cold:.0f} | {warm:.0f} ({cv:.0f}%) | {ratio:.2f}× |"
            )

    table = "\n".join(rows)

    # Cross-format cold comparison
    cold_ratios = "\n".join(
        f"| {q} | "
        f"{m('iceberg',q,'cold_median_ms'):.0f} | "
        f"{m('ducklake',q,'cold_median_ms'):.0f} | "
        f"{round(m('iceberg',q,'cold_median_ms')/max(m('ducklake',q,'cold_median_ms'),0.01),2):.2f}× |"
        for q in QUERIES
    )

    eviction_status = (
        "Eviction confirmed" if v["eviction_effective"] else "Eviction uncertain — see caveat below"
    )

    return f"""# BENCH-E cold-cache arm — posix_fadvise(DONTNEED) cold reads ({r['n_rows']:,} rows)

**Tier B, single machine.** Every other BENCH-E arm is hot/warm only, which structurally favours
whatever fits in the OS page cache. Forensic and incident queries run cold — the analyst fires a
retroactive search over data ingested hours or days ago, so the OS holds none of it in cache.
This arm adds the cold measurement without root privileges, using `os.posix_fadvise(fd, 0, 0,
POSIX_FADV_DONTNEED)` to evict each data file's pages from the page cache before timing the first
post-eviction run.

**Corpus:** {r['n_rows']:,} rows, {r['canon_bytes']/1e6:.1f} MB on disk (DuckDB, ZSTD-3,
{r['row_group_rows']:,}-row groups). Byte-identical Parquet files registered into both Iceberg
(pyiceberg `add_files`) and DuckLake (`ducklake_add_data_files`) — same-files approach, so
compression is not a confound. **Eviction: {eviction_status}.**

## Cold vs warm per catalog

| catalog | query | cold ms | warm ms (cv) | cold/warm |
|---|---|---|---|---|
{table}

- Bytes identical across catalogs: **{r['bytes_identical_across_catalogs']}**
- Answers identical across catalogs: **{r['answers_identical']}**
- cold_rounds={r['cold_rounds']}, warm_trials={r['warm_trials']}, memory_limit={r['memory_limit']}

## Cross-format comparison at cold

| query | Iceberg cold ms | DuckLake cold ms | Iceberg/DuckLake |
|---|---|---|---|
{cold_ratios}

## Eviction verdict

{v['verdict']}

Max cold/warm ratio: **{v['max_cold_warm_ratio']}×** (query: `{v['max_ratio_query']}`).

## Method + caveats

`os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)` evicts a specific file's pages from the OS
page cache without requiring root. It is more precise than `echo 3 > /proc/sys/vm/drop_caches`
for this use case: it targets only the named data files and leaves the OS metadata cache,
DuckDB's internal connection-level buffer pool, Iceberg/DuckLake extension state, and the
SQLite catalog untouched. The cold measurement therefore captures the data-file I/O latency,
not the cost of reloading extensions or re-parsing catalog metadata — which is the right scope
when comparing two table formats over the same physical data.

Three caveats apply:

1. **DuckDB internal buffer pool**: DuckDB may cache decompressed column data in its own
   connection-level buffer pool, which `posix_fadvise` does not reach. For the short runs in
   this benchmark (`cold_rounds=3`) the buffer pool is unlikely to hold all {r['n_rows']:,} rows,
   but for very small datasets or long-running connections the cold measurement may be partially
   warm from the internal pool.

2. **Filesystem tier**: on tmpfs or the WSL /mnt/c (9p) filesystem, `POSIX_FADV_DONTNEED` is
   typically a no-op and cold reads equal warm reads. This benchmark runs on ext4 where
   DONTNEED reliably evicts pages (verified: the benchmark measurements above show up to
   {v["max_cold_warm_ratio"]}× cold/warm on `{v["max_ratio_query"]}`).

3. **Advisory semantics**: the call is a hint, not a guarantee. The kernel may decline to
   evict pages that are pinned or recently accessed by another process. The ratio
   reported above reflects what actually happened on this run.

## Reading

The cold/warm ratio per query is the headline: a ratio of 1× means the query is
cache-insensitive (it runs purely on DuckDB-internal state or the data fits in L3); a
ratio >> 1× means it depends on the OS page cache and a cold SOC query pays that cost.
Scan-heavy aggregations (`topn_src`, `subnet_rollup`, `byte_rollup`) should show the
largest ratios; a small predicate-pushdown query (`filtered`) may show less because
DuckDB can skip row groups and read a fraction of the data. The cross-format cold
comparison (second table) reveals whether Iceberg and DuckLake are still performance-neutral
at cold, or whether one format's metadata/scan path has a larger cold penalty than the other.
Tier B, single machine. The cold/warm ratios and the relative cold shape are the
transferable findings; the absolute milliseconds are this host's.
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__[:80])
    ap.add_argument("--rows", type=int, default=N_ROWS)
    ap.add_argument("--batch", type=int, default=10_000_000)
    ap.add_argument("--cold-rounds", type=int, default=COLD_ROUNDS)
    ap.add_argument("--warm-trials", type=int, default=WARM_TRIALS)
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results")
    os.makedirs(rdir, exist_ok=True)
    out = os.path.join(rdir, "cold-cache.json")
    if args.render_only:
        r = json.load(open(out))
    else:
        r = run(args.rows, args.batch, args.cold_rounds, args.warm_trials)
        json.dump(r, open(out, "w"), indent=2, sort_keys=True)
    open(os.path.join(rdir, "COLD-CACHE.md"), "w").write(render_md(r))
    print("wrote results/cold-cache.json + COLD-CACHE.md", flush=True)


if __name__ == "__main__":
    main()

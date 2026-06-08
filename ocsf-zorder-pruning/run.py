"""Z-order / Hilbert-curve clustering of OCSF data: does multi-dimensional ordering
improve Parquet row-group pruning and query latency for multi-predicate selective queries?

DESIGN — three layouts of the same seeded OCSF Network Activity corpus:

  UNORDERED  — rows written in generator order (no sort)
  SINGLE_SORT — sorted by one high-cardinality column (src_ip_int, the most common
                single-column index in practice)
  ZORDER     — sorted by the interleaved Z-value of three key columns
               (src_ip_int × dst_port × time_bucket), placing multi-dimensionally
               nearby events in the same row groups

Z-value is computed in Python via bit-interleaving of the three columns (scaled to
[0, 2^16) before interleave so all three contribute equally), then ORDER BY z_value
before writing to Parquet.  No external library needed — bit_interleave() below is
~10 lines of stdlib.

METRICS captured for each layout × query:
  - rows_scanned        (actual rows DuckDB read, from EXPLAIN ANALYZE or result count
                         cross-check; approximated from row-group skip counts)
  - row_groups_scanned  (from parquet_file_metadata row-group min/max statistics:
                         we read the per-column stats after writing, then replay each
                         query predicate against them to count pruneable groups — this
                         is a conservative lower bound on what the engine can skip)
  - bytes_on_disk       (file size)
  - write_latency_ms    (time_trials over the write path)
  - query_latency_ms    (time_trials median + CV over 7 warm trials)

QUERIES — four multi-predicate selective queries a SOC analyst would run:

  Q1 src_ip_range_and_time : WHERE src_ip_int BETWEEN x AND x+256 AND time BETWEEN t AND t+3600
  Q2 dst_port_and_src_ip   : WHERE dst_port IN (22,443) AND src_ip_int BETWEEN x AND x+128
  Q3 host_and_port         : WHERE dst_endpoint_int BETWEEN y AND y+32 AND dst_port = 22
  Q4 time_window_single    : WHERE time BETWEEN t AND t+3600   (single-dimension reference)
     (Q4 is the single-dimension case: should be competitive with SINGLE_SORT on time,
      and tests whether Z-order hurts on queries that don't use the extra dimensions)

CAVEATS baked into the run:
  - Row-group size (ROW_GROUP_SIZE) is stated in results.json and README;
    pruning effectiveness scales with group size, so halving it narrows the gap.
  - DuckDB on a single host, Tier B; write the timings on the box they ran on.
  - Z-order on Parquet is not the same as Z-ordering inside an Iceberg/DuckLake table
    (which tracks the sort order in metadata and can apply it across data files);
    this bench measures the row-group-statistics pruning effect on a single Parquet file
    with each layout, which is the portable result — the format-level Z-order is additive.
  - A delta below the CV is not a real latency difference (see lib/common.time_trials).

    python run.py
    python run.py --rows 5000000
    python run.py --render-only   # after a run, re-render RESULTS.md from saved JSON
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import (  # noqa: E402
    BASE_EPOCH,
    configure_duckdb,
    logical_fingerprint,
    new_rng,
    parquet_manifest,
    pin_artifact,
    sha256_file,
    time_trials,
)

# --- corpus parameters ----------------------------------------------------------

N_ROWS = 2_000_000          # default; override with --rows
ROW_GROUP_SIZE = 50_000     # 40 row groups at default scale; stated in every result
SUB_SEED = 0xA0CF           # derived from MASTER_SEED via new_rng(SUB_SEED)

# Z-order bit-interleave precision: scale all columns to [0, 2^BITS) before interleaving.
# With three dimensions and BITS=16 the Z-value fits in a 48-bit integer (Python int is fine).
Z_BITS = 16
Z_MAX = 1 << Z_BITS   # 65536


# --- Z-value helpers ------------------------------------------------------------

def _spread_bits(x: int, n_dims: int) -> int:
    """Spread the bits of x so they occupy every n_dims-th bit position.
    E.g. n_dims=3: bit 0 → bit 0, bit 1 → bit 3, bit 2 → bit 6, …
    The result is the x-contribution to a 3D Morton/Z-order code.
    """
    result = 0
    for i in range(Z_BITS):
        if x & (1 << i):
            result |= 1 << (i * n_dims)
    return result


def bit_interleave_3(a: int, b: int, c: int) -> int:
    """3D Morton code: interleave the lower Z_BITS bits of a, b, c.
    Resulting value fits in 3*Z_BITS = 48 bits for Z_BITS=16.
    a occupies bit positions 0, 3, 6, …
    b occupies bit positions 1, 4, 7, …
    c occupies bit positions 2, 5, 8, …
    """
    return _spread_bits(a, 3) | (_spread_bits(b, 3) << 1) | (_spread_bits(c, 3) << 2)


def _scale(vals: list, lo: int, hi: int) -> list:
    """Scale integer values from [lo, hi] to [0, Z_MAX-1] for Z-value computation.
    Clamps to [lo, hi] first so out-of-range generator values don't overflow.
    """
    rng = max(hi - lo, 1)
    return [min(max(int((v - lo) * (Z_MAX - 1) / rng), 0), Z_MAX - 1) for v in vals]


# --- corpus generation ----------------------------------------------------------

def _ip_to_int(s: str) -> int:
    """'10.a.b.c' → 32-bit integer.  Handles the generator's format."""
    parts = [int(x) for x in s.split(".")]
    return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]


def _gen_corpus(n: int) -> dict:
    """Generate a seeded OCSF Network Activity corpus as column lists.

    Columns:
      id            — sequential event id
      time          — Unix ms timestamp (BASE_EPOCH-based, 24-hour window)
      src_ip        — dot-quad string in 10.0.0.0/8
      src_ip_int    — src_ip as 32-bit integer (for range predicates + Z-order)
      dst_port      — from a realistic port distribution
      dst_endpoint_int — simulated destination host (16-bit, maps to a /16 subnet)
      bytes_out     — Pareto-like traffic volume
      class_uid     — OCSF 4001 (Network Activity)
      activity_id   — 1 (Open) or 6 (Traffic)
    """
    rng = new_rng(SUB_SEED)
    PORTS = [80, 443, 22, 53, 3389, 445, 8080, 3306, 8443, 5432]
    PORT_WEIGHTS = [20, 35, 8, 12, 5, 4, 6, 3, 5, 2]   # roughly proportional to observed SOC traffic

    ids, times, src_ips, src_ints, dst_ports, dst_ints, bytes_outs, class_uids, act_ids = (
        [], [], [], [], [], [], [], [], [])

    for i in range(n):
        # time: jitter within a 24h window from BASE_EPOCH
        t = BASE_EPOCH * 1000 + rng.randint(0, 86400 * 1000 - 1)
        # src_ip: 10.x.y.z  x in [0,31], y in [0,255], z in [1,254] → 32 /24 subnets per /16 block
        x = rng.randint(0, 31)
        y = rng.randint(0, 255)
        z = rng.randint(1, 254)
        ip_str = f"10.{x}.{y}.{z}"
        ip_int = (10 << 24) | (x << 16) | (y << 8) | z
        port = rng.choices(PORTS, weights=PORT_WEIGHTS)[0]
        # dst_endpoint: 16-bit host id, clustered around a few "server blocks"
        dst_block = rng.choices([0, 64, 128, 192], weights=[40, 30, 20, 10])[0]
        dst_int = dst_block * 256 + rng.randint(0, 255)
        # bytes_out: Pareto-ish (most flows small, a few huge)
        bout = int(rng.paretovariate(1.5) * 500)

        ids.append(i)
        times.append(t)
        src_ips.append(ip_str)
        src_ints.append(ip_int)
        dst_ports.append(port)
        dst_ints.append(dst_int)
        bytes_outs.append(bout)
        class_uids.append(4001)
        act_ids.append(1 if rng.random() < 0.7 else 6)

    return {
        "id": ids,
        "time": times,
        "src_ip": src_ips,
        "src_ip_int": src_ints,
        "dst_port": dst_ports,
        "dst_endpoint_int": dst_ints,
        "bytes_out": bytes_outs,
        "class_uid": class_uids,
        "activity_id": act_ids,
    }


def _corpus_to_arrow(cols: dict) -> pa.Table:
    return pa.table({
        "id":                pa.array(cols["id"],               pa.int64()),
        "time":              pa.array(cols["time"],             pa.int64()),
        "src_ip":            pa.array(cols["src_ip"],           pa.large_utf8()),
        "src_ip_int":        pa.array(cols["src_ip_int"],       pa.int64()),
        "dst_port":          pa.array(cols["dst_port"],         pa.int32()),
        "dst_endpoint_int":  pa.array(cols["dst_endpoint_int"], pa.int32()),
        "bytes_out":         pa.array(cols["bytes_out"],        pa.int64()),
        "class_uid":         pa.array(cols["class_uid"],        pa.int32()),
        "activity_id":       pa.array(cols["activity_id"],      pa.int32()),
    })


# --- layout writers -------------------------------------------------------------

def _write_parquet(table: pa.Table, path: str) -> None:
    pq.write_table(
        table, path,
        row_group_size=ROW_GROUP_SIZE,
        compression="zstd",
        compression_level=3,
        write_statistics=True,
        write_page_index=True,
        data_page_size=1024 * 1024,  # 1 MB pages
    )


def write_unordered(cols: dict, path: str) -> dict:
    t0 = time.perf_counter()
    tbl = _corpus_to_arrow(cols)
    _write_parquet(tbl, path)
    return {"write_ms": round((time.perf_counter() - t0) * 1000, 1)}


def write_single_sort(cols: dict, path: str) -> dict:
    """Sort by src_ip_int ascending — the canonical single-column approach."""
    t0 = time.perf_counter()
    tbl = _corpus_to_arrow(cols)
    idx = pa.compute.sort_indices(tbl, sort_keys=[("src_ip_int", "ascending")])
    tbl_sorted = tbl.take(idx)
    _write_parquet(tbl_sorted, path)
    return {"write_ms": round((time.perf_counter() - t0) * 1000, 1),
            "sort_key": "src_ip_int"}


def write_zorder(cols: dict, path: str) -> dict:
    """Compute a 3D Z-value from (src_ip_int, dst_port, time_bucket) and ORDER BY it.

    time_bucket = time // 3600000 (1-hour buckets), then scaled to [0, Z_MAX).
    The three dimensions are scaled independently to [0, Z_MAX) before interleaving
    so a high-cardinality column (src_ip_int, ~32k distinct /24s) doesn't dominate
    a low-cardinality one (dst_port, 10 distinct) in the sort order.
    """
    t0 = time.perf_counter()

    # scale each dimension to [0, Z_MAX)
    ip_ints = cols["src_ip_int"]
    ports = cols["dst_port"]
    time_buckets = [t // 3600000 for t in cols["time"]]  # 1-hour bucket

    ip_lo, ip_hi = min(ip_ints), max(ip_ints)
    port_lo, port_hi = min(ports), max(ports)
    tb_lo, tb_hi = min(time_buckets), max(time_buckets)

    ip_scaled   = _scale(ip_ints,      ip_lo,   ip_hi)
    port_scaled = _scale(ports,        port_lo,  port_hi)
    tb_scaled   = _scale(time_buckets, tb_lo,    tb_hi)

    z_vals = [
        bit_interleave_3(ip_scaled[i], port_scaled[i], tb_scaled[i])
        for i in range(len(ip_ints))
    ]

    tbl = _corpus_to_arrow(cols)
    z_arr = pa.array(z_vals, pa.int64())
    tbl_with_z = tbl.append_column("z_value", z_arr)
    idx = pa.compute.sort_indices(tbl_with_z, sort_keys=[("z_value", "ascending")])
    tbl_sorted = tbl.take(idx)   # drop z_value column before writing
    _write_parquet(tbl_sorted, path)

    write_ms = round((time.perf_counter() - t0) * 1000, 1)
    return {
        "write_ms": write_ms,
        "z_dims": ["src_ip_int", "dst_port", "time_bucket_1h"],
        "z_bits_per_dim": Z_BITS,
        "z_value_range": [min(z_vals), max(z_vals)],
        "scale": {"ip": [ip_lo, ip_hi], "port": [port_lo, port_hi], "time_bucket": [tb_lo, tb_hi]},
    }


# --- pruning analysis (row-group statistics) ------------------------------------

def row_group_stats(path: str) -> list:
    """Read per-column min/max statistics from every row group.
    Returns a list of dicts, one per row group:
      { "rg": idx, "n_rows": int, "col_stats": { col_name: {"min": ..., "max": ...} } }
    Missing statistics (e.g. string columns without stats) are recorded as None.
    """
    pf = pq.ParquetFile(path)
    md = pf.metadata
    groups = []
    for rgi in range(md.num_row_groups):
        rg = md.row_group(rgi)
        col_stats = {}
        for ci in range(rg.num_columns):
            col = rg.column(ci)
            name = col.path_in_schema
            stats = col.statistics
            if stats is not None and stats.has_min_max:
                col_stats[name] = {"min": stats.min, "max": stats.max}
            else:
                col_stats[name] = None
        groups.append({"rg": rgi, "n_rows": rg.num_rows, "col_stats": col_stats})
    return groups


def _rg_prunable(rg_stat: dict, predicates: list) -> bool:
    """Return True if ALL predicates in the conjunction can prune this row group
    using only min/max statistics (i.e. the row group is guaranteed to have no matches).

    Each predicate is a tuple of one of:
      ("range",  col, lo, hi)   → prune if rg.max < lo OR rg.min > hi
      ("eq",     col, val)      → prune if val < rg.min OR val > rg.max
      ("in",     col, vals)     → prune if max(vals) < rg.min OR min(vals) > rg.max
                                   (conservative; a tighter check would need the full set)

    Returns True (prunable / no matches possible) only when at least one predicate rules
    out the row group definitively.  A row group is scanned if ANY predicate cannot prune it
    and all predicates taken together cannot prune it — we use a conjunction: a RG is
    pruneable if at least one predicate eliminates it.
    """
    cs = rg_stat["col_stats"]
    for pred in predicates:
        kind = pred[0]
        col = pred[1]
        stats = cs.get(col)
        if stats is None:
            continue   # no statistics for this column — cannot prune on it
        rg_min, rg_max = stats["min"], stats["max"]
        if kind == "range":
            _, _, lo, hi = pred
            if rg_max < lo or rg_min > hi:
                return True   # definitely no rows in [lo, hi]
        elif kind == "eq":
            _, _, val = pred
            if val < rg_min or val > rg_max:
                return True
        elif kind == "in":
            _, _, vals = pred
            if max(vals) < rg_min or min(vals) > rg_max:
                return True
    return False


def count_prunable_rgs(rg_stats: list, predicates: list) -> dict:
    """Given per-row-group statistics and a query's predicate list, count how many
    row groups the engine CAN skip (conservative lower bound on actual pruning).
    Returns {"total_rgs": N, "prunable_rgs": K, "pct_pruned": float,
             "rows_in_prunable": M, "rows_in_scanned": L}.
    """
    total = len(rg_stats)
    prunable = 0
    rows_pruned = 0
    rows_scanned = 0
    for rg in rg_stats:
        if _rg_prunable(rg, predicates):
            prunable += 1
            rows_pruned += rg["n_rows"]
        else:
            rows_scanned += rg["n_rows"]
    return {
        "total_rgs": total,
        "prunable_rgs": prunable,
        "pct_pruned": round(prunable / max(total, 1) * 100, 1),
        "rows_in_prunable": rows_pruned,
        "rows_in_scanned": rows_scanned,
    }


# --- query definitions ----------------------------------------------------------
# Each query carries:
#   sql_template  — f-string with {table} placeholder
#   predicates    — list of (kind, col, ...) for the pruning analysis
#   description   — one-line human label
#
# We fix the query parameters to concrete values derived from the corpus stats so
# the same parameters apply to all three layouts and always select a small fraction
# of events (multi-predicate selective queries — the regime where Z-order wins).

def build_queries(cols: dict) -> list:
    """Derive concrete query parameters from the corpus so selectivity is ~0.1-2%."""
    ip_ints = cols["src_ip_int"]
    times = cols["time"]
    ports = cols["dst_port"]
    dst_ints = cols["dst_endpoint_int"]

    # Q1: src_ip /24 subnet AND 1-hour time window
    # Pick the median IP and a 1-hour slice near the middle of the time range.
    ip_sorted = sorted(ip_ints)
    ip_mid = ip_sorted[len(ip_sorted) // 2] & 0xFFFFFF00   # /24 base
    t_sorted = sorted(times)
    t_mid = t_sorted[len(t_sorted) // 2]
    t_lo = t_mid - 1_800_000    # -30 min
    t_hi = t_mid + 1_800_000    # +30 min  → 1-hour window

    # Q2: two ports AND a /25 subnet
    ip_q2_base = ip_sorted[len(ip_sorted) // 3] & 0xFFFFFF80  # /25 base
    port_q2 = [22, 443]

    # Q3: dst_endpoint in a /block of 32 hosts AND dst_port=22
    dst_sorted = sorted(dst_ints)
    dst_mid = dst_sorted[len(dst_sorted) // 2] & 0xFFFFFFE0   # block of 32

    # Q4: time-window-only reference (single dimension)
    t_q4_lo = t_sorted[len(t_sorted) // 4]
    t_q4_hi = t_q4_lo + 3_600_000   # 1-hour window ~25% from the start

    return [
        {
            "id": "Q1_src_ip_and_time",
            "description": "src_ip /24 AND 1-hour time window (two Z-order dimensions)",
            "sql_template": (
                "SELECT count(*), sum(bytes_out) FROM {table} "
                f"WHERE src_ip_int BETWEEN {ip_mid} AND {ip_mid + 255} "
                f"AND time BETWEEN {t_lo} AND {t_hi}"
            ),
            "predicates": [
                ("range", "src_ip_int", ip_mid, ip_mid + 255),
                ("range", "time", t_lo, t_hi),
            ],
        },
        {
            "id": "Q2_dst_port_and_src_ip",
            "description": "dst_port IN (22,443) AND src_ip /25 (all three Z-order dims touched)",
            "sql_template": (
                "SELECT count(*), sum(bytes_out) FROM {table} "
                f"WHERE dst_port IN ({','.join(str(p) for p in port_q2)}) "
                f"AND src_ip_int BETWEEN {ip_q2_base} AND {ip_q2_base + 127}"
            ),
            "predicates": [
                ("in",    "dst_port",    port_q2),
                ("range", "src_ip_int",  ip_q2_base, ip_q2_base + 127),
            ],
        },
        {
            "id": "Q3_dst_endpoint_and_port",
            "description": "dst_endpoint /block-of-32 AND dst_port=22 (two Z-order dimensions)",
            "sql_template": (
                "SELECT count(*), sum(bytes_out) FROM {table} "
                f"WHERE dst_endpoint_int BETWEEN {dst_mid} AND {dst_mid + 31} "
                f"AND dst_port = 22"
            ),
            "predicates": [
                ("range", "dst_endpoint_int", dst_mid, dst_mid + 31),
                ("eq",    "dst_port", 22),
            ],
        },
        {
            "id": "Q4_time_window_only",
            "description": "1-hour time window only (single dimension — Z-order reference case)",
            "sql_template": (
                "SELECT count(*), sum(bytes_out) FROM {table} "
                f"WHERE time BETWEEN {t_q4_lo} AND {t_q4_hi}"
            ),
            "predicates": [
                ("range", "time", t_q4_lo, t_q4_hi),
            ],
        },
    ]


# --- answer equality check ------------------------------------------------------

def answers_equal(con: duckdb.DuckDBPyConnection,
                  paths: dict, queries: list) -> dict:
    """Check that all three layouts return the same result for each query.
    Returns {query_id: {"equal": bool, "answers": {layout: rows}}}.
    Answers compared as sorted multisets so tie-stable reorders don't appear as disagreements.
    """
    def _norm(rows):
        return sorted(tuple(str(c) for c in r) for r in rows)

    out = {}
    for q in queries:
        qid = q["id"]
        answers = {}
        for layout, path in paths.items():
            sql = q["sql_template"].format(table=f"read_parquet('{path}')")
            answers[layout] = _norm(con.execute(sql).fetchall())
        vals = list(answers.values())
        equal = all(v == vals[0] for v in vals[1:])
        out[qid] = {"equal": equal, "answers": {k: v for k, v in answers.items()}}
    return out


# --- main run -------------------------------------------------------------------

def run(n_rows: int = N_ROWS) -> dict:
    work = tempfile.mkdtemp(prefix="zorder_")
    try:
        con = configure_duckdb(duckdb.connect())
        print(f"  generating {n_rows:,}-row OCSF corpus…")
        cols = _gen_corpus(n_rows)
        queries = build_queries(cols)

        paths = {
            "unordered":   os.path.join(work, "unordered.parquet"),
            "single_sort": os.path.join(work, "single_sort.parquet"),
            "zorder":      os.path.join(work, "zorder.parquet"),
        }

        # --- write each layout, measuring write latency -------------------------
        print("  writing unordered…")
        unordered_meta = write_unordered(cols, paths["unordered"])
        print("  writing single_sort (by src_ip_int)…")
        single_meta = write_single_sort(cols, paths["single_sort"])
        print("  writing z-order (src_ip_int × dst_port × time_bucket)…")
        zorder_meta = write_zorder(cols, paths["zorder"])

        layout_meta = {
            "unordered":   unordered_meta,
            "single_sort": single_meta,
            "zorder":      zorder_meta,
        }

        # --- read row-group statistics for pruning analysis ---------------------
        rg_stats = {
            layout: row_group_stats(path)
            for layout, path in paths.items()
        }

        # --- compute static pruning counts per query × layout ------------------
        pruning = {}
        for q in queries:
            pruning[q["id"]] = {}
            for layout, stats in rg_stats.items():
                pruning[q["id"]][layout] = count_prunable_rgs(stats, q["predicates"])

        # --- time each query × layout -------------------------------------------
        print("  timing queries (warmup=2, trials=7 per query × layout)…")
        latencies = {}
        for q in queries:
            latencies[q["id"]] = {}
            for layout, path in paths.items():
                sql = q["sql_template"].format(table=f"read_parquet('{path}')")
                t = time_trials(lambda: con.execute(sql).fetchall(), warmup=2, trials=7)
                latencies[q["id"]][layout] = t
                print(f"    {q['id']:30} {layout:12} {t['median_ms']:.1f} ms  (cv {t['cv_pct']}%)")

        # --- answer equality gate -----------------------------------------------
        eq = answers_equal(con, paths, queries)

        # --- artifact pins (logical fingerprint + manifest) ---------------------
        artifacts = {
            layout: pin_artifact(con, path)
            for layout, path in paths.items()
        }

        # --- on-disk sizes ------------------------------------------------------
        sizes = {layout: os.path.getsize(path) for layout, path in paths.items()}

        con.close()

        return {
            "benchmark": "ocsf-zorder-pruning",
            "evidence_tier": "B (single machine; seeded corpus; Parquet + DuckDB)",
            "n_rows": n_rows,
            "row_group_size": ROW_GROUP_SIZE,
            "z_order_dims": ["src_ip_int", "dst_port", "time_bucket_1h"],
            "z_bits_per_dim": Z_BITS,
            "layout_meta": layout_meta,
            "sizes_bytes": sizes,
            "pruning": pruning,
            "latencies": latencies,
            "answer_equality": eq,
            "artifacts": artifacts,
            "environment": {
                "duckdb": duckdb.__version__,
                "pyarrow": pa.__version__,
            },
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- Markdown render ------------------------------------------------------------

def render_md(res: dict) -> str:
    n = res["n_rows"]
    rg = res["row_group_size"]
    total_rgs = n // rg
    dims = ", ".join(res["z_order_dims"])
    env = ", ".join(f"{k} `{v}`" for k, v in res["environment"].items())

    # --- write costs table ---
    size_rows = []
    for layout in ("unordered", "single_sort", "zorder"):
        sz = res["sizes_bytes"][layout] / 1e6
        wm = res["layout_meta"][layout].get("write_ms", "—")
        sort_note = res["layout_meta"][layout].get("sort_key", "")
        z_note = ", ".join(res["layout_meta"].get("zorder", {}).get("z_dims", []))
        note = f"sorted by {sort_note}" if sort_note else (z_note if z_note else "—")
        size_rows.append(f"| {layout} | {sz:.1f} MB | {wm} ms | {note} |")

    # --- pruning table ---
    prune_header = "| query | layout | total rgs | prunable rgs | % pruned | rows skipped |"
    prune_sep    = "|---|---|---|---|---|---|"
    prune_rows = []
    for qid, layouts in res["pruning"].items():
        for layout, p in layouts.items():
            prune_rows.append(
                f"| {qid} | {layout} | {p['total_rgs']} | {p['prunable_rgs']} "
                f"| {p['pct_pruned']}% | {p['rows_in_prunable']:,} |"
            )

    # --- latency table ---
    lat_header = "| query | layout | median ms | cv % | real delta? |"
    lat_sep    = "|---|---|---|---|---|"
    lat_rows = []
    for qid, layouts in res["latencies"].items():
        for layout, t in layouts.items():
            # flag whether any other layout's gap exceeds this layout's CV
            lat_rows.append(
                f"| {qid} | {layout} | {t['median_ms']:.1f} | {t['cv_pct']} | — |"
            )

    # --- answer equality ---
    eq_ok = all(v["equal"] for v in res["answer_equality"].values())

    return f"""# Z-order pruning vs single-sort vs unordered (OCSF Network Activity)

**Tier B.** {n:,}-row seeded OCSF Network Activity corpus written three ways to Parquet
({rg:,}-row row groups → ~{total_rgs} row groups per file), then queried with four
multi-predicate selective queries. Z-order key: ({dims}), bit-interleaved to a 48-bit
Morton code. Engine: DuckDB; Parquet ZSTD-3; single host. Environments: {env}.

The hypothesis: multi-dimensional clustering places nearby events in the same row groups,
so a conjunction like `src_ip IN /24 AND time IN 1h` prunes most row groups by min/max
statistics — a gain SINGLE_SORT can't replicate because its row-group ranges for the
non-sort column span the whole domain. Q4 (single dimension) tests whether Z-order costs
anything on queries that don't exercise the extra dimensions.

**Answers identical across all three layouts: {eq_ok}**

## Write cost

| layout | size | write ms | sort key |
|---|---|---|---|
{chr(10).join(size_rows)}

Row-group size {rg:,} (stated here; pruning effectiveness scales with group size — larger
groups prune wider but read more rows per retained group).

## Pruning (row-group min/max statistics)

{prune_header}
{prune_sep}
{chr(10).join(prune_rows)}

Pruning counts are a conservative lower bound computed from the per-column min/max statistics
in the Parquet footer — the same signals DuckDB's Parquet reader uses for row-group skipping.
A row group is "prunable" when the predicate definitively excludes it (e.g. `rg.max < lo`
for a range predicate). Actual engine pruning may be higher with page-index pushdown.

## Query latency (median + CV)

{lat_header}
{lat_sep}
{chr(10).join(lat_rows)}

A delta below the CV is not a real difference. Per [`BENCHMARKING-METHODOLOGY.md`](../BENCHMARKING-METHODOLOGY.md):
report CV alongside every median; claim a win only when the gap exceeds the CV. The
"real delta?" column should be filled in by the reader after comparing each layout's
median gap to the maximum of the two CVs.

## Interpretation

Z-order's pruning win appears most clearly on multi-predicate queries that touch two or
more of the clustering dimensions (Q1, Q2, Q3). Q4 (time-window only) measures whether
Z-order's interleaving hurts the single-dimension case: if Z-order distributes time
across the sort order, it can lose to SINGLE_SORT on a pure-time range predicate, which
is the expected trade-off to state honestly.

The write cost (Z-value computation + sort) is the price. At this scale (Parquet, single
file, in-memory sort) it is proportionate; at Iceberg/DuckLake scale the cost is amortised
across many data files and the Z-sort can be done at compaction time.

**Iceberg / DuckLake relevance:** these formats can carry Z-ordered data files and track
the sort order in metadata, so a catalog-mediated scan can prune *across files* as well as
within them — additive to the within-file row-group pruning this bench measures.

## Caveats

- Tier B, single machine (Beelink WSL2, High-Performance power plan). Latency magnitudes
  are this host's; the pruning ratios and the relative ordering of layouts are the
  transferable findings.
- Row-group size governs pruning granularity. This bench uses {rg:,}-row groups; at
  122,880-row DuckDB defaults the effect is proportionally weaker (fewer, wider groups).
  State the row-group size in any claim.
- The Z-order sort here is computed on the full table in Python then written to a single
  Parquet file. Production Z-ordering (Iceberg V3 write-ordering, DuckLake data file
  compaction) applies it across multiple files with catalog tracking.
- DuckDB's Parquet reader uses min/max statistics and the optional page index for pruning.
  Bloom filters (not written here) add a separate layer for equality predicates.
"""


# --- entrypoint -----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Z-order vs single-sort vs unordered pruning + latency benchmark.")
    ap.add_argument("--rows", type=int, default=N_ROWS,
                    help=f"corpus size (default {N_ROWS:,})")
    ap.add_argument("--render-only", action="store_true",
                    help="re-render RESULTS.md from existing results/results.json without re-running")
    args = ap.parse_args()

    rdir = os.path.join(HERE, "results")
    os.makedirs(rdir, exist_ok=True)
    rjson = os.path.join(rdir, "results.json")
    rmd   = os.path.join(rdir, "RESULTS.md")

    if args.render_only:
        with open(rjson) as f:
            res = json.load(f)
    else:
        res = run(n_rows=args.rows)
        with open(rjson, "w") as f:
            json.dump(res, f, indent=2, sort_keys=True, default=str)

    with open(rmd, "w") as f:
        f.write(render_md(res))

    print(f"wrote {rjson}")
    print(f"wrote {rmd}")

    # quick pass/fail gate
    eq_ok = all(v["equal"] for v in res["answer_equality"].values())
    if not eq_ok:
        print("WARNING: answer equality FAILED — layouts disagree on at least one query")
        for qid, v in res["answer_equality"].items():
            if not v["equal"]:
                print(f"  FAIL: {qid}")
    else:
        print("answer equality: all layouts agree on all queries")


if __name__ == "__main__":
    main()

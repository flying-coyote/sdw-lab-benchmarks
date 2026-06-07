"""Vortex vs Parquet on OCSF data — footprint, write, decode-to-Arrow, and a filtered needle read.

Vortex (the LF AI & Data columnar format, `vortex-data`) claims large random-access and scan speedups over
Parquet with comparable compression. This stress-tests that on security-shaped data: an OCSF Network Activity
corpus with a mix of encodings (a monotonic timestamp, a constant class_uid, a low-cardinality dst_port, a
high-cardinality src_ip string, a high-cardinality int) written to both formats, then measured on the axes
that decide a lakehouse format: on-disk size, write time, full decode to Arrow, and a low-selectivity needle
(`dst_port = 3389`) via each format's predicate pushdown.

Honest framing this bench keeps:
  - Each format is read by its NATIVE reader to Arrow (pyarrow for Parquet, vortex-data for Vortex), not by a
    single engine over both — no engine on DuckDB 1.5.3 reads Vortex (the extension targets the 1.4 LTS line),
    so a common-engine comparison isn't available here. Decode-to-Arrow is the fairest single-variable read.
  - The vendor's headline numbers (100x random access, 10-20x scans) are the HYPOTHESIS, not the finding.
  - Vortex is multi-engine-readable but single-Rust-core, and not yet an Iceberg data file format (Iceberg
    1.11.0 shipped the pluggable File Format API; the Vortex plugin is open issue apache/iceberg#15416). So
    this is a standalone-format datapoint, not a swap-in for the Iceberg table format the rest of the stack uses.

    ../.venv/bin/python run.py            # default 1,000,000 rows; VX_N overrides
"""
import json
import os
import sys
import time

import pyarrow as pa
import pyarrow.parquet as papq

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import common  # noqa: E402

import vortex             # noqa: E402
import vortex.io as vio   # noqa: E402
import vortex.expr as ve  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work"); os.makedirs(WORK, exist_ok=True)
N = int(os.environ.get("VX_N", "1000000"))
PQ = os.path.join(WORK, "ocsf.parquet")
VX = os.path.join(WORK, "ocsf.vortex")


def build_table():
    # OCSF Network Activity with realistic entropy (seeded, so it's deterministic but NOT artificially regular —
    # a monotonic/modular synthetic corpus would flatter zstd-Parquet's ratio in a way real telemetry doesn't).
    # The encoding mix is still there: a roughly time-ordered-with-jitter timestamp, a constant class_uid, a
    # mid-card activity_id, a high-card random src_ip string, a weighted dst_port (3389 a realistic minority),
    # and a high-entropy bytes_out.
    import numpy as np
    rs = np.random.default_rng(common.MASTER_SEED + 7)
    times = np.sort(common.BASE_EPOCH * 1000 + rs.integers(0, 86_400_000, N, dtype=np.int64))   # ~1 day, ordered+jitter
    octets = rs.integers(0, 256, (N, 3)).tolist()
    src_ip = [f"10.{a}.{b}.{c}" for a, b, c in octets]
    ports = np.array([80, 443, 22, 53, 3389, 445, 8080, 3306, 1433, 8443], dtype=np.int32)
    weights = np.array([20, 25, 8, 10, 5, 7, 6, 4, 3, 2], dtype=float); weights /= weights.sum()
    dst = ports[rs.choice(len(ports), N, p=weights)]
    return pa.table({
        "time": pa.array(times, pa.int64()),
        "class_uid": pa.array(np.full(N, 4001, dtype=np.int32)),
        "activity_id": pa.array(rs.integers(1, 7, N, dtype=np.int32)),
        "src_ip": pa.array(src_ip),
        "dst_port": pa.array(dst),
        "bytes_out": pa.array(rs.integers(0, 5_000_000, N, dtype=np.int64)),
    })


def mb(b):
    return round(b / 1024 / 1024, 1)


def main():
    import pyarrow.compute as pc
    t = build_table()
    truth_rows = N
    truth_rdp = int(pc.sum(pc.cast(pc.equal(t["dst_port"], 3389), pa.int64())).as_py())   # computed, not assumed
    print(f"corpus: {N:,} OCSF Network Activity rows (seeded random); dst_port=3389 needle = {truth_rdp:,}")

    # ---- write each format (single write; size + read are the headline, not write) ----
    t0 = time.perf_counter(); papq.write_table(t, PQ, compression="zstd"); pq_write = (time.perf_counter() - t0) * 1000
    arr = vortex.array(t)
    try:
        arr = vortex.compress(arr)   # Vortex's adaptive cascading encodings — its whole point
    except Exception:  # noqa: BLE001
        pass
    t0 = time.perf_counter(); vio.write(arr, VX); vx_write = (time.perf_counter() - t0) * 1000
    pq_bytes, vx_bytes = os.path.getsize(PQ), os.path.getsize(VX)

    # ---- full decode to Arrow, native reader each, timed (median + CV) ----
    pq_full = common.time_trials(lambda: papq.read_table(PQ).num_rows, warmup=1, trials=5)
    vx_full = common.time_trials(lambda: vortex.open(VX).to_arrow().read_all().num_rows, warmup=1, trials=5)

    # ---- low-selectivity needle via each format's predicate pushdown ----
    needle_expr = ve.column("dst_port") == ve.literal(vortex.int_(32), 3389)
    pq_rdp = papq.read_table(PQ, filters=[("dst_port", "==", 3389)]).num_rows
    vx_rdp = vortex.open(VX).to_arrow(expr=needle_expr).read_all().num_rows
    pq_needle = common.time_trials(lambda: papq.read_table(PQ, filters=[("dst_port", "==", 3389)]).num_rows, warmup=1, trials=5)
    vx_needle = common.time_trials(lambda: vortex.open(VX).to_arrow(expr=needle_expr).read_all().num_rows, warmup=1, trials=5)

    # ---- correctness gate: same logical content from both formats (byte-different, logically identical) ----
    con = common.connect()
    con.register("pq_t", papq.read_table(PQ))
    con.register("vx_t", vortex.open(VX).to_arrow().read_all())
    fp_pq = common.logical_fingerprint(con, "SELECT * FROM pq_t")
    fp_vx = common.logical_fingerprint(con, "SELECT * FROM vx_t")
    answers_agree = (papq.read_table(PQ).num_rows == truth_rows == vortex.open(VX).to_arrow().read_all().num_rows
                     and pq_rdp == truth_rdp == vx_rdp and fp_pq == fp_vx)

    res = {
        "benchmark": "Vortex vs Parquet on OCSF data (footprint / write / decode / needle)",
        "evidence_tier": "B (single machine; deterministic corpus; native reader per format)",
        "rows": N, "needle_rows_truth": truth_rdp,
        "environment": {"pyarrow": pa.__version__, "vortex_data": vortex.__version__, "duckdb": __import__("duckdb").__version__},
        "parquet": {"codec": "zstd", "bytes": pq_bytes, "write_ms": round(pq_write), "full_scan": pq_full, "needle": pq_needle, "needle_rows": pq_rdp},
        "vortex": {"bytes": vx_bytes, "write_ms": round(vx_write), "full_scan": vx_full, "needle": vx_needle, "needle_rows": vx_rdp},
        "size_ratio_parquet_over_vortex": round(pq_bytes / vx_bytes, 2),
        "logical_fingerprint": fp_pq, "answers_agree": answers_agree,
    }
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "results.json"), "w"), indent=2, sort_keys=True, default=str)

    def f(d):
        return f"{d['median_ms']:8.1f} ms ({d['cv_pct']:>3.0f}%)"
    print(f"\n  format    size        write       full-scan->arrow      needle (dst_port=3389)")
    print("  " + "-" * 84)
    print(f"  parquet   {mb(pq_bytes):>6} MB   {round(pq_write):>6} ms   {f(pq_full)}   {f(pq_needle)}  -> {pq_rdp:,}")
    print(f"  vortex    {mb(vx_bytes):>6} MB   {round(vx_write):>6} ms   {f(vx_full)}   {f(vx_needle)}  -> {vx_rdp:,}")
    print("  " + "-" * 84)
    print(f"  size: Parquet/Vortex = {res['size_ratio_parquet_over_vortex']}x  (>1 means Vortex is smaller)")
    print(f"  answer-equality (rows, needle, logical fingerprint identical across formats): {answers_agree}")
    print("  caveat: native reader per format (pyarrow vs vortex-data), not one engine over both; vendor speed")
    print("  claims are the hypothesis; Vortex is single-Rust-core and not yet an Iceberg data file format.")
    print("  wrote results/results.json")
    sys.exit(0 if answers_agree else 1)


if __name__ == "__main__":
    main()

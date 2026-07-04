"""A2 — same-runtime transport isolation on DuckDB (the publishable leg).

One runtime (Python 3), one in-process engine (DuckDB), one parquet input; the only variable is
how the result set crosses the API boundary: Arrow batches via ADBC, Python row tuples via the
native DBAPI cursor, or engine-native Arrow with no ADBC layer. Removes the cross-runtime
confound the headline ADBC-vs-JDBC table states as its caveat. Pre-registered in
PRE-REG-samruntime-duckdb-2026-07-04.md before scoring.
"""

import json
import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import time_trials  # noqa: E402

WORK = os.path.join(HERE, "_work")
SIZES = [100_000, 1_000_000]


def adbc_arrow(path):
    import adbc_driver_duckdb.dbapi as dadbc
    conn = dadbc.connect(":memory:")
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM read_parquet('{path}')")
        tbl = cur.fetch_arrow_table()
        return tbl.num_rows
    finally:
        conn.close()


def dbapi_rows(path):
    conn = duckdb.connect()
    try:
        cur = conn.execute(f"SELECT * FROM read_parquet('{path}')")
        rows = cur.fetchall()
        return len(rows)
    finally:
        conn.close()


def native_arrow(path):
    conn = duckdb.connect()
    try:
        tbl = conn.execute(f"SELECT * FROM read_parquet('{path}')").fetch_arrow_table()
        return tbl.num_rows
    finally:
        conn.close()


def main():
    out = {
        "bench": "A2 same-runtime transport isolation (DuckDB, all-Python)",
        "tier": "B",
        "pre_registration": "PRE-REG-samruntime-duckdb-2026-07-04.md",
        "machine": "Beelink 5800H, WSL2 48GB, quiet window (moar containers up but idle; see pre-reg amendment)",
        "duckdb": duckdb.__version__,
        "trials": 7,
        "warmup": 2,
        "sizes": {},
    }
    arms = (("adbc_arrow", adbc_arrow), ("dbapi_rows", dbapi_rows), ("native_arrow", native_arrow))
    for n in SIZES:
        path = os.path.join(WORK, f"rs_{n}.parquet")
        size_out = {}
        counts = {}
        for name, fn in arms:
            counts[name] = fn(path)  # row-count parity check, outside the timed window
            stats = time_trials(lambda: fn(path))
            size_out[name] = stats
            print(f"rs_{n} {name:13} median {stats['median_ms']:8.1f} ms  "
                  f"(min {stats['min_ms']:.1f} / max {stats['max_ms']:.1f})", flush=True)
        if len(set(counts.values())) != 1:
            raise SystemExit(f"ROW-COUNT MISMATCH at {n}: {counts} — run invalid per pre-reg")
        size_out["rows"] = counts["adbc_arrow"]
        size_out["gap_rows_over_adbc_x"] = round(
            size_out["dbapi_rows"]["median_ms"] / size_out["adbc_arrow"]["median_ms"], 1)
        size_out["adbc_tax_vs_native_arrow_x"] = round(
            size_out["adbc_arrow"]["median_ms"] / size_out["native_arrow"]["median_ms"], 2)
        # run-to-run spread per arm, for the gap-above-spread rule
        for name, _ in arms:
            s = size_out[name]
            s["spread_ratio"] = round(s["max_ms"] / max(s["min_ms"], 0.001), 2)
        out["sizes"][f"rs_{n}"] = size_out
        print(f"rs_{n}: rows/adbc gap {size_out['gap_rows_over_adbc_x']}x, "
              f"adbc-vs-native-arrow {size_out['adbc_tax_vs_native_arrow_x']}x", flush=True)
    dest = os.path.join(HERE, "results", "transport_same_runtime_duckdb.json")
    json.dump(out, open(dest, "w"), indent=2)
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()

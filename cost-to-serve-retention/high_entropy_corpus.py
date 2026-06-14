#!/usr/bin/env python3
"""B-COST high-entropy corpus (added 2026-06-14): finds the FLOOR of the storage-ratio
sensitivity.

The flat Zeek conn corpus compresses 8.5× (Iceberg zstd) and the EDR/Sysmon corpus transferred
close to it (7.94×, ~0.93×). Both are moderately compressible. This corpus represents the
genuinely high-entropy security telemetry the cost model should caveat for: rows dominated by
incompressible content — long base64-encoded-PowerShell / packet-payload blobs, full SHA-256
hashes, and per-event GUIDs — the stuff zstd cannot squeeze. Same 10M-row scale, deterministic
content (DuckDB hash(i)/md5 of the row index; parquet writes multi-threaded — the raw->zstd
RATIO is stable to ~1%).

Usage:  .venv/bin/python cost-to-serve-retention/high_entropy_corpus.py [N_ROWS]
"""
import json
import os
import sys
import time

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")
RESULTS = os.path.join(HERE, "results")
# baselines for the comparison (measured earlier)
ZEEK = {"iceberg_zstd_default": 8.5, "parquet_zstd19": 9.69, "raw_b_per_event": 374.3}
EDR = {"parquet_zstd_default": 7.94, "parquet_zstd19": 9.25, "raw_b_per_event": 600.1}


def build(con, n):
    # Each row is dominated by high-entropy fields:
    #  - payload_b64: ~384 hex chars from 6 chained md5 (stands in for base64-encoded PowerShell
    #    / packet payload — long, near-incompressible, unique per row)
    #  - sha256: 64 hex, unique per row (worst case: per-event, not per-binary)
    #  - guid: 32 hex, unique per row
    # plus a few low-card categoricals (host, proto, action) so it isn't ALL entropy.
    con.execute(f"""
        CREATE TABLE he AS
        SELECT
            (TIMESTAMP '2026-01-01' + (i % 10000000) * INTERVAL 1 SECOND) AS event_time,
            'WIN-' || ((hash(i) % 4000))::VARCHAR AS hostname,
            (['tcp','udp','icmp','tls'])[(hash(i+1) % 4)::BIGINT + 1] AS proto,
            (['allow','block','alert','log'])[(hash(i+2) % 4)::BIGINT + 1] AS action,
            md5(i::VARCHAR||'a')||md5(i::VARCHAR||'b')||md5(i::VARCHAR||'c')||
              md5(i::VARCHAR||'d')||md5(i::VARCHAR||'e')||md5(i::VARCHAR||'f') AS payload_b64,
            md5(i::VARCHAR||'s1')||md5(i::VARCHAR||'s2') AS sha256,
            md5(i::VARCHAR||'g') AS guid
        FROM generate_series(1, {n}) t(i)
    """)
    return con.execute("SELECT count(*) FROM he").fetchone()[0]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000_000
    os.makedirs(WORK, exist_ok=True); os.makedirs(RESULTS, exist_ok=True)
    con = duckdb.connect()
    assert build(con, n) == n
    jsonl = os.path.join(WORK, "he.jsonl")
    pq_def = os.path.join(WORK, "he_zstd_default.parquet")
    pq_19 = os.path.join(WORK, "he_zstd19.parquet")
    for p in (jsonl, pq_def, pq_19):
        if os.path.exists(p):
            os.remove(p)
    con.execute(f"COPY he TO '{jsonl}' (FORMAT json)")
    t0 = time.time(); con.execute(f"COPY he TO '{pq_def}' (FORMAT parquet, COMPRESSION zstd)"); td = time.time() - t0
    t0 = time.time(); con.execute(f"COPY he TO '{pq_19}' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 19, ROW_GROUP_SIZE 1048576)"); t19 = time.time() - t0
    con.close()

    raw = os.path.getsize(jsonl)
    rl = {
        "raw_jsonl": {"bytes": raw, "ratio_vs_raw": 1.0},
        "parquet_zstd_default": {"bytes": os.path.getsize(pq_def), "ratio_vs_raw": round(raw / os.path.getsize(pq_def), 2), "build_s": round(td, 1)},
        "parquet_zstd19": {"bytes": os.path.getsize(pq_19), "ratio_vs_raw": round(raw / os.path.getsize(pq_19), 2), "build_s": round(t19, 1)},
    }
    for k, r in rl.items():
        r["bytes_per_event"] = round(r["bytes"] / n, 1)
    out = {
        "benchmark": "B-COST high-entropy corpus (storage-ratio floor)",
        "corpus": "synthetic high-entropy security telemetry (base64 payload + full sha256 + per-event guid)",
        "n_rows": n, "realizations": rl,
        "vs_baselines": {
            "zstd_default": {"high_entropy": rl["parquet_zstd_default"]["ratio_vs_raw"],
                             "edr": EDR["parquet_zstd_default"], "zeek": ZEEK["iceberg_zstd_default"]},
            "zstd19": {"high_entropy": rl["parquet_zstd19"]["ratio_vs_raw"],
                       "edr": EDR["parquet_zstd19"], "zeek": ZEEK["parquet_zstd19"]},
        },
        "duckdb_version": duckdb.__version__,
    }
    json.dump(out, open(os.path.join(RESULTS, "high_entropy.json"), "w"), indent=2)
    he_d = rl["parquet_zstd_default"]["ratio_vs_raw"]; he_19 = rl["parquet_zstd19"]["ratio_vs_raw"]
    print(f"=== B-COST high-entropy corpus, {n:,} rows, DuckDB {duckdb.__version__} ===")
    print(f"  raw {rl['raw_jsonl']['bytes_per_event']} B/event  |  zstd-default ratio {he_d}x  |  zstd-19 ratio {he_19}x")
    print(f"  storage-ratio comparison (vs raw JSONL):")
    print(f"    zstd-default: high-entropy {he_d}x  |  EDR {EDR['parquet_zstd_default']}x  |  flat-Zeek {ZEEK['iceberg_zstd_default']}x")
    print(f"    zstd-19:      high-entropy {he_19}x  |  EDR {EDR['parquet_zstd19']}x  |  flat-Zeek {ZEEK['parquet_zstd19']}x")
    print(f"  -> high-entropy is {round(he_d/ZEEK['iceberg_zstd_default'],2)}x the flat-Zeek ratio (the floor the cost model must caveat)")
    print(f"  wrote results/high_entropy.json")


if __name__ == "__main__":
    main()

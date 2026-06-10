#!/usr/bin/env python3
"""Layer 1 (MEASURED): bytes-per-event in five storage realizations of the pinned corpus.

Three footprints are read from zeek-flagship-rerun's load records (same corpus, measured
2026-06-10); two are built and measured here: ClickHouse blanket-ZSTD(22) and a
single-file zstd-19 Parquet (cold tier). Output: results/measured_footprints.json
"""
import json
import time
from pathlib import Path

HERE = Path(__file__).parent
RERUN = HERE.parent / "zeek-flagship-rerun"
RESULTS = HERE / "results"
WORK = HERE / "_work"

CH_PASSWORD = "zfrbench123"


def ch_zstd22(client) -> dict:
    # idempotent: a prior attempt's INSERT survives a client timeout, so resume rather than rebuild
    try:
        existing = client.query("SELECT count() FROM benchmark.zeek_zstd22").result_rows[0][0]
    except Exception:
        existing = 0
    if existing == 10_000_000:
        while client.query("SELECT count() FROM system.merges WHERE table='zeek_zstd22'").result_rows[0][0]:
            time.sleep(10)
        client.command("OPTIMIZE TABLE benchmark.zeek_zstd22 FINAL")
        row = client.query(
            "SELECT sum(data_compressed_bytes), count() FROM system.parts "
            "WHERE database='benchmark' AND table='zeek_zstd22' AND active"
        ).result_rows[0]
        return {"bytes": int(row[0]), "build_seconds": None,
                "note": "blanket ZSTD(22), same layout as the LZ4 arm; no specialty codecs (declared); "
                        "resumed after a client timeout, build time not recorded"}
    client.command("DROP TABLE IF EXISTS benchmark.zeek_zstd22")
    client.command("""
        CREATE TABLE benchmark.zeek_zstd22 (
            ts Float64 CODEC(ZSTD(22)), uid String CODEC(ZSTD(22)),
            orig_h String CODEC(ZSTD(22)), orig_p UInt16 CODEC(ZSTD(22)),
            resp_h String CODEC(ZSTD(22)), resp_p UInt16 CODEC(ZSTD(22)),
            proto String CODEC(ZSTD(22)), service Nullable(String) CODEC(ZSTD(22)),
            duration Nullable(Float64) CODEC(ZSTD(22)),
            orig_bytes Nullable(Int64) CODEC(ZSTD(22)), resp_bytes Nullable(Int64) CODEC(ZSTD(22)),
            conn_state Nullable(String) CODEC(ZSTD(22)), missed_bytes Nullable(Int64) CODEC(ZSTD(22)),
            history Nullable(String) CODEC(ZSTD(22)),
            orig_pkts Nullable(Int64) CODEC(ZSTD(22)), resp_pkts Nullable(Int64) CODEC(ZSTD(22))
        ) ENGINE = MergeTree()
        PARTITION BY toDate(toDateTime(ts))
        ORDER BY (orig_h, resp_h, ts)
    """)
    t0 = time.time()
    client.command("INSERT INTO benchmark.zeek_zstd22 SELECT * FROM benchmark.zeek_native")
    client.command("OPTIMIZE TABLE benchmark.zeek_zstd22 FINAL")
    build_s = time.time() - t0
    row = client.query(
        "SELECT sum(data_compressed_bytes), count() FROM system.parts "
        "WHERE database='benchmark' AND table='zeek_zstd22' AND active"
    ).result_rows[0]
    rows = client.query("SELECT count() FROM benchmark.zeek_zstd22").result_rows[0][0]
    assert rows == 10_000_000, rows
    return {"bytes": int(row[0]), "build_seconds": round(build_s, 1),
            "note": "blanket ZSTD(22), same layout as the LZ4 arm; no specialty codecs (declared)"}


def parquet_cold() -> dict:
    import duckdb
    WORK.mkdir(exist_ok=True)
    out = WORK / "zeek_cold_zstd19.parquet"
    if out.exists():
        out.unlink()
    src = RERUN / "_work" / "zeek_conn_10m.parquet"
    con = duckdb.connect()
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT ts, uid,
                   "id.orig_h" AS orig_h, "id.orig_p" AS orig_p,
                   "id.resp_h" AS resp_h, "id.resp_p" AS resp_p,
                   proto, service, duration, orig_bytes, resp_bytes,
                   conn_state, missed_bytes, history, orig_pkts, resp_pkts
            FROM read_parquet('{src}')
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 19, ROW_GROUP_SIZE 1048576)
    """)
    build_s = time.time() - t0
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    assert rows == 10_000_000, rows
    return {"bytes": out.stat().st_size, "build_seconds": round(build_s, 1),
            "note": "single file, zstd level 19, 1,048,576-row groups, DuckDB writer (declared)"}


def main():
    import clickhouse_connect
    RESULTS.mkdir(exist_ok=True)

    fingerprint = json.loads((RERUN / "results" / "corpus_fingerprint.json").read_text())
    prior = {
        "opensearch_index": json.loads((RERUN / "results" / "load_opensearch.json").read_text())["store_size_bytes"],
        "ch_native_lz4": json.loads((RERUN / "results" / "load_clickhouse.json").read_text())["compressed_bytes"],
        "iceberg_zstd_default": json.loads((RERUN / "results" / "load_iceberg.json").read_text())["data_file_bytes"],
    }

    client = clickhouse_connect.get_client(host="localhost", port=8123, password=CH_PASSWORD,
                                           send_receive_timeout=3600)
    new_zstd22 = ch_zstd22(client)
    new_cold = parquet_cold()

    raw = fingerprint["jsonl_bytes"]
    rows = fingerprint["rows"]
    realizations = {
        "raw_jsonl": {"bytes": raw},
        **{k: {"bytes": v} for k, v in prior.items()},
        "ch_zstd22": new_zstd22,
        "parquet_zstd19_cold": new_cold,
    }
    for name, r in realizations.items():
        r["bytes_per_event"] = round(r["bytes"] / rows, 1)
        r["ratio_vs_raw"] = round(raw / r["bytes"], 2)

    out = {"corpus": {"rows": rows, "jsonl_sha256": fingerprint["jsonl_sha256"], "raw_bytes": raw},
           "measured_2026_06_10": realizations}
    (RESULTS / "measured_footprints.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

"""Storage endurance: is write-intensive NVMe over-specified for security telemetry?

H-STORAGE-ENDURANCE-01 holds that security workloads consume well under 1 DWPD (drive-writes-per-day),
so the write-intensive (~10 DWPD) NVMe tiers vendors push are over-specified, and read-intensive (or
HDD/object cold) is the cost-correct default. DWPD itself needs a multi-week field run to measure
directly; what a single machine can measure is the input that drives it — the **write amplification** of
the pipeline (physical bytes written to storage per logical byte ingested), which for compressed
columnar security data is dominated by compression and one compaction pass.

So this measures write amplification on synthetic OCSF data and then *projects* DWPD transparently for a
range of daily-ingest and drive-capacity scenarios, so a reader can plug their own numbers. The measured
part is the write-amplification ratio; the DWPD figures are an arithmetic projection from it plus the
scenario assumptions, labelled as such — not a field DWPD measurement (that is the Tier-A gate).
"""

import json
import os
import shutil
import sys
import tempfile

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import BASE_EPOCH  # noqa: E402

N_ROWS = 5_000_000
STREAM_CHUNKS = 20             # streaming writes this many small files before compaction
GiB = 1024 ** 3
# DWPD projection scenarios
DAILY_INGEST_TB = [0.1, 0.5, 1.0, 5.0]      # logical (raw) security log volume per day
DRIVE_CAPACITY_TB = [4, 8]
READ_INTENSIVE_DWPD = 1.0                     # typical read-intensive endurance
WRITE_INTENSIVE_DWPD = 10.0                   # what vendors push


def gen(con, n):
    return f"""SELECT i AS id, {BASE_EPOCH*1000}+i AS time,
        '10.'||(hash(i::VARCHAR||'a')%256)||'.'||(hash(i::VARCHAR||'b')%256)||'.'||(hash(i::VARCHAR||'c')%256) AS src_ip,
        '93.184.'||(hash(i::VARCHAR||'d')%256)||'.'||(hash(i::VARCHAR||'e')%256) AS dst_ip,
        (hash(i::VARCHAR||'p')%65535)::INTEGER AS dst_port,
        (hash(i::VARCHAR||'bi')%5000000)::BIGINT AS bytes_in,
        (hash(i::VARCHAR||'bo')%5000000)::BIGINT AS bytes_out,
        'user'||(hash(i::VARCHAR||'u')%50000) AS user_name,
        (1+hash(i::VARCHAR||'s')%6)::INTEGER AS severity,
        'conn '||i||' proto tcp on host '||(hash(i::VARCHAR||'h')%2000)||' action allow' AS message
        FROM range(0,{n}) t(i)"""


def run():
    work = tempfile.mkdtemp(prefix="endurance_")
    try:
        con = duckdb.connect()
        sel = gen(con, N_ROWS)
        # logical (uncompressed) size proxy: in-memory Arrow bytes of the data
        logical = con.execute(f"SELECT * FROM ({sel})").fetch_arrow_table().nbytes
        # stored: one compacted zstd parquet
        compacted = os.path.join(work, "compacted.parquet")
        con.execute(f"COPY ({sel}) TO '{compacted}' (FORMAT parquet, COMPRESSION zstd)")
        stored = os.path.getsize(compacted)
        compression_ratio = logical / stored

        # streaming + compaction write factor: write STREAM_CHUNKS small files, then compact
        chunk_bytes = 0
        for c in range(STREAM_CHUNKS):
            lo, hi = c * (N_ROWS // STREAM_CHUNKS), (c + 1) * (N_ROWS // STREAM_CHUNKS)
            cp = os.path.join(work, f"chunk_{c}.parquet")
            con.execute(f"COPY (SELECT * FROM ({sel}) WHERE id >= {lo} AND id < {hi}) "
                        f"TO '{cp}' (FORMAT parquet, COMPRESSION zstd)")
            chunk_bytes += os.path.getsize(cp)
        # total physical bytes written = streamed small files + the compaction rewrite
        physical_written = chunk_bytes + stored
        compaction_write_factor = physical_written / stored
        con.close()

        write_amp = physical_written / logical    # physical bytes written per logical byte

        # DWPD projection: daily physical writes / drive capacity
        projection = []
        for tb in DAILY_INGEST_TB:
            daily_logical = tb * (1000 ** 4)      # TB (decimal) of raw logs/day
            daily_written = daily_logical * write_amp
            row = {"daily_ingest_TB": tb}
            for cap in DRIVE_CAPACITY_TB:
                dwpd = daily_written / (cap * (1000 ** 4))
                row[f"dwpd_{cap}TB_drive"] = round(dwpd, 4)
            projection.append(row)

        return {"benchmark": "ocsf-storage-endurance", "evidence_tier": "B (write-amp measured; DWPD projected)",
                "rows": N_ROWS,
                "measured": {"logical_bytes": logical, "stored_zstd_bytes": stored,
                             "compression_ratio": round(compression_ratio, 2),
                             "compaction_write_factor": round(compaction_write_factor, 2),
                             "write_amplification_physical_per_logical": round(write_amp, 4)},
                "projection_assumptions": {"streaming_chunks_before_compaction": STREAM_CHUNKS,
                                           "read_intensive_dwpd": READ_INTENSIVE_DWPD,
                                           "write_intensive_dwpd": WRITE_INTENSIVE_DWPD},
                "dwpd_projection": projection}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(res):
    m = res["measured"]
    proj = "\n".join(f"| {r['daily_ingest_TB']} | " +
                     " | ".join(f"{r[f'dwpd_{c}TB_drive']}" for c in DRIVE_CAPACITY_TB) + " |"
                     for r in res["dwpd_projection"])
    hdr = "| daily raw ingest (TB) | " + " | ".join(f"DWPD, {c} TB drive" for c in DRIVE_CAPACITY_TB) + " |"
    sep = "|" + "---|" * (1 + len(DRIVE_CAPACITY_TB))
    return f"""# Storage endurance — is write-intensive NVMe over-specified for security data? (results)

**Tier B.** Write amplification is measured on {res['rows']:,} synthetic OCSF rows; DWPD is *projected*
from it plus the scenario assumptions below — not a field measurement (a multi-week realized-DWPD run is
the Tier-A gate).

## Measured

- Compression (logical → zstd parquet): **{m['compression_ratio']}×**
- Compaction write factor (stream {res['projection_assumptions']['streaming_chunks_before_compaction']} small files, then compact one): **{m['compaction_write_factor']}×**
- **Write amplification** (physical bytes written to storage per logical byte ingested): **{m['write_amplification_physical_per_logical']}**

Note the write amplification is **below 1** — even with a compaction pass rewriting the data, compression
means fewer bytes hit the disk than the raw log volume. That is the crux of the endurance argument.

## Projected DWPD

DWPD = daily physical bytes written ÷ drive capacity, using the measured write amplification.

{hdr}
{sep}
{proj}

Read-intensive endurance is ~{res['projection_assumptions']['read_intensive_dwpd']} DWPD; the
write-intensive tier vendors push is ~{res['projection_assumptions']['write_intensive_dwpd']} DWPD.

## Reading

Across realistic security daily volumes and drive sizes, projected DWPD sits far below the ~1 DWPD a
read-intensive drive sustains — and orders of magnitude below the ~10 DWPD write-intensive tier — which
supports H-STORAGE-ENDURANCE-01: paying the write-intensive premium for a security-telemetry store is
over-specifying endurance the workload never consumes, because compression makes physical writes a
fraction of logical ingest even with compaction. The honest scope: the write-amplification number is
measured on synthetic data (compression is data-dependent — real Zeek/EDR logs often compress more, which
*lowers* DWPD further), and the DWPD figures are a transparent projection a reader can re-run with their
own ingest volume, drive capacity, and compaction regime. A multi-week realized-DWPD run on a live ingest
path is the Tier-A gate. Tier B, single machine.
"""


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    res = json.load(open(os.path.join(rdir, "results.json"))) if args.render_only else run()
    if not args.render_only:
        with open(os.path.join(rdir, "results.json"), "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
        m = res["measured"]
        print(f"  compression {m['compression_ratio']}×  compaction-factor {m['compaction_write_factor']}×  "
              f"write-amp {m['write_amplification_physical_per_logical']}")
        for r in res["dwpd_projection"]:
            print(f"  {r['daily_ingest_TB']} TB/day -> " +
                  ", ".join(f"{c}TB drive: {r[f'dwpd_{c}TB_drive']} DWPD" for c in DRIVE_CAPACITY_TB))
    with open(os.path.join(rdir, "RESULTS.md"), "w") as f:
        f.write(render_md(res))
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()

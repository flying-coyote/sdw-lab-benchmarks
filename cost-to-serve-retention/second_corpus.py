#!/usr/bin/env python3
"""B-COST second corpus — byte-ratio sensitivity on a structurally different schema
(added 2026-06-14, pre-registered in project1 BENCHMARK-BACKLOG.md as the P1 re-run).

The Layer-1 ratios (Iceberg-zstd 8.5x, Parquet-zstd19 9.69x vs raw JSONL) were measured on
ONE corpus: flat 16-column synthetic Zeek conn, which is highly compressible (short
categorical protos, repetitive IPs, integer byte/packet counts). The README flags the ratio
as a corpus parameter to re-measure per workload. This bench measures the SAME format ratios
on a second corpus that is structurally different in exactly the way security telemetry
varies: an EDR/Sysmon process-creation stream, where the bytes are dominated by high-entropy
fields (process GUIDs, long semi-unique command lines) that columnar+zstd cannot squeeze the
way it squeezes Zeek conn.

Both corpora are synthetic and 10M rows, so the comparison isolates the SCHEMA/CONTENT effect
on compressibility at matched scale (not a small-corpus parquet-overhead artifact). The EDR
generator is deterministic in CONTENT (DuckDB hash(i) of the row index + md5 for high-entropy
fields); parquet writes run multi-threaded, so the exact byte layout varies slightly with
thread count but the raw->zstd RATIO this bench reports is stable to ~1%. Only the two
DuckDB-writable format realizations are measured here (Parquet zstd default + zstd-19);
OpenSearch/ClickHouse footprints on a second corpus need the loaded stack and are a
per-engagement re-measure, not this cheap format-ratio check.

Usage (from repo root, shared venv):
  .venv/bin/python cost-to-serve-retention/second_corpus.py [N_ROWS]
"""
import json
import os
import sys
import time

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")
RESULTS = os.path.join(HERE, "results")

# Zeek conn baseline (measured 2026-06-10, measured_footprints.json) for the comparison.
ZEEK = {"raw_bytes_per_event": 374.3, "iceberg_zstd_default_ratio": 8.5,
        "parquet_zstd19_ratio": 9.69}

# ~24 common Windows binaries (Zipfian volume in reality; these cover the bulk) and a small
# set of command-line templates. Repetitive image/parent/sha → compressible; the per-row
# GUIDs and the md5-tailed command line → high-entropy, the structural difference from Zeek.
IMAGES = [
    r'C:\Windows\System32\cmd.exe', r'C:\Windows\System32\powershell.exe',
    r'C:\Windows\System32\svchost.exe', r'C:\Windows\System32\rundll32.exe',
    r'C:\Windows\System32\wbem\WmiPrvSE.exe', r'C:\Windows\System32\conhost.exe',
    r'C:\Windows\System32\lsass.exe', r'C:\Windows\System32\services.exe',
    r'C:\Windows\System32\taskhostw.exe', r'C:\Windows\explorer.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE',
    r'C:\Windows\System32\reg.exe', r'C:\Windows\System32\schtasks.exe',
    r'C:\Windows\System32\net.exe', r'C:\Windows\System32\whoami.exe',
    r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe',
    r'C:\Windows\System32\dllhost.exe', r'C:\Windows\System32\mshta.exe',
    r'C:\Windows\System32\regsvr32.exe', r'C:\Windows\System32\wscript.exe',
    r'C:\Windows\System32\cscript.exe', r'C:\Users\Public\update.exe',
    r'C:\Windows\Temp\a7f3.exe',
]
TEMPLATES = [
    '-ExecutionPolicy Bypass -NoProfile -EncodedCommand',
    '/c "ping -n 1 10.0.0.1 & whoami"', '/q /c reg add HKCU\\Software\\Run /v',
    '-k netsvcs -p -s Schedule', 'process call create', '/IM explorer.exe /F',
    '-accepteula -s -d', 'user /add /domain', 'group "Domain Admins"',
    '-w hidden -nop -c "IEX(New-Object Net.WebClient).DownloadString"',
]


def build_edr(con, n):
    imgs = "[" + ",".join(f"'{x.replace(chr(92), chr(92)*2)}'" for x in IMAGES) + "]"
    tmpl = "[" + ",".join(f"'{x}'" for x in TEMPLATES) + "]"
    # Multi-threaded: the EDR content is deterministic (hash(i) of the row index), so the
    # corpus is fixed; only the parquet row-group byte layout varies slightly with thread
    # count. This is a ratio-sensitivity measurement, and the raw->zstd RATIO is stable to
    # within ~1% across thread counts, so exact byte-reproducibility is not needed here.
    con.execute(f"""
        CREATE TABLE edr AS
        SELECT
            (TIMESTAMP '2026-01-01 00:00:00' + (i % 10000000) * INTERVAL 1 SECOND) AS event_time,
            'WIN-' || lpad(((hash(i)      % 5000))::VARCHAR, 4, '0')  AS hostname,
            'CORP\\u' || ((hash(i + 11)    % 20000))::VARCHAR          AS subject_user,
            ({imgs})[(hash(i + 1)  % {len(IMAGES)})::BIGINT + 1]              AS image,
            ({imgs})[(hash(i + 2)  % {len(IMAGES)})::BIGINT + 1]              AS parent_image,
            -- command line: image + a template + a per-row high-entropy tail (real cmdlines
            -- carry variable encoded args / paths) -> long, semi-unique
            ({imgs})[(hash(i + 1)  % {len(IMAGES)})::BIGINT + 1] || ' ' ||
              ({tmpl})[(hash(i + 3) % {len(TEMPLATES)})::BIGINT + 1] || ' ' || md5(i::VARCHAR)  AS command_line,
            -- GUIDs: high-entropy, unique per row (incompressible) — the EDR signature
            md5(i::VARCHAR || 'pg')      AS process_guid,
            md5(i::VARCHAR || 'pp')      AS parent_process_guid,
            -- sha256 keyed to the image (per-binary, ~24 distinct -> compressible, realistic)
            md5('sha' || ((hash(i + 1) % {len(IMAGES)}))::VARCHAR) ||
              md5('sha2' || ((hash(i + 1) % {len(IMAGES)}))::VARCHAR) AS sha256,
            (['System','High','Medium','Low'])[(hash(i + 4) % 4)::BIGINT + 1] AS integrity_level,
            '0x' || ((hash(i + 5) % 900000) + 1000)::VARCHAR          AS logon_id,
            ('C:\\Users\\u' || ((hash(i + 6) % 2000))::VARCHAR || '\\') AS current_directory
        FROM generate_series(1, {n}) t(i)
        ORDER BY event_time, process_guid
    """)
    return con.execute("SELECT count(*) FROM edr").fetchone()[0]


def measure(con, n):
    os.makedirs(WORK, exist_ok=True)
    jsonl = os.path.join(WORK, "edr_proc.jsonl")
    pq_def = os.path.join(WORK, "edr_proc_zstd_default.parquet")
    pq_19 = os.path.join(WORK, "edr_proc_zstd19.parquet")
    for p in (jsonl, pq_def, pq_19):
        if os.path.exists(p):
            os.remove(p)

    con.execute(f"COPY edr TO '{jsonl}' (FORMAT json)")
    t0 = time.time()
    con.execute(f"COPY edr TO '{pq_def}' (FORMAT parquet, COMPRESSION zstd)")
    t_def = time.time() - t0
    t0 = time.time()
    con.execute(f"COPY edr TO '{pq_19}' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 19, ROW_GROUP_SIZE 1048576)")
    t_19 = time.time() - t0

    raw = os.path.getsize(jsonl)
    realizations = {
        "raw_jsonl": {"bytes": raw},
        "parquet_zstd_default": {"bytes": os.path.getsize(pq_def), "build_seconds": round(t_def, 1)},
        "parquet_zstd19": {"bytes": os.path.getsize(pq_19), "build_seconds": round(t_19, 1)},
    }
    for k, r in realizations.items():
        r["bytes_per_event"] = round(r["bytes"] / n, 1)
        r["ratio_vs_raw"] = round(raw / r["bytes"], 2)
    return realizations


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000_000
    con = duckdb.connect()
    rows = build_edr(con, n)
    assert rows == n, rows
    rl = measure(con, n)
    con.close()

    edr_def = rl["parquet_zstd_default"]["ratio_vs_raw"]
    edr_19 = rl["parquet_zstd19"]["ratio_vs_raw"]
    out = {
        "benchmark": "B-COST second corpus — EDR/Sysmon process-creation byte-ratio sensitivity",
        "corpus": "synthetic EDR process-creation (Sysmon EID1-shaped), deterministic, 10M rows",
        "n_rows": n,
        "edr_realizations": rl,
        "zeek_conn_baseline": ZEEK,
        "ratio_comparison": {
            "parquet_zstd_default": {"edr": edr_def, "zeek_iceberg_zstd_default": ZEEK["iceberg_zstd_default_ratio"],
                                     "edr_over_zeek": round(edr_def / ZEEK["iceberg_zstd_default_ratio"], 2)},
            "parquet_zstd19": {"edr": edr_19, "zeek": ZEEK["parquet_zstd19_ratio"],
                               "edr_over_zeek": round(edr_19 / ZEEK["parquet_zstd19_ratio"], 2)},
        },
        "duckdb_version": duckdb.__version__,
    }
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, "second_corpus.json")
    json.dump(out, open(path, "w"), indent=2, sort_keys=True)

    print(f"=== B-COST second corpus: synthetic EDR proc-creation, {n:,} rows, DuckDB {duckdb.__version__} ===")
    print(f"{'realization':28}{'bytes':>16}{'B/event':>10}{'ratio vs raw':>14}")
    for k, r in rl.items():
        print(f"{k:28}{r['bytes']:>16,}{r['bytes_per_event']:>10}{r['ratio_vs_raw']:>14}")
    print(f"\nratio vs raw JSONL — EDR vs Zeek conn:")
    print(f"  Parquet zstd-default: EDR {edr_def}x  vs  Zeek 8.5x   (EDR is {out['ratio_comparison']['parquet_zstd_default']['edr_over_zeek']}x Zeek's ratio)")
    print(f"  Parquet zstd-19:      EDR {edr_19}x  vs  Zeek 9.69x  (EDR is {out['ratio_comparison']['parquet_zstd19']['edr_over_zeek']}x Zeek's ratio)")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()

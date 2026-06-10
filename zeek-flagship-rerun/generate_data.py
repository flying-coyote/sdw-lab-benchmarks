#!/usr/bin/env python3
"""Generate the pinned 10M-row Zeek conn corpus for the flagship re-run.

Streams 1M-row batches into one JSONL file + one Parquet file (bounded memory),
then fingerprints the JSONL with sha256 so the corpus is pinned (methodology #9:
pin the artifact). Field names are the generator's Zeek-native ones (id.orig_h
etc.); the loaders flatten identically for all three arms.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent))
from zeek_generator import ZeekGenerator  # ported verbatim from splunk-db-connect-benchmark

ROWS = 10_000_000
BATCH = 1_000_000
SEED = 42
WORK = Path(__file__).parent / "_work"

SCHEMA = pa.schema([
    ("ts", pa.float64()),
    ("uid", pa.string()),
    ("id.orig_h", pa.string()),
    ("id.orig_p", pa.int32()),
    ("id.resp_h", pa.string()),
    ("id.resp_p", pa.int32()),
    ("proto", pa.string()),
    ("service", pa.string()),
    ("duration", pa.float64()),
    ("orig_bytes", pa.int64()),
    ("resp_bytes", pa.int64()),
    ("conn_state", pa.string()),
    ("missed_bytes", pa.int64()),
    ("history", pa.string()),
    ("orig_pkts", pa.int64()),
    ("resp_pkts", pa.int64()),
    ("tunnel_parents", pa.list_(pa.string())),
])


def main():
    WORK.mkdir(exist_ok=True)
    jsonl = WORK / "zeek_conn_10m.jsonl"
    parquet = WORK / "zeek_conn_10m.parquet"

    gen = ZeekGenerator(seed=SEED)
    writer = pq.ParquetWriter(parquet, SCHEMA, compression="snappy")
    t0 = time.time()
    done = 0
    with open(jsonl, "w") as jf:
        while done < ROWS:
            n = min(BATCH, ROWS - done)
            conns = gen.generate_batch(n)
            for c in conns:
                jf.write(json.dumps(c))
                jf.write("\n")
            data = {k: [c[k] for c in conns] for k in conns[0].keys()}
            writer.write_table(pa.Table.from_pydict(data, schema=SCHEMA))
            done += n
            print(f"  {done:,}/{ROWS:,} rows  ({time.time() - t0:.0f}s)", flush=True)
    writer.close()

    h = hashlib.sha256()
    with open(jsonl, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    meta = {
        "rows": ROWS,
        "seed": SEED,
        "jsonl_sha256": h.hexdigest(),
        "jsonl_bytes": jsonl.stat().st_size,
        "parquet_snappy_bytes": parquet.stat().st_size,
        "generated_unix": time.time(),
        "generator": "zeek_generator.py (ported verbatim from splunk-db-connect-benchmark @ archive)",
    }
    (WORK / "corpus_fingerprint.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()

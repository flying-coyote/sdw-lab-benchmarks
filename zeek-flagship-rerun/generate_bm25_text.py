#!/usr/bin/env python3
"""NEEDLE-BM25 arm (staged-benchmark-open-track-prereg.md, Arm A): extend the pinned 10M-row
zeek-flagship-rerun corpus with a SYNTHETIC text field (HTTP-URI / user-agent / DNS-query-style
strings — no real telemetry, per the injection-surface boundary) so the BM25 fuzzy-full-text
regime — the index's other home turf, alongside needle.py's point-lookup regime — can be
measured against the OpenSearch inverted index vs the ClickHouse/Iceberg lakehouse arms.

Extends the EXISTING corpus by `uid` (read from the pinned _work/zeek_conn_10m.parquet, sha256
c6ed5e3c05f311a6b53fcf6fb39d4f2448c16d74efaf17eb7cba6e76cf5dae52, seed 42, 10,000,000 rows) —
this is a join-key extension, not a new unrelated corpus.

Deterministic, seeded (SEED below), fixed row count = the pinned corpus's row count.

Ground truth planted for the deterministic token/phrase queries (answer-equality gate):
  - RARE_TOKEN in exactly N_RARE rows  -> exact single-token search
  - PHRASE     in exactly N_PHRASE rows (disjoint row set) -> exact phrase/substring search
Five weighted relevance terms (login/session/token/admin/error, independently sampled per row
at different probabilities) give the BM25 ranking query realistic, skewed term frequencies so
relevance ranking is not degenerate.
"""
import hashlib
import json
import random
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

HERE = Path(__file__).parent
WORK = HERE / "_work"
SRC_PARQUET = WORK / "zeek_conn_10m.parquet"
OUT_PARQUET = WORK / "zeek_conn_10m_bm25text.parquet"
OUT_JSONL = WORK / "zeek_conn_10m_bm25text.jsonl"

SEED = 0xB255
BATCH = 1_000_000

RARE_TOKEN = "zqrareplant7k"          # exact single-token search ground truth
N_RARE = 500
PHRASE = "zqplant beacon uplink"      # exact phrase search ground truth (3 tokens, contiguous)
N_PHRASE = 300

RELEVANCE_TERMS = {"login": 0.20, "session": 0.15, "token": 0.10, "admin": 0.05, "error": 0.03}

HTTP_PATHS = ["users", "sessions", "orders", "accounts", "reports", "files", "settings", "search"]
UA_TEMPLATES = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{v}.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36",
    "curl/{v}.1.2",
]
DNS_SUBS = ["www", "api", "cdn", "static", "mail", "vpn", "app", "svc"]
DNS_DOMAINS = ["example-service", "corp-internal", "cloudhost", "datarelay", "netcache"]
DNS_TLDS = ["net", "com", "io"]


def gen_text(rng, plant_rare, plant_phrase):
    kind = rng.random()
    if kind < 0.40:
        base = (f"/api/v{rng.randint(1,3)}/{rng.choice(HTTP_PATHS)}/{rng.randint(1,999999)}"
                f"?id={rng.randint(100000,999999)}")
    elif kind < 0.70:
        tmpl = rng.choice(UA_TEMPLATES)
        base = tmpl.format(v=rng.randint(90, 125))
    else:
        base = f"{rng.choice(DNS_SUBS)}{rng.randint(0,99)}.{rng.choice(DNS_DOMAINS)}.{rng.choice(DNS_TLDS)}"

    extras = []
    for term, p in RELEVANCE_TERMS.items():
        if rng.random() < p:
            extras.append(term)
    if plant_rare:
        extras.append(RARE_TOKEN)
    if plant_phrase:
        extras.append(PHRASE)
    if extras:
        base = base + " " + " ".join(extras)
    return base


def main():
    t0 = time.time()
    uid_col = pq.read_table(SRC_PARQUET, columns=["uid"]).column("uid")
    n = len(uid_col)
    print(f"  read {n:,} uids from pinned corpus ({time.time()-t0:.1f}s)", flush=True)

    rng = random.Random(SEED)
    rare_rows = set(rng.sample(range(n), N_RARE))
    remaining = [i for i in range(n) if i not in rare_rows]
    phrase_rows = set(rng.sample(remaining, N_PHRASE))
    del remaining

    writer = pq.ParquetWriter(OUT_PARQUET, pa.schema([("uid", pa.string()), ("text", pa.string())]),
                              compression="snappy")
    jf = open(OUT_JSONL, "w")
    done = 0
    rng2 = random.Random(SEED ^ 0xA5A5)   # separate stream for text content so planting selection above is stable
    while done < n:
        upper = min(done + BATCH, n)
        uids_batch = uid_col.slice(done, upper - done).to_pylist()
        texts_batch = []
        for local_i, uid in enumerate(uids_batch):
            i = done + local_i
            texts_batch.append(gen_text(rng2, i in rare_rows, i in phrase_rows))
            jf.write(json.dumps({"uid": uid, "text": texts_batch[-1]}))
            jf.write("\n")
        writer.write_table(pa.Table.from_pydict({"uid": uids_batch, "text": texts_batch},
                                                 schema=pa.schema([("uid", pa.string()), ("text", pa.string())])))
        done = upper
        print(f"  {done:,}/{n:,} rows  ({time.time()-t0:.0f}s)", flush=True)
    writer.close()
    jf.close()

    h = hashlib.sha256()
    with open(OUT_JSONL, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    meta = {
        "rows": n,
        "seed": SEED,
        "extends_corpus_sha256": "c6ed5e3c05f311a6b53fcf6fb39d4f2448c16d74efaf17eb7cba6e76cf5dae52",
        "jsonl_sha256": h.hexdigest(),
        "jsonl_bytes": OUT_JSONL.stat().st_size,
        "parquet_snappy_bytes": OUT_PARQUET.stat().st_size,
        "rare_token": RARE_TOKEN, "rare_token_planted_rows": N_RARE,
        "phrase": PHRASE, "phrase_planted_rows": N_PHRASE,
        "relevance_terms": RELEVANCE_TERMS,
        "generated_unix": time.time(),
        "boundary": "structured synthetic strings only; no real telemetry (feedback_security_telemetry_injection_surface)",
    }
    (WORK / "bm25_text_fingerprint.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()

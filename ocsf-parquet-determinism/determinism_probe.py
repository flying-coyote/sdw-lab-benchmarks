"""Is "same data, same file" true? A reproducibility probe for DuckDB → Parquet.

The naive mental model behind content-addressed storage, dedup, and chain-of-custody
hashing is that re-deriving the same logical rows yields the same file, so the same
SHA-256. This probe builds a small normalized event store (a network rollup via
GROUP BY, unioned with two other sources — the shape of a real coalesced SIEM table)
and writes it to Parquet repeatedly under three execution settings, comparing:

  - logical content : SHA-256 of the row SET, order-independent (is the DATA stable?)
  - file bytes      : size + SHA-256 of the .parquet itself (is the FILE stable?)

Settings:
  default-parallel  : DuckDB's defaults (multi-threaded)
  threads=1         : single-threaded
  ordered+parallel  : multi-threaded, with an explicit ORDER BY before COPY
  straight-scan     : a plain SELECT with no aggregation, default parallelism

Everything is seeded off fixed integers (no clocks, no randomness), so the corpus is
identical every run. Any byte movement is therefore the write path, not the data.
"""
import hashlib
import os

import duckdb

TMP = "/tmp"
ROLLUP_MS = 300_000


def build_corpus(con):
    """Deterministic synthetic raw events — no clocks, no randomness."""
    con.execute("""
        CREATE TABLE raw_net AS
            SELECT (i * 2654435761) % 65535        AS port,
                   1767225600000 + (i % 4000)*60000 AS ingest_ms,
                   ((i * 40503) % 100000)          AS dst
            FROM range(400000) t(i);
        CREATE TABLE raw_proc AS
            SELECT 1767225600000 + i*1000          AS ingest_ms,
                   'S-1-5-21-' || (i % 300)        AS sid,
                   'host' || (i % 40)              AS host
            FROM range(60000) t(i);
        CREATE TABLE raw_auth AS
            SELECT 1767225600000 + i*1500          AS ingest_ms,
                   'user' || (i % 500)             AS actor
            FROM range(40000) t(i);
    """)


def coalesced_sql(order_by=False):
    """A coalesced event store: GROUP BY network rollup + UNION ALL of three sources."""
    s = f"""
        SELECT (ingest_ms / {ROLLUP_MS})::BIGINT * {ROLLUP_MS} AS t, 4001 AS cls,
               NULL AS id, port AS p, count(*)::BIGINT AS c
          FROM raw_net GROUP BY 1, port, dst
        UNION ALL
        SELECT ingest_ms, 1007, sid, NULL, 1 FROM raw_proc
        UNION ALL
        SELECT ingest_ms, 3002, actor, NULL, 1 FROM raw_auth
    """
    return f"SELECT * FROM ({s}) ORDER BY 1, 2, 3, 4, 5" if order_by else s


def file_sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]


def content_sha(con, sql):
    rows = con.execute(f"SELECT * FROM ({sql})").fetchall()
    norm = sorted(repr(r) for r in rows)
    return hashlib.sha256("\n".join(norm).encode()).hexdigest()[:16], len(rows)


def trial(label, threads, sql, n=3):
    con = duckdb.connect(":memory:")
    con.execute(f"SET threads={threads}")
    build_corpus(con)
    ch, nrows = content_sha(con, sql)
    sizes, hashes = set(), set()
    for i in range(n):
        p = os.path.join(TMP, f"detprobe_{label}_{i}.parquet")
        con.execute(f"COPY ({sql}) TO '{p}' (FORMAT parquet)")
        sizes.add(os.path.getsize(p)); hashes.add(file_sha(p))
    con.close()
    return {"label": label, "threads": threads, "rows": nrows, "content_sha": ch,
            "file_bytes": sorted(sizes), "bytes_stable": len(sizes) == 1,
            "sha_stable": len(hashes) == 1}


def run():
    return [
        trial("default-parallel", 8, coalesced_sql(order_by=False)),
        trial("threads=1", 1, coalesced_sql(order_by=False)),
        trial("ordered+parallel", 8, coalesced_sql(order_by=True)),
        trial("straight-scan", 8, "SELECT port, ingest_ms, dst FROM raw_net"),
    ]


if __name__ == "__main__":
    rows = run()
    w = max(len(r["label"]) for r in rows)
    print(f"{'setting'.ljust(w)}  thr  rows     content_sha       file_bytes                 "
          f"bytes_stable  sha_stable")
    for r in rows:
        fb = "/".join(str(b) for b in r["file_bytes"])
        print(f"{r['label'].ljust(w)}  {r['threads']:>3}  {r['rows']:<7}  {r['content_sha']}  "
              f"{fb:<25}  {str(r['bytes_stable']):<12}  {r['sha_stable']}")

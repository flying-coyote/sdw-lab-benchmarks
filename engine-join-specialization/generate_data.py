#!/usr/bin/env python3
"""Generate pinned corpora + ground truth (runs on host, no docker needed).

1. TPC-H SF10 via DuckDB tpch extension (deterministic dbgen) -> _work/tpch/*.parquet
2. SOC companions derived from the zeek-flagship-rerun pinned conn corpus
   (sha256 c6ed5e3c...) -> _work/soc/{conn,dns,assets,ioc,conn_enriched}.parquet
3. Ground-truth answers for all 11 canonical queries, computed by DuckDB directly over
   the source Parquet -> _work/ground_truth.json (the oracle for the equality gate)
4. sha256 fingerprints for every parquet -> _work/corpus_fingerprints.json
"""
import hashlib
import json
import sys
from pathlib import Path

import duckdb
import numpy as np

from queries import QUERIES, TPCH_TABLES, SOC_TABLES, render, normalize

HERE = Path(__file__).parent
WORK = HERE / "_work"
ZFR = HERE.parent / "zeek-flagship-rerun" / "_work" / "zeek_conn_10m.parquet"
SF = 10
SEED = 42

CONN_COLS = ('ts, uid, "id.orig_h" AS orig_h, "id.orig_p" AS orig_p, '
             '"id.resp_h" AS resp_h, "id.resp_p" AS resp_p, proto, service, duration, '
             'orig_bytes, resp_bytes, conn_state, missed_bytes, history, orig_pkts, resp_pkts')


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gen_tpch(con):
    out_dir = WORK / "tpch"
    out_dir.mkdir(parents=True, exist_ok=True)
    if all((out_dir / f"{t}.parquet").exists() for t in TPCH_TABLES):
        print("tpch: parquet exists, skipping dbgen", flush=True)
        return
    print(f"tpch: dbgen sf={SF} ...", flush=True)
    con.execute("INSTALL tpch; LOAD tpch;")
    con.execute(f"CALL dbgen(sf={SF})")
    for t in TPCH_TABLES:
        con.execute(f"COPY {t} TO '{out_dir}/{t}.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n:,} rows", flush=True)


def gen_companions(con):
    out_dir = WORK / "soc"
    out_dir.mkdir(parents=True, exist_ok=True)
    assert ZFR.exists(), f"pinned corpus missing: {ZFR}"
    con.execute(f"CREATE OR REPLACE VIEW conn_src AS SELECT {CONN_COLS} FROM read_parquet('{ZFR}')")

    if not (out_dir / "conn.parquet").exists():
        con.execute(f"COPY (SELECT * FROM conn_src) TO '{out_dir}/conn.parquet' "
                    f"(FORMAT PARQUET, COMPRESSION ZSTD)")
        print("soc: conn flattened", flush=True)

    rng = np.random.default_rng(SEED)
    src_hosts = [r[0] for r in con.execute(
        "SELECT DISTINCT orig_h FROM conn_src ORDER BY orig_h").fetchall()]
    dst_hosts = [r[0] for r in con.execute(
        "SELECT DISTINCT resp_h FROM conn_src ORDER BY resp_h").fetchall()]
    ts_min, ts_max = con.execute("SELECT min(ts), max(ts) FROM conn_src").fetchone()
    print(f"soc: {len(src_hosts):,} sources, {len(dst_hosts):,} destinations, "
          f"span {ts_max - ts_min:.0f}s", flush=True)

    import pyarrow as pa
    import pyarrow.parquet as pq

    # assets: one row per distinct source host
    if not (out_dir / "assets.parquet").exists():
        n = len(src_hosts)
        sites = [f"site-{i:02d}" for i in range(8)]
        depts = ["soc", "it-ops", "engineering", "finance", "hr", "legal", "sales",
                 "marketing", "exec", "facilities", "research", "support"]
        crit = rng.choice(["low", "medium", "high", "critical"], size=n,
                          p=[0.50, 0.30, 0.15, 0.05])
        tbl = pa.table({
            "ip": pa.array(src_hosts, pa.string()),
            "site": pa.array(rng.choice(sites, size=n), pa.string()),
            "dept": pa.array(rng.choice(depts, size=n), pa.string()),
            "criticality": pa.array(crit, pa.string()),
            "owner": pa.array([f"user{i:05d}" for i in range(n)], pa.string()),
        })
        pq.write_table(tbl, out_dir / "assets.parquet", compression="zstd")
        print(f"soc: assets {n:,} rows", flush=True)

    # dns: 1M rows, sources zipf-weighted from the conn population, ts within span
    if not (out_dir / "dns.parquet").exists():
        n = 1_000_000
        w = 1.0 / np.arange(1, len(src_hosts) + 1)
        w /= w.sum()
        shuffled = rng.permutation(src_hosts)
        orig = rng.choice(shuffled, size=n, p=w)
        n_dom = 10_000
        dw = 1.0 / np.arange(1, n_dom + 1)
        dw /= dw.sum()
        dom_idx = rng.choice(n_dom, size=n, p=dw)
        domains = np.array([f"host{i}.example-{i % 97}.com" for i in range(n_dom)])
        tbl = pa.table({
            "ts": pa.array(rng.uniform(ts_min, ts_max, size=n), pa.float64()),
            "orig_h": pa.array(orig, pa.string()),
            "query": pa.array(domains[dom_idx], pa.string()),
            "qtype": pa.array(rng.choice(["A", "AAAA", "CNAME"], size=n, p=[0.7, 0.2, 0.1]),
                              pa.string()),
            "answer": pa.array(rng.choice(dst_hosts, size=n), pa.string()),
        })
        pq.write_table(tbl, out_dir / "dns.parquet", compression="zstd")
        print(f"soc: dns {n:,} rows", flush=True)

    # ioc: 2,500 hit indicators sampled from resp_h + 2,500 TEST-NET misses
    if not (out_dir / "ioc.parquet").exists():
        hits = list(rng.choice(dst_hosts, size=2500, replace=False))
        dst_set = set(dst_hosts)
        misses = []
        j = 0
        while len(misses) < 2500:
            cand = f"203.0.{j // 250}.{j % 250 + 1}"
            if cand not in dst_set:
                misses.append(cand)
            j += 1
        indicators = hits + misses
        tbl = pa.table({
            "ioc_value": pa.array(indicators, pa.string()),
            "source": pa.array(rng.choice(["osint-feed-a", "osint-feed-b", "internal"],
                                          size=5000), pa.string()),
            "severity": pa.array(rng.choice(["low", "medium", "high"], size=5000),
                                 pa.string()),
        })
        pq.write_table(tbl, out_dir / "ioc.parquet", compression="zstd")
        print("soc: ioc 5,000 rows (2,500 hit / 2,500 miss)", flush=True)

    # conn_enriched: the denormalized twin (join-tax pair)
    if not (out_dir / "conn_enriched.parquet").exists():
        con.execute(f"""
            COPY (
                SELECT c.*, a.site, a.dept, a.criticality, a.owner
                FROM conn_src c
                JOIN read_parquet('{out_dir}/assets.parquet') a ON c.orig_h = a.ip
            ) TO '{out_dir}/conn_enriched.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{out_dir}/conn_enriched.parquet')"
        ).fetchone()[0]
        assert n == 10_000_000, f"conn_enriched rows {n} != 10M (asset key not covering?)"
        print("soc: conn_enriched 10,000,000 rows", flush=True)


def ground_truth(con):
    """Run every canonical query in DuckDB over the source parquet -> oracle answers."""
    refs = {t: f"read_parquet('{WORK}/tpch/{t}.parquet')" for t in TPCH_TABLES}
    refs |= {t: f"read_parquet('{WORK}/soc/{t}.parquet')" for t in SOC_TABLES}
    gt = {}
    for name, sql in QUERIES.items():
        rows = con.execute(render(sql, refs)).fetchall()
        gt[name] = normalize(rows)
        assert gt[name], f"{name}: EMPTY ground truth (corpus-realism check failed)"
        print(f"ground truth {name}: {len(gt[name])} row(s), first={gt[name][0]}", flush=True)
    (WORK / "ground_truth.json").write_text(json.dumps(gt, indent=2))


def fingerprints():
    fp = {}
    for sub in ("tpch", "soc"):
        for p in sorted((WORK / sub).glob("*.parquet")):
            fp[f"{sub}/{p.name}"] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    (WORK / "corpus_fingerprints.json").write_text(json.dumps(fp, indent=2))
    print(f"fingerprints: {len(fp)} files pinned", flush=True)


def main():
    WORK.mkdir(exist_ok=True)
    con = duckdb.connect()
    gen_tpch(con)
    gen_companions(con)
    ground_truth(con)
    fingerprints()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()

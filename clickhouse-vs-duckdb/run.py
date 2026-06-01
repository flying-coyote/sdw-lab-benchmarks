"""Run the ClickHouse-vs-DuckDB OCSF query benchmark, verify what is verifiable,
write results.

What is deterministic, and is asserted here:
  * the corpus — generated twice, fingerprints compared (sums commute, so this is
    order- and thread-independent), and
  * the answers — every query must return identical rows on both engines, in both
    the Parquet-in-place and native-store configs.

What is not deterministic, and is reported as a distribution, never a constant:
  * the latencies — wall-clock medians (min/max shown) on one machine. Run them on
    other hardware and the millisecond numbers move; the point is the *shape* of
    which engine wins which query, not the absolute milliseconds.

Usage:
    python run.py            # scales 1M and 10M
    python run.py 2000000    # custom scale(s)
"""

import hashlib
import json
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)

import chdb  # noqa: E402
import duckdb  # noqa: E402

from common import canonical  # noqa: E402
import corpus  # noqa: E402
import bench  # noqa: E402

WORK_DIR = os.path.join(HERE, "_work")
RESULTS_DIR = os.path.join(HERE, "results")
DEFAULT_SCALES = [1_000_000, 10_000_000]


def _corpus_is_deterministic(scales):
    """Generate each scale's fingerprint twice; both must match."""
    con = duckdb.connect()
    digests = {}
    ok = True
    for n in scales:
        f1 = corpus.fingerprint(con, n)
        f2 = corpus.fingerprint(con, n)
        ok = ok and (f1 == f2)
        digests[n] = hashlib.sha256(canonical(f1).encode()).hexdigest()[:16]
    con.close()
    return ok, digests


def main():
    scales = [int(a) for a in sys.argv[1:]] or DEFAULT_SCALES
    os.makedirs(RESULTS_DIR, exist_ok=True)

    corpus_ok, corpus_digests = _corpus_is_deterministic(scales)

    scale_results = []
    for n in scales:
        parquet_path = os.path.join(WORK_DIR, f"corpus_{n}.parquet")
        r = bench.run_scale(n, parquet_path)
        r["corpus_fingerprint_sha256_16"] = corpus_digests[n]
        scale_results.append(r)

    # The hard gate: every query, every config, every scale must agree across engines.
    disagreements = [
        {"scale": r["n_events"], "config": cfg_name, "query": q["id"]}
        for r in scale_results
        for cfg_name, cfg in r["configs"].items()
        for q in cfg["queries"]
        if not q["answers_agree"]
    ]
    all_agree = not disagreements

    results = {
        "benchmark": "clickhouse-vs-duckdb-ocsf (C3)",
        "evidence_tier": "B (reproducible corpus + cross-engine-verified answers; "
                         "latencies are machine-specific, not a production claim)",
        "environment": {
            "duckdb_version": duckdb.__version__,
            "chdb_version": chdb.__version__,
            "clickhouse_engine": "chDB (embedded ClickHouse)",
            "cpu_count": os.cpu_count(),
            "platform": platform.platform(),
            "note": "single host, both engines in-process; WSL2 — treat absolute ms as machine-specific",
        },
        "corpus_deterministic": corpus_ok,
        "answers_agree_all": all_agree,
        "disagreements": disagreements,
        "scales": scale_results,
    }

    with open(os.path.join(RESULTS_DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
    _write_markdown(results)

    digest = hashlib.sha256(
        canonical({"corpus_digests": corpus_digests, "agree": all_agree}).encode()
    ).hexdigest()[:16]
    print(
        f"corpus_deterministic={corpus_ok}  answers_agree_all={all_agree}  "
        f"duckdb={duckdb.__version__}  chdb={chdb.__version__}  verify_sha256[:16]={digest}"
    )
    if disagreements:
        print(f"  WARNING: {len(disagreements)} cross-engine answer disagreement(s):")
        for d in disagreements:
            print(f"    {d}")
    print(f"wrote {os.path.join(RESULTS_DIR, 'results.json')}")
    print(f"wrote {os.path.join(RESULTS_DIR, 'RESULTS.md')}")


def _fmt(ms):
    return f"{ms:.1f}"


def _write_markdown(results):
    env = results["environment"]
    lines = []
    a = lines.append

    a("# Results — ClickHouse vs DuckDB on OCSF-shaped event data (C3)\n")
    a(f"- DuckDB: `{env['duckdb_version']}`  ·  ClickHouse engine: `{env['clickhouse_engine']}` "
      f"(`chdb {env['chdb_version']}`)  ")
    a(f"- Host: {env['cpu_count']} vCPU, `{env['platform']}`  ")
    a(f"- Corpus reproducible (fingerprint matches on re-generation): **{results['corpus_deterministic']}**  ")
    a(f"- Cross-engine answers identical (every query, every config): **{results['answers_agree_all']}**  ")
    a(f"- Evidence tier: {results['evidence_tier']}\n")
    a("Latencies are wall-clock **medians** (min/max in the JSON) over repeated trials "
      "after warmup, on one machine. They are not deterministic and not a universal "
      "constant — read them as *which engine wins which query shape*, not as absolute "
      "milliseconds you should expect on other hardware. The corpus and the answers are "
      "the reproducible parts; see `METHODOLOGY.md`.\n")

    for r in results["scales"]:
        n = r["n_events"]
        mb = r["parquet_bytes"] / 1e6
        a(f"## {n:,} events  (Parquet {mb:.0f} MB, fingerprint `{r['corpus_fingerprint_sha256_16']}`)\n")
        for cfg_name, label in (
            ("parquet_in_place", "Config A — both engines query the same Parquet file in place"),
            ("native_store", "Config B — each engine queries its own native store"),
        ):
            cfg = r["configs"][cfg_name]
            a(f"### {label}\n")
            if "ingest" in cfg:
                ing = cfg["ingest"]
                a(f"Load time (median): DuckDB native `CREATE TABLE` "
                  f"**{_fmt(ing['duckdb_native_load']['median_ms'])} ms** · "
                  f"ClickHouse MergeTree insert "
                  f"**{_fmt(ing['clickhouse_mergetree_load']['median_ms'])} ms**.\n")
            a("| query | result rows | answers agree | DuckDB ms | ClickHouse ms | faster | × |")
            a("|---|--:|:--:|--:|--:|:--:|--:|")
            for q in cfg["queries"]:
                a(f"| {q['title']} | {q['result_rows']} | "
                  f"{'yes' if q['answers_agree'] else '**NO**'} | "
                  f"{_fmt(q['duckdb']['median_ms'])} | {_fmt(q['clickhouse']['median_ms'])} | "
                  f"{q['faster_engine']} | {q['speed_ratio']} |")
            a("")
            wins = _win_summary(cfg["queries"])
            a(f"_Per-query winners: DuckDB {wins['duckdb']}, ClickHouse {wins['clickhouse']}, "
              f"tie {wins['tie']} (of {wins['total']})._\n")

    with open(os.path.join(RESULTS_DIR, "RESULTS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def _win_summary(queries):
    out = {"duckdb": 0, "clickhouse": 0, "tie": 0, "total": len(queries)}
    for q in queries:
        out[q["faster_engine"]] = out.get(q["faster_engine"], 0) + 1
    return out


if __name__ == "__main__":
    main()

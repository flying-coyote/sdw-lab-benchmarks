"""R4 — when a schema-trained ZSTD dictionary helps OCSF data, and when Parquet already has it.

"Use zstd" is the usual compression answer, but it hides a regime dimension that matters for security
data specifically. A ZSTD *dictionary* trained on a representative sample lets the codec exploit
cross-record redundancy that a generic codec can only find inside whatever buffer it's handed — so the
dictionary's value depends entirely on how the data is framed:

  - per-event (streaming ingest, queue messages, per-record archival): each ~200-byte OCSF JSON event is
    compressed alone, so a generic codec sees almost no redundancy and a trained dictionary wins big.
  - batched (small blocks of events): as the block grows, a generic codec starts finding the same
    cross-record redundancy on its own, and the dictionary's edge shrinks.
  - columnar (a large Parquet row group): the format already dictionary-encodes each column and then
    block-compresses, capturing the redundancy structurally — the trained-dictionary payload trick
    doesn't transfer, and Parquet reaches a ratio the per-record approaches can't.

Security ingestion lives in the first regime (small, frequent, schema-uniform records); the analytical
lake lives in the third. So the right compression choice is set by where in the pipeline the bytes sit,
not by the codec name — which is the nuance this measures rather than asserting.

Discipline: the dictionary is trained on a HELD-OUT sample (a disjoint row range with the same schema and
distribution, never the test records), so the ratio is honest generalization, not memorizing the test set.
Sizes are exact and reproducible; compress/decompress latencies are medians with CV (machine-specific).

    python run.py                 # default 100k test events, 50k held-out training events
"""

import argparse
import io
import json
import os
import sys
import zlib

import duckdb
import zstandard as zstd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, os.path.join(HERE, "..", "clickhouse-vs-duckdb"))
from common import configure_duckdb, time_trials  # noqa: E402
import corpus  # noqa: E402  (reuse the deterministic OCSF row generator)

DICT_SIZE = 112_640         # 110 KB trained dictionary (zstd's common default magnitude)
BLOCK_SIZES = [1, 10, 100, 1000]   # events per compressed block: per-event -> small batch


def gen_payloads(con, start, n):
    """n OCSF events as individual JSON byte-payloads (the raw-retention / queue-message form).

    corpus.gen_select generates from range(0, n); we shift the row id by `start` so the held-out
    training rows are a disjoint range with the same schema and distribution as the test rows."""
    # the generator keys every column off i; shifting the range shifts every row deterministically,
    # giving held-out records with the same schema/distribution (and a disjoint row_id, so the JSON
    # payloads can't collide with the test set).
    sel = corpus.gen_select(n).replace("FROM range(0, {n})".format(n=n), f"FROM range({start}, {start + n})")
    cols = [c[0] for c in con.execute(f"SELECT * FROM ({sel}) LIMIT 0").description]
    rows = con.execute(sel).fetchall()
    out = []
    for r in rows:
        # compact JSON, sorted keys -> deterministic bytes; this is the per-event payload
        out.append(json.dumps(dict(zip(cols, r)), sort_keys=True, separators=(",", ":"),
                              default=str).encode())
    return out


def blocks(payloads, k):
    """Group payloads into blocks of k events (k=1 is per-event). Each block is the unit compressed."""
    if k == 1:
        return payloads
    out = []
    for i in range(0, len(payloads), k):
        out.append(b"\n".join(payloads[i:i + k]))
    return out


def codecs(train_dict):
    """The codecs under test, as (name, compress_fn, decompress_fn). Dictionary codecs use the
    held-out-trained dictionary; generic ones don't. zlib-6 is the ubiquitous baseline."""
    d = zstd.ZstdCompressionDict(train_dict) if train_dict else None
    def zc(level, use_dict):
        c = zstd.ZstdCompressor(level=level, dict_data=d) if use_dict else zstd.ZstdCompressor(level=level)
        dc = zstd.ZstdDecompressor(dict_data=d) if use_dict else zstd.ZstdDecompressor()
        return (lambda b: c.compress(b)), (lambda b: dc.decompress(b))
    out = [("zlib-6", lambda b: zlib.compress(b, 6), lambda b: zlib.decompress(b))]
    for lvl in (3, 19):
        zcc, zdd = zc(lvl, False)
        out.append((f"zstd-{lvl}", zcc, zdd))
        if train_dict:
            zcd, zdcd = zc(lvl, True)
            out.append((f"zstd-{lvl}+dict", zcd, zdcd))
    return out


def measure(blks, comp, decomp):
    """Compressed size + compress/decompress latency (CV) over the whole block set as one trial."""
    comp_blobs = [comp(b) for b in blks]
    comp_bytes = sum(len(c) for c in comp_blobs)
    ct = time_trials(lambda: [comp(b) for b in blks], warmup=1, trials=5)
    dt = time_trials(lambda: [decomp(c) for c in comp_blobs], warmup=1, trials=5)
    # integrity: round-trip must reproduce the input
    ok = all(decomp(comp(b)) == b for b in blks[: min(50, len(blks))])
    return comp_bytes, ct, dt, ok


def parquet_reference(con, test_sel, work):
    """Columnar baseline: the same events written to one Parquet row group via PyArrow, with the
    codec and the native dictionary encoding toggled. File size is the comparison; this is the regime
    the per-record payload codecs can't reach because the format captures column redundancy structurally."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    tbl = con.execute(test_sel).fetch_arrow_table()
    raw = tbl.nbytes
    refs = {}
    for name, comp, lvl, use_dict in [
        ("parquet snappy + dict", "snappy", None, True),
        ("parquet zstd-3 + dict", "zstd", 3, True),
        ("parquet zstd-19 + dict", "zstd", 19, True),
        ("parquet zstd-3 no-dict", "zstd", 3, False),
    ]:
        p = os.path.join(work, name.replace(" ", "_").replace("+", "p") + ".parquet")
        kw = {"compression": comp, "use_dictionary": use_dict}
        if lvl is not None:
            kw["compression_level"] = lvl
        pq.write_table(tbl, p, row_group_size=len(tbl), **kw)
        refs[name] = {"bytes": os.path.getsize(p)}
    return raw, refs


def run(n_test, n_train):
    import tempfile
    work = tempfile.mkdtemp(prefix="zstd_dict_")
    try:
        con = configure_duckdb(duckdb.connect())
        # held-out training rows are a disjoint range AFTER the test rows
        train_payloads = gen_payloads(con, n_test, n_train)
        test_payloads = gen_payloads(con, 0, n_test)
        raw_bytes = sum(len(p) for p in test_payloads)

        # train the dictionary on the held-out payloads only
        trained = zstd.train_dictionary(DICT_SIZE, train_payloads).as_bytes()

        regimes = {}
        for k in BLOCK_SIZES:
            blks = blocks(test_payloads, k)
            per = {}
            for name, comp, decomp in codecs(trained):
                cb, ct, dt, ok = measure(blks, comp, decomp)
                per[name] = {"comp_bytes": cb, "ratio": round(raw_bytes / cb, 2),
                             "comp_ms": ct["median_ms"], "comp_cv": ct["cv_pct"],
                             "decomp_ms": dt["median_ms"], "decomp_cv": dt["cv_pct"],
                             "roundtrip_ok": ok}
            regimes[f"block_{k}"] = {"events_per_block": k, "n_blocks": len(blks), "codecs": per}
            best = max(per.items(), key=lambda kv: kv[1]["ratio"])
            print(f"  block={k:<4} ({len(blks)} blocks)  best ratio: {best[0]} {best[1]['ratio']}x  "
                  f"| zstd-19 {per['zstd-19']['ratio']}x  zstd-19+dict "
                  f"{per.get('zstd-19+dict',{}).get('ratio','-')}x")

        test_sel = corpus.gen_select(n_test)
        pq_raw, pq_refs = parquet_reference(con, test_sel, work)
        for nm, v in pq_refs.items():
            v["ratio_vs_json"] = round(raw_bytes / v["bytes"], 2)
        con.close()

        return {"benchmark": "ocsf-zstd-dictionary (R4)",
                "evidence_tier": "B (sizes exact + reproducible; latencies machine-specific medians w/ CV)",
                "hypothesis": "H-MV-ZSTD-01 (compression regime, not codec name)",
                "n_test_events": n_test, "n_train_events_heldout": n_train,
                "dict_size_bytes": DICT_SIZE,
                "raw_json_bytes": raw_bytes, "raw_json_bytes_per_event": round(raw_bytes / n_test, 1),
                "regimes": regimes,
                "columnar_reference": {"raw_arrow_bytes": pq_raw, "parquet": pq_refs}}
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def render_md(res):
    def regime_rows(rk):
        cs = res["regimes"][rk]["codecs"]
        return "\n".join(
            f"| {name} | {v['ratio']}× | {v['comp_ms']:.0f} ({v['comp_cv']:.0f}%) | "
            f"{v['decomp_ms']:.0f} ({v['decomp_cv']:.0f}%) |" for name, v in cs.items())
    tables = "\n\n".join(
        f"### {res['regimes'][rk]['events_per_block']} event(s) per block "
        f"({res['regimes'][rk]['n_blocks']} blocks)\n\n"
        f"| codec | ratio vs raw JSON | compress ms (cv) | decompress ms (cv) |\n"
        f"|---|--:|--:|--:|\n{regime_rows(rk)}" for rk in res["regimes"])
    pq = "\n".join(f"| {nm} | {v['bytes']/1e6:.2f} MB | {v['ratio_vs_json']}× |"
                   for nm, v in res["columnar_reference"]["parquet"].items())
    return f"""# When a schema-trained ZSTD dictionary helps OCSF data (R4)

**Tier B · single machine.** {res['n_test_events']:,} OCSF events (~{res['raw_json_bytes_per_event']:.0f}
bytes of JSON each) compressed under a sweep of codecs and block sizes. The ZSTD dictionary is trained on
a **held-out** {res['n_train_events_heldout']:,}-event sample (a disjoint row range, same schema and
distribution, never the test records), so the ratios are honest generalization. Sizes are exact; latencies
are medians with CV.

## Payload regimes — per-event to batched

{tables}

## Columnar reference (one large Parquet row group, PyArrow)

The same events written columnar, where the format dictionary-encodes each column then block-compresses —
capturing cross-record redundancy structurally rather than via a trained payload dictionary:

| layout | size | ratio vs raw JSON |
|---|--:|--:|
{pq}

## Reading

The dictionary's value is a function of how the bytes are framed. At one event per block — the streaming
ingest / queue-message / per-record archival regime security pipelines actually run — a generic codec has
almost no redundancy to exploit inside a ~200-byte payload, so the trained dictionary is the difference
between a poor ratio and a good one. As events are batched into larger blocks, a generic codec finds the
same cross-record redundancy on its own and the dictionary's edge narrows. By the time the data is a large
Parquet row group, the format has already dictionary-encoded each column and block-compressed it, reaching
a ratio the per-record payload codecs can't, and the trained-dictionary trick no longer transfers.

So "use zstd" is an incomplete answer: the right move is set by where in the pipeline the bytes sit. The
per-event hot path that dominates security ingestion is exactly where a schema-trained dictionary pays,
and exactly where a generic codec underperforms — while the analytical lake, which is columnar by
construction, gets its compression from the format and doesn't need the dictionary. The regime is the
lever, not the codec name. Tier B, single machine; the crossover shape is the transferable finding, the
magnitudes are this corpus's.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", type=int, default=100_000)
    ap.add_argument("--train", type=int, default=50_000)
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    out = os.path.join(rdir, "results.json")
    if args.render_only:
        res = json.load(open(out))
    else:
        res = run(args.test, args.train)
        with open(out, "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "RESULTS.md"), "w") as f:
        f.write(render_md(res))
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()

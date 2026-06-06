"""Reproducibility-by-construction: pin the artifact, sweep the scale.

The chDB Bloom-pushdown undercount taught two methodology lessons the hard way, and this script bakes both in
so the next finding can't hide the same way:

  1. SCALE-DEPENDENT. The undercount reproduces at 100M rows / ~8k row groups and not at 10M / ~800, so a
     "cheap" smaller-scale isolation reported clean while the real bug lived one order of magnitude up. The
     fix is to *sweep* scales (lib.common.scale_sweep) rather than trust one.
  2. LAYOUT-DEPENDENT / not byte-reproducible. A fresh DuckDB write rolls a different row-group composition
     each run (the parallel writer isn't byte-reproducible), so "regenerate with the generator + versions"
     does not pin a finding — the artifact's *logical fingerprint* + *structural manifest* do
     (lib.common.pin_artifact). The manifest is also where the precondition lives: the bug needs enough row
     groups, which the manifest records explicitly instead of leaving it implicit in "the generator".

For each scale it writes the DuckDB-Bloom file, pins it (fingerprint + manifest with row-group count and
bloom presence + byte hash), then samples filter values and counts how many undercount under the v3 reader's
default Bloom-pushdown versus the same query with pushdown off (the in-engine control, no external truth
needed). The undercount appears at scale, with the pinned manifest making the precondition (row-group count,
bloom present) explicit. Default scales [1M, 10M]; pass 100000000 to see the trigger (the 100M run is slow).

    python scale_pin_repro.py            # 1M + 10M (fast; both clean — shows the method)
    python scale_pin_repro.py 100000000  # add the 100M scale where it reproduces (~2-3 min)
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import common  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RG = 12_288
NDV = 2000
SAMPLE = 64   # filter values sampled per scale; ~14% undercount at 100M, so a sample catches several


def _gen_sql(n):
    # the report's generator: a ~2000-distinct string column DuckDB writes WITH a Bloom filter
    return (f"SELECT ('user' || (hash(i::VARCHAR || 'u') % {NDV})::VARCHAR) AS user_name "
            f"FROM range(0, {n}) t(i)")


def probe(scale):
    con = common.connect()
    work = tempfile.mkdtemp(prefix="scalepin_")
    pq = os.path.join(work, f"bloom_{scale}.parquet")
    con.execute(f"SET preserve_insertion_order=false")
    con.execute(f"COPY ({_gen_sql(scale)}) TO '{pq}' (FORMAT parquet, ROW_GROUP_SIZE {RG})")
    pin = common.pin_artifact(con, pq)   # fingerprint + manifest (row groups, bloom) + byte hash

    from chdb import session as chs
    sess = chs.Session()

    def ch(value, bloom_on):
        setting = "" if bloom_on else " SETTINGS input_format_parquet_bloom_filter_push_down=0"
        return int(sess.query(
            f"SELECT count(*) FROM file('{pq}', Parquet) WHERE user_name = '{value}'{setting}",
            "CSV").data().strip())

    # in-engine control: default (Bloom pushdown on) vs pushdown off, over the same file
    values = [f"user{v}" for v in range(SAMPLE)]
    undercounts = []
    for v in values:
        on, off = ch(v, True), ch(v, False)
        if on != off:
            undercounts.append({"value": v, "default": on, "bloom_off": off, "short": off - on})
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    return {
        "scale": scale,
        "artifact": {"logical_fingerprint": pin["logical_fingerprint"],
                     "n_row_groups": pin["manifest"]["n_row_groups"],
                     "user_name_bloom": pin["manifest"]["columns"]["user_name"]["has_bloom"],
                     "bytes_sha256": pin["bytes_sha256"]},
        "sampled": SAMPLE,
        "undercounts": len(undercounts),
        "examples": undercounts[:5],
    }


def main():
    scales = [int(a) for a in sys.argv[1:]] or [1_000_000, 10_000_000]
    results = common.scale_sweep(probe, scales)
    out = {
        "benchmark": "chDB Bloom undercount — pinned + scale-swept (reproducibility-by-construction)",
        "method": "lib.common.pin_artifact (layout-independent fingerprint + structural manifest) + scale_sweep",
        "row_group_size": RG, "distinct_values": NDV,
        "environment": {"duckdb": __import__("duckdb").__version__, "chdb": __import__("chdb").__version__},
        "by_scale": {str(s): results[s] for s in scales},
    }
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(out, open(os.path.join(rdir, "scale_pin_repro.json"), "w"), indent=2, sort_keys=True)
    for s in scales:
        r = results[s]
        print(f"scale={s:>12,} rgs={r['artifact']['n_row_groups']:>5} bloom={r['artifact']['user_name_bloom']} "
              f"fp={r['artifact']['logical_fingerprint'][:10]} undercounts={r['undercounts']}/{r['sampled']}"
              + (f"  e.g. {r['examples'][0]['value']} short {r['examples'][0]['short']}" if r['examples'] else ""))
    print("wrote results/scale_pin_repro.json")


if __name__ == "__main__":
    main()

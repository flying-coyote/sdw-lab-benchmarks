"""T2.5 — isolate R8's topn_src divergence: extension read-path vs memory-cap × spill.

R8 (1B, same-files) found 3/4 queries at parity on byte-identical data but topn_src (a 16.7M-distinct
GROUP BY) ran 1.30× faster on DuckLake than on the Iceberg extension — beyond CV. Two candidate causes the
R8 note couldn't separate: (a) the two DuckDB extensions' (iceberg_scan vs ducklake) scan/read paths
genuinely differ on a heavy aggregate, or (b) a 28 GB-cap × drvfs-spill interaction (DuckLake's elevated CV
at 1B was consistent with variable spill).

This separates them at the cheaper 100M scale by adding the controls R8 lacked:
  - a THIRD arm: bare `read_parquet(glob)` over the same files — DuckDB's native reader, no catalog
    extension — the scan-path baseline both extensions should match if neither adds overhead.
  - TWO memory configs on the identical data: a HIGH cap where the 16.7M-group hash aggregate fits in RAM
    (no spill), and a deliberately LOW cap that FORCES the aggregate to spill.
If the iceberg-vs-ducklake gap appears only under the forced-spill cap, the cause is spill, not the read
path; if it persists with no spill, it's the extensions' read path. Feeds H-ICEBERG-INTERFACE-01's
"not-unconditional" caution. Tier B, single machine.

    python topn_isolation.py --rows 100000000
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import configure_duckdb, DUCK_TEMP_DIR  # noqa: E402
from same_files_scan import (write_canonical, copy_tree, register_iceberg,  # noqa: E402
                             register_ducklake, timed, dir_bytes)

TOPN = "SELECT src_ip, count(*) c FROM {t} GROUP BY 1 ORDER BY c DESC, src_ip LIMIT 20"
FILTERED = "SELECT count(*) FROM {t} WHERE dst_port = 443"   # cheap control (no big hash table)
MEM_CONFIGS = [("high_cap_no_spill", "40GB"), ("low_cap_forced_spill", "2GB")]


def run(total_rows, batch, warmup, trials):
    work = tempfile.mkdtemp(prefix="topn_iso_")
    try:
        con = configure_duckdb(duckdb.connect())
        con.execute("INSTALL iceberg; LOAD iceberg; INSTALL ducklake; LOAD ducklake")
        con.execute(f"SET temp_directory='{DUCK_TEMP_DIR}'")
        cdir, canon = write_canonical(con, work, total_rows, batch)
        ice_files = copy_tree(canon, os.path.join(work, "ice_files"))
        dl_files = copy_tree(canon, os.path.join(work, "dl_files"))
        identical = (dir_bytes(ice_files) == dir_bytes(dl_files) == dir_bytes(canon))
        arms = {
            "iceberg_ext": register_iceberg(work, ice_files),
            "ducklake": register_ducklake(con, work, dl_files),
            "read_parquet_glob": (lambda q: q.format(t=f"read_parquet('{cdir}/*.parquet')")),
        }
        # distinct src_ip (the aggregate's group count) for context
        groups = con.execute(arms["read_parquet_glob"]("SELECT count(DISTINCT src_ip) FROM {t}")).fetchone()[0]

        out = {}
        for cfg_name, limit in MEM_CONFIGS:
            con.execute(f"SET memory_limit='{limit}'")
            out[cfg_name] = {}
            for arm, q in arms.items():
                topn = timed(con, q(TOPN), warmup, trials)
                filt = timed(con, q(FILTERED), warmup, trials)
                out[cfg_name][arm] = {"topn_src": topn, "filtered": filt}
                print(f"  [{cfg_name:22} {limit:>5}]  {arm:18}  topn {topn['median_ms']:>7.0f}ms "
                      f"(cv {topn['cv_pct']:>4.1f})  filtered {filt['median_ms']:>6.0f}ms", flush=True)
        con.close()

        def ratio(cfg, a, b, q="topn_src"):
            return round(out[cfg][a][q]["median_ms"] / max(out[cfg][b][q]["median_ms"], 0.01), 2)
        verdict = {
            "topn_ice_over_dl_high_cap": ratio("high_cap_no_spill", "iceberg_ext", "ducklake"),
            "topn_ice_over_dl_forced_spill": ratio("low_cap_forced_spill", "iceberg_ext", "ducklake"),
            "topn_ice_over_glob_high_cap": ratio("high_cap_no_spill", "iceberg_ext", "read_parquet_glob"),
            "topn_dl_over_glob_high_cap": ratio("high_cap_no_spill", "ducklake", "read_parquet_glob"),
        }
        return {"benchmark": "ocsf-read-scan topn isolation (T2.5)",
                "evidence_tier": "B (single machine; hot/warm; medians + CV)",
                "hypothesis": "H-ICEBERG-INTERFACE-01 (R8 topn_src divergence isolation)",
                "n_rows": total_rows, "distinct_src_ip_groups": groups,
                "bytes_identical": identical, "trials": trials,
                "verdict": verdict, "configs": out}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(r):
    def cell(cfg, arm, q):
        v = r["configs"][cfg][arm][q]
        return f"{v['median_ms']:.0f} ({v['cv_pct']:.0f}%)"
    arms = ["iceberg_ext", "ducklake", "read_parquet_glob"]
    rows = "\n".join(
        f"| {cfg} | " + " | ".join(cell(cfg, a, 'topn_src') for a in arms) + " |"
        for cfg, _ in MEM_CONFIGS)
    v = r["verdict"]
    hi, sp = v["topn_ice_over_dl_high_cap"], v["topn_ice_over_dl_forced_spill"]
    # interpret
    gap_high = abs(hi - 1.0) >= 0.15
    gap_spill = abs(sp - 1.0) >= 0.15
    if gap_spill and not gap_high:
        concl = (f"**The divergence is SPILL, not the read path.** With the aggregate fitting in RAM "
                 f"(high cap) the three arms sit at parity (iceberg/ducklake {hi}×), and the gap only "
                 f"appears when the low cap forces a spill (iceberg/ducklake {sp}×). So R8's 1.30× at 1B "
                 f"was the 28 GB-cap × drvfs-spill interaction the note suspected, not a format/read-path "
                 f"property — the same-files read-neutrality claim holds, with a spill-regime caveat.")
    elif gap_high:
        concl = (f"**The divergence is the extensions' read path, not spill.** The gap persists with no "
                 f"spill (iceberg/ducklake {hi}× at high cap), so the two DuckDB extensions (iceberg_scan "
                 f"vs ducklake) genuinely differ on a heavy high-cardinality aggregate over identical "
                 f"bytes — a real, if narrow, qualification of same-files read-neutrality. "
                 f"(forced-spill {sp}×.)")
    else:
        concl = (f"**No divergence reproduced at 100M.** Both caps sit at parity (high {hi}×, spill {sp}×) — "
                 f"R8's 1.30× did not reappear at this scale, consistent with it being a 1B-specific spill "
                 f"effect; the same-files read-neutrality claim holds at 100M.")
    return f"""# Isolating R8's topn_src divergence — read path vs spill (T2.5)

**Tier B, single machine.** {r['n_rows']:,} rows of byte-identical Parquet ({'verified identical' if r['bytes_identical'] else 'NOT identical'})
registered into an Iceberg table, a DuckLake table, and read directly via `read_parquet(glob)`, with the
topn_src 16.7M-group aggregate ({r['distinct_src_ip_groups']:,} distinct src_ip) run under a high memory cap
(fits in RAM, no spill) and a forced-spill low cap.

## topn_src median ms (CV) by arm × memory config

| memory config | Iceberg ext | DuckLake | read_parquet(glob) |
|---|---|---|---|
{rows}

- Iceberg/DuckLake at high cap (no spill): **{hi}×** · at forced spill: **{sp}×**
- Iceberg/read_parquet at high cap: {v['topn_ice_over_glob_high_cap']}× · DuckLake/read_parquet at high cap: {v['topn_dl_over_glob_high_cap']}×

## Reading

{concl} The `read_parquet(glob)` arm is the native-reader scan-path baseline; whichever extension matches
it is paying no read-path overhead. Tier B, single machine, hot/warm; the transferable finding is which of
the two candidate mechanisms (extension read path vs memory-cap spill) the gap isolates to.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=100_000_000)
    ap.add_argument("--batch", type=int, default=50_000_000)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    out = os.path.join(rdir, "topn-isolation.json")
    r = json.load(open(out)) if args.render_only else run(args.rows, args.batch, args.warmup, args.trials)
    if not args.render_only:
        json.dump(r, open(out, "w"), indent=2, sort_keys=True)
    open(os.path.join(rdir, "TOPN-ISOLATION.md"), "w").write(render_md(r))
    print(f"\nverdict: {r['verdict']}")
    print("wrote results/topn-isolation.json + TOPN-ISOLATION.md", flush=True)


if __name__ == "__main__":
    main()

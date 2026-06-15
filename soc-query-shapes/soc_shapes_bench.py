#!/usr/bin/env python3
"""SOC query-shape bench #2+3 — UEBA volume Z-score (two-level aggregation) + rare-value/first-seen
(high-cardinality count-DISTINCT). External-review P4 backlog shapes. Runs the 4 Iceberg-reading
engines over the shared soc.conn (structured flow; aggregate output only — no raw rows surfaced),
each shape timed vs a flat-aggregation baseline, to see whether these regimes reorder the engines.

Tier B, single host (ejs). Run: docker exec ejs-lab python3 /tmp/soc_shapes_bench.py
"""
import json, os, statistics
from pathlib import Path
import ejs_clients as E

CONN = os.environ.get("CONN_TABLE", "soc.conn")
TRIALS = int(os.environ.get("TRIALS", "5"))
OUT = Path(os.environ.get("OUT_DIR", "/tmp/soc_shapes_results"))

# {T}=table ref, {SD}=engine stddev fn. ts is a double epoch -> portable arithmetic.
SHAPES = {
    # UEBA: hourly volume per host -> per-host baseline mean/stddev -> flag volume-spike hosts (Z>3)
    "ueba_zscore": """WITH hourly AS (
  SELECT orig_h, floor(ts/3600) AS hr, count(*) AS c FROM {T} GROUP BY orig_h, floor(ts/3600)
)
SELECT orig_h, count(*) AS hours, avg(c) AS mean_c, {SD}(c) AS sd_c, max(c) AS peak,
       (max(c)-avg(c))/{SD}(c) AS z
FROM hourly GROUP BY orig_h
HAVING count(*) >= 5 AND {SD}(c) > 0 AND (max(c)-avg(c))/{SD}(c) > 3
ORDER BY z DESC LIMIT 20""",
    # rare-value / first-seen: destinations contacted by exactly one source (count-DISTINCT, high-card)
    "rare_dest": """SELECT resp_h, count(DISTINCT orig_h) AS srcs, count(*) AS conns
FROM {T} GROUP BY resp_h HAVING count(DISTINCT orig_h) = 1
ORDER BY conns DESC LIMIT 20""",
    # flat baseline for ranking comparison
    "flat": """SELECT proto, count(*) AS c FROM {T} GROUP BY proto ORDER BY c DESC""",
}


def keyset(rows):
    return sorted([tuple(str(x) for x in r[:1]) + (int(r[-2]) if str(r[-2]).lstrip('-').isdigit() else 0,) for r in rows]) if rows else []


def main():
    out = {"bench": "soc-query-shapes/ueba+rare (two-level agg + high-card count-distinct)", "tier": "B",
           "host": "ejs single host", "table": CONN, "trials": TRIALS, "arms": {}}
    for arm, Cls in E.CLIENTS.items():
        try:
            client = Cls(); ref = client.ref(CONN)
            rec = {}
            for shape, sql_t in SHAPES.items():
                sql = sql_t.format(T=ref, SD=client.SD)
                med, ds, rows = E.time_query(client, sql, TRIALS)
                rec[shape] = {"median_s": round(med, 4),
                              "cv_pct": round(100*statistics.stdev(ds)/statistics.mean(ds), 1) if len(ds) > 1 else 0,
                              "rows": len(rows)}
                if shape in ("ueba_zscore", "rare_dest"):
                    rec[shape]["rowset_hash"] = hash(tuple(sorted(tuple(str(c) for c in r) for r in rows)))
            for s in ("ueba_zscore", "rare_dest"):
                rec[s]["over_flat_x"] = round(rec[s]["median_s"]/rec["flat"]["median_s"], 1) if rec["flat"]["median_s"] else None
            out["arms"][arm] = rec
            print(f"{arm:20} ueba {rec['ueba_zscore']['median_s']:.3f}s ({rec['ueba_zscore']['rows']}r, {rec['ueba_zscore']['over_flat_x']}x flat) | "
                  f"rare {rec['rare_dest']['median_s']:.3f}s ({rec['rare_dest']['rows']}r, {rec['rare_dest']['over_flat_x']}x) | flat {rec['flat']['median_s']:.3f}s", flush=True)
        except Exception as e:
            out["arms"][arm] = {"error": str(e)[:300]}
            print(f"{arm:20} FAIL: {str(e)[:200]}", flush=True)
    for shape in ("ueba_zscore", "rare_dest", "flat"):
        lat = {a: v[shape]["median_s"] for a, v in out["arms"].items() if shape in v and "median_s" in v[shape]}
        out[f"{shape}_ranking"] = sorted(lat, key=lat.get)
    out["ueba_inverts_flat"] = out.get("ueba_zscore_ranking") != out.get("flat_ranking")
    out["rare_inverts_flat"] = out.get("rare_dest_ranking") != out.get("flat_ranking")
    for shape in ("ueba_zscore", "rare_dest"):
        hashes = {a: v[shape].get("rowset_hash") for a, v in out["arms"].items() if shape in v and v[shape].get("rowset_hash") is not None}
        out[f"{shape}_answer_equal"] = (len(set(hashes.values())) == 1) if len(hashes) > 1 else None
    print("\nflat ranking:", out.get("flat_ranking"))
    print("ueba ranking:", out.get("ueba_zscore_ranking"), "| inverts flat:", out["ueba_inverts_flat"], "| answer-equal:", out["ueba_zscore_answer_equal"])
    print("rare ranking:", out.get("rare_dest_ranking"), "| inverts flat:", out["rare_inverts_flat"], "| answer-equal:", out["rare_dest_answer_equal"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ueba_rare.json").write_text(json.dumps(out, indent=2))
    print("-> results/ueba_rare.json")


if __name__ == "__main__":
    main()

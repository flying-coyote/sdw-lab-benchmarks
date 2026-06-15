#!/usr/bin/env python3
"""UEBA + rare-value detection on PLANTED ground truth (the correctness leg the 2026-06-15
SOC-shape bench was missing). Runs the SAME ueba_zscore (two-level agg) and rare_dest
(high-card count-DISTINCT) shapes against soc.conn_ueba_planted, and scores:

  - detection correctness: precision / recall of the flagged ENTITY set vs the planted truth
    (spike hosts for ueba; single-source dests for rare), and whether the high-steady decoys
    leak in as false positives;
  - cross-engine ANSWER-EQUALITY on the flagged entity SET (not the float-laden rows — avg/
    stddev format differently per engine, so set-equality is the meaningful agreement check);
  - latency on THIS corpus (secondary — the 10.3M soc.conn inversion is a different scale and
    is NOT re-litigated here; this only confirms the shapes run and rank on a corpus that fires).

Tier B, single host (ejs). Run in ejs-lab after gen_ueba_corpus.py.
"""
import json, os, statistics
from pathlib import Path
import ejs_clients as E

T = os.environ.get("UEBA_TABLE", "soc.conn_ueba_planted")
TRIALS = int(os.environ.get("TRIALS", "5"))
OUT = Path(os.environ.get("OUT_DIR", "/tmp/ueba_planted_results"))
TRUTH = json.load(open(os.environ.get("TRUTH", "/tmp/ueba_truth.json")))

UEBA = """WITH hourly AS (
  SELECT orig_h, floor(ts/3600) AS hr, count(*) AS c FROM {T} GROUP BY orig_h, floor(ts/3600)
)
SELECT orig_h FROM hourly GROUP BY orig_h
HAVING count(*) >= 5 AND {SD}(c) > 0 AND (max(c)-avg(c))/{SD}(c) > 3
ORDER BY (max(c)-avg(c))/{SD}(c) DESC LIMIT 20"""

RARE = """SELECT resp_h FROM {T} GROUP BY resp_h
HAVING count(DISTINCT orig_h) = 1 ORDER BY count(*) DESC LIMIT 20"""


def score(flagged, truth_set):
    f = set(flagged); t = set(truth_set)
    tp = len(f & t); fp = len(f - t)
    return {"flagged": len(f), "tp": tp, "fp": fp,
            "precision": round(tp / len(f), 3) if f else None,
            "recall": round(tp / len(t), 3) if t else None,
            "false_positives": sorted(f - t)[:10]}


def main():
    ueba_true = set(TRUTH["ueba_spike_hosts"]); rare_true = set(TRUTH["rare_dests"])
    out = {"bench": "soc-query-shapes/ueba+rare PLANTED ground truth", "tier": "B",
           "host": "ejs single host", "table": T, "trials": TRIALS,
           "ground_truth": {"ueba_spike_hosts": len(ueba_true), "rare_dests": len(rare_true),
                            "n_rows": TRUTH.get("n_rows"), "highsteady_decoys": TRUTH.get("n_highsteady_decoy")},
           "arms": {}}
    ueba_sets = {}; rare_sets = {}
    for arm, Cls in E.CLIENTS.items():
        try:
            c = Cls(); ref = c.ref(T)
            um, uds, urows = E.time_query(c, UEBA.format(T=ref, SD=c.SD), TRIALS)
            rm, rds, rrows = E.time_query(c, RARE.format(T=ref), TRIALS)
            uflag = [r[0] for r in urows]; rflag = [r[0] for r in rrows]
            ueba_sets[arm] = set(uflag); rare_sets[arm] = set(rflag)
            out["arms"][arm] = {
                "ueba": {"median_s": round(um, 4),
                         "cv_pct": round(100*statistics.stdev(uds)/statistics.mean(uds), 1) if len(uds) > 1 else 0,
                         **score(uflag, ueba_true)},
                "rare": {"median_s": round(rm, 4),
                         "cv_pct": round(100*statistics.stdev(rds)/statistics.mean(rds), 1) if len(rds) > 1 else 0,
                         **score(rflag, rare_true)},
            }
            a = out["arms"][arm]
            print(f"{arm:12} ueba {a['ueba']['median_s']:.3f}s P={a['ueba']['precision']} R={a['ueba']['recall']} "
                  f"(tp{a['ueba']['tp']} fp{a['ueba']['fp']}) | rare {a['rare']['median_s']:.3f}s "
                  f"P={a['rare']['precision']} R={a['rare']['recall']} (tp{a['rare']['tp']} fp{a['rare']['fp']})", flush=True)
        except Exception as e:
            out["arms"][arm] = {"error": str(e)[:300]}
            print(f"{arm:12} FAIL: {str(e)[:200]}", flush=True)

    # cross-engine answer-equality on the flagged ENTITY set
    ueba_eq = len({frozenset(s) for s in ueba_sets.values()}) == 1 if len(ueba_sets) > 1 else None
    rare_eq = len({frozenset(s) for s in rare_sets.values()}) == 1 if len(rare_sets) > 1 else None
    out["ueba_answer_equal_set"] = ueba_eq
    out["rare_answer_equal_set"] = rare_eq
    # latency ranking (secondary, this corpus only)
    for shape in ("ueba", "rare"):
        lat = {a: v[shape]["median_s"] for a, v in out["arms"].items() if shape in v and "median_s" in v[shape]}
        out[f"{shape}_latency_ranking"] = sorted(lat, key=lat.get)
    print(f"\nueba flagged-set answer-equal across engines: {ueba_eq}")
    print(f"rare flagged-set answer-equal across engines: {rare_eq}")
    print(f"ueba latency ranking (this corpus): {out['ueba_latency_ranking']}")
    print(f"rare latency ranking (this corpus): {out['rare_latency_ranking']}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ueba_planted.json").write_text(json.dumps(out, indent=2))
    print("-> results/ueba_planted.json")


if __name__ == "__main__":
    main()

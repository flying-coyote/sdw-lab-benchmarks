#!/usr/bin/env python3
"""B-DATAHEALTH seed sweep (added 2026-06-14, pre-registered in project1
BENCHMARK-BACKLOG.md as the P1 re-run).

The v1 headline (best-single 47.7%, cross-tool 75.6%) is ONE corpus draw at the
canonical (truth=701, obs=702) seeds. EXT-1 already showed the *ordering* is
robust across a 3x3 staleness x coverage grid; this sweep bounds the *magnitudes*
of the two headline numbers by re-drawing the whole corpus (both the ground-truth
RNG and the observation-flaw RNG) across N independent seed pairs and reporting a
confidence band instead of a point.

It imports run.py and calls gen_ground_truth / gen_observations / score directly,
so it leaves the v1 build-twice determinism path completely untouched (run.py is
not modified). Same V1_PARAMS, same scoring, only the seeds change.

Usage (from repo root, shared venv):
  SDW_DUCK_MEMORY_LIMIT=12GB .venv/bin/python3 ocsf-data-health/seed_sweep.py [N]
"""
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run as m  # noqa: E402  (run.py self-adds ../lib for `common`)

CANONICAL = (701, 702)


def draw(truth_seed: int, obs_seed: int):
    truth = m.gen_ground_truth(seed=truth_seed)
    obs = m.gen_observations(truth, seed=obs_seed, params=m.V1_PARAMS)
    sc = m.score(truth, obs, params=m.V1_PARAMS)
    return {
        "truth_seed": truth_seed,
        "obs_seed": obs_seed,
        "best_single_tool": sc["best_single_tool"],
        "best_single_recovery": sc["best_single_recovery"],
        "cross_tool_recovery": sc["cross_tool_recovery"],
        "cross_minus_best_single": sc["cross_minus_best_single"],
        "residual_gap": sc["residual_gap"],
        "lever_gain": sc["lever"]["lever_gain"],
    }


def band(vals):
    n = len(vals)
    mean = statistics.fmean(vals)
    sd = statistics.stdev(vals) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else 0.0
    # 95% CI, normal approximation (n>=10 so t~z is fine for a Tier-B band)
    ci = 1.96 * se
    cv = (sd / mean * 100) if mean else 0.0
    return {
        "n": n, "mean": mean, "sd": sd, "se": se,
        "ci95_lo": mean - ci, "ci95_hi": mean + ci,
        "min": min(vals), "max": max(vals), "cv_pct": cv,
    }


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    # draw 0 is the canonical published point; the rest are independent re-draws
    seed_pairs = [CANONICAL] + [(1000 + i, 2000 + i) for i in range(n - 1)]
    rows = [draw(ts, os_) for ts, os_ in seed_pairs]

    keys = ["best_single_recovery", "cross_tool_recovery",
            "cross_minus_best_single", "residual_gap", "lever_gain"]
    bands = {k: band([r[k] for r in rows]) for k in keys}

    out = {
        "benchmark": "ocsf-data-health seed sweep (headline-magnitude CI band)",
        "n_draws": len(rows),
        "canonical_point": next(r for r in rows if (r["truth_seed"], r["obs_seed"]) == CANONICAL),
        "bands": bands,
        "draws": rows,
        "best_single_tool_modal": statistics.mode([r["best_single_tool"] for r in rows]),
        "duckdb_version": m.duckdb.__version__,
    }
    path = os.path.join(HERE, "results", "seed_sweep.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)

    print(f"=== B-DATAHEALTH seed sweep: {len(rows)} draws (V1_PARAMS, DuckDB {m.duckdb.__version__}) ===")
    print(f"canonical (701,702): best-single {out['canonical_point']['best_single_recovery']:.1%}  "
          f"cross-tool {out['canonical_point']['cross_tool_recovery']:.1%}")
    print(f"{'measure':<26}{'mean':>8}{'sd':>7}{'95% CI':>18}{'min-max':>16}{'CV%':>7}")
    for k in keys:
        b = bands[k]
        print(f"{k:<26}{b['mean']:>7.1%}{b['sd']:>6.2%}"
              f"   [{b['ci95_lo']:.1%}, {b['ci95_hi']:.1%}]"
              f"   {b['min']:.1%}-{b['max']:.1%}{b['cv_pct']:>6.1f}")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()

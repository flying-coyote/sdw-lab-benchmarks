#!/usr/bin/env python3
"""B-FLATTEN parameter sweep for Modes 2-3 (added 2026-06-14, pre-registered in
project1 BENCHMARK-BACKLOG.md as the P1 re-run).

The v1 headline magnitudes for Mode 2 (grain F1 0.50) and Mode 3 (floating-time
recall ~0.46-0.50) are single points at one corpus parameter and one seed. The
backlog asks for the magnitude as a *function of the corpus parameter*, not a
point, with the seed-induced variance bounded. Mode 1 (absence->NULL) is
structural — 100% by construction — and needs no sweep.

This imports grain.run / timestamps.run (now seed-parameterized, defaults
preserve v1 bit-for-bit) and sweeps:

  Mode 2 (grain): decoy-to-beacon ratio in {0.5,1,2,3,4} at n_beacons=8, across
    8 seeds. The coarse detector flags any steady-per-bucket pair, and beacons
    AND decoys are both steady 5/bucket by construction, so the predicted
    coarse F1 is 2b/(2b+d) = 2/(2+ratio) — a deterministic function of the ratio.
    The sweep confirms that closed form and that the seed barely moves it.

  Mode 3 (floating time): cross-zone fraction in {0,0.25,0.5,0.75,1.0} at
    n_chains=1000, across 8 seeds. Cross-zone chains can never re-correlate once
    the offset is dropped (the 4 zones differ by >=1h >> the 5-min window), so
    predicted floating recall = 1 - (actual cross-zone fraction); the seed noise
    is the binomial draw of how many chains land cross-zone.

Usage (from repo root, shared venv):
  SDW_DUCK_MEMORY_LIMIT=12GB .venv/bin/python3 flattening-fidelity/param_sweep.py
"""
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)

import duckdb  # noqa: E402
from benchmarks import grain, timestamps  # noqa: E402

GRAIN_SEEDS = [202] + [1000 + i for i in range(7)]      # canonical + 7 redraws
TS_SEEDS = [303] + [1000 + i for i in range(7)]
N_BEACONS = 8
DECOY_RATIOS = [0.5, 1, 2, 3, 4]
N_CHAINS = 1000
CROSS_FRACS = [0.0, 0.25, 0.5, 0.75, 1.0]


def band(vals):
    n = len(vals)
    mean = statistics.fmean(vals)
    sd = statistics.stdev(vals) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else 0.0
    return {"n": n, "mean": mean, "sd": sd,
            "ci95_lo": mean - 1.96 * se, "ci95_hi": mean + 1.96 * se,
            "min": min(vals), "max": max(vals)}


def grain_sweep():
    points = []
    for ratio in DECOY_RATIOS:
        n_decoys = int(round(ratio * N_BEACONS))
        coarse, atomic = [], []
        for s in GRAIN_SEEDS:
            r = grain.run(scales=[(N_BEACONS, n_decoys, 200)], seed=s)["scales"][0]
            adv = r["adversary_query_beacon_hunt"]
            coarse.append(adv["coarse_grain"]["f1"])
            atomic.append(adv["atomic_grain"]["f1"])
        predicted = 2 * N_BEACONS / (2 * N_BEACONS + n_decoys)
        points.append({
            "decoy_ratio": ratio, "n_beacons": N_BEACONS, "n_decoys": n_decoys,
            "coarse_f1": band(coarse), "atomic_f1": band(atomic),
            "predicted_coarse_f1_2b_over_2b_plus_d": round(predicted, 4),
        })
    return points


def timestamps_sweep():
    points = []
    for cf in CROSS_FRACS:
        floating, utc, actual_cross = [], [], []
        for s in TS_SEEDS:
            r = timestamps.run(scales=[(N_CHAINS, cf)], seed=s)["scales"][0]
            floating.append(r["floating_local"]["correlation_recall"])
            utc.append(r["utc_normalized"]["correlation_recall"])
            actual_cross.append(r["cross_zone_chains"] / N_CHAINS)
        points.append({
            "cross_zone_fraction_target": cf,
            "actual_cross_fraction": band(actual_cross),
            "floating_recall": band(floating), "utc_recall": band(utc),
            "predicted_floating_recall_1_minus_cross": round(1 - statistics.fmean(actual_cross), 4),
        })
    return points


def main():
    out = {
        "benchmark": "flattening-fidelity Modes 2-3 parameter x seed sweep",
        "note": "Mode 1 (absence->NULL) is structural (100% by construction); not swept.",
        "duckdb_version": duckdb.__version__,
        "grain_decoy_ratio_sweep": grain_sweep(),
        "timestamps_cross_zone_sweep": timestamps_sweep(),
    }
    path = os.path.join(HERE, "results", "param_sweep.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)

    print(f"=== B-FLATTEN Mode 2 (grain) — coarse F1 vs decoy ratio, DuckDB {duckdb.__version__} ===")
    print(f"{'ratio':>6}{'n_dec':>6}{'coarse F1 (mean[min-max] CV~0)':>34}{'pred 2/(2+r)':>14}{'atomic F1':>11}")
    for p in out["grain_decoy_ratio_sweep"]:
        c, a = p["coarse_f1"], p["atomic_f1"]
        print(f"{p['decoy_ratio']:>6}{p['n_decoys']:>6}"
              f"   {c['mean']:.3f} [{c['min']:.3f}-{c['max']:.3f}]"
              f"{p['predicted_coarse_f1_2b_over_2b_plus_d']:>16}"
              f"   {a['mean']:.3f} [{a['min']:.3f}-{a['max']:.3f}]")
    print(f"\n=== B-FLATTEN Mode 3 (floating time) — floating recall vs cross-zone fraction ===")
    print(f"{'target':>7}{'actual':>9}{'floating recall (mean [95% CI] min-max)':>42}{'utc':>7}")
    for p in out["timestamps_cross_zone_sweep"]:
        fr, ac = p["floating_recall"], p["actual_cross_fraction"]
        print(f"{p['cross_zone_fraction_target']:>7}{ac['mean']:>9.3f}"
              f"   {fr['mean']:.3f} [{fr['ci95_lo']:.3f},{fr['ci95_hi']:.3f}] {fr['min']:.3f}-{fr['max']:.3f}"
              f"{p['utc_recall']['mean']:>7.2f}")
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()

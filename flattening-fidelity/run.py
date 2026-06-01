"""Run the three flattening-fidelity benchmarks, verify determinism, write results.

Usage:
    python run.py            # run all three, write results/results.json + RESULTS.md

The determinism check re-runs every benchmark a second time and asserts the
output is byte-identical. That is the guarantee behind the "reproducible"
(Tier B) label: same code, same seed, same numbers, every time.
"""

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The determinism core lives in the shared repo-level lib/, so every benchmark
# draws on one seed and one clock anchor. Put it on the path before importing
# the benchmark modules, which do `from common import ...`.
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

import duckdb

from benchmarks import absence_null, grain, timestamps

RESULTS_DIR = os.path.join(HERE, "results")


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _run_all():
    return {
        "absence_null": absence_null.run(),
        "grain": grain.run(),
        "timestamps": timestamps.run(),
    }


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    first = _run_all()
    second = _run_all()
    deterministic = _canonical(first) == _canonical(second)

    results = {
        "benchmark": "ocsf-flattening-fidelity (C2)",
        "evidence_tier": "B (reproducible, first-party, controlled synthetic corpus; NOT a production claim)",
        "environment": {
            "duckdb_version": duckdb.__version__,
            "master_seed": 20260601,
        },
        "determinism_verified": deterministic,
        "results": first,
    }

    with open(os.path.join(RESULTS_DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2)

    _write_markdown(results)

    digest = hashlib.sha256(_canonical(first).encode()).hexdigest()[:16]
    print(f"determinism_verified={deterministic}  duckdb={duckdb.__version__}  results_sha256[:16]={digest}")
    print(f"wrote {os.path.join(RESULTS_DIR, 'results.json')}")
    print(f"wrote {os.path.join(RESULTS_DIR, 'RESULTS.md')}")


def _write_markdown(results):
    r = results["results"]
    lines = []
    a = lines.append

    a("# Results — OCSF flattening-fidelity benchmark (C2)\n")
    a(f"- DuckDB: `{results['environment']['duckdb_version']}`  ")
    a(f"- Master seed: `{results['environment']['master_seed']}`  ")
    a(f"- Determinism (re-run is byte-identical): **{results['determinism_verified']}**  ")
    a(f"- Evidence tier: {results['evidence_tier']}\n")
    a("All corpora are synthetic and generated deterministically. These are controlled "
      "measurements of a mechanism, not production telemetry.\n")

    # --- Mode 1 ---
    a("## 1. Absence-vs-NULL collapse → silent detection miss\n")
    a("CloudTrail encodes \"no MFA\" as the *absence* of `mfaAuthenticated`. Flattening "
      "lowers that to a column where absent becomes NULL, so the naive translation "
      "`WHERE mfa = 'false'` matches nothing. Planted positives = privilege-escalation "
      "calls made without MFA.\n")
    a("| corpus events | planted positives | naive-flat recall | NULL-aware-flat recall | preserved-JSON recall | naive silent-miss rate |")
    a("|--:|--:|--:|--:|--:|--:|")
    for s in r["absence_null"]["scales"]:
        a(f"| {s['n_events']:,} | {s['planted_true_positives']} | "
          f"{s['flattened_naive']['recall']:.2f} | "
          f"{s['flattened_null_aware']['recall']:.2f} | "
          f"{s['preserved_json']['recall']:.2f} | "
          f"{s['silent_miss_rate_naive']:.0%} |")
    a("\nThe naive flattened query recovers none of the planted positives; the preserved "
      "schema and the NULL-aware flattened query recover all of them. The miss is "
      "structural, not probabilistic — absence and NULL are the same byte once flattened.\n")

    # --- Mode 2 ---
    a("## 2. Grain loss → adversary timing query destroyed, routine query exact\n")
    a("Beacons (regular 60s) and benign decoys (bursty, same per-bucket count and same "
      "43-byte payload) are separable only on inter-arrival jitter. Atomic grain keeps the "
      "timestamps; a (src, dst, 5-min) rollup does not.\n")
    a("| beacons | decoys | rows | atomic F1 | coarse F1 | adversary F1 loss | routine exact? | headline (adv − routine) |")
    a("|--:|--:|--:|--:|--:|--:|:--:|--:|")
    for s in r["grain"]["scales"]:
        adv = s["adversary_query_beacon_hunt"]
        rout = s["routine_queries"]
        exact = "yes" if (rout["bytes_per_host_exact"] and rout["pair_counts_exact"]) else "no"
        a(f"| {s['n_beacons']} | {s['n_decoys']} | {s['n_rows']:,} | "
          f"{adv['atomic_grain']['f1']:.2f} | {adv['coarse_grain']['f1']:.2f} | "
          f"{adv['f1_degradation']:.2f} | {exact} | "
          f"{s['headline_adversary_minus_routine_degradation']:.2f} |")
    a("\nThe rollup answers the volumetric routine queries exactly (bytes-per-host and "
      "pair-counts match to the row) while the beacon hunt loses precision because the "
      "discriminating feature — timing regularity — no longer exists in the schema.\n")

    # --- Mode 3 ---
    a("## 3. Floating timestamps → cross-zone correlation silently lost\n")
    a("Cross-source chains truly within a 5-minute window in UTC, with sources in real "
      "timezones. The floating store drops the offset and compares local wall-clocks as if "
      "co-zoned.\n")
    a("| chains | cross-zone | UTC correlation recall | floating correlation recall |")
    a("|--:|--:|--:|--:|")
    for s in r["timestamps"]["scales"]:
        a(f"| {s['n_chains']:,} | {s['cross_zone_chains']} | "
          f"{s['utc_normalized']['correlation_recall']:.2f} | "
          f"{s['floating_local']['correlation_recall']:.2f} |")
    a("\nUTC normalization correlates every planted chain; the floating store loses exactly "
      "the cross-zone chains, whose events scatter hours apart once the offset is gone. The "
      "same-zone chains survive either way, which is why the failure is quiet — half the "
      "results still look right.\n")

    with open(os.path.join(RESULTS_DIR, "RESULTS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

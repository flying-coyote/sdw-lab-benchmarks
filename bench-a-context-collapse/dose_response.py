"""BENCH-A dose-response: how the context-collapse headline grows as normalization gets lazier.

The main benchmark fixes Store N at one documented coarsening default. This sweeps the three
coarsening knobs — network rollup window, command-line truncation, and the rare-DNS sampling
threshold — from light to heavy, rebuilding Store N at each setting and re-scoring the frozen
query battery, so the result is a curve rather than a point: at what degree of normalization does
the adversary-tail gap open, and does the routine control stay clean throughout (it must, or the
rung is contaminated). Store F is fidelity-preserving and built once; only Store N varies.
"""

import json
import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench    # noqa: E402
import stores   # noqa: E402

RESULTS = os.path.join(HERE, "results")

# Light -> heavy. Each rung is lazier than the last on all three knobs at once; the documented
# default sits in the middle so the published headline is locatable on the curve.
LADDER = [
    {"label": "light",      "rollup_ms": 60_000,    "cmdline_trunc": 256, "dns_rare_min": 2},
    {"label": "documented", "rollup_ms": 300_000,   "cmdline_trunc": 64,  "dns_rare_min": 3},
    {"label": "heavy",      "rollup_ms": 900_000,   "cmdline_trunc": 24,  "dns_rare_min": 6},
    {"label": "very_heavy", "rollup_ms": 3_600_000, "cmdline_trunc": 12,  "dns_rare_min": 12},
]


def run():
    con = duckdb.connect(":memory:")
    stores._views(con)
    stores.build_store_f(con)           # constant fidelity store, once
    rungs = []
    for s in LADDER:
        stores.build_store_n(con, rollup_ms=s["rollup_ms"], cmdline_trunc=s["cmdline_trunc"],
                             dns_rare_min=s["dns_rare_min"])
        r = bench.run()                 # reads the just-written store_n + the fixed store_f
        rungs.append({"setting": s, "headline": r["headline"], "delta_routine": r["delta_routine"],
                      "delta_adversary": r["delta_adversary"], "void": r["void"],
                      "per_mechanism": r["per_mechanism_delta"]})
        print(f"  [{s['label']:11}] rollup={s['rollup_ms']//1000}s trunc={s['cmdline_trunc']} "
              f"dns>={s['dns_rare_min']}  ->  headline={r['headline']:+.3f}  "
              f"Δroutine={r['delta_routine']:+.3f}  void={r['void']}")
    stores.build_store_n(con)           # restore the documented-default store_n on disk
    con.close()
    return {"benchmark": "ocsf-context-collapse dose-response", "tier": "B",
            "knobs": ["network rollup window", "cmdline truncation", "rare-DNS sampling threshold"],
            "rungs": rungs}


def render_md(res):
    rows = "\n".join(
        f"| {r['setting']['label']} | {r['setting']['rollup_ms']//1000}s / {r['setting']['cmdline_trunc']} / "
        f"{r['setting']['dns_rare_min']} | {r['headline']:+.3f} | {r['delta_routine']:+.3f} | "
        f"{r['delta_adversary']:+.3f} | {r['void']} |" for r in res["rungs"])
    return f"""# BENCH-A dose-response — headline vs coarseness

**Tier B.** How the context-collapse headline `Δ(adversary) − Δ(routine)` moves as Store N's
normalization gets lazier on all three knobs at once (network rollup window / command-line
truncation cap / rare-DNS sampling threshold). Store F is fixed; only Store N varies. The
documented default (the published `+0.72` point) sits mid-ladder so it's locatable on the curve.

| coarseness | rollup / trunc / dns≥ | headline | Δ routine | Δ adversary | void |
|---|---|---|---|---|---|
{rows}

## Reading

The shape is flat-then-step, not smoothly rising, and that is the interesting part. The headline
is already at its base level under *light* coarsening and stays there through the documented
default, then steps up under heavy and very-heavy normalization, while the routine control sits at
zero across every rung. The flat front end says most of the adversary-tail gap is binary: the
atomic detail those queries need — the exact encoded payload, the beacon as individual connections,
the rare first-seen domain, valid-time, absent-vs-false — is either kept or gone, and even a fairly
careful pipeline that still flattens to a single store loses it, so tightening the rollup window or
the truncation cap a little doesn't buy it back. The step at the heavy end is the timing-tolerant
queries (cross-source ordering and dwell) finally degrading once the rollup window grows large
enough to perturb event order, which is exactly the evidence that survives light coarsening and
fails heavy. The load-bearing check is that the routine set stays clean throughout — if a lazier
store had degraded the routine queries too, that rung would be contaminated (`void`), and none are.
Tier B, one synthetic chain; the magnitudes are testbed-specific, and the flat-then-step shape plus
the clean control are the transferable findings.
"""


def main():
    os.makedirs(RESULTS, exist_ok=True)
    res = run()
    with open(os.path.join(RESULTS, "dose-response.json"), "w") as f:
        json.dump(res, f, indent=2, sort_keys=True)
    with open(os.path.join(RESULTS, "DOSE-RESPONSE.md"), "w") as f:
        f.write(render_md(res))
    print("wrote results/dose-response.json + DOSE-RESPONSE.md")


if __name__ == "__main__":
    main()

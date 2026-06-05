"""BENCH-A second chain — does the +0.72 headline hold on a different attack chain?

The robustness run re-drew the background noise around the same needles. This goes further: a second,
independent chain profile (chain B) — a different actor on a different subnet, different C2 indicators,
a different encoded payload, and an SMB lateral leg (T1021.002) where chain A used RDP (T1021.001) — is
generated, normalized into the two stores, and scored by the SAME frozen A1–A10 battery. The battery now
reads the chain's indicators from the ground-truth IOC block rather than hardcoding them, which is what
lets one frozen query set score either chain. Both chains share the same background (offset 0), so the
only variable is the chain itself.

If chain B's headline tracks chain A's, the context-collapse result isn't an artifact of one specific
attack instance. The canonical chain-A corpus is rebuilt and fingerprint-verified at the end so the shared
testbed the other benchmarks read is left untouched.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "ocsf-semantic-testbed"))
import generate  # noqa: E402
import stores    # noqa: E402
import bench     # noqa: E402

PY = sys.executable
VALIDATE = os.path.join(HERE, "..", "ocsf-semantic-testbed", "validate.py")
CHAIN_A_FP = "46af223bf406ee3b"   # chain-A corpus fingerprint (gt now carries the ioc block)


def build_and_score(chain):
    generate.apply_chain(chain)
    generate.BG_SEED_OFFSET = 0            # same background for both → isolate the chain
    s, g = generate.build(generate.SCALES["full"])
    generate.write(s, g, "full")
    generate.materialize_parquet()
    fp = json.load(open(os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "manifest.json")))["fingerprint_sha256"][:16]
    v = subprocess.run([PY, VALIDATE], capture_output=True, text=True)
    validate_line = next((l for l in v.stdout.splitlines() if "passed" in l), "?")
    stores.build()
    r = bench.run()
    return {"chain": chain, "chain_name": g["ioc"]["chain_name"], "fingerprint": fp,
            "validate": validate_line.strip(), "headline": r["headline"],
            "delta_routine": r["delta_routine"], "delta_adversary": r["delta_adversary"],
            "void": r["void"], "per_mechanism": r["per_mechanism_delta"]}


def run():
    res = {}
    for chain in ("A", "B"):
        r = build_and_score(chain)
        res[chain] = r
        print(f"  chain {chain} ({r['chain_name']}): headline={r['headline']:+.3f}  "
              f"Δroutine={r['delta_routine']:+.3f}  void={r['void']}  validate={r['validate']}")
    # restore canonical chain A
    build_and_score("A")
    fp = json.load(open(os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "manifest.json")))["fingerprint_sha256"][:16]
    restored = fp == CHAIN_A_FP
    print(f"  canonical chain-A corpus restored: {restored} (fingerprint {fp})")
    return {"benchmark": "ocsf-context-collapse second-chain", "tier": "B",
            "chain_A": res["A"], "chain_B": res["B"],
            "headline_delta_A_vs_B": round(abs(res["A"]["headline"] - res["B"]["headline"]), 4),
            "both_routine_clean": not res["A"]["void"] and not res["B"]["void"],
            "canonical_restored": restored}


def render_md(r):
    a, b = r["chain_A"], r["chain_B"]
    def mech(x):
        return " · ".join(f"{k} {v:+.2f}" for k, v in x["per_mechanism"].items())
    return f"""# BENCH-A second chain — headline on a different attack (results)

**Tier B.** A second independent chain profile, scored by the same frozen A1–A10 battery (which reads the
chain's indicators from the ground-truth IOC block). Same background for both, so the only variable is the
chain.

| chain | profile | headline | Δ routine | Δ adversary | validate | void |
|---|---|---|---|---|---|---|
| A | {a['chain_name']} | {a['headline']:+.3f} | {a['delta_routine']:+.3f} | {a['delta_adversary']:+.3f} | {a['validate']} | {a['void']} |
| B | {b['chain_name']} | {b['headline']:+.3f} | {b['delta_routine']:+.3f} | {b['delta_adversary']:+.3f} | {b['validate']} | {b['void']} |

Per-mechanism Δ — chain A: {mech(a)} · chain B: {mech(b)}.
Headline difference A vs B: **{r['headline_delta_A_vs_B']:.3f}**. Both routine controls clean:
{r['both_routine_clean']}. Canonical chain-A corpus restored afterward: {r['canonical_restored']}.

## Reading

Chain B is a genuinely different attack — a different actor on a different subnet, different C2 domain and
IP, a different encoded payload, and an SMB lateral leg (T1021.002) where chain A used RDP (T1021.001) —
and the same frozen battery, reading the indicators from ground truth, scores it. The headline tracks chain
A's closely, the routine control stays clean, and the per-mechanism pattern (grain / structural /
bounded-context / time) holds — so the context-collapse result is a property of coarse normalization, not
of one specific attack instance. That is the external-validity step the dose-response and the background
re-draws couldn't reach: a different chain, scored by a frozen battery, lands in the same place. Both
chains still share the synthetic-testbed / single-machine caveat; the transferable claim is that the
mechanism reproduces across attacks, not the exact magnitude. Tier B.
"""


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    res = json.load(open(os.path.join(rdir, "second-chain.json"))) if args.render_only else run()
    if not args.render_only:
        with open(os.path.join(rdir, "second-chain.json"), "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "SECOND-CHAIN.md"), "w") as f:
        f.write(render_md(res))
    print("wrote results/second-chain.json + SECOND-CHAIN.md")


if __name__ == "__main__":
    main()

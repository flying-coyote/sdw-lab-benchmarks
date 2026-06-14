#!/usr/bin/env python3
"""APT29 de-gamed BENCH-A — coarsening sensitivity sweep (added 2026-06-14,
pre-registered in project1 BENCHMARK-BACKLOG.md as the B-CONTEXT P1 re-run).

The headline delta (adversary-tail − routine mean blinding recall-loss) was 0.1877
at ONE documented coarsening setting (truncation cap 64 chars, rare-DNS < 3). This
bench is deterministic — it runs UNMODIFIED upstream SigmaHQ rules over real fixed
MITRE APT29 telemetry, so there is no RNG and no stochastic seed band. The honest
way to bound the magnitude is therefore a *coarsening-sensitivity curve*: sweep the
dominant knob (the field-length truncation cap that kills APT29's encoded-PowerShell
tradecraft) and show how the adversary/routine gap moves with it.

It imports run.py's refactored score_stores() (one source of scoring truth) and
rebuilds only Store N per setting; Store F (fidelity) is built once.

Usage (from repo root, shared venv):
  .venv/bin/python ocsf-context-collapse-apt29/coarsening_sweep.py
"""
import json
import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import configure_duckdb  # noqa: E402
import stores  # noqa: E402
import run as runmod  # noqa: E402

WORK = os.path.join(HERE, "_work")

# Truncation cap ladder (chars). cmd_trunc == script_trunc, the documented config's
# coupling; 64 is the published documented point. dns_rare_min held at 3.
TRUNC_LADDER = [256, 128, 64, 32, 16]
DNS_RARE_MIN = 3


def main():
    con = configure_duckdb(duckdb.connect(":memory:"))
    stores._views(con)
    store_f = stores.build_store_f(con)          # fidelity store, built once
    store_n = os.path.join(WORK, "store_n")

    rows = []
    for trunc in TRUNC_LADDER:
        stores.build_store_n(con, cmd_trunc=trunc, script_trunc=trunc, dns_rare_min=DNS_RARE_MIN)
        cost = {"store_f_bytes": stores._bytes(store_f), "store_n_bytes": stores._bytes(store_n)}
        r = runmod.score_stores(con, store_f, store_n, cost)
        adv, rou = r["adversary_tail"], r["routine"]
        rows.append({
            "trunc_chars": trunc,
            "documented": trunc == 64,
            "fired_on_f": r["stats"]["fired_on_f"],
            "adv_mean_recall_loss": adv["mean_recall_loss"], "adv_blind_pct": adv["blind_pct"],
            "rou_mean_recall_loss": rou["mean_recall_loss"], "rou_blind_pct": rou["blind_pct"],
            "delta_mean_recall_loss": r["delta_mean_recall_loss"],
        })
        print(f"  trunc={trunc:>4}{'(documented)' if trunc==64 else '':<12}  "
              f"delta={r['delta_mean_recall_loss']:+.4f}  "
              f"adv={adv['mean_recall_loss']:.3f}/{adv['blind_pct']:.0f}%blind  "
              f"rou={rou['mean_recall_loss']:.3f}/{rou['blind_pct']:.0f}%blind", flush=True)

    # leave _work/store_n in the canonical documented state for the next reader
    stores.build_store_n(con, cmd_trunc=64, script_trunc=64, dns_rare_min=3)
    con.close()

    deltas = [r["delta_mean_recall_loss"] for r in rows]
    out = {
        "benchmark": "apt29 de-gamed BENCH-A — coarsening-sensitivity sweep (truncation cap)",
        "note": ("Deterministic: real APT29 telemetry + unmodified SigmaHQ rules, no RNG. "
                 "The band is the coarsening-sensitivity curve, not a stochastic CI. "
                 "Rule-set-commit variation is a separate axis, left as future work."),
        "dns_rare_min": DNS_RARE_MIN,
        "delta_min": min(deltas), "delta_max": max(deltas),
        "documented_delta": next(r["delta_mean_recall_loss"] for r in rows if r["documented"]),
        "rows": rows,
    }
    path = os.path.join(HERE, "results", "coarsening_sweep.json")
    json.dump(out, open(path, "w"), indent=2, sort_keys=True)
    print(f"\ndelta range across truncation ladder: {min(deltas):+.4f} .. {max(deltas):+.4f} "
          f"(documented 64-char = {out['documented_delta']:+.4f})")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()

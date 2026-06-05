# BENCH-A — OCSF context-collapse

Does normalizing multi-source security telemetry into a single OCSF event store at a
realistic, cost-driven grain degrade *adversary-relevant* queries more than routine
ones? This is a fidelity benchmark, not a performance one: it measures information loss.

Two stores are built from the [shared testbed](../ocsf-semantic-testbed/)'s one corpus,
blind to the query set:

- **Store F** — fidelity-preserving: atomic grain, all four OCSF time types, per-domain
  identity tags, an asset-inventory observable, raw and full command lines kept, absence
  preserved.
- **Store N** — the single normalized/coarse store a pipeline produces under cost
  pressure: one time field from ingestion, network rolled to 5-minute flows, identity
  flattened to one `user_uid`, command lines truncated, MFA-absence coerced to false,
  rare DNS sampled out. Every choice is a documented default, written up in
  [STORE-N-NORMALIZATION.md](STORE-N-NORMALIZATION.md), not a strawman.

The frozen 16-query battery (6 routine controls, 10 adversary-tail) runs against both,
scored against the testbed ground truth. The headline is
`Δ(adversary) − Δ(routine)`, where `Δ(class)` is the mean degradation on Store N minus
Store F over that class.

## Result (first pass, Tier B)

`HEADLINE = +0.719`, with the routine control at `Δ = 0.000` — Store N answers the common
SOC queries exactly as the fidelity store does, so the adversary-tail degradation is a
property of what coarse normalization drops, not of a store broken across the board. Full
numbers, per-mechanism breakdown, and the cost of fidelity are in
[results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
# from the repo root, with the shared venv
.venv/bin/python ocsf-semantic-testbed/generate.py   # the shared corpus (once)
cd bench-a-context-collapse && python run.py         # build stores, score, write results/
```

`run.py` builds both stores, scores the battery twice, and asserts the scored result is
byte-identical (the corpus and the SQL transforms are deterministic; only the testbed's
ground truth and the documented coarsening rules drive the numbers).

## Files

- `stores.py` — builds Store F and Store N from the testbed raw JSONL.
- `bench.py` — the 16 queries against both stores + the fidelity scoring.
- `run.py` — orchestrates, checks determinism, writes `results/`.
- `STORE-N-NORMALIZATION.md` — the documented coarsening default + basis + the Tier-A
  reviewer gate.

## Evidence tier

Tier B: synthetic controlled testbed, single machine, one planted chain. The
routine-survives / adversary-degrades contrast is the finding that holds; the magnitudes
are testbed-specific. Tier-A promotion needs an independent practitioner confirming Store N's
realism (the gate in STORE-N-NORMALIZATION.md) and a second corpus. The public
methodology genericizes the incumbent to a schema-on-read SIEM; no customer data is used.

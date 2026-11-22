# BENCH-A — OCSF context-collapse

## What it measures

Does normalizing multi-source security telemetry into a single OCSF event store at a
realistic, cost-driven grain degrade *adversary-relevant* queries more than routine
ones? This is a fidelity benchmark, not a performance one: it measures information loss.

Two stores are built from the [shared testbed](../ocsf-semantic-testbed/)'s one corpus:

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

*(corrected 2026-11-17: this section used to say the stores were built "blind to the query
set". The battery was frozen first, but `stores.py:146` keeps rollup bytes so that "R4 must
survive", so Store N was built knowing at least one routine query, R4.)*

## Result (first pass, Tier B)

`HEADLINE = +0.719`, with the routine control at `Δ = 0.000`. The headline re-derives from
`results/results.json`: the ten adversary-tail deltas average 0.71904 and the six routine
deltas are all 0.0. Full numbers, per-mechanism breakdown, and the cost of fidelity are in
[results/RESULTS.md](results/RESULTS.md).

Whether the number is measured or follows from construction is split by half, and neither half is
fully measured. The adversary half is a demonstration that each named mechanism removes the answer
to the query written against it: each adversary query is tagged with the one mechanism it was
written to hit, and which query loses what is set by the generator (the C2 domain is resolved
exactly once, so any rare-DNS filter removes it). Five of the ten adversary deltas are exactly 1.0
(A1, A2, A4, A8, A10) because each of those queries needs a field Store N removes outright, so the
+0.719 measures the battery's design more than the knob values; the partial deltas (A3 0.095, A5
0.6, A6 0.993, A7 0.003, A9 0.5) are the ones the store's data determined (`results/results.json`;
reworded 2026-11-22, this used to call the adversary half "measured"). The routine half follows from construction: none of the six routine queries
reads a field any Store N mechanism changes, so its 0.000 could not have come out otherwise
(next section). *(corrected 2026-11-17: the README used to say the routine control at 0.000 shows
the adversary degradation "is a property of what coarse normalization drops, not of a store
broken across the board". The control cannot show that, because it never touches a coarsened
field.)*

## What would have made it fail

The adversary half barely depends on the knobs. In `results/DOSE-RESPONSE.md` the lightest setting
(60 s / 256 / 2) gives the same +0.719 as the documented default, and only the heavy settings move it,
to +0.829, so loosening the knobs did not lower the floor; the partial deltas listed above, and the
two adversary queries that barely degrade (A3 ordering, A7 dwell), are where the result could move
(reworded 2026-11-22: this used to say the adversary half "could have come out lower" and cite the
sweep as showing it).
The routine control could not have failed under these knobs. Store N keeps every auth, process
and API row, so R1, R3 and R6 are exact counts; R2 asks for the top 20 of the 12 destination
ports the generator draws (`../ocsf-semantic-testbed/generate.py:84`) and is answered on Store N
with `sum(flow_count)` (`bench.py:90`), which undoes the rollup; R4 sums bytes the rollup keeps
(`stores.py:146`); R5 asks for the top 50 of about 20 image names, which command-line truncation
does not touch. The dose-response table holds routine Δ at 0.000 up to 3600 s / 12 chars / 12,
which is what the code predicts.

[`../ocsf-context-collapse-apt29/`](../ocsf-context-collapse-apt29/) carries the stronger evidence
for the same hypothesis, because there the routine class could fail and partly did: unmodified
SigmaHQ rules over real APT29 telemetry, split by each rule's own ATT&CK tags, give a routine
recall-loss of 0.16 (4 of 25 routine rules went blind) against 0.348 for the adversary tail, a
gap of +0.188 (directional, not significant at conventional levels on 54 rules; see the note in that
README). That bench is the test in which the control could move; this one is the mechanism
demonstration on a corpus whose answers are known.

## Pre-registration

The query battery and ground truth were frozen 2026-05-31 in a private benchmark repo
(`STORE-N-NORMALIZATION.md`), so neither the frozen text nor a hash is in this repo and the
freeze cannot be checked from here.

## Reproduce

```bash
# from the repo root, with the shared venv
.venv/bin/python ocsf-semantic-testbed/generate.py   # the shared corpus (once)
cd bench-a-context-collapse && python run.py         # build stores, score, write results/
```

`run.py` builds both stores, scores the battery twice, and asserts the scored result is
byte-identical (the corpus and the SQL transforms are deterministic; only the testbed's
ground truth and the documented coarsening rules drive the numbers). `robustness.py`,
`second_chain.py` and `dose_response.py` produce the three supplements below.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json`: the entry point (regenerated by `run.py`).
- [results/ROBUSTNESS.md](results/ROBUSTNESS.md): four background re-draws, headline +0.710 to +0.719.
- [results/SECOND-CHAIN.md](results/SECOND-CHAIN.md): chain B (SMB lateral), +0.710.
- [results/DOSE-RESPONSE.md](results/DOSE-RESPONSE.md): four coarseness levels, +0.719 to +0.829.

## Files

- `stores.py` — builds Store F and Store N from the testbed raw JSONL.
- `bench.py` — the 16 queries against both stores + the fidelity scoring.
- `run.py` — orchestrates, checks determinism, writes `results/`.
- `STORE-N-NORMALIZATION.md` — the documented coarsening default + basis + the Tier-A
  reviewer gate.

## Versions and pins

No `requirements.txt` in this folder; the run uses the root `requirements.txt` (`duckdb==1.5.3`,
which `results/results.json` records).

## Evidence tier and limits

Tier B: synthetic controlled testbed, single machine, one planted chain. The
routine-survives / adversary-degrades contrast is the finding that holds; the magnitudes
are testbed-specific. *(corrected 2026-11-17: the routine half survives by construction; what holds
is that the adversary tail degrades under these knobs, and the routine-versus-adversary contrast is
tested in [../ocsf-context-collapse-apt29/](../ocsf-context-collapse-apt29/).)* Tier-A promotion needs an independent practitioner confirming Store N's
realism (the gate in STORE-N-NORMALIZATION.md) and a second corpus. The public
methodology genericizes the incumbent to a schema-on-read SIEM; no customer data is used.

## Corrections

- *(corrected 2026-11-17: the routine control at 0.000 follows from the battery's routine
  queries avoiding every coarsened field and is not evidence that Store N is realistic; the
  Store N was built knowing at least one routine query, R4 (`stores.py:146`); the APT29 sibling carries the stronger
  evidence.)*

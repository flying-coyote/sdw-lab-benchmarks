# BENCH-A robustness — headline across background draws

**Tier B.** The planted six-stage chain is held byte-identical (generator seed 200); only the background
noise is re-drawn (the six background generators' seeds shift). If `Δ(adversary) − Δ(routine)` holds across
draws, the +0.72 headline isn't keyed to one noise realization.

| bg seed offset | headline | Δ routine | Δ adversary | void |
|---|---|---|---|---|
| 0 | +0.719 | +0.000 | +0.719 | False |
| 1000 | +0.719 | +0.000 | +0.719 | False |
| 2000 | +0.710 | +0.000 | +0.710 | False |
| 3000 | +0.719 | +0.000 | +0.719 | False |

Headline spread across draws: **0.009** (+0.710 … +0.719).
Routine control clean on every draw: **True**. Canonical corpus restored afterward:
True.

## Reading

The headline is stable across background re-draws and the routine control stays clean on each, so the
context-collapse gap is a property of the chain and the coarsening, not of one particular noise
realization — the corpus-draw external-validity worry. The honest scope: this re-draws *noise around the
same needles*, not a different attack. A genuinely different chain (different ATT&CK techniques) is the
deeper external-validity step and needs the frozen battery generalized to read IOCs from ground truth (the
generator, the Store F asset table, and the A1–A10 queries currently hardcode the chain's hosts and
indicators) — a refactor flagged for a dedicated pass. Tier B, single machine.

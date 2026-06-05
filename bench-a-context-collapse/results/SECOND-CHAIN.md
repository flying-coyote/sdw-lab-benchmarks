# BENCH-A second chain — headline on a different attack (results)

**Tier B.** A second independent chain profile, scored by the same frozen A1–A10 battery (which reads the
chain's indicators from the ground-truth IOC block). Same background for both, so the only variable is the
chain.

| chain | profile | headline | Δ routine | Δ adversary | validate | void |
|---|---|---|---|---|---|---|
| A | A — APT29-style, RDP lateral (T1021.001) | +0.719 | +0.000 | +0.719 | 14/14 passed | False |
| B | B — different actor/subnet, SMB lateral (T1021.002) | +0.710 | +0.000 | +0.710 | 14/14 passed | False |

Per-mechanism Δ — chain A: grain +1.00 · time +0.52 · bounded-context +0.55 · structural +0.99 · chain B: grain +1.00 · time +0.50 · bounded-context +0.55 · structural +0.99.
Headline difference A vs B: **0.009**. Both routine controls clean:
True. Canonical chain-A corpus restored afterward: True.

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

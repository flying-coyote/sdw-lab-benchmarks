# BENCH-A dose-response — headline vs coarseness

**Tier B.** How the context-collapse headline `Δ(adversary) − Δ(routine)` moves as Store N's
normalization gets lazier on all three knobs at once (network rollup window / command-line
truncation cap / rare-DNS sampling threshold). Store F is fixed; only Store N varies. The
documented default (the published `+0.72` point) sits mid-ladder so it's locatable on the curve.

| coarseness | rollup / trunc / dns≥ | headline | Δ routine | Δ adversary | void |
|---|---|---|---|---|---|
| light | 60s / 256 / 2 | +0.719 | +0.000 | +0.719 | False |
| documented | 300s / 64 / 3 | +0.719 | +0.000 | +0.719 | False |
| heavy | 900s / 24 / 6 | +0.829 | +0.000 | +0.829 | False |
| very_heavy | 3600s / 12 / 12 | +0.829 | +0.000 | +0.829 | False |

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

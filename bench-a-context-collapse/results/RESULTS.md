# BENCH-A — OCSF context-collapse: results

**Tier B (first pass).** Synthetic, controlled testbed; single machine; one planted
chain. The headline contrast is a real measured finding at this tier; it is not a
production rate. Tier-A promotion is gated on an independent practitioner confirming
Store N's coarsening resembles what shops actually build (see STORE-N-NORMALIZATION.md).

## Headline

```
Δ(routine)    = +0.000   (control — must stay ~0, else the run voids)
Δ(adversary)  = +0.719
HEADLINE      = Δ(adversary) − Δ(routine) = +0.719
```

**Verdict:** supports H-OCSF-CONTEXT-COLLAPSE-01 (coarse normalization degrades adversary-relevant queries disproportionately).

The routine control holds at Δ = +0.000: Store N answers the common SOC/reporting
queries (counts, top-N, egress rollups) exactly as the fidelity store does, so the
adversary-tail degradation below is a property of *what coarse normalization drops*,
not of a store crippled across the board. `void = False`.

## Per-mechanism degradation (Store N vs Store F)

| mechanism | mean Δ | reading |
|---|---|---|
| grain | +1.000 | atomic detail lost (cadence, exact payload, rare events) |
| structural | +0.993 | absence coerced to false (no-MFA indistinguishable) |
| bounded-context | +0.550 | identity/asset flattening (cross-source closure lost) |
| time | +0.524 | one time field + rollup (valid-time and late-arrival lost; ordering/dwell mostly survive) |

The split is the honest part: the queries that crater are the ones whose evidence the
coarse store physically discarded, while ordering (A3) and dwell (A7) mostly survive
coarsening because their milestones aren't buffered and tolerate ~5-minute rollup. Not
every adversary query breaks, and a benchmark that claimed they all did would be less
believable, not more.

## Routine set (R1–R6) — the control

| id | mechanism | fidelity F | fidelity N | Δ (N−F) | note |
|---|---|---|---|---|---|
| R1 | none | 1.000 | 1.000 | +0.000 | auth-event count |
| R2 | none | 1.000 | 1.000 | +0.000 | top-20 dst ports |
| R3 | none | 1.000 | 1.000 | +0.000 | failed-login count |
| R4 | none | 1.000 | 1.000 | +0.000 | egress bytes |
| R5 | none | 1.000 | 1.000 | +0.000 | top-50 images |
| R6 | none | 1.000 | 1.000 | +0.000 | cloud API count |

## Adversary-tail set (A1–A10)

| id | mechanism | fidelity F | fidelity N | Δ (N−F) | note |
|---|---|---|---|---|---|
| A1 | grain | 1.000 | 0.000 | +1.000 | beacon cadence; N: rollup → unanswerable |
| A10 | time | 1.000 | 0.000 | +1.000 | late-arrival recall in true-event-time window |
| A2 | grain | 1.000 | 0.000 | +1.000 | exact encoded payload; N: cmd_line truncated |
| A3 | time | 1.000 | 0.905 | +0.095 | kill-chain order × coverage |
| A4 | time | 1.000 | 0.000 | +1.000 | active-session set; N: valid-time dropped → unanswerable |
| A5 | bounded-context | 1.000 | 0.400 | +0.600 | identity closure across sources |
| A6 | structural | 1.000 | 0.007 | +0.993 | AttachUserPolicy w/o MFA; F:1 N:268 matches (absence vs false) |
| A7 | time | 1.000 | 0.997 | +0.003 | dwell sec (truth 3905) |
| A8 | grain | 1.000 | 0.000 | +1.000 | first-seen C2 domain; N: rare-DNS sampling drops it |
| A9 | bounded-context | 1.000 | 0.500 | +0.500 | distinct assets (truth 2); F:2 N:3 |

## Cost of the fix

Store F is **1.93×** the size of Store N on this corpus
(5,359,973 vs 2,780,438 bytes). Fidelity is not free; the
benchmark reports the price alongside the recovery so "Store F recovers the gap" is
weighed against what it costs to keep.

## Reproduce

```bash
python ../ocsf-semantic-testbed/generate.py     # the shared corpus (deterministic)
python run.py                                    # build stores, score, write results
```

Corpus fingerprint: `820a5d18ed1656217474d98c` · determinism re-check: **identical**.

## Caveats that travel on this result

One synthetic APT29-style chain on one machine; the magnitudes are testbed-specific and
the headline is Tier B. The contrast between routine-survives and adversary-degrades is
the robust finding (it falls out of the architectures, not the data volume). Store N's
normalization is a documented default, not a strawman, but "documented by me" is not the
same as "reviewed" — the named-practitioner sign-off is the Tier-A gate and is Jeremy's
to obtain. Public methodology genericizes the incumbent to a schema-on-read SIEM; no
customer data is involved.

# OCSF flattening-fidelity benchmark

A small, reproducible benchmark for one question: when you flatten semi-structured
security logs (CloudTrail, OCSF) into fixed columns or roll them up to a coarse
grain, which detections silently break, and which queries are unaffected?

It is the first-party measurement behind the essay
[*Flattening away your detection logic*](https://securitydataworks.com/writing/ocsf/flattening-anti-pattern),
which until now carried the grain/time argument as a **Tier-D** claim — a thesis
and a proposed measurement, not a result. This repository runs the measurement.

## What it measures

Three failure modes, each on its own deterministic synthetic corpus, each scored
against a known ground truth by running the *same* detection logic over a lossy
schema and a fidelity-preserving schema:

1. **Absence-vs-NULL collapse → silent detection miss.** CloudTrail encodes "no
   MFA" as the *absence* of `mfaAuthenticated`, not a present-and-false value.
   Flattening coerces absence to NULL, so the natural translation
   `WHERE mfa = 'false'` matches nothing and the privilege-escalation alert
   returns zero. The preserved store (Variant/JSON) keeps absence queryable.
2. **Grain loss → timing query destroyed, volumetric query exact.** A
   `(src, dst, 5-minute)` rollup keeps counts and byte totals but discards
   individual event times. We plant beacons (regular 60s) and benign decoys with
   identical per-bucket volume and payload, separable only on inter-arrival
   jitter, and show the rollup can no longer tell them apart while answering
   routine volumetric queries exactly.
3. **Floating timestamps → cross-zone correlation lost.** Cross-source attack
   chains truly within a 5-minute window, with sources in real timezones. Drop
   the zone offset and the cross-zone chains scatter hours apart, so the
   correlation window silently misses them.

## Results (DuckDB 1.5.3, seed 20260601)

| Failure mode | Lossy schema | Preserved schema |
|---|---|---|
| Absence→NULL, privilege-esc recall | **0.00** (100% silent miss) | **1.00** |
| Grain, beacon-hunt F1 (8 beacons / 16 decoys) | **0.50** | **1.00** |
| Floating time, cross-zone correlation recall | **~0.46–0.50** | **1.00** |

The grain and routine results are split so the asymmetry is visible: the same
rollup that halves beacon-hunt F1 answers bytes-per-host and pair-count queries
*exactly* (matched to the row). Full per-scale numbers in
[`results/RESULTS.md`](results/RESULTS.md); machine-readable in
[`results/results.json`](results/results.json).

## Honesty boundary

This is **Tier B**: a reproducible, first-party, controlled measurement on a
*synthetic* corpus. It is not production telemetry and makes no production claim.
The corpus is built to isolate one mechanism at a time, so the corpus *is* the
argument — read [`METHODOLOGY.md`](METHODOLOGY.md) before trusting any number.
Two magnitudes are corpus parameters, not universal constants, and are labelled
as such there: the grain F1 figure scales with the decoy-to-beacon ratio, and the
floating-time recall tracks the cross-zone fraction. The absence→NULL miss is the
one structural result — it is 100% by construction, because absence and NULL are
the same byte once the column is flattened.

The preserved store uses DuckDB's JSON functions to stand in for **Iceberg V3's
Variant type**, which is the production answer the essay recommends; DuckDB is the
local, reproducible analog, not the deployment target.

## Reproduce

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r ../requirements.txt
python run.py
```

`run.py` runs each benchmark twice and asserts the output is byte-identical
before writing results — the determinism check behind the Tier-B label. Same
code, same seed, same numbers, every run; two independent processes here produced
the identical results digest `4e201f70464eeacb`.

## Layout

```
benchmarks/absence_null.py   failure mode 1
benchmarks/grain.py          failure mode 2
benchmarks/timestamps.py     failure mode 3
run.py                       run all three, verify determinism, write results/
results/                     RESULTS.md + results.json (generated)
```

The seeds, fixed time anchor, and scoring helpers live in the repo-level
[`../lib/common.py`](../lib/common.py), shared with the other benchmarks.

## Related: OCSF field-mapping fidelity (C1)

A separate benchmark — OCSF field-mapping completeness and lossiness across
CrowdStrike, Okta, Palo Alto, Cisco, and Zscaler into OCSF 1.8.0 — is scaffolded
in [`../ocsf-mapping-fidelity/`](../ocsf-mapping-fidelity/). It needs real vendor
schemas rather than a synthetic corpus, so it is stubbed with the protocol and
left unrun until those inputs are gathered.

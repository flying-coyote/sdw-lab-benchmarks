# C1 — OCSF field-mapping fidelity

How completely and how losslessly do real vendor schemas map **into** OCSF 1.8.0?
This benchmark scores two sources field-by-field — **Okta** System Log into
Authentication (3002) and **CrowdStrike** Detection Summary Event into Detection
Finding (2004) — against the real OCSF 1.8.0 schema, and records exactly where
each source field lands a typed attribute, where it crosses a boundary, and where
it has no home but `unmapped`.

> Evidence tier **B**: a first-party mapping judgement against real *documented*
> vendor schemas and the real OCSF schema. It is not production telemetry, and the
> mapping is a reviewable judgement (every field's rationale is in `mapping.py`),
> not a vendor-certified crosswalk.

## Result

| source | OCSF class | fields | typed | coerced | unmapped | coverage | lossy |
|---|---|--:|--:|--:|--:|--:|--:|
| Okta | Authentication (3002) | 50 | 29 | 7 | 14 | 58% | 42% |
| CrowdStrike | Detection Finding (2004) | 43 | 30 | 9 | 4 | 70% | 30% |

- **`coverage`** = fields landing on a typed OCSF attribute, semantics preserved.
- **`coerced`** = a typed home exists but a boundary is crossed (an enum narrows, an
  array collapses to a scalar, an id/label is lost). Counts as lossy.
- **`unmapped`** = no typed home; only `unmapped`/`raw_data` can carry it.

Two findings, not one:

1. **The schema gap.** Even mapping into the classes purpose-built for these events,
   ~40% of Okta's login fields and ~30% of CrowdStrike's detection fields either
   coerce or have no typed OCSF home. The losses are not random — they cluster on a
   few recurring categories (see METHODOLOGY).

2. **The implementation gap (Okta).** OCSF 1.8.0 has a typed-or-coercible home for 36
   of 50 Okta fields, but Okta's own shipped reference mapper
   (`okta/okta-ocsf-syslog`) carries only **18** of 50 into the event. Eighteen fields
   have an OCSF home the integration leaves on the floor — including the
   autonomous-system fields, ISP, domain, network zone, and credential type, all of
   which feed real detections. The schema can hold them; the integration does not.

**Detections:** of 11 named detections, 8 lose at least one field they depend on.
Three survive clean — impossible-travel (geo + IP all typed), suspicious-ASN (typed
in the schema, though Okta's mapper drops it), and known-bad-hash (hashes are
well-modeled). The full breakdown is in `results/RESULTS.md`.

## Why it can't fake a number

- Every OCSF target a mapping points at is validated against
  `schemas/ocsf/ocsf_1.8.0_subset.json` (transcribed from the version-pinned schema
  server). A mapping to an attribute that does not exist in OCSF 1.8.0 fails the run,
  so the coverage figure can't be inflated by inventing a home for a field.
- The inputs are static checked-in files, so the score is a pure function of them.
  `run.py` computes it twice and asserts the two are byte-identical before writing.
- The mapping is not a black box: `mapping.py` carries one record per source field
  with its status and the rationale, and `results.json` carries the resolved per-field
  result. Disagree with a call? It's one line to find and argue with.

## Honest scope

- **Okta** = the documented System Log LogEvent (the login event family Okta's own
  mapper targets); account-administration events would route to Account Change (3001)
  and API events to API Activity (6003), out of scope for this first cut.
- **CrowdStrike** = the publicly-reproduced **Detection Summary Event**, *not* the
  gated full Falcon Data Replicator schema (900+ event types, login-walled). Coverage
  is for that one event, not all CrowdStrike telemetry. CrowdStrike publishes no
  field-level OCSF mapping, so its half is best-effort against the real schema and
  labelled as such.
- Field types for CrowdStrike come from independent third-party reproductions
  (Elastic, Panther, Splunk) that agree, because CrowdStrike's own dictionary is
  gated. Provenance and the public-vs-gated boundary are spelled out in
  `schemas/crowdstrike/PROVENANCE.md`.
- Palo Alto, Cisco, and Zscaler remain scaffold (`schemas/<source>/`); this run scores
  the two sources whose schemas could be sourced with clean provenance.

## Files

```
README.md            this
METHODOLOGY.md       the scoring rules, the recurring seams, the caveats
mapping.py           the reviewable field-by-field mappings + named detections
map_fidelity.py      loaders, OCSF-path validator, scorer
run.py               determinism check + results writers
schemas/ocsf/        OCSF 1.8.0 schema subset (validation target) + provenance
schemas/okta/        Okta LogEvent inventory + provenance
schemas/crowdstrike/ CrowdStrike Detection Summary Event inventory + provenance
results/             results.json + RESULTS.md (generated)
```

## Reproduce

```bash
cd ..                                   # repo root
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt         # only the stdlib + duckdb/chdb shared pins; C1 itself is pure-stdlib
cd ocsf-mapping-fidelity && python run.py
```

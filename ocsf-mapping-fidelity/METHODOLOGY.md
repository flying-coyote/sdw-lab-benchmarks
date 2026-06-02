# Methodology — OCSF field-mapping fidelity (C1)

## What is measured

For two vendor event schemas, every documented source field is assigned exactly one
disposition against the real OCSF 1.8.0 target class:

- **typed** — lands on a typed OCSF attribute with its semantics preserved. The hash
  fields → `file.hashes[]`, the command line → `process.cmd_line`, the source IP →
  `src_endpoint.ip`.
- **coerced** — a typed OCSF attribute can hold it, but mapping crosses a boundary
  and loses information: an enum narrows to fewer values, a structured array collapses
  to a scalar, or an id/label survives but its counterpart does not. Counted as lossy.
- **unmapped** — no typed OCSF attribute fits; only `unmapped` (a generic key/value
  bag) or `raw_data` (a single string blob) can carry it.

From those:

```
coverage        = typed / total_fields            # typed only, per the pre-registered protocol
lossy_fraction  = (coerced + unmapped) / total
detection-breaking = the lossy fields a *named* detection depends on
```

`coverage_incl_coerced` is reported too, for readers who count a coerced-but-present
field as covered.

## The two gaps

The Okta half is scored twice. Once against the OCSF 1.8.0 schema (can a typed home
exist at all?), and once against Okta's own shipped reference mapper,
`okta/okta-ocsf-syslog` (does the integration actually carry the field?). The
difference — fields with an OCSF home that the shipped mapper drops — is the
**implementation gap**, and it is larger than the schema gap. CrowdStrike publishes no
field-level OCSF mapping, so only the schema gap is scored for it, and that asymmetry
is itself a finding: one vendor ships a public (if partial) mapper, the other gates it.

## How a fake number is prevented

- **Target validation.** Every OCSF attribute path in `mapping.py` is resolved against
  `schemas/ocsf/ocsf_1.8.0_subset.json` — a transcription of the real 1.8.0 class and
  object attribute graph from the version-pinned schema server. A path whose first
  segment is not an attribute of the target class, or which descends into a scalar, or
  which names an attribute an object does not have, raises and the run aborts. The
  coverage figure cannot be lifted by inventing an OCSF home.
- **Completeness check.** Every source field in the inventory must have exactly one
  mapping record, and every mapping record must correspond to an inventory field. A
  missing or stray mapping aborts the run, so coverage is over the whole documented
  field set, not a convenient subset.
- **Status/catch-all invariant.** A record with status `unmapped` must target a
  catch-all (`unmapped`/`raw_data`), and a record targeting a catch-all must be
  `unmapped`. This stops a lossy field from being quietly recorded as covered.
- **Determinism.** No clock, no randomness; the score is a pure function of the
  checked-in files. `run.py` scores twice and asserts byte-identity before writing.

## The recurring seams

The lossy fields are not scattered; they fall into a handful of categories that recur
across both sources, the same categories the six-schemas-into-OCSF crosswalk work
surfaced:

1. **Enum narrowing.** Okta `outcome.result` (7 values → ~3 in `status_id`),
   `credentialType` (12 schemes → `is_mfa` + factor); CrowdStrike `Severity` (numeric
   scale → `severity_id` enum), `IOCType` (free string → `observable.type_id` enum).
   The richer source vocabulary collapses.
2. **Open / free-form maps.** Okta `debugContext.debugData`, the three `detailEntry`
   maps, `transaction.detail`; CrowdStrike `PatternDispositionFlags`. OCSF has no typed
   home for an arbitrary key/value bag, so the whole structure lands in `unmapped` —
   and for Okta that bag is exactly where the risk and threat signals live.
3. **Structure / array collapse.** Okta `request.ipChain` (per-hop IP + geo, ordered →
   an IP list, geo and order lost), the heterogeneous `target[]` array (no array slot on
   Authentication); CrowdStrike `GrandparentImageFileName`/`GrandparentCommandLine` (a
   two-level model plus a flat ancestry path, so the grandparent command line has
   nowhere to go), and the conditional nested arrays.
4. **Id-vs-label fidelity.** CrowdStrike `Tactic`/`Technique` arrive as one flat string,
   but OCSF's `attack` object wants `{name, uid}` per tactic and technique; a flat string
   populates one and leaves the other empty, so an ATT&CK-id pivot can't rely on the id.
5. **Signals OCSF has no field for.** Okta `securityContext.isProxy` (a boolean
   anonymizing-proxy flag with no OCSF endpoint attribute), `client.userAgent.browser`
   (OCSF keeps the raw UA, not a parsed-browser field).

## Caveats and what this is not

- The mapping is a documented judgement, not a vendor-certified crosswalk. Reasonable
  people will move a field or two between coerced and typed; the per-field rationale is
  published precisely so that argument can happen on the record. A handful of
  reclassifications shifts coverage by a couple of points and changes none of the
  five seams.
- Coverage is over each source's **scoped** field set (Okta login LogEvent; CrowdStrike
  Detection Summary Event), not over all of that vendor's telemetry, and certainly not
  over "OCSF coverage" in general.
- This measures *schema-mapping fidelity* — a structural property of fitting one
  schema into another. It is not a quality score for any particular product's pipeline,
  and the Okta implementation gap is a statement about one open-source reference mapper
  at one point in time, not about Okta's commercial integrations.
- Magnitudes are corpus-of-fields parameters: 58% / 70% are functions of which fields
  are in scope and the per-field calls, not universal constants. The durable result is
  the *shape* — that the losses concentrate on enums, open maps, nested structure,
  id/label pairing, and signals OCSF lacks a field for — and that a vendor's own shipped
  mapper can realize far less than the schema would allow.

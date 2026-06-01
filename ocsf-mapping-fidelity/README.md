# C1 — OCSF field-mapping fidelity benchmark (scaffold, not yet run)

> Status: **scaffold only.** Protocol below is fixed; the harness in
> `map_fidelity.py` is stubbed and raises `NotImplementedError` until real vendor
> schemas are gathered. No numbers here yet — and none invented.

The sibling `flattening-fidelity/` benchmark measures what flattening and grain do
to detections on a synthetic corpus. C1 measures something it deliberately does
not: how completely and how losslessly real vendor schemas map **into** OCSF. It
needs real inputs, so unlike the synthetic benchmarks it cannot run on a
self-contained corpus, which is why it is scaffolded separately and left unrun
rather than filled with placeholder figures.

## Question

For each major Tier-2 source — CrowdStrike (Falcon Data Replicator), Okta (system
log), Palo Alto (PAN-OS / Cortex), Cisco (NGFW / Secure), Zscaler (NSS/LSS) —
mapped into **OCSF 1.8.0**: what fraction of source fields land on a typed OCSF
attribute, what fraction land only in `unmapped`/`raw_data`, and which
security-relevant fields are lost or coerced in a way that breaks a detection?

## Protocol (pre-registered)

1. **Inputs.** A real event sample (or published schema) per source, and the OCSF
   1.8.0 schema (classes, attributes, enums). Inputs are checked into `schemas/`
   per source, with provenance recorded.
2. **Map.** Apply the vendor's published OCSF mapping where one exists; otherwise
   a best-effort mapping recorded field-by-field in a mapping file, so the mapping
   itself is reviewable rather than a black box.
3. **Score per source.**
   - *coverage* = typed-OCSF-mapped fields / total source fields
   - *lossy* = fields landing only in `unmapped`/`raw_data` or coerced across a
     type boundary (e.g. enum → free string, structured → flattened)
   - *detection-breaking* = the subset of lossy fields a named detection depends
     on (carry the detection and the field, not just a count)
4. **Report.** A per-source table plus the recurring cross-source seams (the
     field categories that map badly everywhere), tied back to the six-schemas
     crosswalk work and OCSF Issue #1515.

## Honesty boundary

This will be **Tier B at best** even when run — it depends on the fidelity of the
input samples and the mapping judgement, both of which get disclosed. Vendor
mappings change version to version; every figure will carry the source schema
version and the OCSF version it was scored against. Until real schemas are in
`schemas/`, this directory publishes nothing.

## Files

```
README.md          this protocol
map_fidelity.py    stubbed harness (raises until inputs exist)
schemas/           one subdir per source for real schema/sample inputs (empty)
```

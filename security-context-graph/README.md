# Security Context Graph (concept-only)

A small, queryable concept graph that merges the scattered OCSF ↔ D3FEND ↔ ATT&CK ↔ NIST
800-53 / CCI / SCF crosswalks into one structure whose differentiator is **honesty about its
own joints**: every edge carries `{rel, source_file, tier, proxy_quality, proxy_note}`, so a
consumer can see how cheap each join's proxy is rather than treating a documentation
hyperlink and a measured field map as the same kind of fact.

This is the evidence behind the controls-layer essay
([securitydataworks.com/writing/ocsf/controls-layer-crosswalk](https://securitydataworks.com/writing/ocsf/controls-layer-crosswalk/)),
not an owned product. It backs the essay and the control-consensus Sankey; per-vendor scoring
stays in the paid Capability Matrix. It overlaps MITRE/CTID's Mappings Explorer by design —
the contribution here is the `proxy_quality` transparency layer and the measured brittleness,
not a rival mapping.

## Why "concept-only"

The graph holds **concepts and entities, never telemetry events** — OCSF classes, digital
artifacts, D3FEND defenses, ATT&CK techniques/tactics, controls, frameworks. That keeps it at
a few thousand nodes (3,284 with SCF), not the 234k per-event nodes that stalled a separate
telemetry benchmark on CPU embedding. The static map needs structure, not vectors, so there
are no embeddings here.

## The chain and the honest state of each joint

```
field ─①─► OCSF class ─②─► digital artifact ─③─► D3FEND defense ─④─► ATT&CK offense ─⑤─► 800-53 / SCF control → frameworks
```

`proxy_quality` tags every edge — the tag is the whole point:

| proxy_quality          | hop  | what the edge actually rests on                                              | tier |
|------------------------|------|------------------------------------------------------------------------------|------|
| `measured`             | ①    | field-level crosswalk read from a mapping table (CIM→OCSF sample shipped)     | A    |
| `doc_link`             | ②    | OCSF↔D3FEND reciprocal `seeAlso`/`references` hyperlinks — not axioms, not fields | A |
| `ontology_curated`     | ③    | D3FEND technique hand-tagged to the artifact it observes/touches             | A    |
| `artifact_cooccurrence`| ④    | offense↔defense inferred from a **shared** artifact; intent-blind (D3FEND #520), a *possibility* of coverage not a guarantee | A (structure) / B (coverage) |
| `curated`              | ④'   | D3FEND's hand-authored ATT&CK-mitigation (`M####`) relations                 | A    |
| `skos_typed`           | ⑤    | D3FEND→800-53/CCI, SKOS `broader`/`narrower`/`exactly`/`related`             | A    |
| `ctid_reroute`         | ⑤'   | SCF→ATT&CK is **CTID's** 800-53→ATT&CK re-routed through SCF's own 800-53 crosswalk (uniform Intersects-With/strength-3); SCF adds no independent ATT&CK signal | A |
| `scf_strm`             | ⑤'   | SCF control → external framework, NIST IR 8477 Set Theory Relationship Mapping | A   |
| `derived`              | —    | rollups computed across hops (e.g. defense→control via the ATT&CK it counters) | B   |

`SCF↔D3FEND direct` does not exist — D3FEND is not one of SCF's 250 frameworks, so the
governance bridge runs through ATT&CK (or through the shared 800-53 hop).

## Run

```bash
python3 scg.py              # public spine (OCSF / D3FEND / ATT&CK / NIST-800-53 / CCI)
python3 scg.py --with-scf   # + the SCF layer (local, ND-gated — see below)
```

Outputs: `results/nodes.json`, `results/edges.json`, `results/fingerprint.txt`,
`results/reconcile.json`. Source paths default to the local `project1` working copies and are
each overridable by env var (`SCG_ONTOLOGY`, `SCG_SCF_SANKEY`, …) so the public spine can run
against vendored copies of the public artifacts.

## SCF licensing gate (CC-BY-ND)

The Secure Controls Framework workbook is **CC-BY-ND**. The public spine carries no SCF
content. The `--with-scf` layer loads from a local, un-redistributed `scf_sankey.json` and its
raw `nodes.json`/`edges.json` (the SCF control→framework mapping cells) are **not** committed
or redistributed — only derived aggregate statistics (consensus counts, the reach numbers in
`reconcile.json`) are publishable. The committed `results/` here are spine-only; the SCF graph
is generated locally into a gitignored directory.

## Reconciliation (every number traces to a source, and the build asserts it)

The build hard-fails unless each figure reproduces. Spine asserts need no SCF; the reach
asserts need `--with-scf`. Confirmed:

| check | value | source |
|---|---|---|
| SKOS edges / controls / techniques | 606 / 402 (111×800-53, 291×CCI) / 79 | `verify_skos_counts.py` logic over the v1.4.0 ontology |
| OCSF↔D3FEND seeAlso pairs / event-class links / distinct classes | 69 / 28 / **27** | ontology `rdfs:seeAlso → schema.ocsf.io` |
| DigitalArtifact leaves / with OCSF seeAlso | 607 / 14 (97.7% leaf-orphan) | ontology subclass tree |
| wall defenses | 120 | `wall_columns.csv` |
| SCF controls→ATT&CK / distinct ATT&CK ids | 108 / 511 | `scf_sankey.json` `map["36"]` |
| wall defenses reaching an SCF control | 118 / 120 (98%) | derived; matches `scf_attack_d3fend_crosswalk.json` |
| SCF ATT&CK-controls reached by a defense | 104 / 108 | derived |
| wall ATT&CK with no SCF control (the Discovery gap) | 33 | derived |
| node count (concept-only) | 3,284 with SCF, < 10k | invariant |
| event nodes | 0 | invariant |

### Integrity note — the build corrected a stale number

The distinct-OCSF-event-class count was carried as **25** in `robustness-map.md` and in the
published essay. Reproducing it from the v1.4.0 ontology gives **27**: the 28 event-class
`seeAlso` links resolve to 27 distinct OCSF classes, with only `module_activity` a shared
target (Load + Unload library events). The earlier 25 came from an older extraction whose
entity→class names differ from the shipped v1.4.0 file (e.g. `d3f:NetworkEvent` vs
`d3f:NetworkConnectionEvent`). All 27 are real OCSF classes. The graph build is what surfaced
the drift — which is the point of a reconciliation pass.

## What this is not

- not a telemetry graph (no events; record→defense runtime annotation does not exist today);
- not a product (the map + thesis are public; per-vendor scoring is the paid Matrix);
- not a rival to D3FEND/OCSF/CTID — it points at the upstream commons and contributes findings.

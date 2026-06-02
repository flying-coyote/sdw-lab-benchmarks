# OCSF 1.8.0 schema — provenance

`ocsf_1.8.0_subset.json` is a transcribed subset of the real OCSF 1.8.0 schema,
used as the validation target for every mapping in this benchmark. The harness
refuses to score a mapping whose OCSF target attribute does not resolve against
this graph, so the subset is what keeps the mapping honest: no inventing an OCSF
attribute that does not exist.

## Version confirmation

OCSF **1.8.0**, released **2026-03-18**, is the current stable release. Verified
three ways, all agreeing:

- `https://api.github.com/repos/ocsf/ocsf-schema/releases/latest` → `tag_name: "1.8.0"`, `published_at: 2026-03-18T14:49:59Z`
- `https://api.github.com/repos/ocsf/ocsf-schema/tags` → `1.8.0` is the highest stable tag (above 1.7.0, 1.6.0, 1.5.0)
- `https://schema.ocsf.io/api/version` → `{"version":"1.8.0"}`; `https://schema.ocsf.io/api/versions` lists `1.8.0` as `default` (only `1.9.0-dev` is newer, and it is unreleased)

## Attribute sets

Every class and object attribute set is transcribed from the version-pinned JSON
API:

- Classes: `https://schema.ocsf.io/1.8.0/api/classes/{authentication,detection_finding}` (and `account_change`, `api_activity`, `base_event` for the class-uid confirmations)
- Objects: `https://schema.ocsf.io/1.8.0/api/objects/{user,actor,network_endpoint,device,process,file,finding_info,attack,observable,metadata,session,http_request,location,os,fingerprint,enrichment}`
- Catch-alls (`unmapped`, `raw_data`, `enrichments`) and their verbatim definitions from `https://schema.ocsf.io/1.8.0/api/classes/base_event`

Confirmed class UIDs: Authentication = 3002 (category 3, IAM), Account Change =
3001 (category 3), API Activity = 6003 (category 6), Detection Finding = 2004
(category 2).

## What is deliberately not reproduced

- Per-attribute data types and requirement levels (required/recommended/optional)
  are at schema.ocsf.io; fidelity scoring here does not use them, so omitting them
  keeps the validation graph small. Object references (the descent edges) and
  attribute names are reproduced faithfully because the validator needs them.
- Objects referenced but not descended into during scoring (e.g. `evidences`,
  `auth_factor`, `autonomous_system`, `tactic`, `technique`, `sub_technique`) are
  intentionally absent from the `objects` map; the validator treats a reference to
  an object it does not hold as "stop here, accept the deeper leaf," and the
  mapping note records the intended leaf. This is why, e.g.,
  `src_endpoint.autonomous_system.number` validates: `src_endpoint`
  (network_endpoint) and its `autonomous_system` attribute are both confirmed, and
  `.number` is accepted as a deeper leaf of an object not transcribed here.

## Catch-all semantics (verbatim from base_event)

- `unmapped` — *"The attributes that are not mapped to the event schema. The names
  and values of those attributes are specific to the event source."* A generic
  object; the explicit landing zone for source fields with no typed home.
- `raw_data` — *"The raw event/finding data as received from the source."* A single
  `string_t` blob in 1.8.0 (it was `json_t` in earlier versions). A field that
  survives only inside `raw_data` is unmapped **and** untyped — worse for retrieval
  than `unmapped`.
- `enrichments` — externally-added context (e.g. geo added onto an IP), **not** a
  home for source fields that lack a typed attribute. Scoring treats it as
  out-of-scope for "did this source field find a typed home."

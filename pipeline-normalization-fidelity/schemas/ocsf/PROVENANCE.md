# OCSF 1.8.0 extension subset — provenance

`ocsf_1.8.0_ext_subset.json` adds the two OCSF classes this bench needs that the C1
(`ocsf-mapping-fidelity`) subset does not transcribe, plus the one new object they
reference. It is **merged on top of** the C1 subset by `score.py`; it does not
duplicate or edit anything C1 ships.

## Why an extension, not an edit

C1's `schemas/ocsf/ocsf_1.8.0_subset.json` covers five classes
(Authentication 3002, Detection Finding 2004, Network Activity 4001, DNS Activity
4003, HTTP Activity 4002). Two of this bench's four source classes have no home
there:

- **AWS CloudTrail → API Activity (6003)** — C1 even lists `api_activity` under
  `other_classes_not_scored_here`.
- **Sysmon process events → Process Activity (1007)** — not present in C1 at all.

The other two source classes are already in C1 and are reused as-is:

- **Zeek conn → Network Activity (4001)** — C1 subset.
- **Authentication source → Authentication (3002)** — C1 subset.

Editing C1's checked-in subset would change the C1 result (its `run.py` asserts a
byte-identical re-score), so the two new classes live here and merge at load time.

## Source of the transcription

Attribute names and object references are transcribed from the **version-pinned**
OCSF 1.8.0 schema server and the 1.8.0 release:

- Process Activity (1007): `https://schema.ocsf.io/1.8.0/classes/process_activity`
  (API: `https://schema.ocsf.io/1.8.0/api/classes/process_activity`)
- API Activity (6003): `https://schema.ocsf.io/1.8.0/classes/api_activity`
  (API: `https://schema.ocsf.io/1.8.0/api/classes/api_activity`)
- `api` object: `https://schema.ocsf.io/1.8.0/objects/api`

Same discipline as the C1 `schemas/ocsf/PROVENANCE.md`: per-attribute requirement
(required/recommended/optional) and data types are **not** reproduced because the
fidelity scoring does not use them — only the attribute graph (does the path
resolve, and is its leaf a scalar or an object reference). A value of `null` is a
scalar leaf; a string value names the OCSF object the attribute references.

## A pinning caveat to resolve before the scored run

This extension is transcribed, not auto-pulled. **Before the first scored run**,
re-pull these three pages from `schema.ocsf.io/1.8.0/` and diff against this file,
the same as the C1 subset was verified against the pinned server. Any 1.8.0
profile-driven attribute the schema server lists but this transcription missed
should be added (an attribute that exists on the server but not here would force a
real mapping target to fail the validator — a false negative, the safe direction,
but still worth closing). The bench's `ready_to_run` flag stays **false** until
that diff is done, exactly because a transcription is a human-verifiable artifact,
not a fetched one.

## Objects reused from C1 (not re-transcribed here)

`process`, `actor`, `device`, `file`, `metadata`, `network_connection_info`,
`network_endpoint`, `network_proxy` (deep), `user`, `session`, `cloud` (deep),
`http_request`, `observable`, `osint` (deep), `attack`, `authorization` (deep),
`malware` (deep), `policy` (deep), `firewall_rule`, `fingerprint`, `enrichment`.
Objects referenced but transcribed in neither file (e.g. `module`, `resource_details`,
`request`, `response`, `service`, `cloud`) resolve as **deep** leaves under the C1
validator (`resolve_ocsf_path` returns `"deep"` and accepts the remaining leaf) —
identical to how C1 already handles `container`, `api`, etc. That is intentional and
matches C1; it is recorded here so the resolution kind is auditable.

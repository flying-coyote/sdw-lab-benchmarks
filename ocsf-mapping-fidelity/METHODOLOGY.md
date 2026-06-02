# Methodology — OCSF field-mapping fidelity (C1)

## What is measured

For six vendor event schemas — Okta → Authentication (3002), CrowdStrike → Detection
Finding (2004), Palo Alto → Network Activity (4001), Cisco ASA → Network Activity
(4001), Cisco Umbrella → DNS Activity (4003), and Zscaler → HTTP Activity (4002) —
every documented source field is assigned exactly one disposition against the real
OCSF 1.8.0 target class:

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
**implementation gap**, and it is larger than the schema gap.

The other five sources are scored only for the schema gap, and the reason is itself a
finding. CrowdStrike's field-level FDR→OCSF mapping is account-manager-gated; Palo
Alto, Cisco ASA, and Cisco Umbrella publish no field-level OCSF crosswalk at all;
**Zscaler** does publish an official ZIA→OCSF mapping for AWS Security Lake (Web →
HTTP Activity 4002, OCSF v1.5.0), but only the class-level routing is publicly
retrievable, not the per-field carry list, so its implementation gap is flagged as a
follow-up rather than fabricated (see `schemas/zscaler/PROVENANCE.md`). Okta is the one
source here whose shipped field-level mapper can be read and scored. The asymmetry —
one vendor ships a public, readable mapper; the rest gate it, omit it, or ship it in a
form you cannot inspect field-by-field — is the durable point, not the single
implementation-gap number. A first-hand case of how wrong a shipped integration can be
even when the schema is generous is recorded in `schemas/palo_alto/PROVENANCE.md`.

The Palo Alto, Cisco, and Zscaler mappings also surface an **OCSF-version
observation**: Zscaler's shipped mapping targets OCSF v1.5.0 while this benchmark
validates against v1.8.0; mapping fidelity is measured against a moving target, and the
version a vendor ships against lags the current schema.

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
   (OCSF keeps the raw UA, not a parsed-browser field); Zscaler's DLP dictionaries /
   engine (a DLP match is a different OCSF class, not an attribute of HTTP Activity).

The firewall, DNS, and proxy sources add seams the identity and endpoint sources did
not, and these are the new contribution of this extension:

6. **Pre/post-NAT (translated-address) collapse.** OCSF Network / DNS / HTTP Activity
   model exactly one address per role — one `src_endpoint`, one `dst_endpoint` — so the
   *translated* or *egress* address has no second-address home. It recurs across all
   four new sources: Palo Alto `natsrc`/`natdst`/`natsport`/`natdport`, Cisco ASA
   `mapped_src_ip`/`mapped_src_port`/`mapped_dst_ip`/`mapped_dst_port`, Umbrella
   `external_ip`, Zscaler `clientpublicip`. A NAT-aware "tie this public flow back to
   the real internal host" detection breaks on every one of them. This is the single
   most consistent new seam.
7. **Firewall action-enum narrowing + lifecycle/disposition conflation.** Palo Alto
   `action` (allow / deny / drop / drop-icmp / reset-client / reset-server / reset-both
   / drop-all) collapses into OCSF `action_id` (Allowed / Denied), losing the
   drop-vs-reset-vs-deny distinction; Cisco ASA `action` (Built / Teardown / Deny)
   collapses too, and worse — Built and Teardown are *lifecycle* states OCSF would put
   in `activity_id`, while Deny is a *disposition* in `action_id`, so a single source
   field straddles two OCSF fields and can populate neither cleanly.
8. **App-ID / cloud-app (CASB) taxonomy.** OCSF has no application-taxonomy attributes,
   so Palo Alto's App-ID metadata (`subcategory_of_app`, `category_of_app`,
   `technology_of_app`, `risk_of_app`, `characteristic_of_app`, `container_of_app`,
   `tunneled_app`, the SaaS/sanctioned flags — eight unmapped fields) and Zscaler's
   cloud-app class (`appclass`) have nowhere to land. The application *name* maps
   (`app_name`); everything the vendor knows *about* the application does not.
9. **URL / content-category taxonomy.** OCSF carries URL categories only on the `url`
   object and primarily as a typed `category_ids` enum with its own taxonomy, so a
   vendor's category hierarchy does not fit: Palo Alto `category`, Zscaler
   `urlcategory` / `urlclass` / `urlsupercategory`, and — most starkly — Umbrella's
   domain `categories` / `blocked_categories`, because DNS Activity has no URL object
   and therefore no category attribute at all. Content categorization is much of what a
   secure web gateway and a DNS-security service are *for*, and it is largely invisible
   to OCSF.
10. **Device-ID / heterogeneous-identity taxonomy.** Palo Alto Device-ID category
    (`src_category` / `dst_category`) coerces into the OCSF endpoint `type_id` enum,
    which does not match; and Umbrella's identity model — `most_granular_identity` plus
    its `_type` — is heterogeneous (a roaming computer, an AD user, a network, or a
    site), so flattening it to one endpoint field loses the type-discriminated meaning,
    and the full `identities` list has no multi-identity home at all. This is the
    network-source echo of Okta's heterogeneous `target[]` array.

A note on what *does* map cleanly, so the seams are not overstated: the network 5-tuple
(IPs, ports, protocol), the session identifiers, timestamps and durations, and — for
Palo Alto — the **directional** byte and packet counters (`bytes_sent`/`bytes_received`
→ `traffic.bytes_out`/`bytes_in`, and the packet equivalents) all land typed. Cisco ASA
reports only a single *total* byte count, so that direction split is simply absent at
the source, not lost in mapping — a source limitation, recorded as such, not an OCSF
seam.

## Caveats and what this is not

- The mapping is a documented judgement, not a vendor-certified crosswalk. Reasonable
  people will move a field or two between coerced and typed; the per-field rationale is
  published precisely so that argument can happen on the record. A handful of
  reclassifications shifts coverage by a couple of points and changes none of the
  five seams.
- Coverage is over each source's **scoped** field set — Okta login LogEvent;
  CrowdStrike Detection Summary Event; the Palo Alto core traffic-session record (five
  license/platform-gated families excluded with stated counts in its provenance); the
  Cisco ASA connection-event message family; the Umbrella v3+ DNS-log columns; the
  Zscaler standard NSS web-log set — not over all of that vendor's telemetry, and
  certainly not over "OCSF coverage" in general. Two of the new sources (Palo Alto's
  family exclusions, Zscaler's customizable NSS feed) involve an explicit scoping
  choice; both are stated in the source provenance so a reader can re-scope and re-run.
- This measures *schema-mapping fidelity* — a structural property of fitting one
  schema into another. It is not a quality score for any particular product's pipeline,
  and the Okta implementation gap is a statement about one open-source reference mapper
  at one point in time, not about Okta's commercial integrations.
- Magnitudes are corpus-of-fields parameters: the per-source figures (46%–70%, ~59%
  overall across 251 fields) are functions of which fields are in scope and the
  per-field calls, not universal constants. The durable result is the *shape* — that the
  losses concentrate on a stable set of seams (enums, open maps, nested structure,
  id/label pairing, signals OCSF lacks; and for the network sources, pre/post-NAT
  collapse, firewall action enums, and the App-ID / URL-category / device-ID
  taxonomies) — and that a vendor's own shipped mapper can realize far less than the
  schema would allow.

# Okta System Log — provenance

`inventory.json` is the documented field set of the Okta System Log **LogEvent**
object, the source schema scored against OCSF Authentication (3002).

## Source schema

- **Authoritative:** Okta System Log API reference, the LogEvent object and its
  nested objects (Actor, Client, UserAgent, GeographicalContext, Geolocation,
  Outcome, Target, Transaction, DebugContext, AuthenticationContext, Issuer,
  SecurityContext, Request, IpAddress). Field names and types are reproduced from
  this reference. The live page (`developer.okta.com/docs/reference/api/system-log/`)
  has migrated to a JS-rendered OpenAPI tag page that no longer exposes the
  per-object property tables, so the inventory was transcribed from the archived
  authoritative version (Wayback snapshot 2023-03-28 of the same reference) and
  corroborated against three independent mirrors that reproduce the native Okta
  JSON: Elastic Filebeat (`exported-fields-okta`), Panther (`supported-logs/okta`),
  and Sekoia (`okta_system_log`).
- The free-form keys inside `debugContext.debugData` (risk signals, deviceFingerprint,
  threat_suspected, behaviors, requestUri) are **not** part of Okta's typed schema —
  `debugData` is documented as `Map[String->Object]`. They are counted as one open-map
  field, not enumerated, because their keys are event-type- and version-dependent.

## Vendor OCSF mapping that exists

Okta publishes an official reference mapper, **`okta/okta-ocsf-syslog`** (the Lambda
behind Okta's Amazon Security Lake / EventBridge integration), which maps System Log
events to **Authentication (class_uid 3002)**. Two caveats it states itself:

1. It implements **only the successful-authentication event** ("ONLY CONSIDERS:
   SUCCESSFUL AUTHENTICATION EVENT").
2. It targets an **early OCSF (0.x, ~2022)** schema — its `category_uid = 3` /
   `category_name = 'Audit Activity events'` is stale (in current OCSF, category 3 is
   IAM). The class UID 3002 is the still-valid anchor.

The mapping in `mapping.py` records, per field, whether this shipped reference mapper
realizes the mapping (`okta_official: true/false`). Where it does, the OCSF target
follows the Lambda's `app.py`/README. Where it does not, the target is a best-effort
mapping against the OCSF 1.8.0 schema, and the gap between the two is itself a result.

Sources:
- Okta blog — "An Automated Approach to Convert Okta System Logs into OCSF"
- GitHub `okta/okta-ocsf-syslog` (README mapping table + `app.py`)
- OCSF Authentication class: `https://schema.ocsf.io/1.8.0/classes/authentication`

## Scope and honesty notes

- Scored against **Authentication (3002)** only. Okta account-administration events
  route to **Account Change (3001)** and Okta API events to **API Activity (6003)**;
  those event families are out of scope for this first cut, which uses the login
  LogEvent field set (the family Okta's own mapper targets).
- The inventory is the **typed documented schema**, not a single captured event, so
  coverage is measured against the schema's field set, not against one payload's
  populated fields.

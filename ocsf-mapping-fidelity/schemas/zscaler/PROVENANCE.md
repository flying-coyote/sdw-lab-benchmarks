# Zscaler Internet Access (ZIA) Web log — provenance

`inventory.json` is the standard **Web log** field set of Zscaler Internet Access,
scored against OCSF **HTTP Activity (4002)**.

## Source schema

- **Authoritative:** Zscaler ZIA documentation, *Analytics → NSS → NSS Feeds →
  NSS Feed Output Format: Web Logs* (`help.zscaler.com/zia/nss-feed-output-format-web-logs`,
  including the downloadable feed-format CSV). ZIA web logs are emitted by the NSS
  (or Cloud NSS to S3) feed; the feed is field-customizable, so the inventory scopes
  to the **documented standard web-log field set** — the `%s{...}` / `%d{...}` tokens
  (e.g. `%s{url}`, `%s{urlcat}`, `%s{reqmethod}`, `%d{respsize}`, `%s{respcode}`),
  each recorded in the field note.
- **Corroborated** against three independent reproductions that agree on the field
  set: **Panther** (`Zscaler.ZIA.WebLog`), **Elastic** (`zscaler_zia` integration),
  and **Rapid7 InsightIDR** (Zscaler NSS). The LogScale/Humio Zscaler integration is
  a fourth.

## Vendor OCSF mapping that exists — and why no per-field `official` flag

Zscaler **does** publish an official ZIA→OCSF mapping for **AWS Security Lake**, and
this is confirmed first-party (AWS CloudWatch "Source configuration for Zscaler
Internet Access" and Zscaler's Security Lake integration help): ZIA **Web Logs map to
HTTP Activity (4002)** (DNS Logs → DNS Activity 4003, Firewall Logs → Network
Activity 4001, Admin Audit → Authentication 3002), at **OCSF v1.5.0**.

That mapping is **class-level confirmed but field-level not publicly retrievable**:
the AWS and Zscaler pages that would carry the per-attribute table are JavaScript-
rendered and do not expose the mapping to a fetch, and there is no Zscaler OCSF
feed-format file in Zscaler's public GitHub org. So, to avoid guessing which web-log
fields the official mapper carries into the OCSF event, **no per-field `official`
flag is carried for Zscaler** (`has_official=False` in the scorer). The Zscaler half
is therefore a **best-effort mapping against the real OCSF 1.8.0 schema** (every
target validated), recorded field-by-field in `mapping.py` with rationale and
labelled best-effort — like the firewalls, Umbrella, and CrowdStrike.

This is a deliberate, honest gap, not an oversight: Zscaler is the one *other* source
(besides Okta) with a real shipped OCSF mapping, so it is the best candidate to
reproduce the Okta "a typed OCSF home exists vs the shipped mapper carries it"
implementation-gap finding. Adding that per-field `official` flag — by dumping an
actual OCSF NSS feed or obtaining Zscaler's Security Lake field mapping — is the one
concrete follow-up flagged for this source. Note also the **OCSF-version mismatch**:
Zscaler's shipped mapping targets v1.5.0 while this benchmark validates against
v1.8.0, which is itself worth recording.

## Scope and honesty notes

- Scored against **HTTP Activity (4002)** only. ZIA DNS, Firewall, Admin-audit, and
  the SaaS/DLP-specific logs are separate feeds routing to other OCSF classes and are
  out of scope for this cut.
- The NSS web-log feed is customizable; the scored set is the documented **standard**
  field set, not a maximal feed. A site that adds fields would have a different
  denominator.
- The shape of the result: the HTTP transaction itself (URL, host, method, status,
  request/response sizes, user agent, referer, client/server IP, user) maps well into
  HTTP Activity, while Zscaler's classification value-add — the URL category/class/
  super-category hierarchy, the cloud-app (CASB) class, the malware-category taxonomy,
  the file-type taxonomy, the DLP dictionaries/engine, and the egress public IP — is
  where the coverage is lost. Coverage is over the scoped web-log field set, not all
  ZIA telemetry.

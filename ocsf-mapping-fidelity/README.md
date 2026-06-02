# C1 — OCSF field-mapping fidelity

How completely and how losslessly do real vendor schemas map **into** OCSF 1.8.0?
This benchmark scores six sources field-by-field, across four OCSF classes, against
the real OCSF 1.8.0 schema, and records exactly where each source field lands a typed
attribute, where it crosses a boundary, and where it has no home but `unmapped`:

- **Okta** System Log → Authentication (3002)
- **CrowdStrike** Detection Summary Event → Detection Finding (2004)
- **Palo Alto** PAN-OS TRAFFIC log → Network Activity (4001)
- **Cisco ASA** connection-event syslog → Network Activity (4001)
- **Cisco Umbrella** DNS log → DNS Activity (4003)
- **Zscaler** ZIA Web log → HTTP Activity (4002)

> Evidence tier **B**: a first-party mapping judgement against real *documented*
> vendor schemas and the real OCSF schema. It is not production telemetry, and the
> mapping is a reviewable judgement (every field's rationale is in `mapping.py`),
> not a vendor-certified crosswalk.

## Result

| source | OCSF class | fields | typed | coerced | unmapped | coverage | lossy |
|---|---|--:|--:|--:|--:|--:|--:|
| Okta | Authentication (3002) | 50 | 29 | 7 | 14 | 58% | 42% |
| CrowdStrike | Detection Finding (2004) | 43 | 30 | 9 | 4 | 70% | 30% |
| Palo Alto | Network Activity (4001) | 83 | 46 | 8 | 29 | 55% | 45% |
| Cisco ASA | Network Activity (4001) | 26 | 16 | 3 | 7 | 62% | 38% |
| Cisco Umbrella | DNS Activity (4003) | 13 | 6 | 2 | 5 | 46% | 54% |
| Zscaler | HTTP Activity (4002) | 36 | 21 | 4 | 11 | 58% | 42% |
| **total** | 4 classes | **251** | **148** | **33** | **70** | **59%** | **41%** |

- **`coverage`** = fields landing on a typed OCSF attribute, semantics preserved.
- **`coerced`** = a typed home exists but a boundary is crossed (an enum narrows, an
  array collapses to a scalar, an id/label is lost). Counts as lossy.
- **`unmapped`** = no typed home; only `unmapped`/`raw_data` can carry it.

Two findings, not one:

1. **The schema gap.** Even mapping into the classes purpose-built for these events,
   roughly 40% of the 251 documented fields either coerce or have no typed OCSF home,
   and the losses are not random — they cluster on a handful of recurring categories
   (see METHODOLOGY). Coverage runs from 46% (Umbrella DNS) to 70% (CrowdStrike); the
   variance is itself informative — a DNS resolver log loses most of its value-add
   into OCSF, a detection-finding maps cleanly.

2. **The implementation gap (Okta).** OCSF 1.8.0 has a typed-or-coercible home for 36
   of 50 Okta fields, but Okta's own shipped reference mapper (`okta/okta-ocsf-syslog`)
   carries only **18** of 50 into the event. Eighteen fields have an OCSF home the
   integration leaves on the floor. Okta remains the only source here with a publicly
   *retrievable* field-level shipped mapper; **Zscaler** publishes an official ZIA→OCSF
   mapping for AWS Security Lake (Web → HTTP Activity 4002, OCSF v1.5.0) but its
   field-level carry list is not publicly retrievable, so its implementation gap is
   flagged as a follow-up rather than fabricated (see `schemas/zscaler/PROVENANCE.md`).
   That asymmetry — most vendors do not publish a retrievable field-level OCSF mapping —
   is itself a result.

**New seams the network / DNS / proxy sources surface.** The firewall, DNS, and proxy
sources add categories the first two did not, the strongest being **pre/post-NAT
collapse**: OCSF Network / DNS / HTTP Activity model one address per role, so the
translated or egress address (Palo Alto `natsrc`/`natdst`, ASA `mapped_*`, Umbrella
`external_ip`, Zscaler `clientpublicip`) has no second-address home — surfaced by all
four new sources. Also recurring: **App-ID / cloud-app (CASB) taxonomy**, **URL /
content-category taxonomy**, and **device-ID / identity taxonomy**, none of which OCSF
has typed attributes for. Detail in METHODOLOGY.

**Detections:** of 31 named detections, 23 lose at least one field they depend on;
8 survive clean. The full breakdown is in `results/RESULTS.md`.

## Why it can't fake a number

- Every OCSF target a mapping points at is validated against
  `schemas/ocsf/ocsf_1.8.0_subset.json` (transcribed from the version-pinned schema
  server: the Authentication, Detection Finding, Network Activity, DNS Activity, and
  HTTP Activity classes plus the objects they reference). A mapping to an attribute
  that does not exist in OCSF 1.8.0 fails the run, so coverage can't be inflated by
  inventing a home for a field.
- The inputs are static checked-in files, so the score is a pure function of them.
  `run.py` computes it twice and asserts the two are byte-identical before writing.
- The mapping is not a black box: `mapping.py` carries one record per source field
  with its status and the rationale, and `results.json` carries the resolved per-field
  result. Disagree with a call? It's one line to find and argue with.

## Honest scope

- **Okta** = the documented System Log LogEvent (the login family Okta's own mapper
  targets); account-admin → Account Change (3001), API → API Activity (6003), out of scope.
- **CrowdStrike** = the publicly-reproduced **Detection Summary Event**, *not* the
  gated full Falcon Data Replicator schema. CrowdStrike publishes no field-level OCSF
  mapping, so its half is best-effort against the real schema and labelled as such.
- **Palo Alto** = the **core NGFW traffic-session record** of the PAN-OS TRAFFIC log;
  five license/platform-gated field families (SD-WAN, 5G/SCTP, CN-Series/Kubernetes,
  GlobalProtect, AI-security) are excluded with stated counts, not silently dropped.
- **Cisco ASA** = the **connection-event message family** (Built/Teardown/Deny across
  TCP/UDP/ICMP/SCTP); ASA's VPN, AAA, and system messages route elsewhere.
- **Cisco Umbrella** = the documented v3+ **DNS-log** column set; the Proxy / Cloud
  Firewall / IP logs are separate types routing to other classes.
- **Zscaler** = the documented standard **Web-log** field set of the NSS feed; ZIA
  DNS / Firewall / Admin-audit feeds route to other classes.
- All four new sources are **best-effort** against the real OCSF 1.8.0 schema (every
  target validated), labelled as such — no vendor field-level crosswalk to anchor them
  on. Per-source provenance (authoritative source + ≥2 independent mirrors) is in each
  `schemas/<source>/PROVENANCE.md`.

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
schemas/palo_alto/   PAN-OS TRAFFIC inventory + provenance
schemas/cisco_asa/   Cisco ASA connection-event inventory + provenance
schemas/cisco_umbrella/ Cisco Umbrella DNS-log inventory + provenance
schemas/zscaler/     Zscaler ZIA Web-log inventory + provenance
results/             results.json + RESULTS.md (generated)
```

## Reproduce

```bash
cd ..                                   # repo root
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt         # only the stdlib + duckdb/chdb shared pins; C1 itself is pure-stdlib
cd ocsf-mapping-fidelity && python run.py
```

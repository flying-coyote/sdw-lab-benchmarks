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

*(corrected 2026-11-17: the table above is what `run.py` computes against the transcribed 1.8.0 subset, and it re-derives exactly from `results/results.json` (251 fields, 148 typed, 33 coerced, 70 unmapped, 58.96%). A later pre-registered re-score on a strict validator built from the full, profiles-applied OCSF 1.8.0 export, in [`../ocsf-1.9-rescore/RESULTS.md`](../ocsf-1.9-rescore/RESULTS.md) section (b), found two PAN-OS targets that do not exist in 1.8.0 (`src_model` and `dst_model` to `*_endpoint.hw_info.model`, because `device_hw_info` has no `model` attribute) and one deprecated target (Zscaler `respcode` to `http_status`, deprecated since 1.1.0). Under that validator the total is 146 typed, 33 coerced and 72 unmapped, coverage 58.17% and lossy 41.83%, and Palo Alto moves from 46 / 8 / 29 (55%) to 44 / 8 / 31 (53.01%); the other five sources do not move. `mapping.py` has not been changed, so a re-run still prints the table above, and the replacement each record would need is listed in `../ocsf-1.9-rescore/results/proposed-mapping-changes.md`.)* *(Added 2026-11-22: under the no-profile 1.8.0 export the same corpus scores 133 typed, 26 coerced and 92 unmapped, coverage 52.99%, with 22 invalid targets (`../ocsf-1.9-rescore/results/six-source-strict.json`, `1.8.0.noprofile`), which that RESULTS file's section (b) also discloses.)*

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

**New loss categories the network / DNS / proxy sources surface.** The firewall, DNS, and proxy
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
  inventing a home for a field. *(corrected 2026-11-17: this holds only as far as the
  subset was transcribed. The validator accepts a reference to an object the subset does
  not hold as a deeper leaf (the deep-accept rule in `schemas/ocsf/PROVENANCE.md`), and
  that rule let the two non-existent PAN-OS `hw_info.model` paths through; the strict
  re-score in `../ocsf-1.9-rescore/` is the check that caught them.)*
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

## Hypothesis mapping

This bench serves three hypotheses *(IDs recorded 2026-06-10 per the benchmark-alignment audit)*:

- **H-SPEC-INTEGRITY-01** — the promotion instrument: the schema-validated scoring is how a
  mapping claim gets promoted from assertion to measured result.
- **H3-INTEGRATION-03** — the lossiness leg: the coerced/unmapped split quantifies what real
  vendor schemas lose mapping into OCSF 1.8.0.
- **H2-SCHEMA-02** — the scoring instrument: the per-field typed/coerced/unmapped protocol is
  the reusable method for scoring any source→OCSF mapping.

## What would have made it fail

The score is a mapping judgement checked by a validator, so it fails in two ways. A target path
that does not resolve in the schema the validator holds stops the run, and that check is real but
only as complete as the transcribed subset (see the 2026-11-17 correction above, where two invalid
PAN-OS paths passed it). A field whose call a reviewer disputes changes the counts by one, which is
why every field carries its rationale in `mapping.py`. There is no baseline arm, because the result
is a coverage count rather than a comparison, and no second reader has re-graded the 251 calls.

## This mapping as an input to the "22 of 22" figure

The 83-field PAN-OS mapping in `mapping.py` was used outside this repository as the input to a
holdout check that reported "22 of 22" corrupted mappings caught by a reasoner. That figure follows
from how the corruptions were built rather than from anything in this mapping: each corrupted class
was asserted under two members of a set the same check had just declared disjoint, which makes it
unsatisfiable whatever mapping it came from, so the reasoner flags every one by construction (the
same construction is recorded for the 231 of 231 corpus figure in section 2 of
`../ontology-vs-schema-gate/PREREGISTRATION.md`). This bench makes no catch-rate, recall or
detection claim. What it measures is the coverage table above, and the 22 is the number of PAN-OS
fields that check's type rules could test, not a result of this bench.

## Pre-registration

None. The bench was scored from checked-in inputs on 2026-06-02 without a frozen design file. The
later re-score that corrects it, `../ocsf-1.9-rescore/`, is pre-registered (hash verified 2026-11-17).

## Reproduce

```bash
cd ..                                   # repo root
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt         # only the stdlib + duckdb/chdb shared pins; C1 itself is pure-stdlib
cd ocsf-mapping-fidelity && python run.py
```

## Results

- `results/RESULTS.md` and `results/results.json`, generated by `run.py` (the RESULTS frontmatter
  and the dated correction note in it are hand-added and are dropped by a re-run).
- Current strict figures for the same 251 fields: `../ocsf-1.9-rescore/RESULTS.md` section (b) and
  `../ocsf-1.9-rescore/results/six-source-strict.json`.

## Files

```
README.md            this
METHODOLOGY.md       the scoring rules, the recurring loss categories (its section "The recurring seams"), the caveats
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

## Versions and pins

The scorer is standard-library Python and imports only `../lib/common.py` (which pulls `duckdb`
from the root `requirements.txt`, pinned at `duckdb==1.5.3`). The OCSF target is the 1.8.0 subset
transcribed in `schemas/ocsf/`, with provenance in `schemas/ocsf/PROVENANCE.md`. The Python and schema inputs are pinned; vendor inventories are fixed by the dated documentation snapshots
in each `schemas/<source>/PROVENANCE.md` (softened 2026-11-22 from "Nothing here is unpinned").

## Evidence tier and limits

Tier B, as stated at the top: one author's mapping judgement against documented field sets and the
real schema, with no second reader and no production telemetry. Coverage is over each source's
scoped field set, not the vendor's whole telemetry.

## Corrections

- 2026-11-17: strict 1.8.0 re-score (146 typed / 58.17%, PAN-OS 53.01%) added beside the subset
  table; the "invented attribute fails the run" claim qualified by the deep-accept rule; the
  detection count in `results/RESULTS.md` corrected from "Two" to 8 of 31 and `run.py` changed to
  compute it; the "22 of 22" section added; one heading reworded.

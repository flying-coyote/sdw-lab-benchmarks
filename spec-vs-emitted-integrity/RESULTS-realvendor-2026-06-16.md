---
type: evidence
title: "Spec-vs-Emitted Integrity Results on Three Named Real Vendors: PAN-OS, Zeek, CloudTrail (2026-06-16)"
created: 2026-06-16
tags: [spec-integrity, pan-os, zeek, cloudtrail, silent-corruption, positional-format]
---

# Spec-vs-emitted integrity — the mechanism, grounded on 3 named real vendors (2026-06-16)

SPEC-INTEGRITY, the leg the 2026-06-15 mechanism run (`RESULTS-2026-06-15.md`) left owed: move the
silent-cascade finding **off the synthetic n=1 onto real vendor formats**. This run uses the **real published
field specs** (fetched verbatim from the vendor docs, high-confidence; source URLs in
`realvendor_spec_vs_emitted.py`) for **PAN-OS TRAFFIC**, **Zeek conn.log**, and **AWS CloudTrail**, applies
each vendor's **real documented cross-version schema change** under a spec-faithful parser pinned to the OLD
version, and scores silent-vs-loud by format class. Tier B/C, pure code diff, no LLM, no real telemetry
(public vendor-doc specs only — cleared 2026-06-16; the code-only diff means the injection boundary doesn't bind).

## Result — only the positional format cascades silently

| vendor | format class | mid-record version change | tail-append change |
|---|---|---|---|
| **PAN-OS TRAFFIC** | positional-delimited | **35 of 47 fields SILENTLY wrong** (cascade from the Source-User position), 0 loud | 0 silent, **1 field silently undelivered** (never read) |
| **Zeek conn.log** | self-describing (`#fields` header) | **0 silent** — new column announced by name | 0 silent, new field visible |
| **AWS CloudTrail** | self-describing (JSON) | **0 silent** — new field is a named key | 0 silent, new key visible |

The real cross-version changes each vendor actually made: PAN-OS grew the TRAFFIC record across 8.x → 10.1/11.0
(and the PR-294 src_user-area shift is the documented mid-record case); Zeek 7.1.0 added the `ip_proto` column;
CloudTrail's record contents are additive across `eventVersion` (requestID/eventID in 1.01, vpcEndpointId 1.04,
tlsDetails later). Replaying those change *shapes* against the real specs: the positional format turns a single
mid-record version change into a **74% (35/47) silent corruption** of the record, while the two self-describing
formats localize every change to a visible/announced field (0 silent).

## What it says

The silent-cascade failure is a **property of the positional format class**, now demonstrated on the real
field specs of three named vendors rather than one synthetic schema. A spec-faithful parser pinned to a PAN-OS
version reads 35 of 47 fields to wrong-but-present values with nothing firing the moment a mid-record field
moves between releases — exactly the PR-294 mechanism, on the real 47-field spec. Zeek's `#fields` header and
CloudTrail's JSON keys make the *same* kind of cross-version change self-announcing. So a SOC's exposure to
silent spec-vs-emitted corruption is decided by **which of its real sources are positional** — PAN-OS-class
syslog CSV is exposed; Zeek/TSV-with-header and JSON sources are not.

## What this is NOT (honest scope)

- **Existence / format-class, NOT a prevalence rate.** This shows the mechanism is real on three named vendor
  formats and quantifies the blast radius on PAN-OS's real spec; it does **not** measure how often vendors
  actually ship spec-vs-emitted disagreements in production (that needs a real-log corpus, which the boundary
  keeps out of scope). Public vendor docs are internally consistent (sample matches spec), so no *new*
  disagreement is discovered here — the documented cross-version changes are replayed deterministically.
- The PAN-OS positional outcome is close to definitional (position = contract → a shift cascades); the
  empirical content is the real specs, the real documented changes that trigger/avoid it, and the 35/47
  magnitude on a real record.
- One change instance per vendor per shape; the cascade size scales with how early the change sits (PR-294 at
  the Source-User position = field 13, hence 35 downstream).

## What it does to the hypothesis

Grounds H-SPEC-INTEGRITY-01's **mechanism** off the synthetic n=1 onto **three named real vendor formats** +
their real documented schema evolution — the "off n=1" the hypothesis needed. **HOLD 3.0/5** (no magnitude
move): this strengthens the structural-mechanism leg, but the **real-vendor prevalence-rate** gate (a measured
disagreement rate over a real-log corpus) remains owed and is boundary-constrained. Route through karen →
hypothesis-validator → contradiction-detector; expected disposition HOLD-with-attach.

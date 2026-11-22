# Spec-vs-emitted integrity

When a vendor's published field spec disagrees with what the product actually emits, a parser written
faithfully to the spec inherits the disagreement. This bench asks what that does by format class, and
the answer it supports is that in a positional format one disagreement shifts every field after it into
a wrong-but-present value with nothing firing, while self-describing formats (key-value, JSON, a TSV with
a `#fields` header) fail loudly on the one field that changed. It is the lab's evidence leg for
H-SPEC-INTEGRITY-01, anchored on the PAN-OS field-shift case behind
[PaloAltoNetworks/Splunk-Apps PR #294](https://github.com/PaloAltoNetworks/Splunk-Apps/pull/294), a pull
request to the Palo Alto Networks Splunk app (link added 2026-11-22; the same URL is cited in
`../ocsf-mapping-fidelity/schemas/palo_alto/PROVENANCE.md`).

## What it measures

Three legs, each a separate dated file:

- **Synthetic mechanism (2026-06-15).** A 12-field PAN-OS-shaped schema, 5,000 records per case, with
  the spec and the divergence both authored by the bench: field omission, type drift and tail-append in
  positional CSV, key rename and omission in key-value pairs, key rename in JSON.
- **Real vendor specs replayed (2026-06-16).** The published field specs of PAN-OS TRAFFIC (47 fields),
  Zeek `conn.log` and AWS CloudTrail, with each vendor's documented cross-version change applied under a
  parser pinned to the older version.
- **Real emitted logs (2026-06-16).** 12,000 real lines from six LogHub 2,000-line samples (Linux, OpenSSH,
  Apache, HDFS, Zookeeper, Proxifier), parsed against each format's published grammar.

## Result

- Synthetic: omitting one mid-record field leaves 5.0 of 12 fields silently wrong per record and 1 loudly
  missing; omission in key-value pairs, or a key rename in key-value or JSON, gives 0 silent and 1 loud
  (`results/spec_vs_emitted.json`).
- Real specs: the PAN-OS mid-record change leaves 35 of 47 fields silently wrong, and Zeek and CloudTrail
  0 (`results/realvendor_spec_vs_emitted.json`).
- Real logs: 14.6% of 12,000 lines deviate from the published grammar (862 silent, 891 loud, re-derived
  from `loghub-prevalence/results/loghub_prevalence.json` on 2026-11-17), from 0% on OpenSSH, Apache and
  HDFS to 43.1% on Linux (862 of 2,000 lines, all silent), including all 677 sshd events, which carry the
  program token `sshd(pam_unix)` rather than the documented `sshd`.

The first two legs follow from construction and say so: a shift in a positional record cascades by
definition, and the files describe themselves as showing the mechanism and its size on a real spec, not a
prevalence. The third leg is measured, and its silent-versus-loud split depends on the consumer.

## What would have made it fail

For the first two legs, nothing in the harness could have produced a different shape, since the
divergence is authored and the parser is spec-faithful by design; what could have come out otherwise is
the size of the cascade on the real PAN-OS spec. The LogHub leg could have found 0% deviation everywhere,
and on three of six systems it did. There is no second parser as a baseline, which matters because a
bracket-field parser and a delimiter parser disagree about what counts as a deviation.

## Pre-registration

None.

## Reproduce

```bash
python3 spec-vs-emitted-integrity/spec_vs_emitted.py               # synthetic leg, seed 7
python3 spec-vs-emitted-integrity/realvendor_spec_vs_emitted.py    # real-spec replay, stdlib only
# LogHub leg: fetch the six samples first (loghub-prevalence/FETCH.md), then
python3 spec-vs-emitted-integrity/loghub-prevalence/loghub_prevalence.py
```

All three are standard-library Python. `spec_vs_emitted.py` writes its output to a fixed path under
`~/sdw-lab-benchmarks/`, so it expects the repository at that location.

## Results

- `RESULTS-2026-06-15.md`: synthetic mechanism.
- `RESULTS-realvendor-2026-06-16.md`: real vendor specs replayed.
- `RESULTS-loghub-prevalence-2026-06-16.md`: real emitted logs, the most recent leg and the only measured
  prevalence.
- Machine-readable outputs in `results/` and `loghub-prevalence/results/`.

## Versions and pins

No third-party packages. The LogHub fetch in `loghub-prevalence/FETCH.md` reads from the repository's
`master` branch rather than a commit, so the corpus is pinned only by the per-system `corpus_sha16`
fingerprints recorded in the results JSON; a changed upstream file would show as a fingerprint mismatch.

## Evidence tier and limits

Tier B for the synthetic and LogHub legs and B/C for the real-spec replay, as each file states. The
LogHub logs are OS, infrastructure and application logs, not commercial security-vendor telemetry, and
the deviation rate depends on each deployment's logging configuration. The LogHub file recommends a
hypothesis confidence move; that is an owner decision through the evidence gate and is not applied here.

## Corrections

- 2026-11-17: one first-person phrase recast in `RESULTS-2026-06-15.md`; this README added.

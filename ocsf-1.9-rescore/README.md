# OCSF 1.9.0 re-score

This bench re-scores two earlier lab results against a stricter instrument and then carries them to OCSF
1.9.0. It re-scores the Tenzir Zeek arm of `../pipeline-normalization-fidelity/` under a gold key that
accepts the alternative OCSF homes Tenzir actually used, it runs the six-source mapping corpus of
`../ocsf-mapping-fidelity/` through a validator built from the full 1.8.0 and 1.9.0 schema exports rather
than the transcribed subset, it counts what 1.9.0 deprecates, it tries Tenzir's current release, and it
builds a small Okta identity-lifecycle arm to see what the 1.9.0 IAM class consolidation costs.

## What it measures

- Field, value and activity fidelity of Tenzir's shipped Zeek mapping under the frozen alternates gold
  (`alternates-gold-zeek_conn.json`), on 6.0.0 / library `671e049` and on v6.22.0 / library `9949f753`.
- How many of the 181 typed and coerced C1 mapping targets are invalid or deprecated under a strict
  full-schema validator in 1.8.0 and in 1.9.0, and what that does to the published coverage.
- The 1.9.0 deprecation counts (classes, attribute slots, names), from pinned and hashed exports.
- The cost of moving an Okta `user.lifecycle.create` / `activate` mapping from `account_change` (3001)
  to `user_management` (3007).

## Result

Of 11 pre-registered hypotheses and sub-hypotheses, 8 held and 3 were falsified (H1 on its
reference-mapper percentage, H7 on its field clause, H8b). H1 to H4 are confirmatory, because the
pre-registration lists what was seen before the freeze (`PREREGISTRATION.md` l.15-19): the alternates
gold was written after seeing where Tenzir 6.0.0 put `uid`, `service` and `history`, so Tenzir's field
100% on that gold (against the June 80%) largely follows from how the gold was built, and the strict
1.8.0 validator's 146 typed and 58.17% for the six-source corpus (against the published 148 and 59%)
comes from invalid and deprecated targets that a desk check had already found (H2). Accept-set activity at 83.30% (against the June 17%)
was likewise predictable, since the `conn_state` by `activity_id` cross-tab had been seen (l.17). The blind, informative results are H5, H7, H8b, H8c and H9
(`RESULTS.md` deviation 8). One more hypothesis, H8a, follows from construction (the class move alone
changes three decisions, which meets its threshold), and both the pre-registration and `RESULTS.md` say
so. Full table in `RESULTS.md`.

## What would have made it fail

Each hypothesis carries a frozen falsifier in `PREREGISTRATION.md`, and three of them fired. Two gates
guard the scorer: G1 checks that the June scorer reproduces its own June numbers on the saved output, and
G2 checks that a reference event built from the new gold scores 1.0 on every metric. The 83.30% activity
figure rests entirely on rejecting Tenzir's Open for Zeek S0, and accepting it (post-hoc, not scored)
would make it 100%.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent at 2026-11-15T20:02:50Z (`.frozen`), not owner-reviewed. Its sha256
`938eb121…589a5844` and the alternates gold's `8eda2514…2390e5` both verify against
`results/PREREG.sha256` (checked 2026-11-17). On in-file evidence the freeze precedes the Tenzir
walk-back, which `results/tenzir-v6.22.0-walkback.txt` stamps as starting at 20:08:57Z; the order of the
other scripts' first scored runs is not stamped in the files, and the pre-registration and the results
entered version control in the same commit (`aa918db`), so commit order cannot confirm the freeze either;
it rests on the hash file and the file times in `VERIFICATION.md` (reworded 2026-11-22).
Deviations are listed in `RESULTS.md` and one more was added after verification (G1 ran the imported June
scorer).

## Reproduce

Run from inside `ocsf-1.9-rescore/` (the verification found that path strings in `emitted-paths-*.json`
differ otherwise). The command list is at the end of `RESULTS.md`, with the missing commands named in its
verification corrections. The six-source, deprecation and IAM steps need only the checked-in exports
under `schemas/` and run under system Python with `-I`. The Zeek re-score needs the regenerated
`../pipeline-normalization-fidelity/_work/` corpus and the saved Tenzir output, and the Tenzir arm needs
Docker with the pinned image and the extracted library tarball.

## Results

- `RESULTS.md`: the entry point, with the verification corrections of 2026-11-15 and the quality-pass
  notes of 2026-11-17 at the end.
- `VERIFICATION.md`: the independent verification (VERIFIED-WITH-FIXES).
- `results/`: per-step JSON and stdout captures; `six-source-strict.json` is the strict corpus re-score
  and `proposed-mapping-changes.md` lists the `mapping.py` records that would need to change (not applied).
- `LEDGER-ROW.md`: the summary row written for the hub ledger.

## Versions and pins

OCSF 1.8.0 and 1.9.0 exports from schema.ocsf.io, checked in under `schemas/` and hashed in the
pre-registration. Tenzir `tenzir/tenzir:v6.22.0` pinned by digest `sha256:bf8067a1…9e20` and library
`9949f753`; the June arm is Tenzir 6.0.0 / library `671e049`, which the June status file records as
pulled through `tenzir/tenzir:latest` and identified with `version()`. Python is system 3.12 for most
scripts and the lab `.venv` (root `requirements.txt`) for the two that import `score.py`.

## Evidence tier and limits

No tier is stated in the folder; the evidence is single host, synthetic seeded corpus for the Zeek arm, documented field sets for the six-source
corpus, two Okta event types for the IAM arm. Agent-run and agent-frozen, independently verified, not
owner-reviewed. The Sysmon shaping judgement in section (d) is disclosed and unscored as fidelity.

## Corrections

- 2026-11-15: verification corrections, listed at the end of `RESULTS.md`.
- 2026-11-17: H8a's by-construction status stated in `RESULTS.md`; first-person narration recast; this
  README added.
- 2026-11-22: the 2026-11-17 audit had written `tier: B`, though no file in the folder stated a tier, so the
  index now reads `not stated` (a Tier B proposal is for the owner), and `claim_kind` and `verdict` now read
  `mixed` and `CAVEAT` to match the Result section (H1 to H4 confirmatory and H8a by construction).
- 2026-11-17 (review): the Result no longer calls the headline numbers measured rather than constructed;
  it says H1 to H4 are confirmatory and names the blind hypotheses.

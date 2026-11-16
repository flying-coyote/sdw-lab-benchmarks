---
type: benchmark-results
title: "R5 H5 results: real published releases as non-authored drift"
created: 2026-11-16
evidence_tier: B (first-party, single host, agent-run; post-hoc relative to the H4 results, see below)
---

# R5 H5: the real-release arm (run 2026-11-16)

**What this is.** The arm `RESULTS.md` lists as "H5 real releases: not run". The versions, the five rules, the
detector functions and the metric are the ones frozen in `PREREGISTRATION.md` (sha256 `d88271c0…a2dcc1`,
2026-11-09T22:59:06Z, agent-frozen, not owner-reviewed). Two things are post-hoc and stated as such: the arm ran a
week after the H4 results were known, and the release-diff driver (`release_arm_2026_11_16.py`) was written after
them. The driver adds no detection logic; it calls the frozen `detect.diff` and runs the frozen rule files through
path (a) using `sigma_run.build`/`backend` unchanged. No tracked file was modified.

**Run.** 2026-11-16T13:02:10Z–13:02:45Z, `.venv/bin/python -I snapshot.py release` (unmodified), then
`.venv/bin/python -I release_arm_2026_11_16.py`. Same host as R5 (Beelink, Ryzen 7 5800H, WSL2 6.6.87.2), Python
3.12.3, Node v22.23.4, `.venv` recreated with pySigma 1.5.1 + `pySigma-backend-duckdb` 0.1.4 + DuckDB 1.5.3 (the
three direct pins from `requirements.txt`; transitive dependencies floated, full set in
`requirements-release-arm-2026-11-16.txt`). `chronyc tracking` System time 0.80 s slow at start (no timings are reported from this
arm, so the offset does not bear on any number below). Agent-run; not independently re-run yet.

**Files (new):** `release_arm_2026_11_16.py`, `snapshots/release.json`, `snapshots/release-log.json`,
`events/release-events-D0-2026-11-16.jsonl`, `events/release-events-D1-2026-11-16.jsonl`,
`results/release-arm-2026-11-16.json`, `requirements-release-arm-2026-11-16.txt` (pip freeze of `.venv`), this file. The per-version `snapshots/rel-*.stderr.log` files are gitignored.

## Coverage

All 13 pre-registered versions started on the first attempt (`release-log.json` `failures: {}`), so the arm has its
full 11 transitions: 6 for `server-filesystem` (2025.8.21 → 2025.11.25 → 2025.12.18 → 2026.1.14 → 2026.7.4 →
2026.7.10 → 2026.8.31) and 5 for `server-everything` (2025.12.18 → 2026.1.14 → 2026.1.26 → 2026.7.4 → 2026.8.18 →
2026.8.31). Every version negotiated protocol 2025-06-18. npm printed a deprecation notice on `server-everything`
2025.12.18 saying date-based versions are no longer published and the package has resumed semantic versioning at
1.0.0; the pinned date versions still installed and ran.

## Headline

The suspicious composite (S3 ∨ S4 ∨ S5) fired on **1 of 11** real release transitions, so H5 as pre-registered
("fires on zero transitions") is **wrong**, which is the outcome the pre-registration said it expected for S4/S5.
The one firing was S4 on `filesystem/read_media_file` at 2026.7.4 → 2026.7.10, description similarity **0.494**
against the 0.5 threshold. The change it caught is a real capability change written by the maintainers: the
description went from "Read an image or audio file. Returns the base64 encoded data and MIME type." to "Read a file
and return it as a base64-encoded content block with its MIME type. Image and audio files are returned as image/audio
content; any other file type is returned as an embedded resource.", and the output schema gained an embedded-resource
branch. Under the pre-registration every release counts as benign, so this is a false positive by definition; a
reviewer might well want to see it, since the description now says any file type is returned (the 2026.7.4 output
schema already allowed a `blob` type, so the manifest shows the documented contract changing, not whether behaviour
did), but that is a reading, not a measured result.

## Per rule, canonical hashing (D1)

| Rule | Transitions fired (of 11) | Events matched (of 65) |
|---|---|---|
| S1 any drift | 6 | 65 |
| S2 contract drift | 4 | 25 |
| S3 hidden-instruction markers | 0 | 0 |
| S4 description similarity < 0.5 | 1 | 1 |
| S5 schema widened | 0 | 0 |
| Composite S3 ∨ S4 ∨ S5 | 1 | 1 |

Source: `results/release-arm-2026-11-16.json` (`summary_D1`, `per_transition.D1`). S1 fired on every changed tool
on every transition, as pre-registered. Five of the 11 transitions emitted no event at all, and their full canonical tool JSON was identical before and after (filesystem 2025.11.25 →
2025.12.18, 2025.12.18 → 2026.1.14, 2026.7.10 → 2026.8.31; everything 2026.7.4 → 2026.8.18, 2026.8.18 → 2026.8.31).
The 65 events are 12 tool additions, 10 removals and 43 updates. Raw hashing (D0) gave the same per-transition event
counts, so no release changed key order on an otherwise unchanged tool.

## What changed, per transition with events

| Transition | Events | What moved (canonical fingerprints) | S2 | Composite |
|---|---|---|---|---|
| filesystem 2025.8.21 → 2025.11.25 | 14 | all 14 input schemas changed (13 went from a bare `$schema` to full properties) and all 14 gained annotations (`readOnlyHint` on 14, `destructiveHint`/`idempotentHint` on 4); 1 also had a description edit (similarity 0.648) | 14 | 0 |
| filesystem 2026.1.14 → 2026.7.4 | 1 | annotations only: `move_file` `destructiveHint` false → true | 0 | 0 |
| filesystem 2026.7.4 → 2026.7.10 | 14 | `openWorldHint` added on all 14, annotation-only on 13; `read_media_file` also changed description and output schema | 1 | 1 (S4, 0.494) |
| everything 2025.12.18 → 2026.1.14 | 22 | camelCase → kebab-case rename: 11 added, 10 removed; `echo` description "Echoes back the input" → "…input string" (0.857) | 1 | 0 |
| everything 2026.1.14 → 2026.1.26 | 1 | 1 tool added (`simulate-research-query`) | 0 | 0 |
| everything 2026.1.26 → 2026.7.4 | 13 | all 13 gained the four annotation hints; 9 of them also dropped `additionalProperties: false` from the input schema | 9 | 0 |

## Findings beyond the pre-registered counts (post-hoc reading, stated as such)

- **S5 missed a real loosening.** On `everything` 2026.1.26 → 2026.7.4, nine tools dropped
  `additionalProperties: false`. In JSON Schema an absent `additionalProperties` permits extra properties, so this
  opens the input schema, but `detect.py:schema_widened` only flags a change from false/absent to true or a schema,
  so false → absent is not counted and S5 stayed silent. That is a fourth unexercised-or-missing branch alongside the
  three listed in `RESULTS.md` Limits. Whether a client enforces either form is a separate question this arm does
  not test.
- **S5 reads only the input schema.** The `read_media_file` change also widened the output schema (an `anyOf` with
  an embedded-resource branch); nothing in the frozen detector compares output schemas beyond the fingerprint.
- **Annotation flips happen in real releases and are visible natively.** `move_file`'s `destructiveHint` went from
  false to true, and `openWorldHint` appeared on 27 tool versions across two transitions (14 filesystem, 13 everything); these move `ai_capability.is_destructive` /
  `is_open_world`, so the new value lands in a native field; telling which way a flag flipped still needs the previous value,
which OCSF has no `prev_` field for and would ride in `unmapped` as S2's fingerprints do. The flip here is toward more caution; the
  rug-pull direction (destructive → not destructive) was still not tested.
- **Most real drift is maintenance.** 13 of the 14 S2 matches on `filesystem` 2025.8.21 → 2025.11.25 are input
  schemas being filled in from a bare `$schema`, and the biggest transition is a tool rename. S1 as a review
  queue would have shown a reviewer 65 entries across 11 releases, 22 of them in one rename.

## Limits

- 11 transitions on two reference servers from one maintainer organization, all on protocol 2025-06-18. This is a
  small sample of benign drift and is not a field false-positive rate; it says the composite is not silent on real
  releases and shows the shape of the one firing.
- Releases are treated as benign by the pre-registration; the one firing is a genuine capability change, which is
  exactly the ambiguity a description-similarity rule cannot resolve.
- Post-hoc as stated above; single host; not yet independently re-run.

## Correction (2026-11-16, after review)

An external review (Fable, 2026-11-16) found, and I reproduced, that the replay did not reconstruct each release as
published. `npx -y <pkg>@<version>` resolves transitive dependencies to their current versions, so on 2026-11-16
every one of the 13 versions ran on `@modelcontextprotocol/sdk` 1.32.2, every `server-filesystem` version ran on
`zod` 4.6.7 with `zod-to-json-schema` 3.25.2, and `server-everything` ran on `zod` 3.25.76 up to 2026.1.26 and
4.6.7 from 2026.7.4 (which declares `zod ^4.0.0` itself). Evidence: the `package.json` files under
`~/.npm/_npx/*/node_modules/` for each version, and `zodToJsonSchema(z.object({path: z.string()}))` run against the
two cached dependency sets, which returns only `{"$schema":"http://json-schema.org/draft-07/schema#"}` under zod
4.6.7 and the full object schema under zod 3.25.76.

Consequences, superseding the earlier text where they conflict:
- The "13 went from a bare `$schema` to full properties" cell for `filesystem` 2025.8.21 → 2025.11.25, and the
  "13 of the 14 S2 matches … are input schemas being filled in" bullet, describe a replay artifact. 2025.8.21
  declares `zod-to-json-schema ^3.23.5` and no `zod`, so under today's zod 4 its schema conversion returns an empty
  schema; the maintainers did not ship 13 empty input schemas. That transition still emits 14 events from changes in
  the package's own code (annotations, titles, output schemas, one description edit at 0.648), but its 14 S2 matches
  cannot be separated from the artifact.
- S2: 25 events across 4 transitions as replayed; 11 across 3 transitions without the 2025.8.21 → 2025.11.25
  transition.
- The composite firing (S4 on `read_media_file`, 0.494) comes from the package's own description string and
  stands. Both descriptions end with " Only works within allowed directories."; without that shared sentence the
  similarity is 0.326. It is one of three description edits in the 65 events (0.494, 0.648, 0.857).
- The `additionalProperties: false` drop on 9 `server-everything` tools coincides with that release moving its own
  declared dependency from zod 3 to zod 4, so it is probably the release's own change, though the SDK that converts
  the schema had also floated to 1.32.2.
- "Every version negotiated 2025-06-18" means each server accepted the 2025-06-18 the snapshotter offered
  (`snapshot.py` `PROTO`); it says nothing about the newest version each server supports.
- A faithful replay would install each version with dependency resolution pinned to its publish date
  (`npm install --before=<date>`); not run.

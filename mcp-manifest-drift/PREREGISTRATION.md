---
type: benchmark-preregistration
title: "R5: MCP tool-manifest drift as a detection (snapshot-and-diff, Sigma over OCSF ai_capability)"
created: 2026-11-09
status: frozen-before-run
review: frozen by agent before run; not owner-reviewed
source: project1/02-projects/securitydataworks/SITE-REVIEW-2026-11-09.md section 5, row R5
---

# Pre-registration: tool-manifest drift as a detection

## Question

When an MCP server's advertised `tools/list` manifest changes between snapshots, can a snapshot-and-diff
detector, expressed as Sigma rules over OCSF events carrying the `ai_capability` object, tell a poisoned
change from a benign one, and which locally available pySigma backends compile and execute those rules
correctly?

## Schema binding (chosen, not standard)

OCSF has no `ai_*` event class on `main` as of the commit read below (the #1754 "AI Agent Activity" draft
is unmerged), so the binding is a choice I am making and it may be superseded:
- Envelope: Application Lifecycle, `class_uid` 6002 (category 6), which carries the `ai_operation` profile
  on `main`. `activity_id` 1 Install = tool newly advertised, 2 Remove = tool no longer advertised,
  8 Update = an advertised tool's contract changed.
- `app` = the MCP server (name, version from `serverInfo`).
- `ai_capability` (merged #1729, 2026-10-07): `name`, `type_id` 1 (Tool), `service.name`,
  `desc_fingerprint`, `input_schema_fingerprint`, `output_schema_fingerprint`, `baseline_fingerprint`,
  `is_readonly`/`is_destructive`/`is_idempotent`/`is_open_world` from MCP annotations where present.
- Sources read: `ocsf/ocsf-schema` `objects/ai_capability.json` at commit
  `6461440105d5a6a219b92150f8895cc88cef842a` (2026-10-07T20:53:57Z); `main` at
  `d1cbd619d76b7e1b8463785cd79beaaf4e3c2bdf`, `version.json` = `1.10.0-dev`.
- Structural fact the design rests on: `ai_capability` carries fingerprints only. Its definition says
  "The object carries no `desc` attribute" and "consumers diff, the object does not assess." There is no
  `prev_*` counterpart for the fingerprints. So the previous fingerprints, the description text delta, a
  similarity score and any schema-widening verdict go in `unmapped.*`, and every rule that reads
  `unmapped.*` is labelled "needs the body / producer-computed", as opposed to "OCSF-expressible".

## Hypotheses and what would prove each wrong

- **H1 (coverage).** Each of the three poisoned changes alters at least one `ai_capability` fingerprint,
  so an OCSF-expressible "contract changed" rule fires on 3 of 3 categories on every server.
  Wrong if any poisoned change leaves all fingerprints equal under canonical hashing.
- **H2 (OCSF-native cannot discriminate).** A rule restricted to OCSF-native `ai_capability` fields cannot
  separate the hidden-instruction poisoning from benign description edits, because both move only
  `desc_fingerprint`; its benign false-positive count on description edits equals the number of benign
  description edits. Wrong if some OCSF-native field (annotations, type, version, cache fields) carries
  information that separates them in this corpus.
- **H3 (canonicalization).** A raw `json.dumps` hash fires on the pure key-reorder benign update (B5) and
  a canonical hash (sorted keys, compact separators, JCS-like) does not. Wrong if both behave the same.
- **H4 (body-aware rules).** The body-aware rules (S3 hidden-instruction markers, S4 description similarity,
  S5 producer-computed schema widening) detect 3 of 3 poisoned categories per server with 0 of 5 authored
  benign updates firing. Wrong if any poisoned change is missed or any authored benign update fires. I
  wrote both the poisonings and the rules, so H4 is circular by construction; the real-release arm below is
  the non-authored check.
- **H5 (real releases).** On consecutive published releases of two reference servers (treated as benign),
  S1 fires on every changed tool and the suspicious composite (S3 or S4 or S5) fires on zero transitions.
  Wrong if the composite fires on any real release transition (a false positive on unauthored benign drift)
  — I expect this one may well be wrong for S4/S5 and will report it as found.
- **H6 (backend agreement).** The three compile/execute paths return identical matched-event sets for every
  rule. Wrong if any path refuses a rule, errors at execution, or returns a different set.
- **H0 (null drift).** Repeated snapshots of an unchanged server produce zero fingerprint changes under
  canonical hashing. Wrong if a static server's manifest varies between snapshots (ordering or dynamic text).

## Instrument

- Live servers (S = 3), each started fresh per run as a stdio subprocess, spoken to with a raw JSON-RPC
  client written here (`initialize`, `notifications/initialized`, `tools/list` following `nextCursor`):
  - `scg`: the lab's read-only Security Context Graph server,
    `/tmp/claude-1000/lab-ai-research/security-context-graph/scg_mcp.py`, run unmodified from its own path.
  - `everything`: `@modelcontextprotocol/server-everything@2026.8.31` via `npx -y`, run from an empty dir.
  - `filesystem`: `@modelcontextprotocol/server-filesystem@2026.8.31` via `npx -y`, one empty allowed dir.
- Snapshot schedule: R = 3 runs × K = 6 snapshots per server, 5 s apart (monotonic timer). If a server
  fails to start twice, it is dropped and reported.
- Injection happens at the snapshot layer: the final snapshot of run 1 for each server is the baseline, and
  eight mutated manifests are derived from it. No running server is patched.
- Target tool per server: the first tool by sorted name whose `inputSchema` has at least one string
  property.
- Poisoned mutations (3):
  - **P1 rug-pull**: target description replaced with a plausible but different-behavior text with no
    keyword markers: "Sends the provided content to the configured remote endpoint and returns the delivery
    receipt." Name, schema, annotations unchanged. (A rug-pull that changes only server-side code with an
    unchanged manifest is invisible to this instrument by design; stated as a limit, not tested.)
  - **P2 hidden instruction**: append to the target description the Invariant Labs tool-poisoning pattern,
    paraphrased: a `<IMPORTANT>` block telling the model to read `~/.ssh/id_rsa` and pass it as `sidenote`,
    and not to mention this to the user. Schema unchanged.
  - **P3 parameter widening**: add optional property `sidenote: {"type": "string"}` (no constraints), set
    `additionalProperties: true`, and strip `enum`/`pattern`/`maxLength`/`format` from existing properties
    of the target tool. Description unchanged.
- Benign mutations (5):
  - **B1 wording fix**: replace the first occurrence of " the " with " a " in the target description
    (or append "." if absent).
  - **B2 clarification**: append "Returns an error if the input is invalid." to the target description.
  - **B3 new tool**: add `health_check`, description "Returns server health status.", empty object schema.
  - **B4 schema narrowing (mirror of P3)**: add `maxLength: 4096` to each existing string property of the
    target tool and add a new required boolean property `dry_run`.
  - **B5 key reorder**: reverse the key order inside every tool object and every `inputSchema`, and
    reverse the tools array. No semantic change.
- Real-release arm (non-authored benign drift): `tools/list` from consecutive published versions,
  each run once, `filesystem` 2025.8.21, 2025.11.25, 2025.12.18, 2026.1.14, 2026.7.4, 2026.7.10, 2026.8.31
  (6 transitions) and `everything` 2025.12.18, 2026.1.14, 2026.1.26, 2026.7.4, 2026.8.18, 2026.8.31
  (5 transitions). A version that fails to start is dropped and reported.
- Detector: diff consecutive snapshots per server keyed by tool name; emit one OCSF event per
  added/removed/changed tool. Two hashing variants, D0 raw (`json.dumps` as received) and D1 canonical.
  Rules run over D1 events except the H3 comparison.
- Body-aware producer fields (`unmapped.*`): `prev_desc_fingerprint`, `prev_input_schema_fingerprint`,
  `desc_added_text` (text in new description absent from old, via difflib opcodes), `desc_similarity`
  (difflib `SequenceMatcher.ratio`, rounded 3), `schema_widened` (bool: any new non-required property with
  type string and none of enum/pattern/maxLength/format/const; any removed enum/pattern/maxLength/format
  on an existing property; any property removed from `required`; `additionalProperties` changed from false
  or absent to true or a schema; a property type broadened to include more types).
- Sigma rules (frozen in `rules/` before the run):
  - **S1 any manifest drift (OCSF-native)**: `class_uid` 6002, `activity_id` in 1, 2, 8,
    `ai_capability.type_id` 1.
  - **S2 contract drift on an existing tool (OCSF-native + fieldref on prev)**: `activity_id` 8 and not
    (`ai_capability.desc_fingerprint` fieldref `unmapped.prev_desc_fingerprint` and
    `ai_capability.input_schema_fingerprint` fieldref `unmapped.prev_input_schema_fingerprint`).
  - **S3 hidden instruction (body-aware)**: `unmapped.desc_added_text` contains any of `<IMPORTANT>`,
    `</IMPORTANT>`, `do not mention`, `do not tell`, `ignore previous`, `ignore all previous`, `~/.ssh`,
    `id_rsa`, `.aws/credentials`, `mcp.json`, `.env`, `before using this tool`, `otherwise the tool will not
    work`, or regex `[​-‏⁠﻿]` (zero-width characters).
  - **S4 description rewrite (body-aware)**: `activity_id` 8 and `unmapped.desc_similarity` < 0.5.
  - **S5 schema widening (producer-computed)**: `unmapped.schema_widened` = true.
  - Suspicious composite = S3 or S4 or S5 (computed as the union of the three rule outputs).
- pySigma paths:
  - (a) `pySigma-backend-duckdb` 0.1.4 on pySigma 1.5.1 (its pin is `pysigma<2`), executed on DuckDB 1.5.3.
  - (b) `pySigma-backend-sqlite` 2.1.1 on pySigma 2.0.3, executed on Python `sqlite3` with a Python
    `REGEXP` function registered (sqlite3 ships none).
  - (c) the path (b) SQL executed verbatim on DuckDB 1.5.3 (the generic-SQL path
    `ocsf-sigma-detection/duckdb_execution.py` already uses). If DuckDB rejects SQLite syntax, that is
    recorded as a refusal, not patched.
  - Events are loaded into one flat table `logs` with dotted column names (`"ai_capability.name"`).

## Metrics

- Per rule, per server, per category: fired / not fired. Detection = poisoned events fired / 3 per server,
  9 total. Authored-benign FP = benign mutations fired / 5 per server, 15 total. Null FP = changes detected
  across unchanged snapshot pairs. Real-release FP = transitions where the composite fired / transitions,
  plus per-tool event counts. Counts reported as k of n, not bare percentages.
- Backend agreement per rule: compile status per path, execution status, matched set equality.
- Variance: rule verdicts are deterministic given a manifest, so verdict variance is zero by construction
  and is reported as such; the variance actually measured is (i) manifest stability across R × K snapshots
  (H0) and (ii) snapshot round-trip latency, median and CV over the K × R snapshots per server, for which
  the RESULTS file carries a rig stamp.

## Environment and versions

Beelink, Ryzen 7 5800H, WSL2 (kernel 6.6.87.2-microsoft-standard-WSL2), Python 3.12.3, Node v22.23.4,
DuckDB 1.5.3, `mcp` 1.30.0 (server SDK used only by `scg`), pySigma 1.5.1 / 2.0.3 as above. Guest clock:
chrony, `chronyc tracking` System time 0.000029 s slow at setup (2026-11-09). Timings use
`time.monotonic_ns`. Windows power plan not verified from inside WSL; recorded as unverified.

## Stop rule

One pre-registered pass of each arm. No rule, marker list, threshold or mutation is changed after the first
result is seen; any post-hoc variant is reported separately and labelled exploratory. A server that fails to
start twice is dropped and reported.

## Cost

$0. Local CPU only. Network use is limited to npm and PyPI package downloads. No model calls.

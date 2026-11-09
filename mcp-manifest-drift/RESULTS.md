---
type: benchmark-results
title: "R5 results: MCP tool-manifest drift as a detection"
created: 2026-11-09
evidence_tier: B (first-party, single host, authored mutations; circularity stated below)
---

# R5 results: tool-manifest drift as a detection

**Pre-registration:** `PREREGISTRATION.md` sha256 `d88271c0e8568a726a607b79a0e7a735e760ca9937e62e9cdbefa0fd99a2dcc1`,
frozen 2026-11-09T22:59:06Z together with the five rule files (hashes in `FROZEN.sha256`).
Frozen by agent before run; not owner-reviewed. First server contact: 2026-11-09T22:59:45Z (`COMMANDS.log`).
Independently re-run and checked 2026-11-09 by a second agent; verdict and the wording fixes applied to this file are
in `VERIFICATION.md`.

**Rig stamp (§7b, for the latency section only):** Beelink, Ryzen 7 5800H, WSL2 kernel 6.6.87.2, run 2026-11-09;
Windows power plan not verified from inside WSL; clock chrony, `chronyc tracking` System time 0.000055 s fast
immediately before the run (`clock-pre-run.txt`); timings by `time.monotonic_ns`. Python 3.12.3, Node v22.23.4,
DuckDB 1.5.3, sqlite 3.45.1, `mcp` 1.30.0, pySigma 1.5.1 + `pySigma-backend-duckdb` 0.1.4 (venv `.venv`) and
pySigma 2.0.3 + `pySigma-backend-sqlite` 2.1.1 (venv `.venv-sqlite`). Two venvs because the DuckDB backend pins
`pysigma<2.0.0` while the current SQLite backend needs `pysigma>=2.0.1`, so the two backends cannot share one
environment.

## Servers snapshotted

| Server | `serverInfo` | Protocol returned | Tools | Snapshots |
|---|---|---|---|---|
| `scg` (lab, `security-context-graph/scg_mcp.py`, unmodified) | security-context-graph 1.30.0 | 2025-06-18 | 7 | 3 runs × 6 |
| `everything` (`@modelcontextprotocol/server-everything@2026.8.31`) | mcp-servers/everything 2.0.0 | 2025-06-18 | 13 | 3 runs × 6 |
| `filesystem` (`@modelcontextprotocol/server-filesystem@2026.8.31`) | secure-filesystem-server 0.2.0 | 2025-06-18 | 14 | 3 runs × 6 |

Target tools picked by the pre-registered rule (first by name with a string parameter): `scg/coverage`,
`everything/echo`, `filesystem/create_directory`.

## Headline

A snapshot-and-diff detector finds every poisoned change, but only because it finds every change: the two
change rules, S1 (OCSF-native) and S2 (OCSF fingerprints compared against producer-carried previous values in
`unmapped`), fire on 9 of 9 poisoned mutations and on 12 of 15 (S1) or 9 of 15 (S2) benign ones, and the
reason is structural, since `ai_capability` carries fingerprints and no description text, so a hidden
instruction and a typo fix produce the identical OCSF signal. The body-aware rules, which read producer-computed
fields that have to sit in `unmapped`, separate the two sets completely on this corpus (9 of 9 detected, 0 of 15
benign fired), but I wrote both the poisonings and the rules, and the non-authored check (real release-to-release
drift) did not run, so that 0 of 15 is an upper bound on how good the rules look, not an estimate of their field
false-positive rate.

## Detection and false-positive counts (canonical hashing, D1; identical on paths a and b)

| Rule | Expressible as | P1 rug-pull | P2 hidden instr. | P3 widening | Detected | B1 wording | B2 clarify | B3 new tool | B4 narrowing | B5 reorder | Benign fired |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 any drift | OCSF-native | 3/3 | 3/3 | 3/3 | **9 of 9** | 3/3 | 3/3 | 3/3 | 3/3 | 0/3 | **12 of 15** |
| S2 contract drift (fieldref) | native fingerprints + `unmapped.prev_*` | 3/3 | 3/3 | 3/3 | **9 of 9** | 3/3 | 3/3 | 0/3 | 3/3 | 0/3 | **9 of 15** |
| S3 hidden-instruction markers | body (`unmapped.desc_added_text`) | 0/3 | 3/3 | 0/3 | 3 of 9 | 0 | 0 | 0 | 0 | 0 | 0 of 15 |
| S4 description similarity < 0.5 | body (`unmapped.desc_similarity`) | 3/3 | 1/3 | 0/3 | 4 of 9 | 0 | 0 | 0 | 0 | 0 | 0 of 15 |
| S5 schema widened | producer-computed boolean | 0/3 | 0/3 | 3/3 | 3 of 9 | 0 | 0 | 0 | 0 | 0 | 0 of 15 |
| Composite S3 ∨ S4 ∨ S5 | body + producer | 3/3 | 3/3 | 3/3 | **9 of 9** | 0 | 0 | 0 | 0 | 0 | **0 of 15** |

Each cell counts servers (of 3) where any event from that mutation matched. Source: `results/scores.json`.

## Per hypothesis

- **H0 null drift: held.** 17 consecutive snapshot pairs per server (15 within a run, 2 across process restarts),
  51 in all, emitted 0 events under both raw and canonical hashing. All three servers return a byte-stable manifest
  across restarts, so on this sample a static server produces no drift noise at all.
- **H1 coverage: held.** Every poisoned mutation moved a fingerprint: P1 and P2 moved only `desc_fingerprint`,
  P3 moved only `input_schema_fingerprint` (`events/native_signatures.json`).
- **H2 OCSF-native cannot discriminate: held, and more broadly than stated.** P2 (hidden instruction), B1 and B2 all
  have the native signature `activity_id 8, desc_fingerprint changed`, on all three servers, and P3 (widening) has
  the same native signature as its mirror B4 (narrowing), `input_schema_fingerprint changed`. No mutation
  touched annotations or `type`, and the detector does not populate `ai_capability.version` or the `cache_*`
  fields at all, so nothing native separated poisoned from benign in this corpus; that is partly a property of the
  mutations chosen, not only of the schema. A rule built
  only on OCSF-native `ai_capability` fields is a change-inventory alert, which is useful for review queues but is
  not a poisoning detection. Part of this holds by construction: the pre-registered P1 left annotations unchanged,
  so a rug-pull that also flips `readOnlyHint` or `destructiveHint` would surface natively in `is_readonly` /
  `is_destructive`, and that case was not tested.
- **H3 canonicalization: held.** Under raw `json.dumps` hashing (D0) the pure key reorder B5 emitted 34 Update
  events (every tool on every server: 7 + 13 + 14) and S1 rose from 12 to 15 of 15 benign; S2 from 9 to 12 of 15.
  Canonical hashing (sorted keys, compact separators) emitted none. The OCSF attribute text already points at
  `serialization_id: JCS`, and this is the concrete reason to follow it.
- **H4 body-aware rules: held on the authored corpus, circular by construction.** 9 of 9 detected, 0 of 15 benign.
  Two things in the numbers suggest the margin is thinner than 0 of 15 makes it look:
  - S4's similarity depends on description length. On `everything/echo` ("Echoes back the input string") the
    benign B2 appended sentence scored 0.571 against a 0.5 threshold, while P2 on the two long descriptions scored
    0.681 and 0.744 and so passed S4 untouched (S3 caught them). A slightly higher threshold, or a benign rewrite of
    a short description, would turn S4 into a false-positive source, and a rug-pull written as a small edit to a
    long description would slip under it.
  - P1 (a rug-pull with no keyword markers) was caught only by S4, so the rug-pull detection rests on one
    length-sensitive heuristic.
- **H5 real releases: not run.** The release arm (13 published versions of `server-filesystem` and
  `server-everything` fetched and started via `npx`) was denied by the session's permission classifier, and I did
  not try to route around it. This is the only arm that would have measured false positives on drift I did not
  write, so the body-aware 0 of 15 should not be quoted as a false-positive rate until it runs. Command to run it:
  `.venv/bin/python -I snapshot.py release && .venv/bin/python -I detect.py` (the release diffing in `detect.py`
  is not yet written; the snapshotter is).
- **H6 backend agreement: partly wrong.**
  - Path (a) DuckDB backend → DuckDB and path (b) SQLite backend → sqlite3 compiled all five rules (including
    `|fieldref`, `|lt` and a zero-width-character `|re`) and returned identical matched sets on every rule, both
    hashing variants.
  - Path (c), SQLite-emitted SQL executed verbatim on DuckDB, compiled 5 of 5 and executed 0 of 5. The SQLite
    backend backtick-quotes dotted OCSF field names (`` `ai_capability.type_id` ``) and DuckDB does not accept
    backtick identifiers (`CatalogException: Scalar Function with name ` = does not exist`). The lab's earlier
    `ocsf-sigma-detection/duckdb_execution.py` used this path successfully on flat, unquoted column names, so the
    generic-SQL path works until the field names look like OCSF. One deviation from "verbatim": on every path
    `sigma_run.py` swaps the projection `SELECT *` for `SELECT` of `metadata.uid` before execution; the path (c)
    error is in the backtick-quoted WHERE clause, not in that projection.
  - Exploratory, post-hoc (`probe_backend_semantics.py`, `results/probe-{a,b}.json`), two latent divergences between
    (a) and (b) that the corpus did not exercise: the DuckDB backend leaves `_` unescaped inside `ILIKE`, so the S3
    value `id_rsa` also matched the text "idXrsa" on path (a) and not on (b); and the DuckDB backend emits a negated
    fieldref without the `COALESCE(..., 0)` the SQLite backend adds, so an Update event with NULL previous
    fingerprints matched S2 on (b) and not on (a). Both are real result differences from the same Sigma rule.

## How much of the detection is actually in Sigma

Honest answer to "can it be a Sigma rule over OCSF": the alerting can, the discrimination mostly cannot.
- S1 and S2 are pure Sigma over OCSF fields (S2 needs previous fingerprints in `unmapped` because OCSF has no
  `prev_` counterpart), and they are the rules that cannot tell poison from maintenance.
- S3 is a Sigma keyword match, but over a description delta that the producer computed and that OCSF has no place
  for, since `ai_capability` deliberately carries no description body.
- S4 and S5 are Sigma comparisons over a similarity score and a widening verdict that the producer computed.
  The detection logic for widening lives in `detect.py:schema_widened`, not in the rule.

So the shape that works on this corpus is a stateful differ that emits OCSF Update events plus a few `unmapped`
analysis fields, with Sigma as the alert layer. The OCSF `ai_capability` text says as much ("consumers diff, the
object does not assess").

## Snapshot latency (variance)

`tools/list` round trip after `initialize`, 18 snapshots per server (3 fresh processes × 6):

| Server | Median ms | CV | Min–max ms | Per-run medians ms | `initialize` ms per run |
|---|---|---|---|---|---|
| `scg` | 2.04 | 139.6% | 1.35–20.5 | 1.53, 2.12, 2.14 | 530, 923, 798 |
| `everything` | 3.44 | 85.9% | 1.87–22.2 | 4.51, 6.89, 2.50 | 5517, 1023, 1540 |
| `filesystem` | 7.65 | 65.2% | 2.78–24.2 | 6.85, 7.93, 7.84 | 8988, 1239, 1521 |

The CVs are high because single snapshots spike to around 20 ms; medians are a few milliseconds, so snapshotting
cost is negligible at any plausible interval. Run-1 `initialize` for the npm servers includes the `npx` package
fetch. These are not comparative claims, so no ratio is drawn from them. Rule verdicts are deterministic given a
manifest, so verdict variance is zero by construction; the measured run-to-run variance in the manifests themselves
is also zero (H0).

Verifier re-run (second session, 2026-11-09T23:10:46Z–23:14:49Z, same host, `chronyc` System time 17 µs fast, npm
packages already cached): medians 2.26 / 5.36 / 9.52 ms (`scg` / `everything` / `filesystem`), CV 124% / 108% / 61%,
max 26.3 / 36.7 / 23.1 ms, per-run medians ranging 1.6–6.4 / 3.7–5.8 / 4.9–13.9 ms. So the medians above reproduce
only to "a few milliseconds", not to the second digit, which is what the CVs predict. The full `tools` list from all
54 re-run snapshots was byte-identical to the original run's, within and across sessions.

## Limits

- Mutations and rules are both mine (H4 circularity); n is 3 poisoned and 5 benign kinds over 3 servers.
- The non-authored benign arm (H5) did not run, so there is no field false-positive estimate.
- A rug-pull that changes server code but not the manifest is invisible to any manifest differ.
- One snapshot cadence (5 s), static servers; servers whose manifests legitimately change at runtime
  (`notifications/tools/list_changed`) were not tested.
- The OCSF binding (Application Lifecycle 6002 + `ai_operation` profile) is my choice on `main` 1.10.0-dev; the
  #1754 draft class may supersede it.
- `schema_widened` was only partly exercised: none of the three target tools carried `enum`, `pattern`,
  `maxLength` or `format`, so P3 fired through two branches only (new unconstrained optional string,
  `additionalProperties` opened). The constraint-removed, required-removed and type-broadened branches never ran.
- Single host, Tier B for method.

## Files

`PREREGISTRATION.md`, `FROZEN.sha256`, `rules/*.yml`, `snapshot.py`, `detect.py`, `sigma_run.py`, `score.py`,
`probe_backend_semantics.py` (exploratory; `sigma_run.py` got a behavior-preserving default-argv edit after the
recorded runs so the probe could import it, identical when an argument is passed), `snapshots/live.json` (+ stderr logs, `live-log.json`),
`events/events-D0.jsonl`, `events/events-D1.jsonl`, `events/labels.json`, `events/null_drift.json`,
`events/native_signatures.json`, `results/sigma-path-{a,b,c}.json`, `results/scores.json`,
`results/probe-{a,b}.json`, `COMMANDS.log`, `clock-pre-run.txt`, `requirements.txt`, `requirements-sqlite.txt`.

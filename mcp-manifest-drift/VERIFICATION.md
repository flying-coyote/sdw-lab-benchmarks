---
type: benchmark-verification
title: "R5 verification: MCP tool-manifest drift"
created: 2026-11-09
verdict: VERIFIED-WITH-FIXES
---

# R5 verification: tool-manifest drift as a detection

**Verdict: VERIFIED-WITH-FIXES.** Every count in `RESULTS.md` reproduced exactly from a re-run of the full analysis
pipeline, and an independent second live snapshot session returned byte-identical manifests. The fixes were to
wording where a claim ran slightly past the evidence, plus one missing limit; no number changed.

## What was checked and how

1. **Pre-registration timing and hash.** `sha256sum PREREGISTRATION.md` = `d88271c0…a2dcc1`, matching `FROZEN.sha256`
   and `RESULTS.md`. File mtime 22:58:48Z, freeze stamp 22:59:06Z, first server contact 22:59:45Z (`COMMANDS.log`,
   `snapshots/live-log.json`). The five rule files also match their frozen hashes and carry the 22:59:06Z mtime.
   Pre-registration was written before the run.
2. **Script timeline (noted, not a deviation).** `snapshot.py` was last modified at 22:59:33Z (after freeze, before
   first contact). `detect.py` (23:05:05Z) and `score.py` (23:05:56Z) were last modified after the live snapshots
   finished (23:03:53Z), so the mutation code was finalised after the manifests were seen. I checked each mutation,
   the target-tool rule, the hashing variants and every `schema_widened` branch in `detect.py` against the
   pre-registration text, and they match it. `sigma_run.py` was edited at 23:06:32Z, after the path runs; the edit is
   the disclosed default-argv change, and my re-run with explicit arguments gave identical outputs.
3. **Analysis re-run.** Original `events/` and `results/` backed up, then `detect.py`, `sigma_run.py a|b|c`,
   `score.py` and `probe_backend_semantics.py a|b` re-run in the original venvs. Result: `events/*` (5 files),
   `results/scores.json`, `results/sigma-path-c.json` and `results/probe-{a,b}.json` byte-identical;
   `results/sigma-path-{a,b}.json` identical apart from the per-query `ms` timings.
4. **Every headline count confirmed** from the re-run: S1 9/9 detected, 12/15 benign (D0 15/15); S2 9/9, 9/15
   (D0 12/15); S3 3/9; S4 4/9; S5 3/9; composite 9/9 and 0/15; D0 55 events vs D1 21, so B5 adds 34 (7 + 13 + 14);
   null drift 17 pairs × 3 servers = 51, 0 events in both variants; similarities echo-B2 0.571, P2 on
   filesystem/scg 0.681/0.744 (echo-P2 0.161, caught by S4); paths a and b agree on every rule; path c refused all 5
   at execution with `CatalogException` on the backtick identifiers (SQL inspected: SQLite backend emits
   `` `ai_capability.type_id` ``, DuckDB backend emits `"..."`).
5. **Probe claims confirmed from the emitted SQL.** Path a emits `ILIKE '%id_rsa%'` with no `ESCAPE`, path b emits
   `LIKE '%id\_rsa%' ESCAPE '\'`; path a emits `NOT (a=b AND c=d)`, path b `NOT COALESCE((...), 0)`. Probe outputs
   reproduce (`probe-underscore` hits S3 on a only; `probe-null-prev` hits S2 on b only).
6. **Independent live re-run** of `snapshot.py live` from a scratch copy (same venv, same `scg_mcp.py`, npm packages
   cached), 2026-11-09T23:10:46Z–23:14:49Z, chrony 17 µs fast. Evidence in `verification/` (`live-rerun.json`,
   `compare.py`, `compare-output.json`, `clock.txt`). 54 snapshots, no failures; one distinct raw manifest per server
   and byte-identical to the original run, so H0 holds across sessions too and every mutation verdict follows.
   Latency medians 2.26 / 5.36 / 9.52 ms vs the original 2.04 / 3.44 / 7.65 ms, CV 124 / 108 / 61% vs
   140 / 86 / 65%: the "few milliseconds" claim holds, the second-digit medians do not reproduce, which is within the
   reported CVs. Run-1 `initialize` dropped from 5517 / 8988 ms to 836 / 3408 ms with packages cached, consistent
   with the stated `npx` fetch explanation.
7. **Versions.** Python 3.12.3, Node v22.23.4, DuckDB 1.5.3, sqlite 3.45.1, `mcp` 1.30.0, pySigma 1.5.1 +
   `pySigma-backend-duckdb` 0.1.4, pySigma 2.0.3 + `pySigma-backend-sqlite` 2.1.1 all confirmed from the venvs and
   recorded in `results/sigma-path-*.json`; npm servers pinned by spec (`@2026.8.31`), `serverInfo` versions
   recorded. Requirements files pin both venvs.
8. **OCSF source claims.** Fetched `objects/ai_capability.json` at the cited commit `6461440…842a`: attributes are
   fingerprints, annotation booleans, cache, transport and identity fields, with no `desc` and no `prev_*`; the text
   says "The object carries no `desc` attribute" and "consumers diff, the object does not assess". `main`
   `version.json` = `1.10.0-dev`. Confirmed.

## Deviations from the pre-registration

- H5 (real-release arm) not run; disclosed plainly in RESULTS, with the release-diffing code still unwritten.
- Path c is not strictly verbatim (`SELECT *` swapped for the uid column on every path); disclosed, and the error
  sits in the WHERE clause, so it does not change the result.
- The backend probe is post-hoc and labelled exploratory. No rule, marker list, threshold or mutation was changed.
- Windows power plan unverified (methodology §7 asks for High Performance); disclosed, and the latency numbers carry
  no comparative claim, so it does not affect a conclusion.

## Fixes applied to RESULTS.md

1. **Headline:** "the OCSF-native rules fire on…" covered S2, which reads `unmapped.prev_*` and so is not
   OCSF-native (the table already said so). Reworded to name S1 as OCSF-native and S2 as fingerprints compared
   against producer-carried previous values.
2. **H2:** "No annotation, type or cache field differed on any mutation" implied the cache and version fields were
   observed. The detector never populates `ai_capability.version` or `cache_*`, and no mutation touched annotations
   or `type`, so the sentence now says that, and that the non-separation is partly a property of the chosen mutations.
3. **Latency:** added the verifier re-run numbers and the note that medians reproduce only to a few milliseconds,
   plus the cross-session byte-identity of the manifests.
4. **Limits:** added that `schema_widened` was only partly exercised (no target tool carried
   `enum`/`pattern`/`maxLength`/`format`, so the constraint-removed, required-removed and type-broadened branches
   never ran; P3 fired through the new-unconstrained-string and `additionalProperties` branches only).
5. A pointer to this file was added under the pre-registration line.

## Note on the run summary (not a file in this directory)

The summary handed to the orchestrator calls S1 and S2 together "the OCSF-only rules"; the same correction as fix 1
applies wherever that summary is reused.

## Commands run (verifier)

```
.venv/bin/python -I detect.py
.venv/bin/python -I sigma_run.py a
.venv-sqlite/bin/python -I sigma_run.py b
.venv-sqlite/bin/python -I sigma_run.py c
.venv/bin/python -I score.py
.venv/bin/python -I probe_backend_semantics.py a
.venv-sqlite/bin/python -I probe_backend_semantics.py b
(scratch copy) chronyc tracking; .venv/bin/python -I snapshot.py live
verification/: ../.venv/bin/python -I compare.py ../snapshots/live.json live-rerun.json
curl https://raw.githubusercontent.com/ocsf/ocsf-schema/6461440105d5a6a219b92150f8895cc88cef842a/objects/ai_capability.json
```
No git commands; no files changed outside this directory apart from scratchpad copies.

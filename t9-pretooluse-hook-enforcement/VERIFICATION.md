---
type: benchmark-verification
title: "T9 verification: PreToolUse hook and permission-rule enforcement, Claude Code 2.1.321 headless"
created: 2026-11-09
area: T9-pretooluse-hook-enforcement
verdict: VERIFIED-WITH-FIXES
verifier: independent agent re-run (separate rig, same method); Gemini cross-check via agy
---

# Verdict: VERIFIED-WITH-FIXES

The measured outcomes reproduce. All 22 re-run cells matched the original on marker and token effects, on the transcript
`permissionDecision` fields, and on the hook-ledger rows. The pre-registration predates the first cell and the versions are
recorded. But `RESULTS.md` has to be corrected before anything quotes it. Three of those fixes are factual errors that the bench's own
raw data contradicts (fixes 1 to 3), and the rest are wording that goes beyond the evidence (fixes 4 to 7). None of the fixes reverses a
headline finding about enforcement.

## How the re-run was isolated

- I built a separate rig at `verify/` with copies of `run_cell.py`, `hooks/` and `mcp/` (the MCP config was repointed to
  `verify/mcp/server.py`). It had a fresh `proj/` (`git init`, `notes.txt`, `secrets/token.txt` = `T9-FIXTURE-NOT-A-SECRET`) and a fresh
  `home/.claude/` holding only a 0600 copy of `~/.claude/.credentials.json`. The original `runs/`, `evidence/` and `home/` were not
  written to, and the original's `.claude.json` (which carries D2b's hand-set trust flag) was not reused, so D2 was not contaminated.
- The same runner with the same `env`-dict isolation: `HOME` and `CLAUDE_CONFIG_DIR` were set to the lab paths, and no parent
  `CLAUDE_CODE_*` variables were passed. Isolation check on `verify/runs/A1.debug.log`: 0 references to `/home/jerem/.claude` and 50 to
  the verify home.
- The credential copy's mtime and size were unchanged across the run (1794276662, 6651 bytes), and the owner's original is unchanged
  (1794262385, 6651). I deleted the copy at close. Spend was 22 headless runs, under USD 0.05 (client-side `total_cost_usd`).
  `verify/home/.claude/.claude.json`, `verify/runs/` and `verify/evidence/otel_*.jsonl` carry account identity, so the
  confidentiality note in `RESULTS.md` applies to `verify/` as well.

## Cells re-run (22 of 37) and outcomes

| Cell | Original | Re-run | Match |
|---|---|---|---|
| A1 | DENIED-flow, `asyncAgent/unknown` | same | yes |
| B1, B2, B5 | BLOCKED-hook, `hook:PreToolUse` (B2 via exit 2) | same, ledger deny row each | yes |
| C2, C5 | BLOCKED-rule, `rule:projectSettings` (C5 `reasonType: rule`) | same | yes |
| D2 | project allow dropped, debug "Dropped 1 project-scoped permissions.allow entry — workspace not yet trusted" | same line | yes |
| D3 | RAN (allowed marker) | same | yes |
| E1, E2 | RAN (forbidden marker), 0 ledger rows; E1 debug log has 0 `disableAllHooks` lines | same | yes |
| E2b | BLOCKED-hook | same | yes |
| E3, E6, E7 | BLOCKED-rule `rule:userSettings` / `rule:projectSettings` (hook returned `allow`) / `rule:cliArg` | same | yes |
| F1 | ledger: `Agent` (no agent fields) + `Bash` with `agent_id` | same | yes |
| F2 | subagent Bash blocked by hook; subagent transcript `reject / hook:PreToolUse`, `isSidechain: true` | same; stream-json again has two `result` events with `permission_denials` of length 1 then 0 | yes (see fix 1) |
| G1, G2 | `mcp_server.source: dynamic`; G2 BLOCKED-hook | same | yes |
| G3 | tool absent from `system/init`, server `connected` | same | yes |
| H1 | console exporter: `Created 0 log exporter(s)` | same | yes |
| H1b | OTLP: `tool_decision {reject, source: hook}` with `tool_parameters`, `hook_registered {userSettings, <matcher>}` | same | yes |
| E1c | OTLP: `tool_decision {accept, config}` + `tool_result`, no `hook_registered` | same | yes |

Not re-run: A2, B3, B4, B6, C1, C3, C4, D1, D2b, D4, E1b, E4, E5, H2, H2b. The original evidence for those was spot-checked only via
`results/cells.md`.

Hook stdin fields (H1, H1b re-run) are the 10 listed in RESULTS, and the hook environment has no `OTEL_*` keys. The fixture token is
absent from every original and re-run `runs/` and `evidence/` file. The original counts check out: 18 ledger rows, 6 OTLP POSTs and 31
log records. `results/cells.json` (02:06:38Z) postdates E1c (02:05:14Z). The model is `claude-haiku-5-5` from `system/init`. Versions
confirmed: Claude Code 2.1.321, mcp 2.3.0 (t8a venv), Python 3.12.3, node v22.23.4.

## Pre-registration timing

`PREREGISTRATION.md` and `.sha256` both have mtime 2026-11-10T01:43:55Z, the hash matches (`89b966b6...`), and the first cell (A1)
ran at 01:48:48Z per `runs/A1.meta.json`. This rests on filesystem mtimes only, with no commit or external timestamp, so call it
"frozen by the agent before the run (mtime evidence)" and not independently timestamped.

## Required fixes to RESULTS.md

1. **F2 / subagent denials in stream-json are misreported (factual error).** Headline 3 ("parent `permission_denials` empty;
   only in the subagent's own transcript"), the F2 table row, and the channel table ("Subagent denials: neither") are contradicted by
   `runs/F2.stdout` and by `results/cells.md` (F2 = 1). The subagent ran in the background, so stream-json carries two `result`
   events: the first lists the subagent's denied `Bash` call (`echo t9-subagent`) in `permission_denials`, and the second (final) one is
   empty. The subagent's tool messages also appear in the stream tagged with `parent_tool_use_id`, as `/docs/en/headless` documents
   (fetched 2026-11-09). The re-run reproduced the `[1, 0]` shape. Corrected statement: the denial is in the first `result` event and in
   parent-tagged messages, and absent from the final `result` event. A consumer that reads only the last line of the stream misses it.
2. **"Rule denials also emit a `system/permission_denied` event" is not true for every rule denial (factual error).** C5 (Read
   rule) and E6 (rule deny with a hook `allow`) emitted no such event in the original or the re-run, while C1-C4, E3, E7 and H2 did. Say
   so in Headline 4 and in the channel table. The docs sentence about `permission_denied` system messages in `/docs/en/headless` sits
   in the `--permission-prompts none` section and covers the fallback denials when nobody can approve, so the docs do not say whether
   hook or rule denials emit that event. Treat this as a measured gap, not a docs contradiction: hook denials never emitted one, and C5
   and E6 did not either.
3. **Deviation timestamps are not real, so "logged as they happened" cannot stand.** At verification time (02:07Z) `RESULTS.md`
   (mtime 02:06:38Z) already contained entries stamped 02:15Z, 02:40Z and 02:45Z. Entries marked "pre-run" are stamped 01:55Z, but A1
   ran at 01:48:48Z. "After E2" is stamped 02:05Z, but E1b/E2b/D2b ran 01:53:55-01:54:06Z, and "after H1/H2" (02:15Z) follows cells that
   ran at 01:53 (H1b/H2b at 01:56). Either rebuild the times from the `meta.json` `ts` values or strike them and keep only the order.
   Also, the "pre-run" `P-allow` entry was rewritten in RESULTS.md to `touch <proj>/t9-allowed-marker`, but the stub (mtime 01:56Z)
   and A1's actual command both use `<lab>/evidence/t9-allowed-marker`. The move into `proj/` came after A1, so restore the original
   wording and keep the post-A1 entry.
4. **Headline 2 overclaims precedence.** "Deny from any source beat allow from every other source" is broader than the measured pairs
   (E3 user-deny vs P/L/C allow, E4 local-deny vs user-allow, E6 project-deny vs hook allow, E7 `--disallowedTools` vs user allow),
   and the pre-registration's own rule limits override claims to measured pairs. Name the pairs instead. For example, project-deny vs
   local-allow and `--settings`-deny vs anything were not run, and managed was not measured at all.
5. **The marker sentence omits E1c.** "`forbidden_marker_exists` true only in E1, E1b, E2" should read E1, E1b, E1c, E2 (meta and
   re-run both show E1c true).
6. **Headline 5 needs scoping.** "Headless runs do not trust the project" should be "a `-p` run in a folder that was never trusted".
   D2b shows that a persisted trust flag (hand-set in `.claude.json`, which is not a documented knob) lifts it. The part about project
   hooks and deny rules running without trust is confirmed by `/docs/en/headless`: "a `-p` session runs the hooks in a project's
   `.claude/settings.json` ... even in a folder you've never trusted".
7. **E1c "nothing on the wire" is broader than what was captured.** Scope it to "no trace in the OTLP log-event stream captured by
   the localhost sink (logs only; metrics exporter set to `none`, no traces)". The absence of `hook_registered` is the only difference
   observed in that stream.
Numbers checked and left as they are: the A1 isolation count (50 lab-home references, matching `t9-pretooluse-hook-enforcement/home` in
the original log) and the spend (about USD 0.05 when only the last `result` per cell is summed; `total_cost_usd` is cumulative, so F1
and F2 repeat the same value in their two result events).

## Gemini cross-check (agy, Gemini, 2026-11-09; Tier D, data not authority)

The prompt (`verify/evidence/gemini_prompt.txt`, no account identifiers) put the five headlines to Gemini with the evidence summary.
The reply is at `verify/evidence/gemini_reply.txt`. The first call failed on argument order (prompt before `-p`), and the second
succeeded.

| Claim | Gemini | My adjudication |
|---|---|---|
| 1 Deny held / deny beats allow everywhere | OVERSTATED: the universal clause exceeds the measured pairs | Agree, fix 4 |
| 2 `disableAllHooks` precedence | SUPPORTED (consistent with Local > Project > User key merge; "only" slightly broad) | Agree; the re-run reproduced E1, E2 and E2b |
| 3 Hooks in subagents/MCP; denial absent from parent stream | CONTRADICTED on the stream-json clause | Agree, fix 1, which the re-run and raw data confirm independently |
| 4 OTel fields; console exporter; no wire trace | OVERSTATED on "no wire-side trace" | Agree, fix 7 |
| 5 Headless does not trust the project | OVERSTATED (scope to never-trusted folder); also claimed that hooks running untrusted contradicts the docs | Agree on scope (fix 6). I reject the docs-contradiction point, because `/docs/en/headless` (fetched 2026-11-09) says outright that `-p` runs project hooks in a never-trusted folder |

## Files

- `verify/` (the re-run rig): `runs/` (22 cells), `evidence/hook_inputs.jsonl`, `evidence/otel_H1b.jsonl`, `evidence/otel_E1c.jsonl`,
  `evidence/cred_before.txt`, `evidence/gemini_prompt.txt`, `evidence/gemini_reply.txt`, `inspect_rerun.py` (reads the raw
  transcripts, stream and ledger directly, without `analyze.py`).
- Before any archive, run `rm -rf verify/home`, because it holds identity-bearing state. The credential copy is already deleted.

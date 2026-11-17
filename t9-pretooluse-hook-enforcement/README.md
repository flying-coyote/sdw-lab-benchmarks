# t9-pretooluse-hook-enforcement (T9)

## What it measures

Whether a `PreToolUse` hook and a `permissions.deny` rule in Claude Code 2.1.321, run headless (`claude -p`), actually
stop a defined Bash command and a defined file read when they are placed in each settings layer (user, shared
project, project-local, `--settings`, `--disallowedTools`), which layer wins when two disagree, whether hooks fire
inside subagents and for MCP tools, and where each decision is recorded (transcript, stream-json, debug log,
OpenTelemetry). Every cell runs in an isolated home directory with fixed prompts, a marker file the forbidden command
would create and a fixture token the forbidden read would leak; the result is compared with the vendor
documentation fetched the same day.

## Result

In the 24 cells where a deny control was in force, none created the marker or leaked the fixture token; the marker
appeared only where `disableAllHooks` had switched the hook off and in the allow cells, and a developer's own
`.claude/settings.local.json` with `disableAllHooks: true` disabled the team's committed hook even when the project
file pinned `false` (`RESULTS.md`, Headline items 1 and 2). Hooks fired inside a background subagent and for an MCP
tool with attribution, and the final stream-json `result` event of the subagent cell carried an empty denial list,
so a consumer reading only the last line misses the denial. These are measured file-system effects and decision
records on real software, scored on what the tool calls did and not on model wording; the precedence findings hold
for the four pairs measured and are not a general precedence rule, and the managed settings tier was not measured.

## What would have made it fail

`PREREGISTRATION.md` lists what would change the conclusion (for example, the project hook still running under a
local `disableAllHooks`, or no `agent_id` on the subagent's Bash call). Allow cells are the contrast for every deny
cell, and because an LLM is in the loop the control for "the model simply declined" is that in every blocked cell the
model did issue the target call, shown by a hook-ledger row or a `permission_denials` entry (`RESULTS.md`, Limits).

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before cell 1 and not owner-reviewed. Its sha256 in `PREREGISTRATION.sha256`
(`89b966b6…ade79f`) still matches, with freeze time 2026-11-10T01:43:55Z; the first cell, A1, ran at 01:48:48Z.
Cells were added and adjusted during the run, and each change is logged with its time in `RESULTS.md` under
Deviations and in `evidence/RESULTS.stub.md`, the in-progress deviations log. 37 headless invocations ran against a
cap of 40, for an estimated spend of about USD 0.05. The pre-registration's isolation section names the host user's
own Claude configuration directory by absolute path; the file is frozen and is left as it is.

## Reproduce

```bash
python3 -I run_cell.py A1 A2 B1 ...     # cells defined in CELLS inside run_cell.py
python3 -I analyze.py                   # writes results/cells.{json,md}
```

`mcp/mcp-config.json` starts the fixture server with absolute paths into the original scratch directory, using the
`mcp` 2.3.0 virtual environment from `../t8a-mcp-before-after/` (`requirements-v2.txt`), so both paths have to be
pointed at this folder and a local venv before the MCP cells will run.

`run_cell.py` writes the settings layers for one cell, runs `claude -p` in an isolated `HOME` and collects the
evidence; it needs the Claude Code CLI at 2.1.321 and an authenticated account. The per-cell `runs/`, the isolated
`home/` and `proj/` trees and the raw OTLP captures are gitignored, because they carry the account's e-mail, account
UUID and organisation id (`RESULTS.md`, Confidentiality note), so `analyze.py` cannot be re-run from this tree; the
committed `results/otel_events_redacted.json` and `evidence/hook_inputs.jsonl` have those identifiers redacted.

Files: `hooks/pretool_guard.py` (the hook), `mcp/server.py` (fixture MCP server on mcp 2.3.0), `mcp/mcp-config.json`,
`mcp/otlp_sink.py` (localhost OTLP sink), `evidence/hook_inputs.jsonl` (18 hook-input rows),
`evidence/hook_inputs_selftest.jsonl` (two pre-run self-test rows, not cells),
`evidence/credentials_mtime_before.txt`.

## Results

- `RESULTS.md` is the entry point: headline, cell results, what the hook receives, where each decision is recorded,
  an OCSF 1.9.0 mapping of one hook decision and one rule decision, docs against measurement, deviations, limits.
- `results/cells.md`, `results/cells.json` and `results/otel_events_redacted.json` are the reducer outputs.
- `VERIFICATION.md` is the independent re-run on a separate rig with a cross-provider check (VERIFIED-WITH-FIXES);
  its fixes are marked `[fixed per verify]` in `RESULTS.md`. `verify/` holds the verifier's copies of the harness
  and its evidence and is not the current result.
- `evidence/RESULTS.stub.md` is the in-progress deviations log the run kept, superseded by `RESULTS.md`.

## Versions and pins

There is no requirements file. The harness is standard library, the fixture MCP server needs `mcp` 2.3.0, and the
rig in the `RESULTS.md` frontmatter names Claude Code 2.1.321, model `claude-haiku-5-5`, Python 3.12.3 and node
v22.23.4. The vendor documentation compared against was fetched on 2026-11-09.

## Evidence tier and limits

Tier B, measured on one host, one version, one run per cell; the documentation compared against is Tier B for what
a feature does (`RESULTS.md`). Headless only, the managed tier unmeasured, no `PermissionRequest`, plugin, HTTP or
`mcp_tool` hooks, and a fixture MCP server whose only tool is `echo`. See Limits in `RESULTS.md`.

## Corrections

- 2026-11-09: verifier fixes are marked `[fixed per verify]` in `RESULTS.md`.
- 2026-11-17: the `RESULTS.md` frontmatter status said "not yet independently verified" after `VERIFICATION.md` had
  been written; it now carries a dated correction. One absolute home-directory path in the Deviations section of
  `RESULTS.md` was replaced with a description of the same directory. This README was added.

---
type: benchmark-results
title: "T9 results: PreToolUse hook and permission-rule enforcement in Claude Code 2.1.321 (headless)"
created: 2026-11-09
area: T9-pretooluse-hook-enforcement
status: in-progress
---

Pre-registration frozen: sha256 `89b966b6c104841e6d12303d13292153f0cae0d9c5b222d33e5f1ec7c4ade79f`, 2026-11-10T01:43:55Z (agent-frozen, not owner-reviewed).

## Deviations (logged as they happen)

- 2026-11-10T01:55Z, pre-run. **Allow target changed from `echo` to `touch`.** The permissions page lists `echo` in the built-in
  read-only command set that runs without a prompt in every mode, so `P-echo` would never have produced a denial for an allow
  rule to lift. `P-allow` is now `touch <lab>/evidence/t9-allowed-marker`, rule `Bash(touch *t9-allowed*)`, scored by marker
  presence. The subagent prompt keeps `echo t9-subagent` because PreToolUse fires whether or not a call needs permission.
- 2026-11-10T01:55Z, pre-run. **E1/E2 sharpened.** The file that sets `disableAllHooks: true` also carries `allow: ["Bash(touch *)"]`,
  so a disabled hook shows as the forbidden marker appearing rather than as an ambiguous permission-flow denial.
- 2026-11-10T01:55Z, pre-run. **B2 and B6 use the exit-2 deny route**, B1/B3/B4/B5 the JSON `permissionDecision` route, so both
  documented deny channels are measured without extra cells.
- 2026-11-10T01:55Z, pre-run. **Debug filter dropped**: `--debug-file` alone (full debug), since the `permissions` category name was
  unverified and a filter could drop the decision lines being collected.
- 2026-11-10T01:55Z, pre-run. **Hook variant passed as argv**, not environment, so each settings file is self-describing.
- 2026-11-10T01:55Z, pre-run. **Credential risk noted**: the only file copied from the owner's `~/.claude/` is `.credentials.json`.
  If the OAuth refresh rotates during the lab, the owner's real session could be affected; A1 runs alone first and the lab copy's
  mtime is compared before and after.
- 2026-11-10T01:52Z, after A1. **Marker files moved inside the project** (`proj/t9-forbidden-marker`, `proj/t9-allowed-marker`; the
  P-bash command is now `touch ./t9-forbidden-marker && echo t9-done`). A1 showed the permission flow treats a `touch` outside the
  working directories as a separate approval ("The path is outside the working directories for this session"), which would have
  confounded every allow-rule cell with a second reason to deny. Patterns `*t9-forbidden*` / `*t9-allowed*` are unchanged.
- 2026-11-10T01:52Z, after A1. **Isolation confirmed**: `runs/A1.debug.log` has 0 references to `/home/jerem/.claude` and 50 to the lab
  home; the only settings paths probed were the lab user file, `/etc/claude-code/managed-settings.json` (absent), and the lab project
  and local files. Credentials file mtime and size unchanged after A1 (1794262385, 6651 bytes).
- 2026-11-10T02:05Z, after E2. **Three cells added (E1b, E2b, D2b; total 34 of the 40 cap).** E2 ran the forbidden command: a user-file
  `disableAllHooks: true` switched off the project hook because the project file never set the key, so the "project outranks user"
  prediction only applies when the project pins `disableAllHooks: false`. E1b/E2b pin it in the project file and re-test the local
  and user `true`. D2b re-runs the project allow rule after hand-setting `projects.<proj>.hasTrustDialogAccepted: true` in the lab
  `.claude.json` (a hand-edited state file, not a documented knob), to test whether trust is what D2 lacked.
- 2026-11-10T02:15Z, after H1/H2. **OTel console exporter produced nothing**: `runs/H1.debug.log` shows `[3P telemetry] isTelemetryEnabled=true`
  but `getOtlpLogExporters: types=[]` and `Created 0 log exporter(s)` with `OTEL_LOGS_EXPORTER=console`, so the documented console
  exporter did not instantiate in this headless run on 2.1.321. Two cells added (H1b, H2b; total 36 of 40) with `OTEL_LOGS_EXPORTER=otlp`,
  `OTEL_EXPORTER_OTLP_PROTOCOL=http/json` and a localhost sink (`mcp/otlp_sink.py` on 127.0.0.1:4318) standing in for a collector.

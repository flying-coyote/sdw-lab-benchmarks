---
type: evidence
title: "T2 — Platform telemetry fidelity: which fields of one scripted agent session each platform emits"
created: 2026-11-09
tags: [ai-telemetry, opentelemetry, claude-code, ollama, vertex-ai, bedrock, azure-foundry, copilot, chatgpt-enterprise, audit-logging]
---

# RESULTS: the native telemetry carries identity, model, tokens and cost; the content fields are opt-in, and no platform carries all twelve by default

**Pre-registration:** `PREREGISTRATION.md`, sha256 `8baf545d07e266f9f7da9ad39344d22f08b30a4d20d531a921fed551f7a4e24c`,
frozen 2026-11-10T00:55:35Z. Frozen by agent before run; not owner-reviewed.

**Rig stamp (§7b).** Beelink, Ryzen 7 5800H, WSL2 (kernel 6.6.87.2), 14 vCPU, 47 GB; Windows power plan not
checked for this run; 2026-11-10 00:55 to about 01:30 UTC. Clock: chrony running, but `chronyc tracking`
reported the guest **0.58 to 0.61 s slow** of NTP at the start (only the 0.606 s reading is logged in
`COMMANDS.log`; the 0.58 s figure is unlogged), outside the methodology's "milliseconds or
less" threshold, so every absolute duration in this file is context only and none is a claim. Timings were
taken under contention: other benches were running on the host, the Claude Code process and the harness
ran under `nice -n 10 taskset -c 0-3`, the collector under `--cpus=1`, and the Ollama debug trials
overlapped the default trials. This bench scores field presence, not latency.

**Versions.** Claude Code 2.1.321 (OAuth, Max plan; `--model haiku` resolved to `claude-haiku-5-5`);
`otel/opentelemetry-collector-contrib:0.145.0` (`sha256:a7343f01869071ea3f4c5e1e97df1bb1b3c4d5c77247db80e053a80b9df530c4`);
Ollama 0.20.6, model `gemma4:e4b` (8.0B, Q4_K_M; weights blob `sha256-4c27e0f5b5adf02ac956c7322bd2ee7636fe3f45a8512c9aba5385242cb6e09a`, from the journal load line, added at verification); Docker 29.5.3; gcloud 560.0.0; Python 3.12.3, harness
stdlib-only (`requirements.txt`). Commands in `COMMANDS.log`.

**Spend.** USD 0. Claude Code ran on the subscription (its `cost_usd` attribute is the list-price notional,
about USD 0.0008 per session). No Vertex call was made (below). Ollama is local.

## Headline

Across three trials each, Claude Code's OpenTelemetry export at its documented defaults delivered **8 of
the 12 fields** (user identity including the account email, session id, tool name, model id, four token
counters, a USD cost, host attributes, timestamps) and withheld the four content fields (prompt text,
tool arguments, tool output, response text) as lengths or the literal `<REDACTED>`. With every documented
content gate on, **all 12 arrived with values matching the known session**, but the tool output (the file
content) arrived only on the traces path, which is behind a beta flag. The attribute set was identical
across the three trials of each configuration (zero unstable attributes).

Ollama's server log at default level carried **none of the eight content, identity, model-per-request or
token fields**: in each window it held only Gin access lines (timestamp, status, latency, `127.0.0.1`,
`POST /api/chat`) and model-load lines naming the weights by blob digest and architecture. The same windows
also held 1, 3 and 4 chat requests from other clients on this host (corrected at verification from 1, 3, 5), and nothing in a line distinguishes
them from the bench's own two requests. Everything a security team would want (model, token counts,
tool call, response) came back in the **client response body** instead, so for Ollama the record exists
only if the caller keeps it.

Of the six documented platforms, none is all-present at its default; Bedrock invocation logging, once
switched on, is the closest (identity ARN, full request and response bodies up to 100 KB, token counts;
no cost field), and the ChatGPT Enterprise Compliance API is the only one whose public description leads
with conversation text and user identity while saying nothing about tokens or cost.

## The table

Legend: **M+** measured present, **M−** measured absent, **M+ (flag)** present only with the named opt-in,
**D+** documented present (not measured), **D−** documented absent, **NS** not stated in the vendor pages
fetched, **n/a** the field is on the client's side by construction. Sources for every D cell are in
`docs-evidence/DOCUMENTED-COLUMNS.md`. Arm B (Vertex) and arm D are documented only.

| Field | Claude Code OTel, defaults (A1) | Claude Code OTel, all gates (A2) | Ollama server log, default | Ollama server log, `OLLAMA_DEBUG=1` | Ollama client response | Vertex AI audit logs (Data Access) | Vertex AI request-response logging | AWS Bedrock invocation logging | Azure OpenAI in Foundry diagnostics | GitHub Copilot audit log | ChatGPT Enterprise Compliance API |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 user identity | M+ `user.email`, `user.account_uuid`, `user.account_id`, `organization.id`, `user.id` | M+ | M− | M− | M− | D+ `AuthenticationInfo` (principal email; not redacted on success) | D− "No schema column identifies the caller" | D+ `identity.arn` | NS (metrics are aggregates; log caller object id not stated) | D+ `actor`, `user` | D+ workspace users |
| F2 session id | M+ `session.id` (one per trial) | M+ | M− | M− | M− | D− per request only | D− `request_id` per request | D− `requestId` per request; session only if caller tags `requestMetadata` | D− | D+ `agent_session_id` on agent events only | D+ conversation |
| F3 prompt text | M− length 101; `prompt`/`prompt_text` = `<REDACTED>` | M+ (flag `OTEL_LOG_USER_PROMPTS`) verbatim on `user_prompt` and on the `claude_code.interaction` span | M− | M− length in characters only (`completion request … prompt=448`, `=1090`) | n/a (client sent it) | NS | D+ `request_payload` / `full_request` | D+ `input.inputBodyJson` (≤100 KB inline) | NS | D− "does not include client session data, such as the prompts" | D+ conversations |
| F4 tool name | M+ `tool_name=Read` on `tool_decision`, `tool_result` | M+ | M− | M− | M+ `tool_calls[].function.name` | NS | D+ inside payload (function call) | D+ inside body (tool use block) | NS | D− | NS |
| F5 tool arguments | M− `tool_input_size_bytes=89` only | M+ (flag `OTEL_LOG_TOOL_DETAILS`) `tool_input` JSON and `file_path` span attribute, as the resolved absolute path | M− | M− | M+ `arguments.path` | NS | D+ inside payload | D+ inside body | NS | D− | NS |
| F6 tool output / file content | M− `tool_result_size_bytes=138` only | M+ (flags `OTEL_LOG_TOOL_CONTENT` + `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA`) `tool.output` span event, file content verbatim; **traces path only, not on logs** | M− | M− | n/a (the harness produced it) | NS | D+ as part of the next request's contents | D+ as `toolResult` in the next request body | NS | D− | NS |
| F7 model id | M+ `claude-haiku-5-5` on events, metrics | M+ | M− per request; weights named at load by blob digest and `architecture=gemma4` | M+ per request in scheduler lines (`context for request finished runner.name=registry.ollama.ai/library/gemma4:e4b`) | M+ `gemma4:e4b` | D+ via resource name (inferred from the method path, not quoted) | D+ `model`, `model_version` | D+ `modelId` | D+ `ModelName`, `ModelVersion` dimensions | NS | NS |
| F8 token counts | M+ input, output, cache read, cache creation (events and `claude_code.token.usage`) | M+ | M− | M+ input only: `loading cache slot … prompt=98` / `=267`, equal to the client's `prompt_eval_count`; no output count | M+ `prompt_eval_count`, `eval_count` | NS | D+ inside `full_response` (`usageMetadata`; inferred from the API shape) | D+ `inputTokenCount`, `outputTokenCount` | D+ per-minute metrics, not per request | D− | NS |
| F9 cost | M+ `cost_usd`, `cost_usd_micros`, `claude_code.cost.usage` (list-price basis) | M+ | M− | M− | M− | D− | D− | D− (no cost field) | D+ `FoundryModelEstimatedCost` (Preview, aggregate estimate) | D− | NS |
| F10 response text | M− length 24; `response` = `<REDACTED>` | M+ (flag `OTEL_LOG_ASSISTANT_RESPONSES`) sentinel verbatim | M− | M− | M+ | NS | D+ `response_payload` / `full_response` | D+ `output.outputBodyJson` | NS | D− | D+ |
| F11 caller network identity | M+ host attributes (`os.type`, `os.version`, `host.arch`, `wsl.version`, `terminal.type`); **no client IP** | M+ | M+ `127.0.0.1` on every line, which does not attribute between clients | M+ `127.0.0.1`, same as default | M− | D+ `caller_ip` (may be redacted) | D− | D− (ARN, no IP) | D+ `CallerIPAddress` (common resource-log schema) | NS | NS |
| F12 timestamps | M+ | M+ | M+ | M+ | M+ `created_at` | D+ | D+ `logging_time` | D+ `timestamp` | D+ | D+ | D+ |

Three cells deserve a sentence each. Claude Code's F11 is host identity, not network identity, so a SIEM
cannot correlate a Claude Code event with a firewall or proxy record by IP; the correlation key the export
gives you is the account email. Ollama's F11 is the opposite problem: an IP that is present on every line
and identical for every local client, so it carries no attribution. Claude Code's F6 is the one field that
needs the beta tracing flag; everything else in A2 arrives on the logs signal that the documentation calls
production-ready.

## Arm A detail: Claude Code

Per trial, the export held the same 54 (A1) or 60 (A2) items: one `user_prompt`, one `tool_decision`, two
`api_request`, one `tool_result`, one `assistant_response`, plus startup events (`managed_settings_resolved`
1, `plugin_loaded` 10, `hook_registered` 8, `hook_execution_start`/`complete` 3 each, `mcp_server_connection`
11), 12 metric data points (`session.count` 1, `cost.usage` 2, `token.usage` 8, `active_time.total` 1), and in
A2 six spans (`claude_code.interaction`, two `claude_code.llm_request`, `claude_code.tool`,
`claude_code.tool.execution`, `claude_code.tool.blocked_on_user`). `score.py` found **no attribute present
in some trials and not others** for any event, metric or span name, and every event type appeared in every
trial (H3). Values matched the known session in all six trials: the prompt verbatim (A2), `tool_name=Read`,
`tool_input` = `{"file_path":"/tmp/claude-1000/lab-ai-research/t2-platform-telemetry/fixtures/known.txt"}`
(the resolved absolute path, not the relative path in the prompt), the `tool.output` span event's `content`
equal to the fixture text, and `response` equal to the sentinel. Token counts were stable: the first request
read 34,420 cached tokens and emitted 86 output tokens in all six trials; the second read 36,333 cached tokens
in five of the six trials (A2 trial 3 read 34,420 and wrote 199 cache-creation tokens instead; corrected at
verification) and emitted 24, 147, 178 (A1) and 148, 184, 24 (A2) output tokens while `response_length` was 24 in every trial, so the
extra output tokens are not in the visible response (the documentation says `assistant_response` excludes
thinking and tool-use blocks) and their cause was not determined in this run; it is not an A1-versus-A2
effect. `input_tokens` was 2 on every request because almost the whole prompt was cache. Per-session
`cost_usd` summed to about USD 0.00076 (A1 trial 1) and USD 0.00083 (A2 trial 1).

Three attributes appeared on every event and metric that the documentation I fetched did not list:
`anthropic.provider=firstParty`, `anthropic.custom_base_url=False`, `anthropic.plan=max`. They may be in
the part of the page I did not read; I note them as present and undocumented-to-me rather than
undocumented.

The A1 content fields are not merely absent: `prompt`, `prompt_text` and `response` exist on the event with
the literal value `<REDACTED>`, and `tool_input_size_bytes` / `tool_result_size_bytes` give the sizes, so a
parser sees the shape of the interaction without its content.

## Arm C detail: Ollama

Default level (system service, `journalctl -u ollama`, sliced by epoch window per trial): 132, 137 and 151
lines, all `level=INFO`, Gin access lines, or four unlevelled `load_backend:` lines per window (wording
corrected at verification). Each window held the bench's two `POST /api/chat` lines (matched
to the harness latencies within 0.6 s: 44.9/49.6 s, 45.1/58.8 s, 58.1/61.0 s) and 1, 3 and 4 further
`/api/chat` lines from other clients on the host (trial 3's window also holds trial 2's own final request,
caught by the window's 2 s lead padding; the original text counted it as foreign and said 5, corrected at
verification), plus, in trial 1's window only, an `/api/show` from `::1`. Every line in the window
read `127.0.0.1` or `::1`, carried no request id, no model name and no user, so the bench's requests are
identifiable only by latency coincidence. Model identity appears at load time only, as the blob path
(`--model /usr/share/ollama/.ollama/models/blobs/sha256-…`) and `architecture=gemma4`, never per request;
the service reloaded the model repeatedly inside the windows with `KvSize` alternating between 4096 and
8192, which is consistent with another client requesting a different context size (the harness never set
`num_ctx`, so the attribution is inferred), and is itself a tell that the log is a shared, unattributed
stream. No prompt text, tool name, path, sentinel, token count or cost appeared.

Client response body (what the caller is told): `model=gemma4:e4b`, `prompt_eval_count=267`, `eval_count=22`
on the final turn in all three trials, `created_at`, five nanosecond durations, the `tool_calls` array with
`read_file` and `{"path": "fixtures/known.txt"}` on the first turn, and the sentinel in `message.content`
on the second. No user, session or cost field.

Debug level (`OLLAMA_DEBUG=1`, private instance on 127.0.0.1:11435 using the same model store read-only;
three trials, 155 / 14 / 14 lines, the first including the one-time model load): debug level adds per-request
scheduler lines that name the model (`context for request finished runner.name=registry.ollama.ai/library/gemma4:e4b`,
`after processing request finished event …`), a `completion request images=0 prompt=448` / `prompt=1090` line
whose number is a prompt length in characters, not tokens, and a `loading cache slot … prompt=98` /
`prompt=267` line whose number equals the client's `prompt_eval_count` on each turn in all three trials, so
the **input token count per request is in the debug log**. No output token count, no prompt text, tool name,
path, sentinel, user, session or cost appeared in any debug slice. Debug level is still a shared stream with
no request id; attribution is by sequence. Debug trial 1 ran 490 s against 39.5 and 38.6 s for trials 2 and 3,
the difference being core saturation (deviation 7), not the logging level.

## Arm B: Vertex AI, not run

Pre-run check before the freeze: `gcloud billing projects describe` returned `billingEnabled: False` for all
five projects the account lists (`second-brain-fc-2026`, `gen-lang-client-0022256122`,
`gen-lang-client-0593967652`, `proven-metric-475219-u7`, `technology-combinations`), and `gcloud billing
accounts list` returned none. Per the brief, billing was not enabled and the arm is recorded as not run; no
Gemini call was made; spend USD 0. The project's IAM policy had no `auditConfigs`, so Data Access logs were
off. The Vertex columns are documented only.

## Hypotheses

- **H1 (defaults): supported.** All three A1 trials carried F1, F2, F4, F7, F8, F9, F11 (as host attributes)
  and F12, and the lengths of F3 and F10, with no prompt text, path or sentinel anywhere in the export.
- **H2 (gates): supported**, with the qualification that F6 arrived only through the traces (beta) path.
  Prompt verbatim, path as the resolved absolute path, sentinel in `tool.output.content` and in `response`,
  in all three A2 trials.
- **H3 (stability): supported.** Zero unstable attributes across trials for every event, metric and span
  name; every type present in every trial.
- **H4 (Ollama): default-level clause supported** in all three trials (F1, F3, F4, F5, F6, F8, F9, F10 absent;
  F7 only at load). **Debug-level clause falsified in two parts, in all three trials**: the model name appears
  per request in scheduler lines, and the input token count appears per request as the cache-slot `prompt=`
  value (98 and 267, equal to the client's `prompt_eval_count`). The rest of the clause held (no prompt text,
  no output tokens, no tool, path, sentinel, user or cost). Client clause supported (F7, F8, F10 and the
  tool call present; F1, F2, F9 absent).
- **H5 (no all-present default column): supported.** The only all-present column is Claude Code with four
  opt-in flags, one of them beta.
- **H6 (identity and content inversely distributed): not falsified; the second clause is weakly supported.**
  (Reworded at verification from "survives on a technicality": the cross-provider reviewer judged that
  overstated, and the data agree, because no column meets the falsifier's "by default" condition and Bedrock
  would fail it on cost even when enabled.) The falsifier needed identity, prompt text, tokens and cost
  together by default. Bedrock invocation logging, once enabled, carries `identity.arn`, the full request
  body, and both token counts; it lacks a cost field, and it is off by default. The ChatGPT Enterprise
  clause rests on tokens and cost being *not stated* rather than documented absent. So the hypothesis is
  not falsified, but the pattern it describes is
  weaker than I pre-registered it: the real split is "content requires an opt-in" (Claude Code gates, Bedrock
  logging, Vertex request-response logging, Copilot's preview API-usage stream) rather than "identity and
  content live on different platforms". The ChatGPT Enterprise column, which fits the hypothesis best, is
  also the weakest-sourced (public announcement plus search snippets; the help article is login-gated).

## Deviations from the pre-registration

1. The first A1 trial was discarded and re-run: the collector's `file` exporter failed to open `/out` (the
   image runs unprivileged; the host directory needed mode 777). Logged in `COMMANDS.log`; the discarded
   stdout is kept under `results/_discarded-claude-A1-t1-collector-perm-error/`.
2. The Ollama journal windows were first cut with UTC strings that `journalctl` read as America/New_York;
   `journal_slice.sh` re-cut them by epoch. The default trials 2 and 3 were run in the background without
   the in-line journal capture, so all three were sliced afterwards by their `session.json` timestamps.
3. The Claude Code session was not the bare three-step shape the pre-registration describes: `claude -p`
   inherited the account's user-level plugins, hooks and MCP servers (10 `plugin_loaded`, 8 `hook_registered`,
   11 `mcp_server_connection` events, and about 34k cached system-prompt tokens per request). The three
   session events of interest are unaffected, but the event counts and token figures describe this
   account's configuration, not a clean install. The parent session's `CLAUDECODE` marker variables were
   unset so the child would run.
4. The debug-level Ollama trials ran concurrently with default-level trials 2 and 3 and with other benches,
   on the 4-core affinity; their latencies are not comparable to anything.
5. Post-capture redaction, not a measurement change: `scrub_identifiers.py` replaced the values of
   `user.email`, `user.account_uuid`, `user.account_id`, `organization.id` and `user.id` with placeholders
   in `collector/out/*.jsonl` and `results/claude-*/events_flat.json` after scoring; `score.py` re-run on
   the scrubbed files produced an identical A2 block (the only block the pre-scrub copy held) and the A1
   scores above. The scorer tests key presence, so the scrub cannot change a score.
6. The Vertex request-response logging token cell and the Vertex audit model cell are inferences from the
   API shape, not quotations, and are labelled so in the table.
7. The private debug-level Ollama instance was started on cores 0-3 as pre-registered; during debug trial 1
   those four cores were at 100% with two other benches' processes pinned to them as well, the first turn
   took 7 m 57 s, and I re-pinned the server and its runner to cores 6, 9, 10 and 12 (still a four-core cap)
   mid-trial. Trials 2 and 3 ran on those cores. This changes nothing scored; it is why the debug durations
   differ by an order of magnitude.
8. Added at verification: the captured `results/*/env.txt` files carried the parent session's local
   messaging token, socket path and two session ids; these four values were redacted post-capture, the same
   class of change as deviation 5. No scored file was touched. See `VERIFICATION.md` fix 7.

## Limits

One host, one account, one day, one Claude Code version (2.1.321) and one Ollama version (0.20.6). The
Claude Code arm measures what the client exports on an OAuth Max account; a direct-API-key, Bedrock, Vertex
or Foundry deployment of Claude Code populates only `user.id` and `session.id` per the documentation, which
this bench did not test. The documented columns are the vendors' descriptions of their own products (Tier
B for what a feature emits), fetched on one day, and the ChatGPT Enterprise column rests on an announcement
and search snippets. Methodology §10: generation is not the scored quantity here; for the record the model
returned the sentinel in 6 of 6 Claude Code trials, 3 of 3 default-level and 3 of 3 debug-level Ollama
trials. Independent verification: see `VERIFICATION.md` (verdict VERIFIED-WITH-FIXES, 2026-11-09).

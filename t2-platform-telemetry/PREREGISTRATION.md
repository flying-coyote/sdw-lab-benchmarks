---
type: benchmark-preregistration
title: "T2 — Platform telemetry fidelity: which fields of one scripted agent session each platform actually emits"
created: 2026-11-09
status: frozen-by-agent-before-run
tags: [ai-telemetry, opentelemetry, claude-code, ollama, vertex-ai, bedrock, azure-foundry, copilot, chatgpt-enterprise, audit-logging]
---

# Pre-registration: T2, platform telemetry fidelity

Frozen by the agent before any measurement was run; not owner-reviewed. The sha256 of this file and the
freeze timestamp are recorded at the top of `RESULTS.md`. Anything run that is not listed here is labelled
*exploratory* in the results, and every departure from this file is listed under "Deviations" there.

## Question

When one agent session with a known shape (a user prompt, one tool call that reads a file, one model
response) runs against each of several AI platforms, which of the fields a security team would want in its
telemetry actually arrive in the platform's own export, as it ships, and which only arrive after an opt-in
flag, and which never arrive at all? The output is a field × platform table with three values per cell:
*measured* (seen in this run), *documented* (vendor documentation says it is emitted; not measured here),
*absent* (measured or documented as not emitted).

The motivating question is the SIEM-side one: if an organisation wants to answer "who asked the agent what,
what did the agent touch, which model answered, and what did it cost", can it get that from the platform's
native telemetry, or does it need a proxy or gateway in the path?

## Ground truth: the scripted session

One fixture file, `fixtures/known.txt`, holds one sentinel line. The sentinel is a nonsense token (no
exploit content, no credentials; it is only there so that a file read can be detected in the telemetry by
value): `SDW-T2-SENTINEL-7f3a9c2e`. The fixture is labelled as a test fixture inside the file.

The session, identical in intent across every measured arm:

1. User prompt (verbatim): `Read the file fixtures/known.txt and reply with exactly the sentinel token it contains, nothing else.`
2. Expected tool call: a file read of `fixtures/known.txt` (Claude Code: the `Read` tool; Ollama: a `read_file`
   tool defined by the harness script and executed by the harness).
3. Expected model response: the sentinel token.

Everything in the session is known in advance, so the scoring is presence/absence of each field, and where
a value arrives, whether it matches the known value.

## Fields scored (the rows of the table)

| # | Field | What counts as present |
| --- | --- | --- |
| F1 | User identity | an account email, account UUID, or IdP subject tied to the human |
| F2 | Session identity | a session id that groups the events of one session |
| F3 | Prompt text | the user's prompt, verbatim or truncated |
| F4 | Tool name | the name of the tool invoked (`Read` / `read_file`) |
| F5 | Tool arguments | the file path passed to the tool |
| F6 | Tool output / file content | the sentinel value as returned by the tool |
| F7 | Model id | the model identifier that served the request |
| F8 | Token counts | input and output token counts (cache counts noted separately) |
| F9 | Cost | a currency cost figure attached to the request or session |
| F10 | Response text | the assistant's response text |
| F11 | Caller network identity | client IP or host attributes |
| F12 | Timestamps | per-event timestamps |

## Arms

### Arm A — Claude Code OpenTelemetry export (measured)

Claude Code 2.1.321 run non-interactively (`claude -p`) from this directory with `--allowedTools Read` and
`--model haiku`, authenticated through the account's existing Max subscription (OAuth, so the runs carry no
marginal spend; the `cost_usd` attribute is still emitted as the account's notional cost). Exporter target:
a local OpenTelemetry Collector, `otel/opentelemetry-collector-contrib:0.145.0`, bound to `127.0.0.1` only,
OTLP/gRPC on 4317 and OTLP/HTTP on 4318, writing each signal to a JSON-lines file with the `file` exporter
(`collector/otel-config.yaml`, validated with the image's `validate` sub-command before the run).

Two configurations, each run three times (3 trials per configuration, 6 Claude Code sessions in all):

- **A1, documented defaults.** `CLAUDE_CODE_ENABLE_TELEMETRY=1`, `OTEL_METRICS_EXPORTER=otlp`,
  `OTEL_LOGS_EXPORTER=otlp`, `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317`,
  export intervals shortened to 1000 ms so a short `-p` session flushes (`OTEL_METRIC_EXPORT_INTERVAL=1000`,
  `OTEL_LOGS_EXPORT_INTERVAL=1000`). No content gate set.
- **A2, every documented content gate on.** A1 plus `OTEL_LOG_USER_PROMPTS=1`, `OTEL_LOG_ASSISTANT_RESPONSES=1`,
  `OTEL_LOG_TOOL_DETAILS=1`, `OTEL_LOG_TOOL_CONTENT=1`, `OTEL_METRICS_INCLUDE_VERSION=true`,
  `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`, `OTEL_TRACES_EXPORTER=otlp`, `OTEL_TRACES_EXPORT_INTERVAL=1000`.
  `OTEL_LOG_RAW_API_BODIES` is deliberately left off: the documentation says it carries the whole
  conversation including the system prompt, and the question here is field-level fidelity, not body capture.

Source of the variable names: code.claude.com/docs/en/monitoring-usage, fetched 2026-11-09 (vendor
documentation, Tier B for what the product emits). The documented defaults predict, for A1: identity
(`user.email`, `user.account_uuid`, `user.id`), `session.id`, `tool_name`, `model`, token counts, `cost_usd`,
`prompt_length` and `response_length` only, with prompt text, response text, tool arguments and tool output
redacted or omitted. For A2 the documentation predicts prompt text on `user_prompt`, response text on
`assistant_response`, `tool_input` (file path) on `tool_result`, and raw file content in the `tool.output`
span event.

The Claude Code process runs under `nice -n 10 taskset -c 0-3`, the collector container with `--cpus=1`.
Each session is wrapped in a 300 s timeout.

### Arm B — Google Vertex AI (conditional; run only if billing is already enabled)

Pre-run check, already done 2026-11-09 before this freeze: `gcloud billing projects describe` on every
project the account can list (`second-brain-fc-2026`, `gen-lang-client-0022256122`,
`gen-lang-client-0593967652`, `proven-metric-475219-u7`, `technology-combinations`) returned
`billingEnabled: False`, and `gcloud billing accounts list` returned no accounts. The brief says: if billing
is not enabled, do not enable it, record the arm as not run. **Arm B is therefore recorded as not run**, and
the Vertex AI column in the table is filled from vendor documentation only (Cloud Audit Logs Data Access
logs, and Gemini request-response logging to BigQuery), marked *documented, not measured*. The project's
current IAM `auditConfigs` state is recorded as evidence (it was empty, meaning Data Access logs are off).
No Gemini call is made. Spend: USD 0.

### Arm C — Ollama local server logs (measured)

Ollama 0.20.6, already running as a systemd service on this host (`OLLAMA_HOST=0.0.0.0:11434`, default log
level). The harness (`run_ollama_session.py`, Python stdlib only) performs the same session against
`http://127.0.0.1:11434/api/chat` with a `read_file` tool declared in the request, executes the tool call
itself by reading the fixture, returns the tool result, and records the final response. Model:
`gemma4:e4b` (already pulled). Request options pin `num_thread: 4`. The request carries `stream: false`.
Three trials.

What is scored: the lines `journalctl -u ollama` emits between the harness's start and end timestamps,
at the service's default log level, plus the response body the harness itself receives (so the table can
distinguish "the server logs it" from "the client was told it"). The harness also runs a second, private
Ollama instance from this directory with `OLLAMA_DEBUG=1`, `OLLAMA_HOST=127.0.0.1:11435`, under
`nice -n 10 taskset -c 0-3`, pointing `OLLAMA_MODELS` at the existing model store, **only if** that store
is readable by this user; if it is not, the debug-level arm is recorded as not run rather than restarting
the system service, which is outside this directory.

Prediction from the Ollama troubleshooting documentation (docs.ollama.com/troubleshooting, fetched
2026-11-09): the server log is a Gin access log (timestamp, status, latency, client IP, method, path) plus
model load events; the documentation says nothing about prompt text, model id per request, or token
counts in the log, so the pre-registered expectation is that F1, F3, F4, F5, F6, F8, F9 and F10 are absent
from the server log, F7 is present only through model-load lines (not per request), and F11 and F12 are
present.

### Arm D — documented only (no credentials here)

AWS Bedrock model invocation logging, Azure OpenAI in Microsoft Foundry diagnostic settings, GitHub Copilot
audit log, ChatGPT Enterprise Compliance API. Each column is filled from vendor documentation fetched on
2026-11-09 with the URL recorded, and marked *documented, not measured*. Where a vendor page could not be
fetched (OpenAI's help-centre article is login-gated), the column is filled from the vendor's public
announcement and labelled with that lower tier.

## Hypotheses, with what would prove each wrong

- **H1 (Claude Code defaults).** At documented defaults (A1), the export carries F1, F2, F4, F7, F8, F9, F11,
  F12 and the *lengths* of F3 and F10, but not the text of F3, F5, F6 or F10. Falsified if any prompt text,
  file path or sentinel value appears in the A1 export, or if any of F1, F2, F7, F8 or F9 is missing in all
  three A1 trials.
- **H2 (Claude Code with gates).** With every documented content gate on (A2), F3, F5, F6 and F10 all arrive
  with values that match the known session (prompt verbatim, path `fixtures/known.txt`, sentinel in the
  tool output, sentinel in the response). Falsified if any of the four is missing in all three A2 trials,
  or arrives with a value that does not match.
- **H3 (Claude Code field stability).** The set of attribute names present on each event type is identical
  across the three trials of a configuration (zero field-presence variance). Falsified if any attribute
  appears in some trials and not others, which would mean the export is not a stable schema contract.
- **H4 (Ollama).** The Ollama server log at default level carries none of F1, F3, F4, F5, F6, F8, F9, F10, and
  no per-request F7; the client response body carries F7, F8 and F10 and the tool call (F4, F5) but no F1,
  F2, F9. Falsified if the server log shows the prompt, the model id per request, or token counts.
- **H5 (no platform emits every row).** No platform in the table, measured or documented, has all twelve
  rows present without an opt-in flag. Falsified if any column is all-present at its default.
- **H6 (identity and content are inversely distributed).** Platforms that carry strong user identity by
  default (Claude Code OAuth, Vertex audit logs, Bedrock `identity.arn`, Copilot audit) carry no prompt text
  by default, and the platform that carries full prompt text (ChatGPT Enterprise Compliance API) carries no
  token or cost figure. Falsified by any documented or measured platform that carries both identity and
  prompt text by default together with tokens and cost.

## Metrics

- Per (arm, configuration, field): present / absent, and for present fields, value-match against the known
  session (exact, truncated, or mismatched).
- Per (arm, configuration, event type): the attribute-name set, and its variance across the three trials
  (count of attributes present in fewer than three trials).
- Per trial: event counts by event name, metric data points by metric name, span counts by span name; wall
  time of the session under a monotonic timer.
- For Arm C: raw journal line count and the set of distinct line shapes.

Durations are incidental here and reported only as context: the bench measures presence, not latency.
Timings are taken under contention (other benches running on the host) and under a 4-core affinity cap.

## Instrument, versions, commands

Recorded in `RESULTS.md` and `COMMANDS.log`: Claude Code version, collector image digest, Ollama version
and model digest, Python version, `requirements.txt` (the harness is stdlib-only, so the pin file records
the interpreter and the absence of third-party packages), every command run, and `chronyc tracking` before
the run.

## Stop rule and cost cap

- Each Claude Code session: 300 s timeout; a configuration whose first two trials both fail to produce any
  OTLP output is recorded as such and not retried further.
- Ollama session: 600 s timeout per trial (CPU inference on a 9.6 GB model with 4 threads is slow).
- Spend cap: USD 0 actual (Max subscription for Claude Code, local Ollama, no Vertex call). The brief's USD 10
  Vertex cap is not reached because the arm does not run.
- The whole bench stops after 90 minutes of wall time regardless, and whatever is on disk is reported.

## What this bench does not do

It does not measure retention, query cost or SIEM ingestion of the telemetry (R6 covers storage cost). It
does not test adversarial content or injection through the tool output; the fixture is inert. It does not
compare models. It measures one host, one account, one Claude Code version, one Ollama version, on one day,
and the documented columns are the vendors' own descriptions of their products (Tier B for what the product
does, C for any efficacy claim), not independent measurements.

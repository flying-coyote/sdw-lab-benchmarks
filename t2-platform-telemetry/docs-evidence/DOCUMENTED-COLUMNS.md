---
type: evidence
title: "T2 documented columns: what each platform's own documentation says it emits (not measured here)"
created: 2026-11-09
tags: [ai-telemetry, vertex-ai, bedrock, azure-foundry, copilot, chatgpt-enterprise, documentation]
---

# Documented columns (fetched 2026-11-09, UTC evening; all vendor documentation, Tier B for what the product emits)

Each entry records the URL as fetched, the page's own date where it shows one, and the sentences the table
cells rest on. Where a page did not state something, the cell says *not stated* rather than *absent*; a
cell is *absent* only where the vendor says so or where the documented schema has no place for the value.

## Google Vertex AI (arm B: not run, billing disabled on every project the account can list)

**Cloud Audit Logs for Vertex AI.** `https://docs.cloud.google.com/vertex-ai/docs/general/audit-logging`
(redirected from cloud.google.com; the page now titles itself for the "Gemini Enterprise Agent Platform";
no page date shown). Data Access logs are "disabled by default and written only when you explicitly
enable them"; `endpoints.generateContent`, `endpoints.streamGenerateContent`, `endpoints.predict`,
`endpoints.rawPredict`, `endpoints.countTokens`, `publishers.models.generateContent` and
`publishers.models.predict` are DATA_READ operations. An entry carries `protoPayload` (an `AuditLog` with
`serviceName=aiplatform.googleapis.com`), `AuthenticationInfo` (caller identity) and
`RequestMetadata.caller_ip`. The page says these operations "read or write user-provided data" and does not
say whether the request or response body is included. The Cloud Audit Logs overview
(`https://docs.cloud.google.com/logging/docs/audit`) adds: "Audit logging doesn't redact the caller's
principal email address for any access that succeeds or for any write operation"; "Except for BigQuery,
Data Access audit logs are disabled by default because they can generate large volumes of data"; enabling
them "might result in your Google Cloud project being charged for additional log usage". Neither page
documents token counts or cost in the audit entry.

**Gemini request-response logging to BigQuery.**
`https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/request-response-logging` (no page
date shown). Disabled by default; enabled per publisher model with `PublisherModelConfig.loggingConfig`
(`enabled`, `samplingRate` 0 to 1, `bigqueryDestination.outputUri`, `enableOtelLogging`), or per endpoint
with `predictRequestResponseLoggingConfig`. Supports `generateContent` and `streamGenerateContent` for
Gemini and `rawPredict`/`streamRawPredict` for Anthropic partner models. Columns: `endpoint`,
`deployed_model_id`, `logging_time`, `request_id`, `request_payload`, `response_payload`, `model`,
`model_version`, `api_method`, `full_request` (JSON), `full_response` (JSON), `metadata` (JSON, includes
request latency), `otel_log` (JSON, only with OpenTelemetry logging on). "No schema column identifies the
caller." Request-response pairs over the BigQuery Write API 10 MB row limit are not recorded. Token counts
are not a column, but Gemini's `generateContent` response body carries `usageMetadata`, so they would sit
inside `full_response` (inference from the API shape, not from this page). No cost column.

**State of the account at run time (read-only checks, `gcloud` 560.0.0, 2026-11-09):** five projects
listed, `billingEnabled: False` on each, no billing accounts, `aiplatform`, `logging` and `bigquery` APIs
enabled on `second-brain-fc-2026`, IAM `auditConfigs` absent (Data Access logs off). No Gemini call made.

## AWS Bedrock model invocation logging

`https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html` (no page date
shown). "Model invocation logging is disabled by default." Covers `Converse`, `ConverseStream`,
`InvokeModel`, `InvokeModelWithResponseStream` on the `bedrock-runtime` endpoint ("Calls made through other
endpoints, such as the same APIs on `bedrock-mantle`, are not currently captured"). Destinations: CloudWatch
Logs and S3, same account and Region. Log entry fields: `schemaType`, `schemaVersion`, `timestamp`,
`accountId`, `region`, `requestId`, `operation`, `modelId`, `identity.arn` ("The AWS STS or IAM ARN of the
principal that made the request ... Captured automatically"), `requestMetadata` (caller-supplied tags,
optional), `input.inputContentType`, `input.inputBodyJson` ("The request body sent to the model (up to 100
KB)"), `input.inputTokenCount`, `output.outputContentType`, `output.outputBodyJson` ("up to 100 KB"),
`output.outputTokenCount`. "Binary data (such as images) and JSON bodies larger than 100 KB are not
included inline" and go to S3 under the data prefix. No cost field; no session field (a conversation is
the caller's construct, so a session id exists only if the caller puts one in `requestMetadata`). Tool
definitions and tool-use blocks travel inside the Converse request/response bodies, so tool name and
arguments are present as part of `inputBodyJson`/`outputBodyJson` rather than as top-level fields.

## Azure OpenAI in Microsoft Foundry: diagnostic settings and metrics

Overview `https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/monitor-openai` (canonical
`foundry-classic/openai/how-to/monitor-openai`, `ms.date` 2025-11-06, `updated_at` 2026-05-12) and the
reference `https://learn.microsoft.com/en-us/azure/ai-foundry/openai/monitor-openai-reference` (`ms.date`
2026-05-19). Resource log categories for `Microsoft.CognitiveServices/accounts`: `Audit`,
`RequestResponse`, `Trace`, `AzureOpenAIRequestUsage`, `ManagedNetworkEvent`, all landing in the
`AzureDiagnostics` table; "Resource logs aren't collected and stored until you create a diagnostic
setting". The overview's sample query projects `TimeGenerated, _ResourceId, Category, OperationName,
DurationMs, ResultSignature, properties_s`. Neither page lists the `properties_s` sub-fields, and neither
page states that prompt or completion text appears in any log category; the metrics reference lists token
counters (`ProcessedPromptTokens`, `GeneratedTokens`, `TokenTransaction`, `InputTokens`, `OutputTokens`,
`cacheReadInputTokens`, `ephemeral5mInputTokens`, `ephemeral1hInputTokens`) with dimensions
`ApiName`, `ModelDeploymentName`, `ModelName`, `ModelVersion`, `Region`, `StreamType`, `StatusCode` and a
`FoundryModelEstimatedCost` metric (Preview, "an estimate and is not an invoice or billed charge"). Metrics
are aggregates per minute, not per request, so identity and session are *absent* from the metric path by
construction; the `RequestResponse` log has a caller IP in the common resource-log schema (`CallerIPAddress`
is a standard Azure resource-log column) but the Foundry pages do not state a user object id. Cells for
prompt text and response text are therefore *not stated* rather than *absent*.

## GitHub Copilot audit log

`https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-enterprise/review-audit-logs`
(no page date shown): "The audit log includes a record of: Changes to your Copilot plan, such as changes
to settings and policies or a user losing or receiving a license; Agent activity on the GitHub website."
"The audit log does not include client session data, such as the prompts a user sends to Copilot
locally." "The audit log retains events for the last 180 days." Search with `action:copilot`; agent
activity with `actor:Copilot`. The enterprise event reference
(`https://docs.github.com/en/enterprise-cloud@latest/admin/monitoring-activity-in-your-enterprise/reviewing-audit-logs-for-your-enterprise/audit-log-events-for-your-enterprise`)
lists the `copilot.*` events (seat, policy, plan, content-exclusion, clickwrap, memory opt-out) and the
common fields `@timestamp`, `action`, `actor`, `actor_id`, `business`, `org`, `repo`, `user`, `user_agent`,
`request_id`, `token_id`, `token_scopes`; none of the Copilot events carries prompt text, model, tokens or
cost. The agentic events reference (`https://docs.github.com/en/copilot/reference/agentic-audit-log-events`)
adds `actor_is_agent`, `agent_session_id` and `user` (the initiating person) for agent activity, and
describes a public-preview stream of "Copilot API usage records" (Enterprise Managed Users or data
residency) with `type` (request or response), `user_id`, `enterprise_id`, `endpoint`, `body` ("request or
response body (JSON-encoded string)"), `@timestamp`, `truncated` (1 MB limit), `event_id`,
`github_request_id`; model, tokens and cost are not stated for that stream. The table scores the audit log
proper; the preview API-usage stream is noted as a separate, opt-in path.

## ChatGPT Enterprise Compliance API

OpenAI's help-centre article (`https://help.openai.com/en/articles/9261474-...`) returned HTTP 403 to an
unauthenticated fetch on 2026-11-09, and search snippets from it say the API documentation requires being
"logged into your Enterprise workspace", so this column rests on the public announcement:
`https://openai.com/index/new-tools-for-chatgpt-enterprise/` (2024-07-18; also 403 to a direct fetch,
quoted here through SecurityWeek's same-day report
`https://www.securityweek.com/openai-rolls-out-compliance-api-and-integrations-for-chatgpt-enterprise/`):
the API provides "a record of time-stamped interactions, including conversations, uploaded files" and
covers "workspace GPT configuration and metadata, memories, and workspace users". Search snippets from the
help article (2026-11-09) add: a "new conversations logs system was released" on 2026-03-05, deprecating
the earlier stateful route; access is through a "workspace-scoped Admin key"; only a workspace owner can
grant the "Conversation messages" permission; events can take "up to 30 minutes (p99)" to appear and
user-deleted conversations remain available "for up to 30 days after deletion" (the last two from a
third-party connector guide, Tier C). So: user identity, conversation (session) id, prompt text and response
text are *documented*; model id is *not stated* in the sources reachable here; token counts and cost are
*not stated* and no public source describes them, so they are scored *not stated* rather than *absent*.
This column is the weakest-sourced in the table and should be re-checked from inside a workspace.

# CS0066 and CS0067, step by step: what the record could hold, and what this bench did with it

Inputs: ATLAS v2026.10 `employs_edges.csv` rows for AML.CS0066 and AML.CS0067 (step order as given there); R1's
`technique_artifact_ocsf.csv` for the crosswalk-route grade where R1 graded the technique (R1 covered the 27
Incidents only, so techniques that appear only in Exercises carry "not graded by R1" and a grade I made here from the
crosswalk row, Tier D); the OCSF 1.9.0 schema for the direct read. "Defender ground" follows R1's rule: not
Reconnaissance (TA0002), Resource Development (TA0003) or AI Attack Adaptation (TA0001). Maturity is the technique's
ATLAS v2026.10 `maturity` field; the draft essay should not call the Demonstrated ones Realized.

Grades: direct = an OCSF object or dedicated field denotes the same kind; generic = parent kind only; proxy = a
carrier field could hold a reference; none = nothing. "Here" = how this bench's corpus records the step
(`api_operation` and the field a rule reads), and the observed state of the single-step rule on it (three seeds, both
engines, from `coverage.json`).

## AML.CS0066 ZombieAgent (Exercise; Radware vs ChatGPT connectors, 2025-09-25)

| # | ATLAS step | Maturity | Defender ground | Crosswalk route → OCSF 1.9.0 (R1 grade) | Direct OCSF read | Here (op / field) | Single-step rule, state |
|---|---|---|---|---|---|---|---|
| 1 | T0065 LLM Prompt Crafting | Realized | no (TA0001) | d3f:DigitalMessage → `email` (generic) | none on victim ground | not planted | dark by position |
| 2 | T0079 Stage Capabilities | Realized | no (TA0003) | d3f:File → `file.path` (direct) | none on victim ground | not planted | dark by position |
| 3 | T0068 LLM Prompt Obfuscation | Realized | yes (TA0007) but acts on attacker content | d3f:DigitalMessage → `email` (generic) | `message_context.prompt_text` carries the text, nothing marks concealment | the fixture marker sits in `message_context_prompt_text` on the ingest event; no rule reads it | dark (out of scope by design: no text classification) |
| 4 | T0093 Prompt Infiltration via Public-Facing Application | Realized | yes (TA0004) | d3f:DigitalText → `message_context.prompt_text` (generic, profile only) | `api_activity` + `message_context` (profile) | `mail.fetch` with the content in `message_context_prompt_text` | a1_ingest_mail: NOISY (kind match; every inbox session fetches mail) |
| 5 | T0051.001 Indirect prompt injection (the T1698 step) | Realized | yes (TA0005) | d3f:DigitalMessage → `email` (generic) | same event as step 4; the schema has no "content became instruction" fact | same event as step 4 | same as step 4; the T1698 analytic AN2293 needs "instruction evidence" the record does not carry |
| 6 | T0080.000 Memory | Realized | yes (TA0006) | d3f:Database → `database.name` (direct, 6005) | `datastore_activity` 6005 or an `api_activity` row on a memory service | `memory.write` (planted, not truth) | no rule here; recorded as a row a hunt could read |
| 7 | T0053 AI Agent Tool Invocation | Demonstrated | yes (TA0012) | d3f:Application → `application.name` (direct) (not graded by R1; crosswalk row R101) | `api.operation` names the tool; `ai_agent` names the agent | every planted tool call | the tool kind alone is not a signal; every benign session invokes tools |
| 8 | T0085.001 AI Agent Tools (collection) | Demonstrated | yes (TA0009) | d3f:Application → `application.name` (direct) (not graded by R1; row R156) | `api.operation` = search/list; `api.request.data` holds the query as a blob | `mail.search`, `contacts.list` | a3_collect_mailbox: NOISY (kind match; 35% of benign inbox sessions search) |
| 9 | T0054 LLM Jailbreak (URL-dictionary bypass) | Realized | yes (TA0007) | no crosswalk row (class gap) → none | nothing marks "guard bypassed"; the shape shows as many short opens to one host | 24 `http.open` to one `.invalid` host in under 3 minutes | a7_url_burst (Sigma event_count, SQLite only): NOISY (benign docs crawls fire it) |
| 10 | T0086 Exfiltration via AI Agent Tool Invocation (the T1700 step) | Realized | yes (TA0010) | d3f:Application → `application.name` (direct) | `dst_endpoint.hostname` / `http_request.url` on the outbound call | same 24 `http.open` events; `dst_endpoint_hostname` off the allowlist | a5_outbound_offlist: NOISY (users do open off-allowlist links) |
| 11 | T0085.001 AI Agent Tools (contacts for propagation) | Demonstrated | yes (TA0009) | as step 8 | as step 8 | `contacts.list` (same rule as step 8) | as step 8 |
| 12 | T0143 LLM Prompt Propagation | Demonstrated | yes (TA0015) | d3f:DigitalMessage / d3f:DocumentFile → `email` / `file` (generic) (not graded by R1) | `mail.send` rows exist, but nothing marks that the body carries the prompt | `mail.send` × 3 (planted, not truth) | no rule here; a kind rule on `mail.send` would be noise by construction |

## AML.CS0067 Claude Code GitHub Action (Exercise; Microsoft Defender research, disclosed 2026-06-05)

| # | ATLAS step | Maturity | Defender ground | Crosswalk route → OCSF 1.9.0 (R1 grade) | Direct OCSF read | Here (op / field) | Single-step rule, state |
|---|---|---|---|---|---|---|---|
| 1 | T0095.000 Code Repositories (recon) | Realized | no (TA0002) | d3f:CodeRepository → `url.url_string` (proxy); d3f:Credential → `programmatic_credential.uid` (generic) | public-repo reads leave no victim record | not planted | dark by position |
| 2 | T0084.001 Tool Definitions | Demonstrated | no (TA0008 is Discovery; here on attacker side) | d3f:ApplicationConfiguration (parent row R152) → generic | none | not planted | dark by position |
| 3 | T0084.002 Activation Triggers | Demonstrated | no (as above) | as step 2 | none | not planted | dark by position |
| 4 | T0065 LLM Prompt Crafting | Realized | no (TA0001) | d3f:DigitalMessage → `email` (generic) | none | not planted | dark by position |
| 5 | T0093 Prompt Infiltration via Public-Facing Application | Realized | yes (TA0004) | d3f:DigitalText → `message_context.prompt_text` (generic, profile only) | the issue/PR body in `message_context.prompt_text` on the read | `issue.read` / `pr.read` with the content in `message_context_prompt_text` | a2_ingest_repo: NOISY (every CI-review session reads an issue or PR) |
| 6 | T0051.001 Indirect prompt injection (T1698) | Realized | yes (TA0005) | d3f:DigitalMessage → `email` (generic) | same event as step 5 | same event as step 5 | as step 5 |
| 7 | T0054 LLM Jailbreak (compliance framing, prefix removal) | Realized | yes (TA0007) | no crosswalk row → none | nothing in the record marks a refusal bypass | not a separate event; the prefix removal shows only in step 10's argument | dark as a step; its effect is what a6 matches |
| 8 | T0053 AI Agent Tool Invocation (Read on `/proc/self/environ`) | Demonstrated | yes (TA0005) | d3f:Application → `application.name` (direct) (not graded by R1) | `api.operation` = the tool; the path is inside `api.request.data` (blob) | `file.read` with `/proc/self/environ` in `api_request_data` | a4_read_procenv: DETECTED (content match on the one path the case study names) |
| 9 | T0098 AI Agent Tool Credential Harvesting | Demonstrated | yes (TA0013) | d3f:Credential / d3f:Email / d3f:WebFileResource / d3f:CodeRepository (generic; not graded by R1) | the response blob would hold the environment; nothing types "credential returned" | the same `file.read` row's `api_response_data` (fixture, no values) | same event as step 8 |
| 10 | T0085.002 Conversation Context and Memory (emit de-prefixed key) | Demonstrated | yes (TA0009) | d3f:DigitalMessage → `email` (generic; crosswalk keep row) | the emitted text sits in a tool argument or `message_context.response_text`; no credential-shape field | `web.fetch` query string and `bash.exec` argument carry the fixture `api03-…` string | a6_credential_shape: NOISY by the frozen truth (its bash.exec hits were planted but not marked truth); DETECTED when the channel events count (supplementary) |
| 11 | T0086 Exfiltration via AI Agent Tool Invocation (T1700) | Realized | yes (TA0010) | d3f:Application → `application.name` (direct) | `dst_endpoint.hostname` / `http_request.url` on the outbound call | one `web.fetch` to an off-allowlist `.invalid` host | a5_outbound_offlist: NOISY |

## Reading the two tables

Six of the twelve ZombieAgent steps and five of the eleven Claude Code steps are on defender ground and leave a row
in this corpus. Of those rows, the ones that fire cleanly on their own are the ones that match on the attack's own
content (the `/proc/self/environ` path, the de-prefixed key marker), which is the same split R1 found across eight
Incident techniques. The steps the two new ATT&CK IDs name, T0051.001 for T1698 and T0086 for T1700, land on
generic carriers (an ingest event that every benign session also has, and an outbound call whose only distinguishing
fact is the destination), which is why the session-level and content-qualified rules in `RESULTS.md` exist.

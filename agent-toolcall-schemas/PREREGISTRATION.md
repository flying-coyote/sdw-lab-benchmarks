---
type: benchmark-preregistration
title: "R2: one MCP tools/call, three schemas (OCSF ai_operation, OTel gen_ai/mcp, OWASP AOS)"
created: 2026-11-09
area: R2-toolcall-three-schemas
status: frozen-by-agent-before-run (not owner-reviewed)
---

# Pre-registration: one `tools/call`, three schemas

Written before any capture, mapping or timing was run. The sha256 of this file is recorded at the top of
`RESULTS.md`. Anything changed after the freeze is logged in RESULTS.md under "Deviations".

## Question

When one real MCP `tools/call` exchange (request, response, and the `tools/list` entry that advertised the
tool) is recorded in each of three schemas, which facts does each schema keep in a typed attribute, keep only
inside an untyped container, push to `unmapped` or a custom namespace, or drop? And what does the
unmapped-JSON shape cost at query time compared with a typed shape, on five hunt queries fixed in advance?

## Schemas under test (exact versions, pinned by commit)

| Schema | Version pinned | Shape used for a tool call |
|---|---|---|
| OCSF (main) | `ocsf/ocsf-schema` main @ `d1cbd619d76b7e1b8463785cd79beaaf4e3c2bdf` (version.json `1.10.0-dev`, 2026-11-09); 1.9.0 is the latest release on schema.ocsf.io | API Activity 6003 + `ai_operation` profile (`ai_agent`, `ai_capability`, `ai_status`, `message_context`, `delegation`); tool arguments and result in `api.request.data` / `api.response.data` (`json_t`) |
| OCSF draft #1754 | PR head `davemcatcisco/ocsf-schema@08d6f530bfcda1675f54dc6351624051efb368b4` (open draft, updated 2026-11-09) | `ai_agent_activity` (Application category, uid 9), activity Tool Use, `ai_agent_tool_use_info` (`name`, `is_pre_occurrence`, `ai_tool_input` json_t, `ai_tool_response` json_t). Scored as a second OCSF variant. |
| OpenTelemetry GenAI + MCP semantic conventions | `open-telemetry/semantic-conventions-genai` main @ `e6658f14c9d9ea0760825f029cb82e7673f48fab` (2026-11-06; manifest schema_url `gen-ai-dev/1.42.0-dev`, depends on semconv `v1.45.0`; every attribute `stability: development`) | MCP client span `tools/call {tool}` with `mcp.*`, `jsonrpc.*`, `gen_ai.*`, `rpc.response.status_code`, `error.type`, `network.*` attributes; `gen_ai.tool.call.arguments` / `.result` are `type: any`, opt-in |
| OWASP Agent Observability Standard (AOS) | `OWASP/www-project-agent-observability-standard` main @ `9a9bc37ca05531735a70ca17042e3a480c41fab7` (2025-07-17; no tagged release) `docs/spec/trace/extend_ocsf.md` | OCSF API Activity 6003 with `actor.user` (type_id 99 "AI Agent"), `api.service`, `api.operation`, and agent/tool/step context in `unmapped.aos.*` (the "Agent with Tool Execution" example) |

Instrument versions: MCP Python SDK `mcp==2.3.0` (server class `MCPServer`, LATEST_PROTOCOL_VERSION
`2026-07-28`), `duckdb==1.5.3`, `pyarrow==23.0.1`, Python 3.12.3. The lab has no DuckDB MCP server under
`/tmp/claude-1000/lab-ai-research` (the only MCP server there is `security-context-graph/scg_mcp.py`, a graph
server), so the instrument is a minimal reference server written on the SDK, backed by an in-memory DuckDB.

## Instrument

1. `server.py`: an `MCPServer` named `sdw-lab-duckdb` v0.1.0 over stdio, seeded synthetic tables, five
   tools with MCP annotations so the `ai_capability` hint attributes have something to carry:
   `list_tables` (read-only, idempotent), `describe_table` (read-only), `run_query` (read-only, rejects
   non-SELECT), `count_failed_logins` (read-only, structured output), `export_table` (destructive, writes
   Parquet into a sandbox directory).
2. `proxy.py`: a line-level stdio tee that sits between the SDK client and the server process and writes
   every JSON-RPC message in both directions to `capture/wire.jsonl` with a `time.monotonic_ns()` stamp.
   The capture is the real wire traffic between the SDK client and the SDK server.
3. `capture.py`: an SDK `ClientSession` that runs `initialize`, `tools/list`, then exactly 10 `tools/call`
   requests: 2 metadata calls, 3 `run_query` (one valid, one SQL syntax error, one rejected `DROP`),
   2 `count_failed_logins`, 1 `export_table`, 1 `describe_table` on a missing table, and 1 call to a tool
   that does not exist. No model is in the loop; the agent and model identity that an agent runtime would
   add are supplied from a fixed harness config and labelled "harness-supplied" in every output.
4. `map_schemas.py`: deterministic mappers, one per schema, from each captured call (request + response +
   the advertising `tools/list` entry + session context) to a record in that schema. Each mapper is driven by
   a declared spec table (fact -> target path -> class). The script asserts the value is present at the
   declared path in the emitted record, so the loss table is generated from emitted records, not hand-typed.
   OCSF records are checked attribute-by-attribute against the pinned OCSF main object definitions.

## Fact inventory and classification rubric

The fact inventory is every distinct field observed on the wire for a `tools/call` exchange plus the
`tools/list` entry for the called tool, plus four context facts an agent runtime knows (agent id, agent name,
model, session/conversation), plus call duration measured by the proxy. Each fact gets one class per schema:

- **TYPED**: carried by an attribute the schema defines with a specific type (string, int, bool, enum,
  timestamp, or a defined object), so an engine can filter it as a column.
- **BLOB**: carried, but only inside an attribute the schema defines as untyped (`json_t`, OTel `any`, or a
  free-text string holding serialized JSON), so a query must parse it.
- **UNMAPPED**: carried only in `unmapped` (OCSF) or in a custom attribute name outside the convention
  (OTel, prefixed `sdw.`), so it exists but is not part of the schema's contract.
- **DROPPED**: no sensible place; omitted.

A fact is TYPED only if the attribute's semantics match the fact (no stuffing a tool name into an unrelated
string field). Where the producer has a reasonable choice between a typed attribute and `unmapped`, the
mapper follows the schema's own documentation or example (for AOS, its published 6003 example).

## Hypotheses (and what would prove each wrong)

- **H1 (OCSF main vs AOS)**: OCSF main with the `ai_operation` profile types more of the tool-call facts than
  AOS on OCSF, and AOS puts at least half of the agent- and tool-specific facts (tool name, tool annotations,
  agent model, session, step, arguments, result, isError) in `unmapped`. *Wrong if* AOS types as many facts as
  OCSF main, or puts fewer than half of those facts in `unmapped`.
- **H2 (OTel)**: OTel types the protocol-level facts (method, JSON-RPC request id, protocol version, session id,
  tool name, error code) at least as completely as OCSF main, and has no typed attribute for the server's tool
  annotations (readOnly/destructive/idempotent/openWorld hints) or for an input-schema fingerprint. *Wrong if*
  OTel types fewer protocol-level facts than OCSF main, or has typed annotation attributes.
- **H3 (arguments and results)**: no schema types per-tool arguments or results; all three carry them as BLOB
  (or UNMAPPED for AOS). *Wrong if* any schema has typed attributes for individual argument values.
- **H4 (query cost, primary)**: at 1M synthetic calls, the AOS-style layout (tool name, session and status in an
  `unmapped` JSON string) has median warm latency at least 3x the OCSF typed layout on Q1, Q3, Q4 and Q5.
  *Wrong if* the ratio is under 1.5x on any of those four, or if the difference is inside the pooled CV.
  The OTel map-attributes layout is predicted to sit between the two.
- **H4b (null control)**: Q2 hunts inside the arguments, which are JSON in every layout, so the ratio is
  predicted within 1.5x across all three layouts. *Wrong if* any layout is more than 1.5x slower on Q2.
- **H5 (size)**: the AOS layout is at least 1.3x the OCSF typed layout on disk at the same codec and row group.
  *Wrong if* under 1.3x.

## Query-cost instrument

`gen_corpus.py` generates N synthetic tool calls from one seeded RNG (`lib.common.MASTER_SEED`-derived sub-seed,
fixed epoch anchor) with a fixed distribution over 400 agents, 6 servers, 18 tools, ~20k sessions, an ~4%
error rate, and argument JSON whose shape depends on the tool. The same logical calls are written three ways:

- **L1 typed (OCSF 6003 + ai_operation)**: nested structs `ai_agent`, `ai_capability` (with `service`,
  `transaction_uid`, hint booleans), `ai_status`, `session`, `api.request.data` / `api.response.data` as JSON
  strings, `status_id`, `time`.
- **L2 attributes map (OTel span as commonly landed in a lake)**: `trace_id`, `span_id`, `start_time`,
  `duration_ns`, `span_name`, and `attributes MAP(VARCHAR, VARCHAR)`, the shape the OpenTelemetry Collector
  ClickHouse exporter uses for span attributes.
- **L3 AOS (OCSF 6003 base + `unmapped` JSON string)**: typed `actor.user.uid/name`, `api.operation`,
  `api.service.name`, `status_id`, `time`; tool name, session, step, isError, arguments and outputs inside an
  `unmapped` VARCHAR holding the AOS JSON.

Parity: all three written by DuckDB `COPY ... (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 122880)`
ordered by time; codec and row-group count read back from `parquet_metadata()` before timing.

Five hunt queries, fixed here, each returning one comparable answer that must be identical across layouts:

- **Q1 tool by agent**: count of `export_table` calls by agent `agent-0042`.
- **Q2 argument hunt (null control)**: count of `run_query` calls whose `sql` argument matches
  `(?i)copy\s.+\sto\s` (exfil-shaped SQL).
- **Q3 tool breadth on errors**: top 10 agents by count of distinct tools among errored calls (answer = the
  ordered list of agent, count pairs; ties broken by agent id).
- **Q4 failure bursts**: number of sessions with at least 3 errored calls.
- **Q5 off-allowlist use**: count of calls whose (server name, tool name) pair is not in a 12-row allowlist
  table (anti-join).

Timing: warm/hot only (no root page-cache purge, labelled as such), `lib.common.time_trials` with 2 warmups and
7 timed trials (`time.perf_counter`, monotonic), repeated in 3 separate processes, so each (layout, query) has
21 samples. Reported: median, min, max, CV per pass and pooled; ratios L2/L1 and L3/L1. On-disk bytes and write
time reported separately. Primary scale 1M rows; a 100k scale point is also run to check the ratio does not
flip with scale (methodology §9).

## Metrics

Loss table counts per schema (TYPED / BLOB / UNMAPPED / DROPPED over the fact inventory); per-fact class table;
query latency stats as above; on-disk bytes; answer equality across layouts.

## Stop rule

One capture run, one mapping run, one timing run of 3 passes at each scale. No query, layout or mapping is
re-tuned after seeing timings. If answers disagree across layouts, that is a bug in my generator or SQL; the fix
is logged as a deviation and the whole timing run is repeated once. If pooled CV exceeds the measured delta for a
query, that query's ratio is reported as not distinguishable.

## Cost

$0. Local CPU only on the Beelink (Ryzen 7 5800H, WSL2), no paid API calls, no model calls. Disk under 1 GB.

## Known limits, declared in advance

- stdio transport only; the review also asked for one Streamable-HTTP server, which this run does not capture
  (HTTP adds transport and session-header facts, so the stdio inventory undercounts transport facts).
- Agent and model identity are harness-supplied, since no agent runtime is in the loop.
- AOS is scored on its published OCSF example; a producer could legally put more AOS facts into typed OCSF
  attributes, and that would change its counts.
- The query-cost corpus is synthetic; latencies are one machine, warm cache, one engine (DuckDB). Ratios within
  this run are the claim, not absolute times.

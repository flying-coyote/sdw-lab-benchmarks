---
type: benchmark-preregistration
title: "T8a: MCP logging before and after 2026-07-28, stdio and Streamable HTTP, captured at client, server and proxy"
created: 2026-11-09
area: T8a-mcp-before-after
status: frozen-by-agent-before-run (not owner-reviewed)
---

# Pre-registration: what an MCP exchange leaves behind, before and after the 2026-07-28 revision

Written before any fixture was run. The sha256 of this file and the freeze time are recorded at the top of
`RESULTS.md`. Anything changed after the freeze is logged in `RESULTS.md` under "Deviations".

## Question

For one stdio MCP server and one Streamable-HTTP MCP server, each driven by the official Python SDK release that
implements MCP protocol revision 2025-11-25 and by the release that implements 2026-07-28, which facts about a
`tools/call` exchange are observable at each of four capture points (the wire as seen by a proxy, the client
process, the server's stderr, and an OpenTelemetry exporter at either end), through which channel (protocol
message, HTTP header, stderr line, OTel span attribute, in-protocol `notifications/message`), and which facts move
or disappear between the two revisions? Secondary: which of those moves are the protocol revision and which are
the SDK rewrite that shipped alongside it?

## Why two comparisons, not one

`mcp` 1.30.0 (PyPI 2026-09-07) speaks revisions up to 2025-11-25 and cannot speak 2026-07-28. `mcp` 2.3.0 (PyPI
2026-10-02) speaks both: `mcp.Client(mode="legacy")` runs the `initialize` handshake at 2025-11-25, and
`mcp.Client(mode="auto")` (the default) probes `server/discover` and adopts 2026-07-28 when the server answers it
(`mcp/client/client.py` lines 336-341, `mcp/client/_probe.py`). So a 1.30.0-vs-2.3.0 comparison confounds the
protocol change with the SDK rewrite (OTel middleware, `_meta` stamping and the per-request logging gate are 2.x
code regardless of era). Methodology §1 (configuration parity): hold the SDK constant for the revision comparison.

| Arm | Client | Server | Revision expected on the wire | What the arm isolates |
|---|---|---|---|---|
| A | `mcp` 1.30.0 `ClientSession` | `mcp` 1.30.0 `FastMCP` | 2025-11-25 | the "before" people actually run |
| B | `mcp` 2.3.0 `Client(mode="legacy")` | `mcp` 2.3.0 `MCPServer` | 2025-11-25 | same SDK as C, old revision (control) |
| C | `mcp` 2.3.0 `Client(mode="auto")` | `mcp` 2.3.0 `MCPServer` | 2026-07-28 | the "after" |
| C-log | `mcp` 2.3.0 `Client(mode="auto", log_level="info")` | `mcp` 2.3.0 `MCPServer` | 2026-07-28 | the per-request logging opt-in (SEP-2575) |
| D | `mcp` 2.3.0 `Client(mode="auto")` | `mcp` 1.30.0 `FastMCP` | 2025-11-25 after fallback | what `server/discover` gets from a server that does not implement it |

B vs C is the protocol finding. A vs B is the SDK finding. Every fact is reported in both columns.

Each arm runs on both transports (stdio, Streamable HTTP), so 10 cells. Each cell runs 3 times. Two extra
single-run checks, both on stdio: (i) B and C with the OpenTelemetry API installed but no `TracerProvider`
configured, to answer "does anything reach an exporter by default"; (ii) C with
`opentelemetry-instrumentation-httpx` pinned in the server venv, to test whether trace context survives a
server-to-backend HTTP hop (separable sub-arm; if the package cannot be installed the sub-arm is recorded as not
run, and the bench finishes without it).

## Instrument

- `server_v1.py` (mcp 1.30.0, `FastMCP`) and `server_v2.py` (mcp 2.3.0, `MCPServer`): the same fixture server on
  both SDKs, named `t8a-fixture`, version `0.1.0`, defaults untouched (log level INFO, `json_response=False`,
  stateful HTTP, host 127.0.0.1). Tools, all labelled test fixtures, none carrying attack content:
  `echo(text)` (read-only annotations), `scan.v2-beta(target)` (a tool name using every character class SEP-986
  allows, `^[A-Za-z0-9._-]{1,128}$`, for the `Mcp-Name` fidelity question), `fail_tool(reason)` (raises
  `ValueError`, exercising the masked `Error executing tool` path), `log_then_echo(text)` (calls `ctx.info()` twice
  then returns, exercising in-protocol logging), `fetch_backend(url)` (an `httpx.get` to a localhost listener, for
  the trace-hop sub-arm only). One static resource `fixture://note`.
- Fixed call script, identical in every cell: `tools/list`; `echo`; `scan.v2-beta`; `fail_tool`; a call to a tool
  that does not exist (`no_such_tool`); `echo` with the required argument missing; `log_then_echo`; `tools/list`
  again (does the 2.x client cache suppress the second wire call, SEP-2549); `resources/read fixture://note`;
  `resources/read fixture://missing` (the -32002 to -32602 change); `fetch_backend` (sub-arm cells only).
- Capture points per run:
  1. Wire. stdio: `proxy_stdio.py`, the R2 line-level tee (`agent-toolcall-schemas/proxy.py`), every JSON-RPC
     line in both directions with `time.monotonic_ns()`. HTTP: `proxy_tcp.py`, a raw TCP tee bound to
     127.0.0.1 that forwards bytes unchanged and logs every chunk with direction and `monotonic_ns`; the byte log
     is parsed afterwards with `h11` 0.16.0, so SSE framing is never touched in flight. Both ends are localhost.
  2. Client process. `client.jsonl`: what the SDK client object exposes after each call (negotiated protocol
     version, server info, result, `isError`, exception type and JSON-RPC error code) plus every
     `notifications/message` delivered to the `logging_callback`.
  3. Server stderr, redirected to `server.stderr` with no formatter added. Lines are attributed afterwards to
     the module that logged them (uvicorn access log, `mcp.server.lowlevel.server`, `mcp.server.runner`,
     `mcp.server.mcpserver.*`, Python warnings) and reported per source.
  4. OpenTelemetry. `opentelemetry-sdk` 1.45.2 `TracerProvider` with a JSON-lines file exporter configured in
     both processes by the harness (an operator action, declared as such) to `server.otel.jsonl` and
     `client.otel.jsonl`. Check (i) above runs without the provider.
  5. Backend listener (`backend.py`, sub-arm only): logs the request headers it received.
- Thread cap: the runner and every child run under `taskset -c 0-3 nice -n 10`. Timings are incidental to this
  bench and are taken under contention from other benches on the host; they are reported as medians with CV
  and no latency claim is made from them.

## Fact inventory

The R2 inventory (`agent-toolcall-schemas/map_schemas.py`, FACTS list) is reused where it applies, and these are
added because the revision moves or introduces them:

| Fact | Where the revision says it lives (2026-07-28 changelog) |
|---|---|
| `initialize` request/result and `notifications/initialized` | removed (SEP-2575) |
| `server/discover` request/result (`supportedVersions`, `capabilities`, `instructions`) | added (SEP-2575) |
| per-request `_meta` protocol version, `clientInfo`, client capabilities | added (SEP-2575) |
| per-result `_meta` `serverInfo` | added (SEP-2575, SHOULD) |
| `Mcp-Session-Id` HTTP header | removed (SEP-2567) |
| `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` HTTP headers | `Mcp-Method`/`Mcp-Name` added (SEP-2243) |
| `traceparent`/`tracestate` in `_meta` | documented (SEP-414) |
| `notifications/message` log entries; `logging/setLevel`; `_meta` `io.modelcontextprotocol/logLevel` | deprecated / removed / added (SEP-2577, SEP-2575) |
| `ttlMs`, `cacheScope` on list results | added (SEP-2549) |
| JSON-RPC error code for a missing resource | -32002 to -32602 |
| JSON-RPC error code or `isError` for an unknown tool, for invalid arguments | (observed) |
| stderr lines per request, per failure, per deprecation | (observed) |
| OTel span per request, attribute set, parent linkage client to server | (observed) |

Per cell the deliverable is a presence matrix: fact × capture point, with the channel named. The score for a
cell is the set of facts reachable at each capture point; "moved" means reachable in both B and C but at a
different point or through a different channel, "disappeared" means reachable in B and not in C, "appeared"
means the reverse. For facts that have an OCSF `ai_operation` path in the R2 `OCSF_MAIN` spec the R2 class
(TYPED / HASHED / BLOB / UNMAPPED / DROPPED) is carried over by citation; new facts get an OCSF-main path and
class in RESULTS, with the judgment calls named.

## Hypotheses, each with what would prove it wrong

- H1 (wire shape). In C the wire carries no `initialize` and no `notifications/initialized`, every request's
  `params._meta` carries `io.modelcontextprotocol/protocolVersion` = `2026-07-28` and a `clientInfo`, and every
  result carries `_meta` `serverInfo`. In A and B the wire carries `initialize` and no per-request `_meta`
  stamp. Wrong if any C request lacks the stamp, or any C exchange includes `initialize`.
- H2 (sessions over HTTP). In A and B the proxy sees `Mcp-Session-Id` on the `initialize` response and on every
  later request; in C it sees none. Wrong if C carries the header or A/B omit it.
- H3 (routing headers). In C every HTTP POST carries `MCP-Protocol-Version`, `Mcp-Method` and, for `tools/call`,
  `Mcp-Name` equal to the body's tool name; A carries only `MCP-Protocol-Version` (after `initialize`) and the
  `tools/list`/`tools/call` methods are recoverable only from the body. Pre-registered uncertainty for B: the
  2.3.0 `send_request` stamps `Mcp-Name` for name-bearing requests regardless of mode (`client/session.py`
  lines 566-571), so B may carry `Mcp-Name` without `Mcp-Method`; if it does, the gateway hook for the tool
  name is an SDK fact, not a revision fact, and RESULTS says so. `scan.v2-beta` is header-safe ASCII so
  `Mcp-Name` carries it verbatim; wrong if the header value differs from the body name.
- H4 (stderr). A's server stderr carries one INFO line per request (`Processing request of type …`,
  `lowlevel/server.py` line 733) plus the tool-failure line; B and C carry no per-request line at INFO and the
  same `Tool %r failed` INFO line, so the per-request stderr record disappears with the SDK (A to B), not the
  revision (B to C). Wrong if B and C differ from each other on per-request lines, or if 2.3.0 logs one.
- H5 (OTel). A emits zero spans at either end. B and C each emit one SERVER span per inbound request with
  `mcp.method.name`, `mcp.protocol.version`, `jsonrpc.request.id`, and for `tools/call` `gen_ai.operation.name`
  and `gen_ai.tool.name`, plus one CLIENT span per outbound request, and the server span's parent is the client
  span (trace context injected into `_meta` as `traceparent`). Wrong if B differs from C on span count or
  attribute set, if A emits a span, or if the server span is not a child of the client span.
- H6 (OTel by default). With the OTel API importable but no `TracerProvider` configured (check i), the wire
  carries no `traceparent` and nothing is exported, in B and C alike. Wrong if `traceparent` appears.
- H7 (in-protocol logging). A delivers both `ctx.info()` messages as `notifications/message` without any
  `logging/setLevel` (1.30.0 `send_log_message` has no level gate). B delivers them too. C delivers none by
  default and C-log delivers both. Wrong if C (default) delivers any, or C-log delivers none.
- H8 (`server/discover` against a 2025-era server, arm D). stdio: the 1.30.0 server answers `-32601` method
  not found, the client falls back to `initialize`, and the negotiated version is 2025-11-25. HTTP: the 1.30.0
  server rejects the pre-session POST at the HTTP layer (4xx, no session) or with `-32601`, and the fallback
  lands on 2025-11-25. Wrong if the connection fails, or lands on a different version. The exact wire exchange
  is recorded either way.
- H9 (error codes). Missing resource: A and B return `-32002`, C returns `-32602`. Unknown tool and invalid
  arguments: all arms return a `CallToolResult` with `isError: true` (not a JSON-RPC error) and the client sees
  the cause only as text. Wrong if any arm uses a JSON-RPC error for the unknown tool, or C keeps `-32002`.
- H10 (cache, `ttlMs`). C's `tools/list` result carries `ttlMs` and `cacheScope`; with the default `ttlMs` of 0
  the second `tools/list` still reaches the wire. A and B carry neither field. Wrong if C omits them or the
  second list is suppressed.
- H11 (trace hop, sub-arm). Without httpx instrumentation the backend listener sees no `traceparent`; with
  `opentelemetry-instrumentation-httpx` it sees one whose trace id equals the server span's. Wrong if the
  uninstrumented hop carries it or the instrumented one does not.
- H12 (repeatability). The presence matrix is identical across the 3 repeats of every cell. Any difference is
  reported per cell.

## Exact versions

Python 3.12.3. `venv-v1`: `mcp==1.30.0` (PyPI 2026-09-07), `opentelemetry-sdk==1.45.2`, `opentelemetry-api==1.45.2`,
`starlette==1.10.0`, `uvicorn==0.54.0`, `httpx==0.28.1`, `h11==0.16.0`. `venv-v2`: `mcp==2.3.0` and
`mcp-types==2.3.0` (PyPI 2026-10-02), `opentelemetry-sdk==1.45.2`, `opentelemetry-api==1.45.2`,
`starlette==1.10.0`, `uvicorn==0.54.0`, `httpx2==2.16.0` (the 2.x client's HTTP stack), `httpx==0.28.1` (for the
fixture tool), `h11==0.16.0`. Full `pip freeze` in `requirements-v1.txt` and `requirements-v2.txt`. Proxies,
parser and scorer run under `venv-v2`. Host: Beelink, AMD Ryzen 7 5800H, WSL2 6.6.87.2, 14 threads, 47 GiB,
Docker not used (every process is a local Python process bound to 127.0.0.1).

## Metrics

1. Presence matrix per cell (fact × capture point × channel).
2. Diff tables B→C (revision) and A→B (SDK): moved / disappeared / appeared, with counts.
3. Counts per cell: wire messages, HTTP requests, stderr lines by source, spans by end, log notifications.
4. Incidental: per-call round trip (client-side `perf_counter_ns`), median and CV over 3 repeats, labelled
   "under contention", no claim.

## Stop rule and cost cap

Spend: $0 (local only). Wall time cap: 3 hours from freeze. A cell is abandoned after 3 failed server starts or
a single probe/handshake hang over 30 s, recorded as a deviation, and the bench reports the remaining cells.
No retries that are not logged.

## Safety and scope

Defensive measurement. No attack payloads, no exploit code, no credentials; the only planted inputs are an
unusual-but-valid tool name, a deliberately failing tool, a missing tool, a missing argument and a missing
resource URI, all labelled fixtures. Every listener binds to 127.0.0.1. Nothing about any employer.

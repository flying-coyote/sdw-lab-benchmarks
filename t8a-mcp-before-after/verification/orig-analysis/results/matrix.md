# Presence matrix (rep 1 of each cell; stability in stability.md)

## stdio

| fact | A-stdio | B-stdio | C-stdio | Clog-stdio | D-stdio |
|---|---|---|---|---|---|
| negotiated version (client) | 2025-11-25 | 2025-11-25 | 2026-07-28 | 2026-07-28 | 2025-11-25 |
| client API | ClientSession | Client | Client | Client | Client |
| wire: initialize requests | 1 | 1 | 0 | 0 | 1 |
| wire: notifications/initialized | 1 | 1 | 0 | 0 | 1 |
| wire: server/discover requests | 0 | 0 | 1 | 1 | 1 |
| wire: server/discover outcome | None | None | result supportedVersions=['2026-07-28'] instructions=yes ttlMs=0 cacheScope=private serverInfo=yes | result supportedVersions=['2026-07-28'] instructions=yes ttlMs=0 cacheScope=private serverInfo=yes | error -32602 Invalid request parameters |
| wire: JSON-RPC requests | 11 | 11 | 11 | 11 | 12 |
| wire: requests carrying _meta protocolVersion | 0 | 0 | 11 | 11 | 1 |
| wire: requests carrying _meta clientInfo | 0 | 0 | 11 | 11 | 1 |
| wire: requests carrying _meta logLevel | 0 | 0 | 0 | 10 | 0 |
| wire: requests carrying _meta traceparent | 0 | 10 | 11 | 11 | 11 |
| wire: JSON-RPC results | 10 | 10 | 10 | 10 | 10 |
| wire: results carrying _meta serverInfo | 0 | 0 | 10 | 10 | 0 |
| wire: tools/list requests (2 issued) | 2 | 2 | 2 | 2 | 2 |
| wire: tools/list result has ttlMs | False | False | True | True | False |
| wire: tools/list ttlMs value | None | None | 0 | 0 | None |
| wire: tools/list cacheScope | None | None | private | private | None |
| wire: fail_tool outcome | isError=True text='Error executing tool fail_tool: fixture raised: fixture failure' | isError=True text='Error executing tool fail_tool' | isError=True text='Error executing tool fail_tool' | isError=True text='Error executing tool fail_tool' | isError=True text='Error executing tool fail_tool: fixture raised: fixture failure' |
| client sees fail_tool cause | True | False | False | False | True |
| wire: unknown tool outcome | isError=True text='Unknown tool: no_such_tool' | isError=True text='Unknown tool: no_such_tool' | isError=True text='Unknown tool: no_such_tool' | isError=True text='Unknown tool: no_such_tool' | isError=True text='Unknown tool: no_such_tool' |
| wire: missing-argument outcome | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' |
| wire: missing resource outcome | jsonrpc error 0 | jsonrpc error -32602 | jsonrpc error -32602 | jsonrpc error -32602 | jsonrpc error 0 |
| wire: notifications/message | 2 | 2 | 0 | 2 | 2 |
| client: log notifications delivered | 2 | 2 | 0 | 2 | 2 |
| wire: logging/setLevel | 0 | 0 | 0 | 0 | 0 |
| stderr: non-empty lines | 11 | 45 | 45 | 45 | 105 |
| stderr: lines by class | per_request=10, tool_outcome=1 | deprecation_warning=4, other=1, tool_outcome=3, traceback=37 | deprecation_warning=4, other=1, tool_outcome=3, traceback=37 | deprecation_warning=4, other=1, tool_outcome=3, traceback=37 | other=32, per_request=10, tool_outcome=1, traceback=62 |
| stderr: one line per request | True | False | False | False | True |
| stderr: tool name on failure | False | True | True | True | False |
| stderr: failure cause | False | True | True | True | False |
| stderr: MCPDeprecationWarning | False | True | True | True | False |
| OTel server exporter | configured | configured | configured | configured | configured |
| OTel server spans | 0 | 12 | 11 | 11 | 0 |
| OTel server attribute keys | [] | error.type, gen_ai.operation.name, gen_ai.tool.name, jsonrpc.request.id, mcp.method.name, mcp.protocol.version, rpc.response.status_code | error.type, gen_ai.operation.name, gen_ai.tool.name, jsonrpc.request.id, mcp.method.name, mcp.protocol.version, rpc.response.status_code | error.type, gen_ai.operation.name, gen_ai.tool.name, jsonrpc.request.id, mcp.method.name, mcp.protocol.version, rpc.response.status_code | [] |
| OTel server spans with remote parent | 0 | 11 | 11 | 11 | 0 |
| OTel server error.type values | {} | -32602=1, tool_error=3 | -32602=1, tool_error=3 | -32602=1, tool_error=3 | {} |
| OTel server: tool arguments on span | False | False | False | False | False |
| OTel client exporter | configured | configured | configured | configured | configured |
| OTel client spans | 0 | 11 | 11 | 11 | 12 |
| OTel client attribute keys | [] | error.type, jsonrpc.request.id, mcp.method.name, rpc.response.status_code | error.type, jsonrpc.request.id, mcp.method.name, rpc.response.status_code | error.type, jsonrpc.request.id, mcp.method.name, rpc.response.status_code | error.type, jsonrpc.request.id, mcp.method.name, rpc.response.status_code |
| OTel: trace ids shared client/server | 0 | 11 | 11 | 11 | 0 |

## http

| fact | A-http | B-http | C-http | Clog-http | D-http |
|---|---|---|---|---|---|
| negotiated version (client) | 2025-11-25 | 2025-11-25 | 2026-07-28 | 2026-07-28 | 2025-11-25 |
| client API | ClientSession | Client | Client | Client | Client |
| wire: initialize requests | 1 | 1 | 0 | 0 | 1 |
| wire: notifications/initialized | 1 | 1 | 0 | 0 | 1 |
| wire: server/discover requests | 0 | 0 | 1 | 1 | 1 |
| wire: server/discover outcome | None | None | result supportedVersions=['2026-07-28'] instructions=yes ttlMs=0 cacheScope=private serverInfo=yes | result supportedVersions=['2026-07-28'] instructions=yes ttlMs=0 cacheScope=private serverInfo=yes | no JSON-RPC response (HTTP 400) |
| wire: JSON-RPC requests | 11 | 11 | 11 | 11 | 12 |
| wire: requests carrying _meta protocolVersion | 0 | 0 | 11 | 11 | 1 |
| wire: requests carrying _meta clientInfo | 0 | 0 | 11 | 11 | 1 |
| wire: requests carrying _meta logLevel | 0 | 0 | 0 | 10 | 0 |
| wire: requests carrying _meta traceparent | 0 | 10 | 11 | 11 | 11 |
| wire: JSON-RPC results | 10 | 10 | 10 | 10 | 10 |
| wire: results carrying _meta serverInfo | 0 | 0 | 10 | 10 | 0 |
| wire: tools/list requests (2 issued) | 2 | 2 | 2 | 2 | 2 |
| wire: tools/list result has ttlMs | False | False | True | True | False |
| wire: tools/list ttlMs value | None | None | 0 | 0 | None |
| wire: tools/list cacheScope | None | None | private | private | None |
| wire: fail_tool outcome | isError=True text='Error executing tool fail_tool: fixture raised: fixture failure' | isError=True text='Error executing tool fail_tool' | isError=True text='Error executing tool fail_tool' | isError=True text='Error executing tool fail_tool' | isError=True text='Error executing tool fail_tool: fixture raised: fixture failure' |
| client sees fail_tool cause | True | False | False | False | True |
| wire: unknown tool outcome | isError=True text='Unknown tool: no_such_tool' | isError=True text='Unknown tool: no_such_tool' | isError=True text='Unknown tool: no_such_tool' | isError=True text='Unknown tool: no_such_tool' | isError=True text='Unknown tool: no_such_tool' |
| wire: missing-argument outcome | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' |
| wire: missing resource outcome | jsonrpc error 0 (HTTP 200) | jsonrpc error -32602 (HTTP 200) | jsonrpc error -32602 (HTTP 400) | jsonrpc error -32602 (HTTP 400) | jsonrpc error 0 (HTTP 200) |
| wire: notifications/message | 2 | 2 | 0 | 2 | 2 |
| client: log notifications delivered | 2 | 2 | 0 | 2 | 2 |
| wire: logging/setLevel | 0 | 0 | 0 | 0 | 0 |
| HTTP: TCP connections | 14 | 14 | 1 | 2 | 14 |
| HTTP: POSTs | 12 | 12 | 11 | 11 | 13 |
| HTTP: standalone GET stream | 1 | 1 | 0 | 0 | 1 |
| HTTP: DELETE (session end) | 1 | 1 | 0 | 0 | 1 |
| HTTP: POSTs with Mcp-Session-Id | 11 | 11 | 0 | 0 | 11 |
| HTTP: responses with Mcp-Session-Id | 13 | 13 | 0 | 0 | 14 |
| HTTP: POSTs with MCP-Protocol-Version | 11 | 11 | 11 | 11 | 12 |
| HTTP: POSTs with Mcp-Method | 0 | 0 | 11 | 11 | 1 |
| HTTP: Mcp-Method equals body method | 0 | 0 | 11 | 11 | 1 |
| HTTP: tools/call POSTs | 6 | 6 | 6 | 6 | 6 |
| HTTP: tools/call POSTs with Mcp-Name | 0 | 0 | 6 | 6 | 0 |
| HTTP: Mcp-Name equals body tool name | 0 | 0 | 6 | 6 | 0 |
| HTTP: Mcp-Name for scan.v2-beta | None | None | scan.v2-beta | scan.v2-beta | None |
| HTTP: resources/read with Mcp-Name | 0 | 0 | 2 | 2 | 0 |
| HTTP: response content types | application/json=1, text/event-stream=11 | application/json=1, text/event-stream=11 | application/json=11 | application/json=10, text/event-stream=1 | application/json=2, text/event-stream=11 |
| HTTP: response statuses | 200=11, 202=1 | 200=11, 202=1 | 200=10, 400=1 | 200=10, 400=1 | 200=11, 202=1, 400=1 |
| stderr: non-empty lines | 33 | 57 | 55 | 55 | 35 |
| stderr: lines by class | per_request=10, session_lifecycle=2, tool_outcome=1, traceback=10, uvicorn=10 | deprecation_warning=4, other=1, session_lifecycle=2, tool_outcome=3, traceback=37, uvicorn=10 | deprecation_warning=4, other=1, tool_outcome=3, traceback=37, uvicorn=10 | deprecation_warning=4, other=1, tool_outcome=3, traceback=37, uvicorn=10 | per_request=10, session_lifecycle=4, tool_outcome=1, traceback=10, uvicorn=10 |
| stderr: one line per request | True | False | False | False | True |
| stderr: tool name on failure | False | True | True | True | False |
| stderr: failure cause | False | True | True | True | False |
| stderr: MCPDeprecationWarning | False | True | True | True | False |
| OTel server exporter | configured | configured | configured | configured | configured |
| OTel server spans | 0 | 12 | 11 | 11 | 0 |
| OTel server attribute keys | [] | error.type, gen_ai.operation.name, gen_ai.tool.name, jsonrpc.request.id, mcp.method.name, mcp.protocol.version, rpc.response.status_code | error.type, gen_ai.operation.name, gen_ai.tool.name, jsonrpc.request.id, mcp.method.name, mcp.protocol.version, rpc.response.status_code | error.type, gen_ai.operation.name, gen_ai.tool.name, jsonrpc.request.id, mcp.method.name, mcp.protocol.version, rpc.response.status_code | [] |
| OTel server spans with remote parent | 0 | 11 | 11 | 11 | 0 |
| OTel server error.type values | {} | -32602=1, tool_error=3 | -32602=1, tool_error=3 | -32602=1, tool_error=3 | {} |
| OTel server: tool arguments on span | False | False | False | False | False |
| OTel client exporter | configured | configured | configured | configured | configured |
| OTel client spans | 0 | 11 | 11 | 11 | 12 |
| OTel client attribute keys | [] | error.type, jsonrpc.request.id, mcp.method.name, rpc.response.status_code | error.type, jsonrpc.request.id, mcp.method.name, rpc.response.status_code | error.type, jsonrpc.request.id, mcp.method.name, rpc.response.status_code | error.type, jsonrpc.request.id, mcp.method.name, rpc.response.status_code |
| OTel: trace ids shared client/server | 0 | 11 | 11 | 11 | 0 |

## single-run checks

| fact | A-stdio-backend | B-stdio-nootel | C-stdio-backend | C-stdio-backend-instr | C-stdio-nootel |
|---|---|---|---|---|---|
| negotiated version (client) | 2025-11-25 | 2025-11-25 | 2026-07-28 | 2026-07-28 | 2026-07-28 |
| client API | ClientSession | Client | Client | Client | Client |
| wire: initialize requests | 1 | 1 | 0 | 0 | 0 |
| wire: notifications/initialized | 1 | 1 | 0 | 0 | 0 |
| wire: server/discover requests | 0 | 0 | 1 | 1 | 1 |
| wire: server/discover outcome | None | None | result supportedVersions=['2026-07-28'] instructions=yes ttlMs=0 cacheScope=private serverInfo=yes | result supportedVersions=['2026-07-28'] instructions=yes ttlMs=0 cacheScope=private serverInfo=yes | result supportedVersions=['2026-07-28'] instructions=yes ttlMs=0 cacheScope=private serverInfo=yes |
| wire: JSON-RPC requests | 12 | 11 | 12 | 12 | 11 |
| wire: requests carrying _meta protocolVersion | 0 | 0 | 12 | 12 | 11 |
| wire: requests carrying _meta clientInfo | 0 | 0 | 12 | 12 | 11 |
| wire: requests carrying _meta logLevel | 0 | 0 | 0 | 0 | 0 |
| wire: requests carrying _meta traceparent | 0 | 0 | 12 | 12 | 0 |
| wire: JSON-RPC results | 11 | 10 | 11 | 11 | 10 |
| wire: results carrying _meta serverInfo | 0 | 0 | 11 | 11 | 10 |
| wire: tools/list requests (2 issued) | 2 | 2 | 2 | 2 | 2 |
| wire: tools/list result has ttlMs | False | False | True | True | True |
| wire: tools/list ttlMs value | None | None | 0 | 0 | 0 |
| wire: tools/list cacheScope | None | None | private | private | private |
| wire: fail_tool outcome | isError=True text='Error executing tool fail_tool: fixture raised: fixture failure' | isError=True text='Error executing tool fail_tool' | isError=True text='Error executing tool fail_tool' | isError=True text='Error executing tool fail_tool' | isError=True text='Error executing tool fail_tool' |
| client sees fail_tool cause | True | False | False | False | False |
| wire: unknown tool outcome | isError=True text='Unknown tool: no_such_tool' | isError=True text='Unknown tool: no_such_tool' | isError=True text='Unknown tool: no_such_tool' | isError=True text='Unknown tool: no_such_tool' | isError=True text='Unknown tool: no_such_tool' |
| wire: missing-argument outcome | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' | isError=True text='Error executing tool echo: 1 validation error for echoArguments\ntext\n ' |
| wire: missing resource outcome | jsonrpc error 0 | jsonrpc error -32602 | jsonrpc error -32602 | jsonrpc error -32602 | jsonrpc error -32602 |
| wire: notifications/message | 2 | 2 | 0 | 0 | 0 |
| client: log notifications delivered | 2 | 2 | 0 | 0 | 0 |
| wire: logging/setLevel | 0 | 0 | 0 | 0 | 0 |
| HTTP: TCP connections | None | None | None | None | None |
| HTTP: POSTs | None | None | None | None | None |
| HTTP: standalone GET stream | None | None | None | None | None |
| HTTP: DELETE (session end) | None | None | None | None | None |
| HTTP: POSTs with Mcp-Session-Id | None | None | None | None | None |
| HTTP: responses with Mcp-Session-Id | None | None | None | None | None |
| HTTP: POSTs with MCP-Protocol-Version | None | None | None | None | None |
| HTTP: POSTs with Mcp-Method | None | None | None | None | None |
| HTTP: Mcp-Method equals body method | None | None | None | None | None |
| HTTP: tools/call POSTs | None | None | None | None | None |
| HTTP: tools/call POSTs with Mcp-Name | None | None | None | None | None |
| HTTP: Mcp-Name equals body tool name | None | None | None | None | None |
| HTTP: Mcp-Name for scan.v2-beta | None | None | None | None | None |
| HTTP: resources/read with Mcp-Name | None | None | None | None | None |
| HTTP: response content types | None | None | None | None | None |
| HTTP: response statuses | None | None | None | None | None |
| stderr: non-empty lines | 13 | 45 | 46 | 46 | 45 |
| stderr: lines by class | other=1, per_request=11, tool_outcome=1 | deprecation_warning=4, other=1, tool_outcome=3, traceback=37 | deprecation_warning=4, other=2, tool_outcome=3, traceback=37 | deprecation_warning=4, other=2, tool_outcome=3, traceback=37 | deprecation_warning=4, other=1, tool_outcome=3, traceback=37 |
| stderr: one line per request | True | False | False | False | False |
| stderr: tool name on failure | False | True | True | True | True |
| stderr: failure cause | False | True | True | True | True |
| stderr: MCPDeprecationWarning | False | True | True | True | True |
| OTel server exporter | configured | not configured | configured | configured | not configured |
| OTel server spans | 0 | None | 12 | 13 | None |
| OTel server attribute keys | [] | None | error.type, gen_ai.operation.name, gen_ai.tool.name, jsonrpc.request.id, mcp.method.name, mcp.protocol.version, rpc.response.status_code | error.type, gen_ai.operation.name, gen_ai.tool.name, http.method, http.status_code, http.url, jsonrpc.request.id, mcp.method.name, mcp.protocol.version, rpc.response.status_code | None |
| OTel server spans with remote parent | 0 | None | 12 | 12 | None |
| OTel server error.type values | {} | None | -32602=1, tool_error=3 | -32602=1, tool_error=3 | None |
| OTel server: tool arguments on span | False | None | False | False | None |
| OTel client exporter | configured | not configured | configured | configured | not configured |
| OTel client spans | 0 | None | 12 | 12 | None |
| OTel client attribute keys | [] | None | error.type, jsonrpc.request.id, mcp.method.name, rpc.response.status_code | error.type, jsonrpc.request.id, mcp.method.name, rpc.response.status_code | None |
| OTel: trace ids shared client/server | 0 | None | 12 | 12 | None |
| backend_requests | 1 | None | 1 | 1 | None |
| backend_traceparent | None | None | None | 00-3d7bf70f6adbc1e4cf11ec068e117ca2-bdd0c392546bf450-03 | None |
| backend_traceparent_trace_in_server_spans | None | None | False | True | None |

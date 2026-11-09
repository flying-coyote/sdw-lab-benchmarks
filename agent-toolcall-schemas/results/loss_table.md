| class | ocsf_main | ocsf_1754_draft | otel_genai_mcp | aos | aos_example1 |
|---|---|---|---|---|---|
| TYPED | 24 | 22 | 19 | 11 | 8 |
| HASHED | 3 | 3 | 0 | 0 | 0 |
| BLOB | 3 | 3 | 3 | 0 | 0 |
| UNMAPPED | 3 | 5 | 11 | 22 | 25 |
| DROPPED | 0 | 0 | 0 | 0 | 0 |

| fact | group | OCSF main (6003 + ai_operation) | OCSF #1754 draft | OTel GenAI+MCP | AOS on OCSF (ex. 2) | AOS ex. 1 (sensitivity) |
|---|---|---|---|---|---|---|
| jsonrpc_version | protocol | UNMAPPED `unmapped.jsonrpc` | UNMAPPED `unmapped.jsonrpc` | TYPED `attributes.jsonrpc.protocol.version` | UNMAPPED `unmapped.sdw.jsonrpc` | UNMAPPED `unmapped.sdw.jsonrpc` |
| request_id | protocol | TYPED `ai_capability.transaction_uid` | TYPED `ai_capability.transaction_uid` | TYPED `attributes.jsonrpc.request.id` | TYPED `metadata.correlation_uid` | UNMAPPED `unmapped.aos.step.id` |
| method | protocol | TYPED `api.operation` | UNMAPPED `unmapped.mcp.method` | TYPED `attributes.mcp.method.name` | UNMAPPED `unmapped.aos.step.type` | TYPED `api.operation` |
| protocol_version | protocol | TYPED `api.version` | UNMAPPED `unmapped.mcp.protocol_version` | TYPED `attributes.mcp.protocol.version` | UNMAPPED `unmapped.sdw.mcp_protocol_version` | UNMAPPED `unmapped.sdw.mcp_protocol_version` |
| transport | protocol | TYPED `ai_capability.transport_id` | TYPED `ai_capability.transport_id` | TYPED `attributes.network.transport` | UNMAPPED `unmapped.sdw.transport` | UNMAPPED `unmapped.sdw.transport` |
| primitive_kind | protocol | TYPED `ai_capability.type_id` | TYPED `ai_capability.type_id` | TYPED `attributes.gen_ai.operation.name` | UNMAPPED `unmapped.aos.step.operation.type` | UNMAPPED `unmapped.aos.step.type` |
| tool_name | tool | TYPED `ai_capability.name` | TYPED `ai_agent_tool_use_info.name` | TYPED `attributes.gen_ai.tool.name` | TYPED `api.operation` | UNMAPPED `unmapped.aos.tool_call.name` |
| arguments | payload | BLOB `api.request.data` | BLOB `ai_agent_tool_use_info.ai_tool_input` | BLOB `attributes.gen_ai.tool.call.arguments` | UNMAPPED `unmapped.aos.step.operation.tool.inputs` | UNMAPPED `unmapped.aos.tool_call.arguments` |
| result_content | payload | BLOB `api.response.data.content` | BLOB `ai_agent_tool_use_info.ai_tool_response.content` | BLOB `attributes.gen_ai.tool.call.result.content` | UNMAPPED `unmapped.aos.step.operation.tool.outputs` | UNMAPPED `unmapped.sdw.result_content` |
| structured_content | payload | BLOB `api.response.data.structuredContent` | BLOB `ai_agent_tool_use_info.ai_tool_response.structuredContent` | BLOB `attributes.gen_ai.tool.call.result.structuredContent` | UNMAPPED `unmapped.sdw.structured_content` | UNMAPPED `unmapped.sdw.structured_content` |
| is_error | outcome | TYPED `status_id` | TYPED `status_id` | TYPED `attributes.error.type` | TYPED `status_id` | TYPED `status_id` |
| error_text | outcome | TYPED `api.response.error_message` | TYPED `status_detail` | TYPED `status.description` | TYPED `api.response.message` | UNMAPPED `unmapped.sdw.error_text` |
| server_name | server | TYPED `ai_capability.service.name` | TYPED `ai_capability.service.name` | UNMAPPED `attributes.sdw.mcp.server.name` | TYPED `api.service.name` | TYPED `api.service.name` |
| server_version | server | TYPED `ai_capability.service.version` | TYPED `ai_capability.service.version` | UNMAPPED `attributes.sdw.mcp.server.version` | TYPED `api.service.version` | TYPED `api.service.version` |
| server_instructions | server | UNMAPPED `unmapped.mcp.server_instructions` | UNMAPPED `unmapped.mcp.server_instructions` | UNMAPPED `attributes.sdw.mcp.server.instructions` | UNMAPPED `unmapped.sdw.server_instructions` | UNMAPPED `unmapped.sdw.server_instructions` |
| server_capabilities | server | UNMAPPED `unmapped.mcp.server_capabilities` | UNMAPPED `unmapped.mcp.server_capabilities` | UNMAPPED `attributes.sdw.mcp.server.capabilities` | UNMAPPED `unmapped.sdw.server_capabilities` | UNMAPPED `unmapped.sdw.server_capabilities` |
| client_name | client | TYPED `message_context.application.name` | TYPED `message_context.application.name` | TYPED `resource.service.name` | UNMAPPED `unmapped.sdw.client_name` | UNMAPPED `unmapped.sdw.client_name` |
| client_version | client | TYPED `message_context.application.version` | TYPED `message_context.application.version` | TYPED `resource.service.version` | UNMAPPED `unmapped.sdw.client_version` | UNMAPPED `unmapped.sdw.client_version` |
| tool_description | advert | HASHED `ai_capability.desc_fingerprint` | HASHED `ai_capability.desc_fingerprint` | TYPED `attributes.gen_ai.tool.description` | UNMAPPED `unmapped.sdw.tool_description` | UNMAPPED `unmapped.sdw.tool_description` |
| tool_input_schema | advert | HASHED `ai_capability.input_schema_fingerprint` | HASHED `ai_capability.input_schema_fingerprint` | UNMAPPED `attributes.sdw.mcp.tool.input_schema` | UNMAPPED `unmapped.sdw.tool_input_schema` | UNMAPPED `unmapped.sdw.tool_input_schema` |
| tool_output_schema | advert | HASHED `ai_capability.output_schema_fingerprint` | HASHED `ai_capability.output_schema_fingerprint` | UNMAPPED `attributes.sdw.mcp.tool.output_schema` | UNMAPPED `unmapped.sdw.tool_output_schema` | UNMAPPED `unmapped.sdw.tool_output_schema` |
| ann_read_only | advert | TYPED `ai_capability.is_readonly` | TYPED `ai_capability.is_readonly` | UNMAPPED `attributes.sdw.mcp.tool.annotations.readOnlyHint` | UNMAPPED `unmapped.sdw.annotations.readOnlyHint` | UNMAPPED `unmapped.sdw.annotations.readOnlyHint` |
| ann_destructive | advert | TYPED `ai_capability.is_destructive` | TYPED `ai_capability.is_destructive` | UNMAPPED `attributes.sdw.mcp.tool.annotations.destructiveHint` | UNMAPPED `unmapped.sdw.annotations.destructiveHint` | UNMAPPED `unmapped.sdw.annotations.destructiveHint` |
| ann_idempotent | advert | TYPED `ai_capability.is_idempotent` | TYPED `ai_capability.is_idempotent` | UNMAPPED `attributes.sdw.mcp.tool.annotations.idempotentHint` | UNMAPPED `unmapped.sdw.annotations.idempotentHint` | UNMAPPED `unmapped.sdw.annotations.idempotentHint` |
| ann_open_world | advert | TYPED `ai_capability.is_open_world` | TYPED `ai_capability.is_open_world` | UNMAPPED `attributes.sdw.mcp.tool.annotations.openWorldHint` | UNMAPPED `unmapped.sdw.annotations.openWorldHint` | UNMAPPED `unmapped.sdw.annotations.openWorldHint` |
| start_time_ns | timing | TYPED `start_time` | TYPED `start_time` | TYPED `start_time_unix_nano` | TYPED `time` | TYPED `time` |
| duration_ns | timing | TYPED `duration` | TYPED `duration` | TYPED `duration_ns` | TYPED `duration` | TYPED `duration` |
| agent_uid | context | TYPED `ai_agent.uid` | TYPED `ai_agent.uid` | TYPED `attributes.gen_ai.agent.id` | TYPED `actor.user.uid` | TYPED `actor.user.uid` |
| agent_name | context | TYPED `ai_agent.name` | TYPED `ai_agent.name` | TYPED `attributes.gen_ai.agent.name` | TYPED `actor.user.name` | TYPED `actor.user.name` |
| agent_instance | context | TYPED `ai_agent.instance_uid` | TYPED `ai_agent.instance_uid` | UNMAPPED `attributes.sdw.agent.instance_id` | UNMAPPED `unmapped.sdw.agent_instance` | UNMAPPED `unmapped.sdw.agent_instance` |
| model_name | context | TYPED `ai_agent.ai_model.name` | TYPED `ai_agent.ai_model.name` | TYPED `attributes.gen_ai.request.model` | UNMAPPED `unmapped.aos.context.model.id` | UNMAPPED `unmapped.aos.context.model.id` |
| model_provider | context | TYPED `ai_agent.ai_model.ai_provider` | TYPED `ai_agent.ai_model.ai_provider` | TYPED `attributes.gen_ai.provider.name` | UNMAPPED `unmapped.aos.context.model.provider.name` | UNMAPPED `unmapped.aos.context.model.provider.name` |
| session_uid | context | TYPED `actor.session.uid` | TYPED `actor.session.uid` | TYPED `attributes.gen_ai.conversation.id` | TYPED `actor.session.uid` | UNMAPPED `unmapped.aos.context.session.id` |

#!/usr/bin/env python3
"""Map each captured tools/call to four records (OCSF main, OCSF #1754 draft, OTel GenAI/MCP, AOS) and build
the loss table from the emitted records.

Every fact has, per schema, a target path and a class (TYPED / HASHED / BLOB / UNMAPPED / DROPPED). The record is
built by writing each fact's value at its path; afterwards the script re-reads every path from the emitted
record (so the table cannot claim a path the record does not hold) and checks OCSF paths against the pinned
OCSF object definitions and OTel keys against the pinned registries.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REF = HERE / "ref"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)

# Harness-supplied context: no agent runtime or model is in the loop, so these are fixed and labelled.
HARNESS = {"agent_uid": "agent-r2-harness", "agent_name": "r2-capture-harness",
           "agent_instance": "r2-harness-run-1", "model_name": "harness-no-model", "model_provider": "none",
           "session_uid": "r2-session-0001"}


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def sha256(o) -> str:
    return hashlib.sha256(canon(o).encode()).hexdigest()


# ---------------------------------------------------------------- load the capture
wire = [json.loads(l) for l in (HERE / "capture" / "wire.jsonl").open()]
msgs = [(w["dir"], w["t_mono_ns"], json.loads(w["raw"])) for w in wire]
req = {m["id"]: (t, m) for d, t, m in msgs if d == "c2s" and "id" in m}
resp = {m["id"]: (t, m) for d, t, m in msgs if d == "s2c" and "id" in m}
init_req = next(m for _, m in req.values() if m["method"] == "initialize")
init_res = resp[init_req["id"]][1]["result"]
tools_list = next(resp[i][1]["result"]["tools"] for i, (_, m) in req.items() if m["method"] == "tools/list")
advert = {t["name"]: t for t in tools_list}

calls = []
for i, (t0, m) in sorted(req.items()):
    if m["method"] != "tools/call":
        continue
    t1, r = resp[i]
    calls.append({"req": m, "resp": r, "t0": t0, "t1": t1, "advert": advert.get(m["params"]["name"])})
assert len(calls) == 10, len(calls)

# ---------------------------------------------------------------- the fact inventory
# (id, group, getter). Getter returns the value, or None when the fact is absent for this call.
A = lambda c: c["advert"] or {}
ANN = lambda c, k: (A(c).get("annotations") or {}).get(k)
RES = lambda c: c["resp"].get("result", {})
FACTS = [
    ("jsonrpc_version", "protocol", lambda c: c["req"]["jsonrpc"]),
    ("request_id", "protocol", lambda c: c["req"]["id"]),
    ("method", "protocol", lambda c: c["req"]["method"]),
    ("protocol_version", "protocol", lambda c: init_res["protocolVersion"]),
    ("transport", "protocol", lambda c: "stdio"),
    ("primitive_kind", "protocol", lambda c: "tool"),
    ("tool_name", "tool", lambda c: c["req"]["params"]["name"]),
    ("arguments", "payload", lambda c: c["req"]["params"].get("arguments")),
    ("result_content", "payload", lambda c: RES(c).get("content")),
    ("structured_content", "payload", lambda c: RES(c).get("structuredContent")),
    ("is_error", "outcome", lambda c: RES(c).get("isError")),
    ("error_text", "outcome", lambda c: RES(c)["content"][0]["text"] if RES(c).get("isError") else None),
    ("server_name", "server", lambda c: init_res["serverInfo"]["name"]),
    ("server_version", "server", lambda c: init_res["serverInfo"]["version"]),
    ("server_instructions", "server", lambda c: init_res.get("instructions")),
    ("server_capabilities", "server", lambda c: init_res.get("capabilities")),
    ("client_name", "client", lambda c: init_req["params"]["clientInfo"]["name"]),
    ("client_version", "client", lambda c: init_req["params"]["clientInfo"]["version"]),
    ("tool_description", "advert", lambda c: A(c).get("description")),
    ("tool_input_schema", "advert", lambda c: A(c).get("inputSchema")),
    ("tool_output_schema", "advert", lambda c: A(c).get("outputSchema")),
    ("ann_read_only", "advert", lambda c: ANN(c, "readOnlyHint")),
    ("ann_destructive", "advert", lambda c: ANN(c, "destructiveHint")),
    ("ann_idempotent", "advert", lambda c: ANN(c, "idempotentHint")),
    ("ann_open_world", "advert", lambda c: ANN(c, "openWorldHint")),
    ("start_time_ns", "timing", lambda c: c["t0"]),
    ("duration_ns", "timing", lambda c: c["t1"] - c["t0"]),
    ("agent_uid", "context", lambda c: HARNESS["agent_uid"]),
    ("agent_name", "context", lambda c: HARNESS["agent_name"]),
    ("agent_instance", "context", lambda c: HARNESS["agent_instance"]),
    ("model_name", "context", lambda c: HARNESS["model_name"]),
    ("model_provider", "context", lambda c: HARNESS["model_provider"]),
    ("session_uid", "context", lambda c: HARNESS["session_uid"]),
]
FACT_IDS = [f[0] for f in FACTS]

# ---------------------------------------------------------------- per-schema specs: fact -> (path, class, note)
T, H, B, U, D = "TYPED", "HASHED", "BLOB", "UNMAPPED", "DROPPED"
FP = lambda v: {"algorithm_id": 3, "value": sha256(v)}  # OCSF fingerprint, SHA-256
ERRSTAT = lambda v: 2 if v else 1                       # OCSF status_id Failure / Success

OCSF_MAIN = {
    "jsonrpc_version": ("unmapped.jsonrpc", U, "no OCSF attribute for the JSON-RPC envelope version"),
    "request_id": ("ai_capability.transaction_uid", T, "also api.request.uid"),
    "method": ("api.operation", T, ""),
    "protocol_version": ("api.version", T, "api.version = 'version of the API service'; judgment call"),
    "transport": ("ai_capability.transport_id", T, "enum 1 = stdio"),
    "primitive_kind": ("ai_capability.type_id", T, "enum 1 = Tool"),
    "tool_name": ("ai_capability.name", T, ""),
    "arguments": ("api.request.data", B, "json_t"),
    "result_content": ("api.response.data.content", B, "json_t"),
    "structured_content": ("api.response.data.structuredContent", B, "json_t"),
    "is_error": ("status_id", T, "2 Failure / 1 Success"),
    "error_text": ("api.response.error_message", T, "string"),
    "server_name": ("ai_capability.service.name", T, ""),
    "server_version": ("ai_capability.service.version", T, ""),
    "server_instructions": ("unmapped.mcp.server_instructions", U, ""),
    "server_capabilities": ("unmapped.mcp.server_capabilities", U, ""),
    "client_name": ("message_context.application.name", T, "message_context.application = initiating client"),
    "client_version": ("message_context.application.version", T, ""),
    "tool_description": ("ai_capability.desc_fingerprint", H, "fingerprint only; text not carried"),
    "tool_input_schema": ("ai_capability.input_schema_fingerprint", H, "fingerprint only"),
    "tool_output_schema": ("ai_capability.output_schema_fingerprint", H, "fingerprint only"),
    "ann_read_only": ("ai_capability.is_readonly", T, ""),
    "ann_destructive": ("ai_capability.is_destructive", T, ""),
    "ann_idempotent": ("ai_capability.is_idempotent", T, ""),
    "ann_open_world": ("ai_capability.is_open_world", T, ""),
    "start_time_ns": ("start_time", T, "timestamp_t (ms); proxy monotonic clock, not wall time"),
    "duration_ns": ("duration", T, "long_t ms"),
    "agent_uid": ("ai_agent.uid", T, ""),
    "agent_name": ("ai_agent.name", T, ""),
    "agent_instance": ("ai_agent.instance_uid", T, ""),
    "model_name": ("ai_agent.ai_model.name", T, ""),
    "model_provider": ("ai_agent.ai_model.ai_provider", T, ""),
    "session_uid": ("actor.session.uid", T, "or message_context.uid"),
}

# #1754 draft: ai_agent_activity (Application category, so the ai_operation profile still applies). The class has
# no `api` object, so protocol facts that OCSF main puts on `api` move to unmapped unless ai_capability holds them.
OCSF_1754 = dict(OCSF_MAIN)
OCSF_1754.update({
    "method": ("unmapped.mcp.method", U, "no api object on ai_agent_activity; activity_id Tool Use implies it"),
    "protocol_version": ("unmapped.mcp.protocol_version", U, "no api object"),
    "tool_name": ("ai_agent_tool_use_info.name", T, "also ai_capability.name via profile"),
    "arguments": ("ai_agent_tool_use_info.ai_tool_input", B, "json_t"),
    "result_content": ("ai_agent_tool_use_info.ai_tool_response.content", B, "json_t"),
    "structured_content": ("ai_agent_tool_use_info.ai_tool_response.structuredContent", B, "json_t"),
    "error_text": ("status_detail", T, "base-event string"),
})

OTEL = {
    "jsonrpc_version": ("attributes.jsonrpc.protocol.version", T, "recommended only when not 2.0"),
    "request_id": ("attributes.jsonrpc.request.id", T, ""),
    "method": ("attributes.mcp.method.name", T, "enum"),
    "protocol_version": ("attributes.mcp.protocol.version", T, ""),
    "transport": ("attributes.network.transport", T, "'pipe' for stdio per mcp/common.yaml"),
    "primitive_kind": ("attributes.gen_ai.operation.name", T, "execute_tool"),
    "tool_name": ("attributes.gen_ai.tool.name", T, ""),
    "arguments": ("attributes.gen_ai.tool.call.arguments", B, "type any, opt-in"),
    "result_content": ("attributes.gen_ai.tool.call.result.content", B, "type any, opt-in"),
    "structured_content": ("attributes.gen_ai.tool.call.result.structuredContent", B, "type any, opt-in"),
    "is_error": ("attributes.error.type", T, "'tool_error' when isError, plus span status ERROR"),
    "error_text": ("status.description", T, "span status description"),
    "server_name": ("attributes.sdw.mcp.server.name", U,
                    "no MCP server-name attribute; server.service.name is defined for network connections"),
    "server_version": ("attributes.sdw.mcp.server.version", U, ""),
    "server_instructions": ("attributes.sdw.mcp.server.instructions", U, ""),
    "server_capabilities": ("attributes.sdw.mcp.server.capabilities", U, ""),
    "client_name": ("resource.service.name", T, "the instrumented client's own resource"),
    "client_version": ("resource.service.version", T, ""),
    "tool_description": ("attributes.gen_ai.tool.description", T, "free-text string attribute"),
    "tool_input_schema": ("attributes.sdw.mcp.tool.input_schema", U,
                          "gen_ai.tool.definitions (any) is defined for inference spans, not execute_tool"),
    "tool_output_schema": ("attributes.sdw.mcp.tool.output_schema", U, ""),
    "ann_read_only": ("attributes.sdw.mcp.tool.annotations.readOnlyHint", U, "no annotation attributes"),
    "ann_destructive": ("attributes.sdw.mcp.tool.annotations.destructiveHint", U, ""),
    "ann_idempotent": ("attributes.sdw.mcp.tool.annotations.idempotentHint", U, ""),
    "ann_open_world": ("attributes.sdw.mcp.tool.annotations.openWorldHint", U, ""),
    "start_time_ns": ("start_time_unix_nano", T, "span field; proxy monotonic clock here"),
    "duration_ns": ("duration_ns", T, "end - start"),
    "agent_uid": ("attributes.gen_ai.agent.id", T, ""),
    "agent_name": ("attributes.gen_ai.agent.name", T, ""),
    "agent_instance": ("attributes.sdw.agent.instance_id", U, "no instance attribute (service.instance.id is the process)"),
    "model_name": ("attributes.gen_ai.request.model", T, "normally on the parent inference span"),
    "model_provider": ("attributes.gen_ai.provider.name", T, ""),
    "session_uid": ("attributes.gen_ai.conversation.id", T, "mcp.session.id exists but stdio has no MCP session id"),
}

# AOS, following its published "Agent with Tool Execution" 6003 example (extend_ocsf.md @ 9a9bc37).
AOS = {
    "jsonrpc_version": ("unmapped.sdw.jsonrpc", U, "not in the AOS example"),
    "request_id": ("metadata.correlation_uid", T, "example uses correlation_uid = tool execution id"),
    "method": ("unmapped.aos.step.type", U, "example: step.type 'toolCall'; api.operation holds the tool name"),
    "protocol_version": ("unmapped.sdw.mcp_protocol_version", U, ""),
    "transport": ("unmapped.sdw.transport", U, ""),
    "primitive_kind": ("unmapped.aos.step.operation.type", U, "'tool_execution'"),
    "tool_name": ("api.operation", T, "example 2 puts the tool name in api.operation (example 1 puts 'tools/call')"),
    "arguments": ("unmapped.aos.step.operation.tool.inputs", U, "list of {name, value}"),
    "result_content": ("unmapped.aos.step.operation.tool.outputs", U, "list of {kind, text}"),
    "structured_content": ("unmapped.sdw.structured_content", U, "no AOS slot"),
    "is_error": ("status_id", T, "also unmapped.aos.step.operation.tool.is_error"),
    "error_text": ("api.response.message", T, "example puts tool output text in api.response.message"),
    "server_name": ("api.service.name", T, ""),
    "server_version": ("api.service.version", T, ""),
    "server_instructions": ("unmapped.sdw.server_instructions", U, ""),
    "server_capabilities": ("unmapped.sdw.server_capabilities", U, ""),
    "client_name": ("unmapped.sdw.client_name", U, "no slot in the example"),
    "client_version": ("unmapped.sdw.client_version", U, ""),
    "tool_description": ("unmapped.sdw.tool_description", U, "tool definitions live in AOS AgBOM, not the trace event"),
    "tool_input_schema": ("unmapped.sdw.tool_input_schema", U, ""),
    "tool_output_schema": ("unmapped.sdw.tool_output_schema", U, ""),
    "ann_read_only": ("unmapped.sdw.annotations.readOnlyHint", U, ""),
    "ann_destructive": ("unmapped.sdw.annotations.destructiveHint", U, ""),
    "ann_idempotent": ("unmapped.sdw.annotations.idempotentHint", U, ""),
    "ann_open_world": ("unmapped.sdw.annotations.openWorldHint", U, ""),
    "start_time_ns": ("time", T, ""),
    "duration_ns": ("duration", T, "base OCSF; not shown in the AOS example"),
    "agent_uid": ("actor.user.uid", T, "agent as user, type_id 99 'AI Agent' (semantic stretch AOS documents)"),
    "agent_name": ("actor.user.name", T, "same stretch"),
    "agent_instance": ("unmapped.sdw.agent_instance", U, ""),
    "model_name": ("unmapped.aos.context.model.id", U, ""),
    "model_provider": ("unmapped.aos.context.model.provider.name", U, ""),
    "session_uid": ("actor.session.uid", T, "example 2 uses actor.session.uid"),
}

# Sensitivity: AOS's own first example on the same page ("Agent Activity Events") puts 'tools/call' in api.operation
# and the tool name, arguments and session in unmapped.aos. The two examples disagree; the query-cost L3 layout
# follows this one (as pre-registered), the primary loss column follows example 2.
AOS_EX1 = dict(AOS)
AOS_EX1.update({
    "method": ("api.operation", T, "example 1: api.operation = 'tools/call'"),
    "tool_name": ("unmapped.aos.tool_call.name", U, ""),
    "arguments": ("unmapped.aos.tool_call.arguments", U, ""),
    "result_content": ("unmapped.sdw.result_content", U, "example 1 has no output slot"),
    "request_id": ("unmapped.aos.step.id", U, "example 1 has no correlation_uid"),
    "session_uid": ("unmapped.aos.context.session.id", U, ""),
    "error_text": ("unmapped.sdw.error_text", U, "example 1 has no response"),
    "primitive_kind": ("unmapped.aos.step.type", U, "'toolCall'"),
})

SCHEMAS = OrderedDict([("ocsf_main", OCSF_MAIN), ("ocsf_1754_draft", OCSF_1754), ("otel_genai_mcp", OTEL),
                       ("aos", AOS), ("aos_example1", AOS_EX1)])
for name, spec in SCHEMAS.items():
    assert set(spec) == set(FACT_IDS), (name, set(FACT_IDS) ^ set(spec))


def convert(fid: str, schema: str, v):
    """Schema-specific value encoding for a fact."""
    if v is None:
        return None
    if schema.startswith("ocsf") and fid in ("tool_description", "tool_input_schema", "tool_output_schema"):
        return FP(v)
    if schema.startswith("ocsf") or schema.startswith("aos"):
        if fid == "is_error":
            return ERRSTAT(v)
        if fid == "transport":
            return 1 if not schema.startswith("aos") else v
        if fid == "primitive_kind":
            return 1 if not schema.startswith("aos") else "tool_execution"
        if fid == "start_time_ns":
            return v // 1_000_000
        if fid == "duration_ns":
            return v // 1_000_000  # OCSF duration is long_t milliseconds
        if fid == "request_id":
            return str(v)
        if fid == "method" and schema == "aos":  # example 2 only
            return "toolCall"
        if fid == "arguments" and schema == "aos":  # example 1 keeps the dict
            return [{"name": k, "value": a} for k, a in v.items()]
        if fid == "result_content" and schema == "aos":
            return [{"kind": x.get("type"), "text": x.get("text")} for x in v]
    if schema == "otel":
        pass
    if schema == "otel_genai_mcp":
        if fid == "is_error":
            return "tool_error" if v else None
        if fid == "transport":
            return "pipe"
        if fid == "primitive_kind":
            return "execute_tool"
        if fid == "request_id":
            return str(v)
        if fid == "method":
            return v
    return v


def set_path(rec: dict, path: str, v) -> None:
    # OTel attribute keys contain dots; split only the first segment for attributes/resource.
    if path.startswith(("attributes.", "resource.")):
        top, key = path.split(".", 1)
        m = re.match(r"(gen_ai\.tool\.call\.result)\.(content|structuredContent)$", key)
        if m:
            rec.setdefault(top, {}).setdefault(m.group(1), {})[m.group(2)] = v
        else:
            rec.setdefault(top, {})[key] = v
        return
    parts = path.split(".")
    cur = rec
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = v


def get_path(rec: dict, path: str):
    if path.startswith(("attributes.", "resource.")):
        top, key = path.split(".", 1)
        m = re.match(r"(gen_ai\.tool\.call\.result)\.(content|structuredContent)$", key)
        if m:
            return rec.get(top, {}).get(m.group(1), {}).get(m.group(2))
        return rec.get(top, {}).get(key)
    cur = rec
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def skeleton(schema: str, c: dict) -> dict:
    if schema == "ocsf_main":
        return {"category_uid": 6, "class_uid": 6003, "activity_id": 99, "activity_name": "Invoke",
                "type_uid": 600399, "severity_id": 1, "time": c["t1"] // 1_000_000,
                "metadata": {"version": "1.10.0-dev", "profiles": ["ai_operation"],
                             "product": {"name": "r2-capture-proxy", "vendor_name": "SDW lab"}},
                "ai_capability": {"source_id": 1}, "api": {"request": {"uid": str(c["req"]["id"])}},
                "src_endpoint": {"name": "stdio client (r2 harness)", "hostname": "localhost"}}
    if schema == "ocsf_1754_draft":
        return {"category_uid": 6, "class_uid": 6009, "activity_id": 7, "activity_name": "Tool Use (draft)",
                "severity_id": 1, "time": c["t1"] // 1_000_000,
                "metadata": {"version": "1.10.0-dev+pr1754", "profiles": ["ai_operation"],
                             "product": {"name": "r2-capture-proxy", "vendor_name": "SDW lab"}},
                "ai_capability": {"source_id": 1}, "ai_agent_tool_use_info": {"is_pre_occurrence": False}}
    if schema == "otel_genai_mcp":
        return {"name": f"tools/call {c['req']['params']['name']}", "kind": "CLIENT",
                "status": {"code": "ERROR" if c["resp"]["result"].get("isError") else "UNSET"}}
    if schema.startswith("aos"):
        return {"category_uid": 6, "category_name": "Application Activity", "class_uid": 6003,
                "class_name": "API Activity", "activity_id": 1, "activity_name": "Tool Execution",
                "type_uid": 600301, "severity_id": 1,
                "metadata": {"version": "1.0.0", "product": {"name": "AOS Security Layer", "vendor_name": "AOS"}},
                "actor": {"user": {"type_id": 99, "type": "AI Agent"}}, "api": {"response": {"code": 200}},
                "src_endpoint": {"type_id": 99, "name": "AI Agent Endpoint", "hostname": "localhost"},
                "unmapped": {"aos": {"step": {"operation": {"tool": {"id": c["req"]["params"]["name"],
                                                                   "execution_id": str(c["req"]["id"]),
                                                                   "is_error": c["resp"]["result"].get("isError")}}}}}}
    raise KeyError(schema)


# ---------------------------------------------------------------- pinned-schema path checks
def load_ocsf(name: str, base: Path):
    p = base / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


DICT = json.loads((REF / "ocsf_main" / "dictionary.json").read_text())["attributes"]
PR1754_TOOLUSE = json.loads((REF / "pr1754_ai_agent_tool_use_info.json").read_text())
PR1754_CLASS = json.loads((REF / "pr1754_ai_agent_activity.json").read_text())


def obj_attrs(name: str) -> dict | None:
    if name == "ai_agent_tool_use_info":
        return PR1754_TOOLUSE["attributes"]
    o = load_ocsf(name, REF / "ocsf_main")
    if o is None:
        return None
    attrs = dict(o.get("attributes", {}))
    if o.get("extends") and o["extends"] != "object":
        parent = obj_attrs(o["extends"])
        attrs.update(parent or {})
    return attrs


def root_attrs(schema: str) -> dict:
    a = {}
    for f in ("event_base", "event_application", "event_api_activity", "profile_ai_operation", "profile_trace"):
        a.update(json.loads((REF / "ocsf_main" / f"{f}.json").read_text()).get("attributes", {}))
    if schema == "ocsf_1754_draft":
        for k in ("api", "src_endpoint", "dst_endpoint", "http_request", "http_response", "resources"):
            a.pop(k, None)
        a.update(PR1754_CLASS["attributes"])
    return a


PR_TYPES = {"ai_agent_tool_use_info": "ai_agent_tool_use_info", "ai_tool_input": "json_t",
            "ai_tool_response": "json_t", "is_pre_occurrence": "boolean_t"}


def check_ocsf_path(schema: str, path: str) -> str:
    """'ok', 'ok:json' (descends into json_t), 'unmapped', or 'MISSING:<seg>'."""
    if path.startswith("unmapped."):
        return "unmapped"
    attrs = root_attrs(schema)
    for i, seg in enumerate(path.split(".")):
        if attrs is None or seg not in attrs:
            return f"MISSING:{seg}"
        t = PR_TYPES.get(seg) or DICT.get(seg, {}).get("type")
        if seg == "ai_model":
            t = "ai_model"
        if t == "json_t":
            return "ok" if i == len(path.split(".")) - 1 else "ok:json"
        if t and not t.endswith("_t"):
            attrs = obj_attrs(t)
        else:
            attrs = None
    return "ok"


OTEL_TEXT = "\n".join(p.read_text() for p in REF.glob("otel_*.yaml"))


def check_otel_key(path: str) -> str:
    if not path.startswith(("attributes.", "resource.")):
        return "span-field"
    key = path.split(".", 1)[1]
    key = re.sub(r"\.(content|structuredContent)$", "", key)
    if key.startswith("sdw."):
        return "custom"
    if key in ("service.name", "service.version"):
        return "ok"  # resource attributes, semconv v1.45.0 model/service
    return "ok" if re.search(rf"(key|id): {re.escape(key)}\b", OTEL_TEXT) else "MISSING"


# ---------------------------------------------------------------- build records + table
records = {s: [] for s in SCHEMAS}
cells = {s: {} for s in SCHEMAS}
checks = []
for c in calls:
    for s, spec in SCHEMAS.items():
        rec = skeleton(s, c)
        for fid, group, get in FACTS:
            path, cls, note = spec[fid]
            v = convert(fid, s, get(c))
            if v is None:
                continue
            set_path(rec, path, v)
            assert get_path(rec, path) == v, (s, fid, path)
            cells[s].setdefault(fid, (path, cls, note))
        if s == "otel_genai_mcp":
            rec["end_time_unix_nano"] = c["t1"]
        records[s].append(rec)

for s, spec in SCHEMAS.items():
    for fid in FACT_IDS:
        path, cls, note = spec[fid]
        if s.startswith("ocsf") or s.startswith("aos"):
            chk = check_ocsf_path(s, path)
        else:
            chk = check_otel_key(path)
        checks.append({"schema": s, "fact": fid, "path": path, "class": cls, "check": chk})
        if cls == T and s != "otel_genai_mcp":
            assert chk == "ok", (s, fid, path, chk)
        if cls in (B,) and s != "otel_genai_mcp":
            assert chk.startswith("ok"), (s, fid, path, chk)
        if cls == T and s == "otel_genai_mcp":
            assert chk in ("ok", "span-field"), (s, fid, path, chk)

for s in SCHEMAS:
    (OUT / f"records_{s}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records[s]))

group_of = {f[0]: f[1] for f in FACTS}
counts = {s: Counter(SCHEMAS[s][f][1] for f in FACT_IDS) for s in SCHEMAS}
summary = {
    "n_calls": len(calls), "n_facts": len(FACT_IDS),
    "negotiated_protocol_version": init_res["protocolVersion"],
    "counts": {s: dict(counts[s]) for s in SCHEMAS},
    "facts": [{"fact": f, "group": group_of[f], **{s: {"path": SCHEMAS[s][f][0], "class": SCHEMAS[s][f][1],
                                                       "note": SCHEMAS[s][f][2]} for s in SCHEMAS}}
              for f in FACT_IDS],
    "checks": checks,
}
(OUT / "loss_table.json").write_text(json.dumps(summary, indent=1))

# Markdown table
hdr = "| fact | group | OCSF main (6003 + ai_operation) | OCSF #1754 draft | OTel GenAI+MCP | AOS on OCSF (ex. 2) | AOS ex. 1 (sensitivity) |\n|---|---|---|---|---|---|---|\n"
rows = []
for f in FACT_IDS:
    cells_md = [f"{SCHEMAS[s][f][1]} `{SCHEMAS[s][f][0]}`" for s in SCHEMAS]
    rows.append(f"| {f} | {group_of[f]} | " + " | ".join(cells_md) + " |")
cnt = "| class | " + " | ".join(SCHEMAS) + " |\n|---|" + "---|" * len(SCHEMAS) + "\n"
for k in (T, H, B, U, D):
    cnt += f"| {k} | " + " | ".join(str(counts[s].get(k, 0)) for s in SCHEMAS) + " |\n"
(OUT / "loss_table.md").write_text(cnt + "\n" + hdr + "\n".join(rows) + "\n")
print(cnt)
# group-level view for H1/H2
for s in SCHEMAS:
    g = Counter((group_of[f], SCHEMAS[s][f][1]) for f in FACT_IDS)
    print(s, dict(sorted(g.items())))
bad = [c for c in checks if c["check"].startswith("MISSING")]
print("path-check failures:", bad)

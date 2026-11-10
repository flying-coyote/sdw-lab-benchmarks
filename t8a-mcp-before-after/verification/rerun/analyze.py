#!/usr/bin/env python3
"""Build the T8a presence matrix from the captures. Usage: analyze.py [runs-dir]

For every runs/<cell>/rep<N>/ it derives one facts record from the four capture points (wire, client, server
stderr, OTel at both ends), checks the record is identical across repeats (ignoring values that are expected to
vary: ids, timings), and writes results/facts.json, results/matrix.md, results/timing.md, results/stability.md.
Every number in RESULTS.md comes from these files.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "runs"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)

META_PV = "io.modelcontextprotocol/protocolVersion"
META_CI = "io.modelcontextprotocol/clientInfo"
META_SI = "io.modelcontextprotocol/serverInfo"
META_LL = "io.modelcontextprotocol/logLevel"


# ------------------------------------------------------------------ loaders
def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.open()] if p.exists() else []


def wire_messages(run: Path) -> list[dict]:
    """Normalize both transports to a list of {dir, t, msg, http: {...}|None}."""
    out = []
    if (run / "wire.jsonl").exists():
        for w in load_jsonl(run / "wire.jsonl"):
            out.append({"dir": w["dir"], "t": w["t_mono_ns"], "msg": json.loads(w["raw"]), "http": None})
    elif (run / "http.jsonl").exists():
        for ex in load_jsonl(run / "http.jsonl"):
            if "parse_error" in ex:
                out.append({"dir": "parse_error", "t": None, "msg": {}, "http": ex}); continue
            q, s = ex["request"], ex["response"] or {}
            h = {"method": q["method"], "status": s.get("status"), "req_headers": q["headers"],
                 "resp_headers": s.get("headers", {}), "resp_ct": (s.get("headers") or {}).get("content-type"),
                 "truncated": s.get("truncated", False), "conn": ex["conn"]}
            body = (q.get("body") or {}).get("json")
            if body is not None:
                out.append({"dir": "c2s", "t": ex["t_conn_open_ns"], "msg": body, "http": h})
            else:
                out.append({"dir": "c2s", "t": ex["t_conn_open_ns"], "msg": {"_http_only": q["method"]}, "http": h})
            sb = s.get("body") or {}
            if sb.get("json") is not None:
                out.append({"dir": "s2c", "t": ex["t_conn_open_ns"], "msg": sb["json"], "http": h})
            for ev in sb.get("sse_events", []):
                if "json" in ev:
                    out.append({"dir": "s2c", "t": ex["t_conn_open_ns"], "msg": ev["json"], "http": h, "sse_id": ev.get("id")})
    return out


STDERR_CLASSES = [
    ("uvicorn", re.compile(r"^INFO:\s|^StreamableHTTP session manager")),
    ("session_lifecycle", re.compile(r"session ID|Terminating session")),
    ("per_request", re.compile(r"^Processing request of type")),
    ("tool_outcome", re.compile(r"^Tool '.*' (failed|rejected|raised|not listed)")),
    ("deprecation_warning", re.compile(r"MCPDeprecationWarning|DeprecationWarning")),
    ("traceback", re.compile(r"^Traceback|^\s+File \"|^\s+\^|^\s{2,}\S|^[A-Za-z_.]*(Error|Exception)\b|^The above exception|^anyio\.")),
    ("shutdown_noise", re.compile(r"Error in standalone SSE writer|Shutting down|Waiting for application shutdown")),
]


def classify_stderr(lines: list[str]) -> Counter:
    c: Counter = Counter()
    for ln in lines:
        if not ln.strip():
            continue
        for name, rx in STDERR_CLASSES:
            if rx.search(ln):
                c[name] += 1
                break
        else:
            c["other"] += 1
    return c


# ------------------------------------------------------------------ fact extraction
def facts_for(run: Path) -> dict:
    rj = json.loads((run / "run.json").read_text())
    cli = load_jsonl(run / "client.jsonl")
    W = wire_messages(run)
    reqs = [w for w in W if w["dir"] == "c2s" and "method" in w["msg"] and "id" in w["msg"]]
    notifs_c2s = [w for w in W if w["dir"] == "c2s" and "method" in w["msg"] and "id" not in w["msg"]]
    results = [w for w in W if w["dir"] == "s2c" and "result" in w["msg"]]
    errors = [w for w in W if w["dir"] == "s2c" and "error" in w["msg"]]
    notifs_s2c = [w for w in W if w["dir"] == "s2c" and "method" in w["msg"]]
    by_id_req = {w["msg"]["id"]: w for w in reqs}
    by_id_resp = {w["msg"]["id"]: w for w in results + errors}

    def meta_of_req(w):
        return ((w["msg"].get("params") or {}).get("_meta") or {})

    def meta_of_res(w):
        return ((w["msg"].get("result") or {}).get("_meta") or {})

    f: dict = {"cell": rj["arm"] + "-" + rj["transport"] + ("-nootel" if rj.get("no_otel") else "") + ("-backend" if rj.get("backend") else "") + ("-instr" if rj.get("instrument") else ""),
               "rep": rj["rep"], "client_rc": rj.get("client_rc"), "error": rj.get("error")}
    neg = next((r for r in cli if r["kind"] == "negotiated"), {})
    f["negotiated_version"] = neg.get("protocol_version")
    f["server_info_seen_by_client"] = neg.get("server_info")
    f["client_api"] = next((r.get("api") for r in cli if r["kind"] == "start"), None)
    f["client_sdk"] = next((r.get("sdk_version") for r in cli if r["kind"] == "start"), None)
    # handshake / discover
    f["wire_initialize_requests"] = sum(1 for w in reqs if w["msg"]["method"] == "initialize")
    f["wire_initialized_notifications"] = sum(1 for w in notifs_c2s if w["msg"]["method"] == "notifications/initialized")
    disc = [w for w in reqs if w["msg"]["method"] == "server/discover"]
    f["wire_discover_requests"] = len(disc)
    f["discover_outcome"] = None
    if disc:
        d = disc[0]
        r = by_id_resp.get(d["msg"]["id"])
        if r is None:
            f["discover_outcome"] = "no JSON-RPC response" + (f" (HTTP {d['http']['status']})" if d["http"] else "")
        elif "error" in r["msg"]:
            f["discover_outcome"] = f"error {r['msg']['error']['code']} {r['msg']['error'].get('message','')[:60]}" + (f" (HTTP {r['http']['status']})" if r["http"] else "")
        else:
            res = r["msg"]["result"]
            f["discover_outcome"] = f"result supportedVersions={res.get('supportedVersions')} instructions={'yes' if res.get('instructions') else 'no'} ttlMs={res.get('ttlMs')} cacheScope={res.get('cacheScope')} serverInfo={'yes' if META_SI in (res.get('_meta') or {}) else 'no'}"
    # per-request _meta
    non_hs = [w for w in reqs if w["msg"]["method"] not in ("initialize",)]
    f["n_requests"] = len(reqs)
    f["requests_with_meta_protocolVersion"] = sum(1 for w in non_hs if META_PV in meta_of_req(w))
    f["requests_with_meta_clientInfo"] = sum(1 for w in non_hs if META_CI in meta_of_req(w))
    f["requests_with_meta_logLevel"] = sum(1 for w in non_hs if META_LL in meta_of_req(w))
    f["requests_with_traceparent"] = sum(1 for w in non_hs if "traceparent" in meta_of_req(w))
    f["n_results"] = len(results)
    f["results_with_meta_serverInfo"] = sum(1 for w in results if META_SI in meta_of_res(w))
    f["results_with_resultType"] = sum(1 for w in results if "resultType" in (w["msg"].get("result") or {}))
    # tools/list
    tl_req = [w for w in reqs if w["msg"]["method"] == "tools/list"]
    f["wire_tools_list_requests"] = len(tl_req)
    tl_res = [by_id_resp[w["msg"]["id"]]["msg"]["result"] for w in tl_req if w["msg"]["id"] in by_id_resp and "result" in by_id_resp[w["msg"]["id"]]["msg"]]
    f["tools_list_ttlMs"] = tl_res[0].get("ttlMs") if tl_res else None
    f["tools_list_cacheScope"] = tl_res[0].get("cacheScope") if tl_res else None
    f["tools_list_has_ttl_key"] = ("ttlMs" in tl_res[0]) if tl_res else None
    # tool calls
    calls = [w for w in reqs if w["msg"]["method"] == "tools/call"]
    f["wire_tools_call_requests"] = len(calls)

    def call_outcome(name_filter, idx=0):
        cs = [w for w in calls if w["msg"]["params"]["name"] == name_filter]
        if len(cs) <= idx:
            return None
        r = by_id_resp.get(cs[idx]["msg"]["id"])
        if r is None:
            return "no response"
        if "error" in r["msg"]:
            return f"jsonrpc error {r['msg']['error']['code']}"
        res = r["msg"]["result"]
        txt = (res.get("content") or [{}])[0].get("text", "")
        return f"isError={res.get('isError')} text={txt[:70]!r}"
    f["fail_tool_outcome"] = call_outcome("fail_tool")
    f["fail_tool_cause_visible_to_client"] = ("fixture raised" in (f["fail_tool_outcome"] or ""))
    f["unknown_tool_outcome"] = call_outcome("no_such_tool")
    f["invalid_args_outcome"] = call_outcome("echo", 1)
    # resources
    rr = [w for w in reqs if w["msg"]["method"] == "resources/read"]
    f["missing_resource_outcome"] = None
    for w in rr:
        if w["msg"]["params"].get("uri") == "fixture://missing":
            r = by_id_resp.get(w["msg"]["id"])
            if r and "error" in r["msg"]:
                f["missing_resource_outcome"] = f"jsonrpc error {r['msg']['error']['code']}" + (f" (HTTP {r['http']['status']})" if r["http"] else "")
            elif r:
                f["missing_resource_outcome"] = "result"
    # protocol logging
    logn = [w for w in notifs_s2c if w["msg"]["method"] == "notifications/message"]
    f["wire_log_notifications"] = len(logn)
    f["wire_log_notifications_with_relatedRequestId"] = sum(1 for w in logn if "relatedRequestId" in ((w["msg"].get("params") or {}).get("_meta") or {}) or "relatedRequestId" in (w["msg"].get("params") or {}))
    f["client_log_notifications"] = sum(1 for r in cli if r["kind"] == "log_notification")
    f["wire_setLevel_requests"] = sum(1 for w in reqs if w["msg"]["method"] == "logging/setLevel")
    f["wire_other_s2c_notifications"] = Counter(w["msg"]["method"] for w in notifs_s2c if w["msg"]["method"] != "notifications/message")
    # http headers
    posts = [w for w in W if w["http"] and w["dir"] == "c2s" and w["http"]["method"] == "POST"]
    if posts:
        rh = lambda w, k: w["http"]["req_headers"].get(k)
        f["http_posts"] = len(posts)
        f["http_connections"] = len({w["http"]["conn"] for w in W if w["http"]})
        f["http_methods_seen"] = Counter(w["http"]["method"] for w in W if w["http"] and w["dir"] == "c2s")
        f["http_req_with_session_id"] = sum(1 for w in posts if rh(w, "mcp-session-id"))
        f["http_resp_with_session_id"] = sum(1 for w in W if w["http"] and w["dir"] == "s2c" and w["http"]["resp_headers"].get("mcp-session-id"))
        f["http_req_with_protocol_version_hdr"] = sum(1 for w in posts if rh(w, "mcp-protocol-version"))
        f["http_req_with_mcp_method_hdr"] = sum(1 for w in posts if rh(w, "mcp-method"))
        f["http_mcp_method_matches_body"] = sum(1 for w in posts if rh(w, "mcp-method") and rh(w, "mcp-method") == w["msg"].get("method"))
        tc = [w for w in posts if w["msg"].get("method") == "tools/call"]
        f["http_tools_call_posts"] = len(tc)
        f["http_tools_call_with_mcp_name"] = sum(1 for w in tc if rh(w, "mcp-name"))
        f["http_mcp_name_matches_body"] = sum(1 for w in tc if rh(w, "mcp-name") == w["msg"]["params"]["name"])
        f["http_mcp_name_scan_value"] = next((rh(w, "mcp-name") for w in tc if w["msg"]["params"]["name"] == "scan.v2-beta"), None)
        f["http_resources_read_with_mcp_name"] = sum(1 for w in posts if w["msg"].get("method") == "resources/read" and rh(w, "mcp-name"))
        f["http_resp_content_types"] = Counter(w["http"]["resp_ct"] for w in posts)
        f["http_resp_statuses"] = Counter(str(w["http"]["status"]) for w in posts)
        f["http_user_agent"] = posts[0]["http"]["req_headers"].get("user-agent")
        f["http_standalone_get"] = sum(1 for w in W if w["http"] and w["dir"] == "c2s" and w["http"]["method"] == "GET")
        f["http_delete"] = sum(1 for w in W if w["http"] and w["dir"] == "c2s" and w["http"]["method"] == "DELETE")
    # stderr
    lines = (run / "server.stderr").read_text(errors="replace").splitlines() if (run / "server.stderr").exists() else []
    f["stderr_lines_total"] = sum(1 for l in lines if l.strip())
    f["stderr_by_class"] = dict(classify_stderr(lines))
    f["stderr_has_tool_name_on_failure"] = any("fail_tool" in l for l in lines)
    f["stderr_has_fail_cause"] = any("fixture raised" in l for l in lines)
    f["stderr_has_per_request_line"] = any(l.startswith("Processing request of type") for l in lines)
    f["stderr_has_deprecation"] = any("MCPDeprecationWarning" in l for l in lines)
    f["stderr_has_request_id_or_tool_name_per_request"] = any(re.search(r"tools/call|request id|\bid=", l) for l in lines)
    # OTel
    for end in ("server", "client"):
        p = run / f"{end}.otel.jsonl"
        if not p.exists():
            f[f"otel_{end}"] = "not configured"
            f[f"otel_{end}_spans"] = None
            continue
        spans = load_jsonl(p)
        f[f"otel_{end}"] = "configured"
        f[f"otel_{end}_spans"] = len(spans)
        f[f"otel_{end}_kinds"] = dict(Counter(s["kind"] for s in spans))
        f[f"otel_{end}_attr_keys"] = sorted({k for s in spans for k in s["attributes"]})
        f[f"otel_{end}_error_spans"] = sum(1 for s in spans if s["status"] == "ERROR")
        f[f"otel_{end}_error_types"] = dict(Counter(str(s["attributes"].get("error.type")) for s in spans if s["status"] == "ERROR"))
        if end == "server":
            f["otel_server_spans_with_remote_parent"] = sum(1 for s in spans if s.get("parent_remote"))
            f["otel_server_tool_names"] = sorted({s["attributes"].get("gen_ai.tool.name") for s in spans if s["attributes"].get("gen_ai.tool.name")})
            f["otel_server_scan_name"] = next((s["attributes"].get("gen_ai.tool.name") for s in spans if s["attributes"].get("gen_ai.tool.name") == "scan.v2-beta"), None)
            f["otel_server_has_arguments"] = any(k.startswith("gen_ai.tool.call") for s in spans for k in s["attributes"])
            f["otel_server_exception_events"] = sum(1 for s in spans for e in s["events"] if e["name"] == "exception")
    if (run / "server.otel.jsonl").exists() and (run / "client.otel.jsonl").exists():
        st = {s["trace_id"] for s in load_jsonl(run / "server.otel.jsonl")}
        ct = {s["trace_id"] for s in load_jsonl(run / "client.otel.jsonl")}
        f["otel_shared_trace_ids"] = len(st & ct)
    # backend
    if (run / "backend.jsonl").exists():
        b = load_jsonl(run / "backend.jsonl")
        f["backend_requests"] = len(b)
        f["backend_traceparent"] = [r["headers"].get("traceparent") for r in b]
        if f.get("otel_server_spans"):
            st = {s["trace_id"] for s in load_jsonl(run / "server.otel.jsonl")}
            f["backend_traceparent_trace_in_server_spans"] = [bool(tp and tp.split("-")[1] in st) for tp in f["backend_traceparent"]]
    # timing (incidental)
    f["step_dur_ns"] = {r["step"]: r["dur_ns"] for r in cli if r["kind"] == "step"}
    f["connect_dur_ns"] = neg.get("dur_ns")
    f["wall_ns"] = rj.get("wall_ns")
    return f


VARIABLE_KEYS = {"rep", "step_dur_ns", "connect_dur_ns", "wall_ns", "http_user_agent", "backend_traceparent"}


def stable_view(f: dict) -> str:
    return json.dumps({k: v for k, v in f.items() if k not in VARIABLE_KEYS}, sort_keys=True, default=str)


def main() -> None:
    all_facts: dict[str, list[dict]] = defaultdict(list)
    for cell_dir in sorted(RUNS.iterdir()):
        if not cell_dir.is_dir():
            continue
        for rep_dir in sorted(cell_dir.iterdir()):
            if not (rep_dir / "run.json").exists():
                continue
            if (rep_dir / "tcp.jsonl").exists() and not (rep_dir / "http.jsonl").exists():
                import subprocess
                subprocess.run([sys.executable, str(HERE / "parse_http.py"), str(rep_dir)], check=True, stdout=subprocess.DEVNULL)
            f = facts_for(rep_dir)
            all_facts[f["cell"]].append(f)
    (OUT / "facts.json").write_text(json.dumps(all_facts, indent=1, default=str))

    # stability
    stab = ["# Repeat stability (H12)", "", "| cell | reps | identical presence record across reps | differing keys |", "|---|---|---|---|"]
    for cell, fs in all_facts.items():
        views = [stable_view(f) for f in fs]
        ident = len(set(views)) == 1
        diff = []
        if not ident:
            keys = set().union(*[json.loads(v).keys() for v in views])
            diff = sorted(k for k in keys if len({json.dumps(json.loads(v).get(k), sort_keys=True) for v in views}) > 1)
        stab.append(f"| {cell} | {len(fs)} | {'yes' if ident else 'NO'} | {', '.join(diff) if diff else ''} |")
    (OUT / "stability.md").write_text("\n".join(stab) + "\n")

    # matrix: rows = facts, cols = cells (rep1 values)
    cells = [c for c in ["A-stdio", "B-stdio", "C-stdio", "Clog-stdio", "D-stdio", "A-http", "B-http", "C-http", "Clog-http", "D-http"] if c in all_facts]
    extra = sorted(c for c in all_facts if c not in cells)
    rows = [
        ("negotiated_version", "negotiated version (client)"),
        ("client_api", "client API"),
        ("wire_initialize_requests", "wire: initialize requests"),
        ("wire_initialized_notifications", "wire: notifications/initialized"),
        ("wire_discover_requests", "wire: server/discover requests"),
        ("discover_outcome", "wire: server/discover outcome"),
        ("n_requests", "wire: JSON-RPC requests"),
        ("requests_with_meta_protocolVersion", "wire: requests carrying _meta protocolVersion"),
        ("requests_with_meta_clientInfo", "wire: requests carrying _meta clientInfo"),
        ("requests_with_meta_logLevel", "wire: requests carrying _meta logLevel"),
        ("requests_with_traceparent", "wire: requests carrying _meta traceparent"),
        ("n_results", "wire: JSON-RPC results"),
        ("results_with_meta_serverInfo", "wire: results carrying _meta serverInfo"),
        ("wire_tools_list_requests", "wire: tools/list requests (2 issued)"),
        ("tools_list_has_ttl_key", "wire: tools/list result has ttlMs"),
        ("tools_list_ttlMs", "wire: tools/list ttlMs value"),
        ("tools_list_cacheScope", "wire: tools/list cacheScope"),
        ("fail_tool_outcome", "wire: fail_tool outcome"),
        ("fail_tool_cause_visible_to_client", "client sees fail_tool cause"),
        ("unknown_tool_outcome", "wire: unknown tool outcome"),
        ("invalid_args_outcome", "wire: missing-argument outcome"),
        ("missing_resource_outcome", "wire: missing resource outcome"),
        ("wire_log_notifications", "wire: notifications/message"),
        ("client_log_notifications", "client: log notifications delivered"),
        ("wire_setLevel_requests", "wire: logging/setLevel"),
        ("http_connections", "HTTP: TCP connections"),
        ("http_posts", "HTTP: POSTs"),
        ("http_standalone_get", "HTTP: standalone GET stream"),
        ("http_delete", "HTTP: DELETE (session end)"),
        ("http_req_with_session_id", "HTTP: POSTs with Mcp-Session-Id"),
        ("http_resp_with_session_id", "HTTP: responses carrying a JSON-RPC message with Mcp-Session-Id (DELETE response not counted)"),
        ("http_req_with_protocol_version_hdr", "HTTP: POSTs with MCP-Protocol-Version"),
        ("http_req_with_mcp_method_hdr", "HTTP: POSTs with Mcp-Method"),
        ("http_mcp_method_matches_body", "HTTP: Mcp-Method equals body method"),
        ("http_tools_call_posts", "HTTP: tools/call POSTs"),
        ("http_tools_call_with_mcp_name", "HTTP: tools/call POSTs with Mcp-Name"),
        ("http_mcp_name_matches_body", "HTTP: Mcp-Name equals body tool name"),
        ("http_mcp_name_scan_value", "HTTP: Mcp-Name for scan.v2-beta"),
        ("http_resources_read_with_mcp_name", "HTTP: resources/read with Mcp-Name"),
        ("http_resp_content_types", "HTTP: response content types"),
        ("http_resp_statuses", "HTTP: response statuses"),
        ("stderr_lines_total", "stderr: non-empty lines"),
        ("stderr_by_class", "stderr: lines by class"),
        ("stderr_has_per_request_line", "stderr: one line per request"),
        ("stderr_has_tool_name_on_failure", "stderr: tool name on failure"),
        ("stderr_has_fail_cause", "stderr: failure cause"),
        ("stderr_has_deprecation", "stderr: MCPDeprecationWarning"),
        ("otel_server", "OTel server exporter"),
        ("otel_server_spans", "OTel server spans"),
        ("otel_server_attr_keys", "OTel server attribute keys"),
        ("otel_server_spans_with_remote_parent", "OTel server spans with remote parent"),
        ("otel_server_error_types", "OTel server error.type values"),
        ("otel_server_has_arguments", "OTel server: tool arguments on span"),
        ("otel_client", "OTel client exporter"),
        ("otel_client_spans", "OTel client spans"),
        ("otel_client_attr_keys", "OTel client attribute keys"),
        ("otel_shared_trace_ids", "OTel: trace ids shared client/server"),
    ]

    def cellval(c, k):
        fs = all_facts[c]
        v = fs[0].get(k)
        if isinstance(v, dict):
            v = ", ".join(f"{a}={b}" for a, b in sorted(v.items())) or "{}"
        if isinstance(v, list):
            v = ", ".join(map(str, v)) if v else "[]"
        s = str(v).replace("|", "\\|")
        return s

    md = ["# Presence matrix (rep 1 of each cell; stability in stability.md)", ""]
    for group, cols in (("stdio", [c for c in cells if c.endswith("stdio")]), ("http", [c for c in cells if c.endswith("http")])):
        md += [f"## {group}", "", "| fact | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        for k, label in rows:
            if group == "stdio" and k.startswith("http_"):
                continue
            md.append(f"| {label} | " + " | ".join(cellval(c, k) for c in cols) + " |")
        md.append("")
    if extra:
        md += ["## single-run checks", "", "| fact | " + " | ".join(extra) + " |", "|---|" + "---|" * len(extra)]
        for k, label in rows:
            md.append(f"| {label} | " + " | ".join(cellval(c, k) for c in extra) + " |")
        for k in ("backend_requests", "backend_traceparent", "backend_traceparent_trace_in_server_spans"):
            md.append(f"| {k} | " + " | ".join(cellval(c, k) for c in extra) + " |")
        md.append("")
    (OUT / "matrix.md").write_text("\n".join(md))

    # timing (incidental)
    tm = ["# Incidental timings (ms, median over reps, CV %; under contention, no claim)", "", "| cell | connect | tools/list#1 | tools/call echo | fail_tool | log_then_echo | wall |", "|---|---|---|---|---|---|---|"]
    for c in cells + extra:
        fs = all_facts[c]

        def med_cv(vals):
            vals = [v / 1e6 for v in vals if v is not None]
            if not vals:
                return "-"
            m = statistics.median(vals)
            cv = (statistics.pstdev(vals) / statistics.mean(vals) * 100) if len(vals) > 1 and statistics.mean(vals) else 0
            return f"{m:.1f} ({cv:.0f}%)"
        conn = [f.get("connect_dur_ns") or f["step_dur_ns"].get("initialize") for f in fs]
        tm.append(f"| {c} | {med_cv(conn)} | {med_cv([f['step_dur_ns'].get('tools/list#1') for f in fs])} | {med_cv([f['step_dur_ns'].get('tools/call echo') for f in fs])} | {med_cv([f['step_dur_ns'].get('tools/call fail_tool') for f in fs])} | {med_cv([f['step_dur_ns'].get('tools/call log_then_echo') for f in fs])} | {med_cv([f['wall_ns'] for f in fs])} |")
    (OUT / "timing.md").write_text("\n".join(tm) + "\n")
    print("\n".join(stab))
    print(f"cells: {len(all_facts)}; wrote results/facts.json, matrix.md, stability.md, timing.md")


if __name__ == "__main__":
    main()

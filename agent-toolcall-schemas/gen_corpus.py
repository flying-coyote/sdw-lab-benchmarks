#!/usr/bin/env python3
"""Generate N synthetic MCP tool calls and write them three ways (L1 typed OCSF, L2 OTel attributes map, L3 AOS
unmapped JSON) with identical codec and row-group size. Usage: gen_corpus.py N
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pyarrow as pa

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
from common import BASE_EPOCH, configure_duckdb, new_rng, pin_artifact  # noqa: E402

import duckdb  # noqa: E402

SERVERS = {
    "duckdb-lab": ["list_tables", "describe_table", "run_query", "export_table"],
    "files": ["read_file", "write_file", "list_dir", "exec_command"],
    "github": ["search_issues", "create_issue", "get_pr"],
    "slack": ["post_message", "search_messages"],
    "jira": ["get_ticket", "create_ticket", "search"],
    "web": ["fetch_url", "search_web"],
}
TOOLS = [(s, t) for s, ts in SERVERS.items() for t in ts]
assert len(TOOLS) == 18
DESTRUCTIVE = {"export_table", "write_file", "exec_command", "create_issue", "post_message", "create_ticket"}
# 12-row allowlist; the 6 pairs left out are the off-allowlist set Q5 counts.
ALLOWLIST = [p for p in TOOLS if p[1] not in {"export_table", "exec_command", "write_file", "create_issue",
                                              "fetch_url", "post_message"}]
assert len(ALLOWLIST) == 12
TOOL_W = {"run_query": 30, "list_tables": 6, "describe_table": 8, "export_table": 2, "read_file": 14,
          "write_file": 3, "list_dir": 6, "exec_command": 2, "search_issues": 6, "create_issue": 1, "get_pr": 4,
          "post_message": 3, "search_messages": 4, "get_ticket": 5, "create_ticket": 1, "search": 4,
          "fetch_url": 4, "search_web": 5}
N_AGENTS = 400


def args_for(rng, tool):
    if tool == "run_query":
        if rng.random() < 0.002:
            return {"sql": f"COPY (SELECT * FROM auth_events WHERE user_name LIKE 'u{rng.randint(0, 99)}%') "
                           f"TO 's3://bucket-{rng.randint(0, 9)}/x.parquet'", "limit": 20}
        return {"sql": f"SELECT user_name, count(*) FROM auth_events WHERE status = 'Failure' "
                       f"AND src_ip LIKE '10.0.{rng.randint(0, 3)}.%' GROUP BY 1 LIMIT {rng.randint(5, 50)}",
                "limit": 20}
    if tool in ("read_file", "write_file", "list_dir"):
        return {"path": f"/srv/data/{rng.randint(0, 999)}/file{rng.randint(0, 99)}.txt"}
    if tool == "exec_command":
        return {"command": rng.choice(["whoami", "ls -la /tmp", "cat /etc/hosts", "curl -s http://example.org"])}
    if tool in ("describe_table", "export_table"):
        return {"table": rng.choice(["auth_events", "process_events", "dns_events"]),
                **({"filename": f"out{rng.randint(0, 99)}.parquet"} if tool == "export_table" else {})}
    if tool in ("fetch_url",):
        return {"url": f"https://site{rng.randint(0, 500)}.example.com/page{rng.randint(0, 50)}"}
    return {"query": f"term-{rng.randint(0, 5000)}", "max": rng.randint(5, 50)}


def generate(n: int):
    rng = new_rng(9202)  # R2 sub-seed
    tools, tw = [t for t in TOOLS], [TOOL_W[t[1]] for t in TOOLS]
    agent_w = [1.0 / (k + 1) ** 0.8 for k in range(N_AGENTS)]
    cols = {k: [] for k in ("i", "time_ms", "agent", "server", "tool", "session", "is_error", "req_id",
                            "duration_ms", "args", "result")}
    agents = rng.choices(range(N_AGENTS), weights=agent_w, k=n)
    picks = rng.choices(range(len(tools)), weights=tw, k=n)
    t = BASE_EPOCH * 1000
    for i in range(n):
        a = agents[i]
        s, tl = tools[picks[i]]
        t += rng.randint(1, 120)
        err_p = 0.12 if tl in ("run_query", "exec_command", "fetch_url") else 0.02
        err = rng.random() < err_p
        cols["i"].append(i)
        cols["time_ms"].append(t)
        cols["agent"].append(f"agent-{a:04d}")
        cols["server"].append(s)
        cols["tool"].append(tl)
        cols["session"].append(f"sess-{a:04d}-{(t // 1_800_000) % 100000:05d}")  # ~30 min sessions per agent
        cols["is_error"].append(err)
        cols["req_id"].append(str(rng.randint(1, 10_000_000)))
        cols["duration_ms"].append(rng.randint(1, 900))
        cols["args"].append(json.dumps(args_for(rng, tl)))
        cols["result"].append(json.dumps([{"type": "text", "text": "Error executing tool " + tl if err
                                           else f"ok {rng.randint(0, 10_000)} rows"}]))
    return pa.table(cols)


L1_SQL = """
SELECT make_timestamp(time_ms * 1000) AS time, 6003 AS class_uid, 99 AS activity_id,
  CASE WHEN is_error THEN 2 ELSE 1 END AS status_id, duration_ms::BIGINT AS duration,
  {'session': {'uid': session}} AS actor,
  {'uid': agent, 'name': agent || '-name', 'instance_uid': agent || '-i1',
   'ai_model': {'name': 'model-x', 'ai_provider': 'provider-y'}} AS ai_agent,
  {'name': tool, 'type_id': 1, 'source_id': 1, 'transport_id': 2, 'transaction_uid': req_id,
   'service': {'name': server, 'version': '1.0.0'},
   'is_readonly': tool NOT IN ({destr}), 'is_destructive': tool IN ({destr})} AS ai_capability,
  {'operation': 'tools/call', 'version': '2025-11-25',
   'request': {'uid': req_id, 'data': args},
   'response': {'data': result, 'error_message': CASE WHEN is_error THEN 'Error executing tool ' || tool END}} AS api
FROM base ORDER BY time_ms
"""

L2_SQL = """
SELECT md5(req_id || i::VARCHAR) AS trace_id, substr(md5(i::VARCHAR), 1, 16) AS span_id,
  time_ms * 1000000 AS start_time_unix_nano, duration_ms * 1000000 AS duration_ns,
  'tools/call ' || tool AS span_name, CASE WHEN is_error THEN 'ERROR' ELSE 'UNSET' END AS status_code,
  map_from_entries(list_concat([
    {'k': 'mcp.method.name', 'v': 'tools/call'}, {'k': 'mcp.protocol.version', 'v': '2025-11-25'},
    {'k': 'jsonrpc.request.id', 'v': req_id}, {'k': 'gen_ai.operation.name', 'v': 'execute_tool'},
    {'k': 'gen_ai.tool.name', 'v': tool}, {'k': 'gen_ai.agent.id', 'v': agent},
    {'k': 'gen_ai.agent.name', 'v': agent || '-name'}, {'k': 'gen_ai.conversation.id', 'v': session},
    {'k': 'gen_ai.request.model', 'v': 'model-x'}, {'k': 'gen_ai.provider.name', 'v': 'provider-y'},
    {'k': 'network.transport', 'v': 'tcp'}, {'k': 'sdw.mcp.server.name', 'v': server},
    {'k': 'gen_ai.tool.call.arguments', 'v': args}, {'k': 'gen_ai.tool.call.result', 'v': result}],
    CASE WHEN is_error THEN [{'k': 'error.type', 'v': 'tool_error'}] ELSE [] END)) AS attributes
FROM base ORDER BY time_ms
"""

# AOS "Agent Activity" example shape (extend_ocsf.md example 1): api.operation = 'tools/call', tool name, arguments,
# session, agent context and step inside unmapped.aos; actor.user carries the agent; status_id is base OCSF.
L3_SQL = """
SELECT make_timestamp(time_ms * 1000) AS time, 6003 AS class_uid, 1 AS activity_id, 'Agent Tool Use' AS activity_name,
  CASE WHEN is_error THEN 2 ELSE 1 END AS status_id, duration_ms::BIGINT AS duration,
  {'user': {'uid': agent, 'name': agent || '-name', 'type_id': 99, 'type': 'AI Agent'}} AS actor,
  {'operation': 'tools/call', 'service': {'name': server, 'version': '1.0.0'}} AS api,
  {'type_id': 99, 'name': 'AI Agent Endpoint'} AS src_endpoint,
  to_json({'aos': {
     'tool_call': {'name': tool, 'arguments': json(args)},
     'context': {'agent': {'id': agent, 'name': agent || '-name', 'version': '1.0.0'},
                 'session': {'id': session}, 'model': {'id': 'model-x', 'provider': {'name': 'provider-y'}}},
     'step': {'id': req_id, 'type': 'toolCall', 'is_error': is_error,
              'outputs': json(result)}}})::VARCHAR AS unmapped
FROM base ORDER BY time_ms
"""


def main(n: int) -> None:
    outdir = HERE / "data" / f"n{n}"
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    base = generate(n)
    gen_s = time.perf_counter() - t0
    con = configure_duckdb(duckdb.connect())
    con.register("base_arrow", base)
    con.execute("CREATE TABLE base AS SELECT * FROM base_arrow")
    con.execute("CREATE TABLE allowlist(server VARCHAR, tool VARCHAR)")
    con.executemany("INSERT INTO allowlist VALUES (?, ?)", ALLOWLIST)
    con.execute(f"COPY allowlist TO '{outdir}/allowlist.parquet' (FORMAT parquet)")
    destr = ", ".join(f"'{d}'" for d in sorted(DESTRUCTIVE))
    meta = {"n": n, "generate_s": round(gen_s, 2), "layouts": {}}
    for name, sql in (("L1_typed", L1_SQL.replace("{destr}", destr)), ("L2_otel_map", L2_SQL),
                      ("L3_aos_unmapped", L3_SQL)):
        path = outdir / f"{name}.parquet"
        t1 = time.perf_counter()
        con.execute(f"COPY ({sql}) TO '{path}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 122880)")
        write_s = time.perf_counter() - t1
        codecs = sorted({r[0] for r in con.execute(
            f"SELECT DISTINCT compression FROM parquet_metadata('{path}')").fetchall()})
        rgs = con.execute(f"SELECT num_row_groups FROM parquet_file_metadata('{path}')").fetchone()[0]
        meta["layouts"][name] = {"bytes": path.stat().st_size, "write_s": round(write_s, 3), "codecs": codecs,
                                 "row_groups": int(rgs), "pin": pin_artifact(con, str(path))}
        print(name, meta["layouts"][name]["bytes"], codecs, rgs, f"write {write_s:.2f}s")
    (outdir / "corpus_meta.json").write_text(json.dumps(meta, indent=1, default=str))


if __name__ == "__main__":
    main(int(sys.argv[1]))

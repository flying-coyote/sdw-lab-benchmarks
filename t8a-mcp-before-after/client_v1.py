#!/usr/bin/env python3
"""T8a client on mcp 1.30.0 (ClientSession, initialize handshake). Writes client.jsonl.

Usage: client_v1.py stdio <out-dir> <proxy-cmd...>
       client_v1.py http  <out-dir> <url>
Env: T8A_OTEL_FILE (client OTel exporter), T8A_BACKEND_URL (adds the fetch_backend call).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client, get_default_environment
from mcp.client.streamable_http import streamable_http_client
from pydantic import AnyUrl

import t8a_common

t8a_common.configure_otel("t8a-client-v1")
mode, out_dir = sys.argv[1], Path(sys.argv[2])
rest = sys.argv[3:]
CLIENT_LOG = out_dir / "client.jsonl"


def rec(**kw):
    kw["t_mono_ns"] = time.monotonic_ns()
    t8a_common.jsonl_append(CLIENT_LOG, kw)


async def on_log(params):
    rec(kind="log_notification", level=params.level, logger=params.logger, data=params.data)


async def step(name, coro):
    t0 = time.perf_counter_ns()
    try:
        r = await coro
        dt = time.perf_counter_ns() - t0
        d = r.model_dump(mode="json", by_alias=True, exclude_none=True) if hasattr(r, "model_dump") else r
        rec(kind="step", step=name, ok=True, dur_ns=dt, result=d)
        return r
    except Exception as e:  # JSON-RPC error or SDK exception
        dt = time.perf_counter_ns() - t0
        code = getattr(getattr(e, "error", None), "code", None)
        rec(kind="step", step=name, ok=False, dur_ns=dt, exc=type(e).__name__, exc_str=str(e), jsonrpc_code=code)
        return None


async def drive(session: ClientSession):
    init = await step("initialize", session.initialize())
    rec(kind="negotiated", protocol_version=init.protocolVersion if init else None,
        server_info=init.serverInfo.model_dump(mode="json") if init else None)
    await step("tools/list#1", session.list_tools())
    for name, args in t8a_common.CALLS:
        await step(f"tools/call {name}", session.call_tool(name, args))
    await step("tools/list#2", session.list_tools())
    await step("resources/read fixture://note", session.read_resource(AnyUrl("fixture://note")))
    await step("resources/read fixture://missing", session.read_resource(AnyUrl("fixture://missing")))
    if os.environ.get("T8A_BACKEND_URL"):
        await step("tools/call fetch_backend", session.call_tool("fetch_backend", {"url": os.environ["T8A_BACKEND_URL"]}))


async def main():
    CLIENT_LOG.write_text("")
    rec(kind="start", sdk_version=__import__("importlib.metadata").metadata.version("mcp"), mode=mode, api="ClientSession")
    if mode == "stdio":
        params = StdioServerParameters(command=rest[0], args=rest[1:], env=t8a_common.server_env(get_default_environment()))
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w, logging_callback=on_log) as s:
                await drive(s)
    else:
        async with streamable_http_client(rest[0]) as (r, w, get_sid):
            async with ClientSession(r, w, logging_callback=on_log) as s:
                await drive(s)
                rec(kind="http_session_id", session_id=get_sid())
    rec(kind="end")


asyncio.run(main())

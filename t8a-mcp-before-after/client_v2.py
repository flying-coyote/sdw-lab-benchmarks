#!/usr/bin/env python3
"""T8a client on mcp 2.3.0 (mcp.Client). Writes client.jsonl.

Usage: client_v2.py stdio <out-dir> <mode> <log_level|-> <proxy-cmd...>
       client_v2.py http  <out-dir> <mode> <log_level|-> <url>
mode: legacy | auto | 2026-07-28. Env: T8A_OTEL_FILE, T8A_BACKEND_URL.
"""
from __future__ import annotations

import asyncio
import importlib.metadata
import os
import sys
import time
from pathlib import Path

from mcp import Client, StdioServerParameters
from mcp.client.stdio import get_default_environment

import t8a_common

t8a_common.configure_otel("t8a-client-v2")
mode, out_dir, conn_mode, log_level = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4]
rest = sys.argv[5:]
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
    except Exception as e:
        dt = time.perf_counter_ns() - t0
        code = getattr(getattr(e, "error", None), "code", None)
        rec(kind="step", step=name, ok=False, dur_ns=dt, exc=type(e).__name__, exc_str=str(e), jsonrpc_code=code)
        return None


async def main():
    CLIENT_LOG.write_text("")
    rec(kind="start", sdk_version=importlib.metadata.version("mcp"), mode=mode, api="Client", conn_mode=conn_mode,
        log_level=None if log_level == "-" else log_level)
    target = StdioServerParameters(command=rest[0], args=rest[1:], env=t8a_common.server_env(get_default_environment())) if mode == "stdio" else rest[0]
    kw = dict(mode=conn_mode, logging_callback=on_log)
    if log_level != "-":
        kw["log_level"] = log_level
    t0 = time.perf_counter_ns()
    async with Client(target, **kw) as c:
        rec(kind="negotiated", protocol_version=c.protocol_version, dur_ns=time.perf_counter_ns() - t0,
            server_info=c.server_info.model_dump(mode="json") if c.server_info else None,
            discover=c.session.discover_result.model_dump(mode="json", by_alias=True, exclude_none=True) if c.session.discover_result else None,
            initialize=c.session.initialize_result.model_dump(mode="json", by_alias=True, exclude_none=True) if c.session.initialize_result else None)
        await step("tools/list#1", c.list_tools())
        for name, args in t8a_common.CALLS:
            await step(f"tools/call {name}", c.call_tool(name, args))
        await step("tools/list#2", c.list_tools())
        await step("resources/read fixture://note", c.read_resource("fixture://note"))
        await step("resources/read fixture://missing", c.read_resource("fixture://missing"))
        if os.environ.get("T8A_BACKEND_URL"):
            await step("tools/call fetch_backend", c.call_tool("fetch_backend", {"url": os.environ["T8A_BACKEND_URL"]}))
    rec(kind="end")


asyncio.run(main())

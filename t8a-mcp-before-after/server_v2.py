#!/usr/bin/env python3
"""T8a fixture server on mcp 2.3.0 (MCPServer). Test fixture; no attack content.

Usage: server_v2.py stdio | http <port>
Defaults are untouched (log level INFO, SSE responses, stateful HTTP, host 127.0.0.1, default middleware).
"""
from __future__ import annotations

import os
import sys

import httpx
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations

import t8a_common

t8a_common.configure_otel("t8a-fixture-server-v2")
if os.environ.get("T8A_HTTPX_INSTRUMENT") == "1":  # trace-hop sub-arm only
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    HTTPXClientInstrumentor().instrument()

server = MCPServer(name="t8a-fixture", version="0.1.0", instructions="T8a logging fixture server (SDW lab).")

RO = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


@server.tool(annotations=RO)
def echo(text: str) -> str:
    """Return the text unchanged (fixture)."""
    return text


@server.tool(name="scan.v2-beta", annotations=RO)
def scan_v2_beta(target: str) -> str:
    """Fixture tool whose name uses dot and hyphen; returns a canned string."""
    return f"fixture scan of {target}: nothing to report"


@server.tool(annotations=RO)
def fail_tool(reason: str) -> str:
    """Always raises ValueError (fixture)."""
    raise ValueError(f"fixture raised: {reason}")


@server.tool(annotations=RO)
async def log_then_echo(text: str, ctx: Context) -> str:
    """Emit two in-protocol log messages then return the text (fixture)."""
    await ctx.info(f"log_then_echo start: {text}")
    await ctx.info("log_then_echo done")
    return text


@server.tool(annotations=RO)
def fetch_backend(url: str) -> str:
    """GET a localhost URL and return the status code (fixture, trace-hop sub-arm)."""
    if not url.startswith("http://127.0.0.1"):
        raise ValueError("fixture only reaches 127.0.0.1")
    r = httpx.get(url, timeout=5.0)
    return f"backend status {r.status_code}"


@server.resource("fixture://note")
def note() -> str:
    """A static fixture note."""
    return "fixture note body"


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if mode == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host="127.0.0.1", port=int(sys.argv[2]))

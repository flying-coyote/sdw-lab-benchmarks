#!/usr/bin/env python3
"""T8a fixture server on mcp 1.30.0 (FastMCP). Test fixture; no attack content.

Usage: server_v1.py stdio | http <port>
Defaults are untouched (log level INFO, SSE responses, stateful HTTP, host 127.0.0.1).
"""
from __future__ import annotations

import sys

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

import t8a_common

t8a_common.configure_otel("t8a-fixture-server-v1")

port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
server = FastMCP("t8a-fixture", instructions="T8a logging fixture server (SDW lab).", port=port)

RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


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
        server.run("streamable-http")

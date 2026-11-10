#!/usr/bin/env python3
"""T9 fixture stdio MCP server (mcp 2.3.0 MCPServer). One tool, no attack content."""
import sys
from mcp.server.mcpserver import MCPServer
server = MCPServer(name="t9fixture", version="0.1.0", instructions="T9 lab fixture.")

@server.tool()
def echo(text: str) -> str:
    """Return the text unchanged (fixture)."""
    sys.stderr.write(f"t9fixture echo called: {text}\n")
    return text

if __name__ == "__main__":
    server.run(transport="stdio")

#!/usr/bin/env python3
"""Minimal reference DuckDB MCP server (stdio) for R2.

Built on the MCP Python SDK (mcp 2.x, MCPServer). Backed by an in-memory DuckDB seeded with small synthetic
tables, so every tools/call returns real query output. Tool annotations are set so the OCSF ai_capability
hint attributes have something to carry. Read-only tools reject anything that is not a SELECT.
"""
from __future__ import annotations

import os
import random
import re
from pathlib import Path
from typing import TypedDict

import duckdb
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

HERE = Path(__file__).resolve().parent
SANDBOX = HERE / "capture" / "sandbox"

con = duckdb.connect(":memory:")
rng = random.Random(20260601 + 2)
users = [f"user{i:03d}" for i in range(50)]
con.execute("CREATE TABLE auth_events(time TIMESTAMP, user_name VARCHAR, src_ip VARCHAR, status VARCHAR)")
con.executemany(
    "INSERT INTO auth_events VALUES (TIMESTAMP '2026-01-01' + to_seconds(?), ?, ?, ?)",
    [(i * 17, rng.choice(users), f"10.0.{rng.randint(0, 3)}.{rng.randint(1, 254)}",
      "Failure" if rng.random() < 0.1 else "Success") for i in range(5000)])
con.execute("CREATE TABLE process_events(time TIMESTAMP, host VARCHAR, cmd_line VARCHAR)")
con.executemany(
    "INSERT INTO process_events VALUES (TIMESTAMP '2026-01-01' + to_seconds(?), ?, ?)",
    [(i * 31, f"host{rng.randint(1, 20):02d}", rng.choice(["powershell -enc AAA", "cmd /c whoami", "notepad.exe"]))
     for i in range(2000)])

server = MCPServer(name="sdw-lab-duckdb", version="0.1.0",
                   instructions="Read-mostly DuckDB server over synthetic security tables (SDW lab R2).")

RO = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


def _tables() -> list[str]:
    return [r[0] for r in con.execute("SELECT table_name FROM information_schema.tables ORDER BY 1").fetchall()]


@server.tool(annotations=RO)
def list_tables() -> list[str]:
    """List the tables available in the lab DuckDB database."""
    return _tables()


@server.tool(annotations=RO)
def describe_table(table: str) -> list[dict]:
    """Return column names and types for one table."""
    if table not in _tables():
        raise ValueError(f"unknown table: {table}")
    return [{"column": c, "type": t} for c, t, *_ in con.execute(f'DESCRIBE "{table}"').fetchall()]


@server.tool(annotations=RO)
def run_query(sql: str, limit: int = 20) -> list[dict]:
    """Run a read-only SELECT against the lab database and return up to `limit` rows."""
    if not re.match(r"(?is)^\s*(select|with)\b", sql):
        raise ValueError("only SELECT/WITH statements are allowed")
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, [str(v) for v in row])) for row in cur.fetchmany(limit)]


class FailedLogins(TypedDict):
    user: str
    hours: int
    failed: int


@server.tool(annotations=RO, structured_output=True)
def count_failed_logins(user: str, hours: int = 24) -> FailedLogins:
    """Count failed authentications for a user in the first `hours` hours of the corpus."""
    n = con.execute(
        "SELECT count(*) FROM auth_events WHERE user_name = ? AND status = 'Failure' "
        "AND time < TIMESTAMP '2026-01-01' + to_hours(?)", [user, hours]).fetchone()[0]
    return {"user": user, "hours": hours, "failed": int(n)}


@server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True,
                                         idempotent_hint=False, open_world_hint=False))
def export_table(table: str, filename: str) -> str:
    """Export a table to a Parquet file in the server's sandbox directory (overwrites)."""
    if table not in _tables():
        raise ValueError(f"unknown table: {table}")
    if not re.fullmatch(r"[A-Za-z0-9_\-]+\.parquet", filename):
        raise ValueError("filename must be a bare *.parquet name")
    SANDBOX.mkdir(parents=True, exist_ok=True)
    out = SANDBOX / filename
    con.execute(f"COPY \"{table}\" TO '{out}' (FORMAT parquet)")
    return f"wrote {os.path.getsize(out)} bytes to sandbox/{filename}"


if __name__ == "__main__":
    server.run("stdio")

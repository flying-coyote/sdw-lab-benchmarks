#!/usr/bin/env python3
"""Drive the reference server through the stdio tee with the SDK client; 10 tools/call requests."""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
CAP = HERE / "capture" / "wire.jsonl"

CALLS = [
    ("list_tables", {}),
    ("describe_table", {"table": "auth_events"}),
    ("run_query", {"sql": "SELECT user_name, count(*) AS n FROM auth_events WHERE status='Failure' "
                          "GROUP BY 1 ORDER BY 2 DESC", "limit": 5}),
    ("run_query", {"sql": "SELEC user_name FROM auth_events"}),           # SQL syntax error
    ("run_query", {"sql": "DROP TABLE auth_events"}),                     # rejected by the tool
    ("count_failed_logins", {"user": "user007", "hours": 24}),
    ("count_failed_logins", {"user": "user042", "hours": 6}),
    ("export_table", {"table": "process_events", "filename": "process_events.parquet"}),
    ("describe_table", {"table": "dns_events"}),                          # missing table
    ("delete_all_rows", {"table": "auth_events"}),                        # tool does not exist
]


async def main() -> None:
    CAP.parent.mkdir(parents=True, exist_ok=True)
    CAP.write_text("")
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(HERE / "proxy.py"), str(CAP), sys.executable, str(HERE / "server.py")])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            await s.list_tools()
            for name, args in CALLS:
                try:
                    res = await s.call_tool(name, args)
                    print(name, "isError=", getattr(res, "is_error", None))
                except Exception as e:  # JSON-RPC level error
                    print(name, "EXC", type(e).__name__, e)
    n = sum(1 for _ in CAP.open())
    print(f"captured {n} wire messages -> {CAP}")


if __name__ == "__main__":
    asyncio.run(main())

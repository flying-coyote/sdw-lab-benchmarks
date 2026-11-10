#!/usr/bin/env python3
"""Raw TCP tee for the HTTP arms: 127.0.0.1:<listen> -> 127.0.0.1:<target>, bytes forwarded unchanged.

Usage: proxy_tcp.py <listen-port> <target-port> <capture.jsonl>
Every chunk read from either side is appended as {"conn": n, "dir": "c2s"|"s2c", "t_mono_ns": ..., "b64": ...}.
Framing (HTTP/1.1, chunked SSE) is parsed afterwards with h11, never in flight.
"""
import asyncio
import base64
import json
import sys
import time

listen_port, target_port, cap_path = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
cap = open(cap_path, "a", buffering=1)
conn_counter = 0


def log(conn: int, direction: str, data: bytes) -> None:
    cap.write(json.dumps({"conn": conn, "dir": direction, "t_mono_ns": time.monotonic_ns(),
                          "b64": base64.b64encode(data).decode("ascii")}) + "\n")


async def pump(conn: int, direction: str, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await r.read(65536)
            if not data:
                break
            log(conn, direction, data)
            w.write(data)
            await w.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        pass
    finally:
        try:
            w.close()
        except Exception:
            pass


async def handle(cr: asyncio.StreamReader, cw: asyncio.StreamWriter) -> None:
    global conn_counter
    conn_counter += 1
    conn = conn_counter
    log(conn, "open", b"")
    try:
        sr, sw = await asyncio.open_connection("127.0.0.1", target_port)
    except OSError as e:
        log(conn, "error", str(e).encode())
        cw.close()
        return
    await asyncio.gather(pump(conn, "c2s", cr, sw), pump(conn, "s2c", sr, cw))
    log(conn, "close", b"")


async def main() -> None:
    server = await asyncio.start_server(handle, "127.0.0.1", listen_port)
    async with server:
        await server.serve_forever()


asyncio.run(main())

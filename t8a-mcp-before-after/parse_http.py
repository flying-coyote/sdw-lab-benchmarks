#!/usr/bin/env python3
"""Parse a proxy_tcp.py byte log into http.jsonl: one record per HTTP exchange (request + response), with headers,
JSON bodies and SSE events. Uses h11 in lockstep per connection; framing is never touched in flight.
Usage: parse_http.py <run-dir>"""
from __future__ import annotations

import base64
import json
import sys
from collections import defaultdict
from pathlib import Path

import h11

run = Path(sys.argv[1])
conns = defaultdict(lambda: {"c2s": b"", "s2c": b"", "t0": None, "t_c2s": [], "t_s2c": []})
for line in (run / "tcp.jsonl").open():
    w = json.loads(line)
    c = conns[w["conn"]]
    if c["t0"] is None:
        c["t0"] = w["t_mono_ns"]
    if w["dir"] in ("c2s", "s2c"):
        data = base64.b64decode(w["b64"])
        c[w["dir"]] += data
        c["t_" + w["dir"]].append((w["t_mono_ns"], len(c[w["dir"]])))


def parse_body(ct: str, body: bytes) -> dict:
    out: dict = {"bytes": len(body)}
    if "event-stream" in ct:
        events = []
        for block in body.decode("utf-8", "replace").replace("\r\n", "\n").split("\n\n"):
            lines = block.split("\n")
            data = "".join(l[5:].lstrip() for l in lines if l.startswith("data:"))
            ev = next((l[6:].strip() for l in lines if l.startswith("event:")), None)
            eid = next((l[3:].strip() for l in lines if l.startswith("id:")), None)
            comment = [l for l in lines if l.startswith(":")]
            if data:
                try:
                    events.append({"event": ev, "id": eid, "json": json.loads(data)})
                except Exception:
                    events.append({"event": ev, "id": eid, "raw": data[:300]})
            elif comment:
                events.append({"comment": comment[0][:80]})
        out["sse_events"] = events
    elif body and "json" in ct:
        try:
            out["json"] = json.loads(body)
        except Exception:
            out["raw"] = body.decode("utf-8", "replace")[:500]
    elif body:
        out["raw"] = body.decode("utf-8", "replace")[:500]
    return out


def hdrs(h) -> dict:
    return {k.decode().lower(): v.decode() for k, v in h}


records = []
for conn, c in sorted(conns.items()):
    srv = h11.Connection(h11.SERVER)
    cli = h11.Connection(h11.CLIENT)
    srv.receive_data(c["c2s"]); srv.receive_data(b"")
    cli.receive_data(c["s2c"])  # no EOF: a stream the client closed mid-chunk parses as "truncated" with its complete chunks kept
    cycle = 0
    while True:
        # ---- request
        req = None
        body = b""
        done = False
        while True:
            try:
                ev = srv.next_event()
            except h11.RemoteProtocolError as e:
                records.append({"conn": conn, "cycle": cycle, "parse_error": f"request: {e}"}); done = True; break
            if ev is h11.NEED_DATA or ev is h11.PAUSED or isinstance(ev, h11.ConnectionClosed):
                done = True; break
            if isinstance(ev, h11.Request):
                req = {"method": ev.method.decode(), "target": ev.target.decode(), "headers": hdrs(ev.headers)}
            elif isinstance(ev, h11.Data):
                body += ev.data
            elif isinstance(ev, h11.EndOfMessage):
                break
        if done or req is None:
            break
        req["body"] = parse_body(req["headers"].get("content-type", ""), body)
        # tell the client-side parser what was asked (method matters for HEAD/204 rules), then read the response
        cli.send(h11.Request(method=req["method"], target=req["target"], headers=[("Host", "x")]))
        cli.send(h11.EndOfMessage())
        resp = None
        rbody = b""
        truncated = False
        while True:
            try:
                ev = cli.next_event()
            except h11.RemoteProtocolError as e:
                resp = {"parse_error": f"response: {e}"}; break
            if ev is h11.NEED_DATA or isinstance(ev, h11.ConnectionClosed) or ev is h11.PAUSED:
                truncated = resp is not None; break
            if isinstance(ev, h11.InformationalResponse):
                continue
            if isinstance(ev, h11.Response):
                resp = {"status": ev.status_code, "headers": hdrs(ev.headers)}
            elif isinstance(ev, h11.Data):
                rbody += ev.data
            elif isinstance(ev, h11.EndOfMessage):
                break
        if resp is not None and "status" in resp:
            resp["body"] = parse_body(resp["headers"].get("content-type", ""), rbody)
            if truncated:
                resp["truncated"] = True
        records.append({"conn": conn, "cycle": cycle, "t_conn_open_ns": c["t0"], "request": req, "response": resp})
        cycle += 1
        if truncated or resp is None:
            break
        # synthetic response on the server-side parser so it will accept the next request on this connection
        try:
            srv.send(h11.Response(status_code=200, headers=[("content-length", "0")]))
            srv.send(h11.EndOfMessage())
            srv.start_next_cycle()
            cli.start_next_cycle()
        except h11.LocalProtocolError:
            break

with (run / "http.jsonl").open("w") as f:
    for r in records:
        f.write(json.dumps(r, default=str) + "\n")
print(f"{run}: {len(records)} HTTP exchanges over {len(conns)} connections")

#!/usr/bin/env python3
"""Localhost backend listener for the trace-hop sub-arm: logs request headers, answers 200.

Usage: backend.py <port> <headers.jsonl>
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

port, out = int(sys.argv[1]), sys.argv[2]


class H(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        with open(out, "a", buffering=1) as f:
            f.write(json.dumps({"t_mono_ns": time.monotonic_ns(), "path": self.path,
                                "headers": {k.lower(): v for k, v in self.headers.items()}}) + "\n")
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet
        return


HTTPServer(("127.0.0.1", port), H).serve_forever()

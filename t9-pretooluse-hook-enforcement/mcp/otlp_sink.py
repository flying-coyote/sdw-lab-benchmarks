#!/usr/bin/env python3
"""Minimal OTLP/HTTP JSON sink on 127.0.0.1:4318: appends every POST body to evidence/otel_collector.jsonl (lab fixture)."""
import json, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
OUT = sys.argv[1]
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n)
        try: payload = json.loads(body)
        except Exception: payload = {"_raw_b64_len": n, "content_type": self.headers.get("Content-Type")}
        with open(OUT, "a") as f: f.write(json.dumps({"t": time.time(), "path": self.path, "ct": self.headers.get("Content-Type"), "payload": payload}) + "\n")
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b"{}")
    def log_message(self, *a): pass
HTTPServer(("127.0.0.1", 4318), H).serve_forever()

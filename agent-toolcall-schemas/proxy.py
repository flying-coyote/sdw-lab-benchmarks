#!/usr/bin/env python3
"""Line-level stdio tee between an MCP client and a server process.

Usage: proxy.py <capture.jsonl> <server-cmd...>
Every newline-delimited JSON-RPC message in either direction is forwarded unchanged and appended to the
capture file as {"dir": "c2s"|"s2c", "t_mono_ns": ..., "raw": "<line>"}; the raw line is kept verbatim.
"""
import json
import subprocess
import sys
import threading
import time

cap_path, cmd = sys.argv[1], sys.argv[2:]
lock = threading.Lock()
cap = open(cap_path, "a", buffering=1)
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)


def log(direction: str, line: bytes) -> None:
    with lock:
        cap.write(json.dumps({"dir": direction, "t_mono_ns": time.monotonic_ns(),
                              "raw": line.decode("utf-8").rstrip("\n")}) + "\n")


def s2c() -> None:
    for line in proc.stdout:
        log("s2c", line)
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()


t = threading.Thread(target=s2c, daemon=True)
t.start()
for line in sys.stdin.buffer:
    log("c2s", line)
    proc.stdin.write(line)
    proc.stdin.flush()
proc.stdin.close()
proc.wait()
t.join(timeout=2)

#!/usr/bin/env python3
"""Line-level stdio tee between an MCP client and a server process (R2 proxy.py, stderr redirected).

Usage: proxy_stdio.py <capture.jsonl> <server-stderr-file> <server-cmd...>
Every newline-delimited JSON-RPC message in either direction is forwarded unchanged and appended to the
capture file as {"dir": "c2s"|"s2c", "t_mono_ns": ..., "raw": "<line>"}.
"""
import json
import subprocess
import sys
import threading
import time

cap_path, err_path, cmd = sys.argv[1], sys.argv[2], sys.argv[3:]
lock = threading.Lock()
cap = open(cap_path, "a", buffering=1)
err = open(err_path, "ab", buffering=0)
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err)


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

"""R5 snapshotter: raw JSON-RPC over stdio to MCP servers, capture tools/list.

Live arm: R runs x K snapshots per server, fresh process per run, monotonic spacing.
Release arm: one tools/list per published version of two reference servers.
Usage: python -I snapshot.py live|release
"""
import json, os, subprocess, sys, time, select, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE / "snapshots"
WORK = HERE / "work"          # empty dirs: npx cwd and the filesystem server's allowed root
PROTO = "2025-06-18"
VENV_PY = str(HERE / ".venv/bin/python")
SCG = "/tmp/claude-1000/lab-ai-research/security-context-graph/scg_mcp.py"
NPX = shutil.which("npx")


def server_cmds(fs_ver="2026.8.31", ev_ver="2026.8.31"):
    (WORK / "fsroot").mkdir(parents=True, exist_ok=True)
    return {
        "scg": [VENV_PY, SCG],
        "everything": [NPX, "-y", f"@modelcontextprotocol/server-everything@{ev_ver}", "stdio"],
        "filesystem": [NPX, "-y", f"@modelcontextprotocol/server-filesystem@{fs_ver}", str(WORK / "fsroot")],
    }


class Client:
    def __init__(self, cmd, errlog):
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errlog,
                                  cwd=str(WORK), bufsize=0)
        self.buf = b""
        self.nid = 0

    def _send(self, obj):
        self.p.stdin.write((json.dumps(obj) + "\n").encode()); self.p.stdin.flush()

    def _readline(self, timeout):
        end = time.monotonic() + timeout
        while b"\n" not in self.buf:
            left = end - time.monotonic()
            if left <= 0:
                raise TimeoutError("no response")
            r, _, _ = select.select([self.p.stdout], [], [], left)
            if r:
                chunk = os.read(self.p.stdout.fileno(), 65536)
                if not chunk:
                    raise EOFError("server closed stdout")
                self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return line

    def request(self, method, params=None, timeout=120):
        self.nid += 1
        rid = self.nid
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
        while True:
            line = self._readline(timeout).strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue          # non-JSON stdout noise
            if msg.get("id") == rid and ("result" in msg or "error" in msg):
                return msg

    def initialize(self):
        r = self.request("initialize", {"protocolVersion": PROTO, "capabilities": {},
                                        "clientInfo": {"name": "sdw-r5-snapshotter", "version": "0.1"}}, timeout=300)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return r

    def tools_list(self):
        """Return (raw response texts, tools) following nextCursor; time the full listing."""
        tools, raws, cursor = [], [], None
        while True:
            r = self.request("tools/list", {"cursor": cursor} if cursor else {})
            if "error" in r:
                raise RuntimeError(r["error"])
            raws.append(r["result"])
            tools.extend(r["result"].get("tools", []))
            cursor = r["result"].get("nextCursor")
            if not cursor:
                return raws, tools

    def close(self):
        try:
            self.p.stdin.close(); self.p.terminate(); self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


def capture(name, cmd, k, gap_s, tag):
    out = []
    with open(SNAP / f"{tag}-{name}.stderr.log", "ab") as err:
        for attempt in (1, 2):
            c = Client(cmd, err)
            try:
                t0 = time.monotonic_ns()
                init = c.initialize()
                init_ms = (time.monotonic_ns() - t0) / 1e6
                nxt = time.monotonic()
                for i in range(k):
                    while time.monotonic() < nxt:
                        time.sleep(0.05)
                    nxt += gap_s
                    t1 = time.monotonic_ns()
                    raws, tools = c.tools_list()
                    out.append({"server": name, "tag": tag, "snapshot": i, "attempt": attempt,
                                "list_ms": (time.monotonic_ns() - t1) / 1e6, "init_ms": init_ms,
                                "serverInfo": init.get("result", {}).get("serverInfo"),
                                "protocolVersion": init.get("result", {}).get("protocolVersion"),
                                "tools": tools, "raw_pages": len(raws)})
                return out, None
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
                out = []
            finally:
                c.close()
    return [], last


def main():
    SNAP.mkdir(exist_ok=True); WORK.mkdir(exist_ok=True)
    mode = sys.argv[1]
    log = {"mode": mode, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "failures": {}}
    if mode == "live":
        R, K, GAP = 3, 6, 5.0
        rows = []
        for run in range(1, R + 1):
            for name, cmd in server_cmds().items():
                snaps, err = capture(name, cmd, K, GAP, f"live-r{run}")
                for s in snaps:
                    s["run"] = run
                rows += snaps
                if err:
                    log["failures"][f"{name}-r{run}"] = err
                print(f"run {run} {name}: {len(snaps)} snapshots {err or ''}", flush=True)
        (SNAP / "live.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    elif mode == "release":
        versions = {"filesystem": ["2025.8.21", "2025.11.25", "2025.12.18", "2026.1.14", "2026.7.4", "2026.7.10", "2026.8.31"],
                    "everything": ["2025.12.18", "2026.1.14", "2026.1.26", "2026.7.4", "2026.8.18", "2026.8.31"]}
        rows = []
        for name, vers in versions.items():
            for v in vers:
                cmd = server_cmds(fs_ver=v, ev_ver=v)[name]
                if name == "everything" and v < "2026":
                    pass
                snaps, err = capture(name, cmd, 1, 0.0, f"rel-{v}")
                if err and name == "everything":
                    # older server-everything builds may not take the 'stdio' arg; retry once without it
                    snaps, err2 = capture(name, cmd[:-1], 1, 0.0, f"rel-{v}")
                    err = None if snaps else f"{err} | without-arg: {err2}"
                for s in snaps:
                    s["version"] = v
                rows += snaps
                if err:
                    log["failures"][f"{name}@{v}"] = err
                print(f"{name}@{v}: {len(snaps[0]['tools']) if snaps else 0} tools {err or ''}", flush=True)
        (SNAP / "release.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    log["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (SNAP / f"{mode}-log.json").write_text(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()

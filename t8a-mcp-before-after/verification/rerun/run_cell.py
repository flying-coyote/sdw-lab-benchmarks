#!/usr/bin/env python3
"""Run one T8a cell: start server (+ proxies), run the client, collect every capture into runs/<cell>/rep<N>/.

Usage: run_cell.py <arm> <transport> <rep> [--no-otel] [--backend]
arm: A | B | C | Clog | D ; transport: stdio | http
Writes run.json with versions, commands, exit codes and wall time. Runs under venv-v2's python; the arm picks
which venv's python launches the client and server.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY1 = str(HERE / "venv-v1" / "bin" / "python")
PY2 = str(HERE / "venv-v2" / "bin" / "python")
ARMS = {
    # arm: (client_py, client_script, conn_mode, log_level, server_py)
    "A": (PY1, "client_v1.py", None, None, PY1),
    "B": (PY2, "client_v2.py", "legacy", "-", PY2),
    "C": (PY2, "client_v2.py", "auto", "-", PY2),
    "Clog": (PY2, "client_v2.py", "auto", "info", PY2),
    "D": (PY2, "client_v2.py", "auto", "-", PY1),
}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_port(port: int, timeout: float = 20.0) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main() -> None:
    arm, transport, rep = sys.argv[1], sys.argv[2], int(sys.argv[3])
    no_otel = "--no-otel" in sys.argv
    backend = "--backend" in sys.argv
    instrument = "--instrument" in sys.argv
    client_py, client_script, conn_mode, log_level, server_py = ARMS[arm]
    tag = f"{arm}-{transport}" + ("-nootel" if no_otel else "") + ("-backend" if backend else "") + ("-instr" if instrument else "")
    out = HERE / "runs" / tag / f"rep{rep}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    server_script = "server_v1.py" if server_py == PY1 else "server_v2.py"
    env = dict(os.environ)
    env.pop("T8A_OTEL_FILE", None)
    env.pop("T8A_BACKEND_URL", None)
    env["PYTHONUNBUFFERED"] = "1"  # warnings filters left stock (pre-reg: defaults untouched)
    senv = dict(env)
    cenv = dict(env)
    if instrument:
        senv["T8A_HTTPX_INSTRUMENT"] = "1"
        cenv["T8A_HTTPX_INSTRUMENT"] = "1"  # forwarded to a stdio server child by t8a_common.server_env
    if not no_otel:
        senv["T8A_OTEL_FILE"] = str(out / "server.otel.jsonl")
        cenv["T8A_OTEL_FILE"] = str(out / "client.otel.jsonl")
    procs: list[subprocess.Popen] = []
    run = {"arm": arm, "transport": transport, "rep": rep, "no_otel": no_otel, "backend": backend, "instrument": instrument,
           "server_script": server_script, "server_python": server_py, "client_python": client_py,
           "client_script": client_script, "conn_mode": conn_mode, "log_level": log_level,
           "t_start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "commands": []}
    if backend:
        bport = free_port()
        bp = subprocess.Popen([PY2, str(HERE / "backend.py"), str(bport), str(out / "backend.jsonl")], env=env)
        procs.append(bp)
        run["commands"].append(bp.args)
        wait_port(bport)
        cenv["T8A_BACKEND_URL"] = f"http://127.0.0.1:{bport}/hop"
        # the server makes the call; the URL travels as a tool argument, so only the client env needs it
    t0 = time.monotonic_ns()
    try:
        if transport == "stdio":
            # client -> proxy_stdio (venv-v2 python, stdlib only) -> server (arm's python); server stderr -> file
            proxy_cmd = [PY2, str(HERE / "proxy_stdio.py"), str(out / "wire.jsonl"), str(out / "server.stderr"),
                         server_py, str(HERE / server_script), "stdio"]
            if client_script == "client_v1.py":
                cmd = [client_py, str(HERE / client_script), "stdio", str(out), *proxy_cmd]
            else:
                cmd = [client_py, str(HERE / client_script), "stdio", str(out), conn_mode, log_level, *proxy_cmd]
            # the server inherits the client's env through the proxy; give it the server OTel file instead
            cenv_stdio = dict(cenv)
            if not no_otel:
                cenv_stdio["T8A_SERVER_OTEL_FILE"] = senv["T8A_OTEL_FILE"]
            run["commands"].append(cmd)
            cp = subprocess.run(cmd, env=cenv_stdio, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=120)
            run["client_rc"] = cp.returncode
            (out / "client.stdout").write_bytes(cp.stdout)
            (out / "client.stderr").write_bytes(cp.stderr)
        else:
            sport, pport = free_port(), free_port()
            scmd = [server_py, str(HERE / server_script), "http", str(sport)]
            sp = subprocess.Popen(scmd, env=senv, cwd=HERE, stdout=open(out / "server.stdout", "wb"),
                                  stderr=open(out / "server.stderr", "wb"))
            procs.append(sp)
            run["commands"].append(scmd)
            if not wait_port(sport):
                raise RuntimeError("server did not open its port in 20 s")
            pcmd = [PY2, str(HERE / "proxy_tcp.py"), str(pport), str(sport), str(out / "tcp.jsonl")]
            pp = subprocess.Popen(pcmd, env=env, cwd=HERE, stderr=open(out / "proxy.stderr", "wb"))
            procs.append(pp)
            run["commands"].append(pcmd)
            if not wait_port(pport):
                raise RuntimeError("proxy did not open its port")
            url = f"http://127.0.0.1:{pport}/mcp"
            if client_script == "client_v1.py":
                cmd = [client_py, str(HERE / client_script), "http", str(out), url]
            else:
                cmd = [client_py, str(HERE / client_script), "http", str(out), conn_mode, log_level, url]
            run["commands"].append(cmd)
            cp = subprocess.run(cmd, env=cenv, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            run["client_rc"] = cp.returncode
            (out / "client.stdout").write_bytes(cp.stdout)
            (out / "client.stderr").write_bytes(cp.stderr)
            time.sleep(0.5)  # let the server flush its last stderr/OTel lines
    except Exception as e:
        run["error"] = f"{type(e).__name__}: {e}"
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        run["wall_ns"] = time.monotonic_ns() - t0
        run["t_end_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        (out / "run.json").write_text(json.dumps(run, indent=1))
        print(json.dumps({k: run.get(k) for k in ("arm", "transport", "rep", "client_rc", "error", "wall_ns")}))


if __name__ == "__main__":
    main()

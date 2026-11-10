#!/usr/bin/env python3
"""T2 arm C: one scripted agent session against a local Ollama server, stdlib only.

The harness is the "agent": it sends the prompt with a read_file tool declared, executes the tool call
itself by reading the fixture, returns the tool result, and records the final response. Everything the
client sees is saved so the table can separate "server logged it" from "client was told it".

Usage: run_ollama_session.py --host http://127.0.0.1:11434 --model gemma4:e4b --out results/ollama-default-t1
"""
import argparse, json, os, sys, time, urllib.request, datetime

PROMPT = "Read the file fixtures/known.txt and reply with exactly the sentinel token it contains, nothing else."
TOOLS = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a UTF-8 text file from the working directory and return its contents.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "relative file path"}},
                       "required": ["path"]},
    },
}]


def post(host, body):
    req = urllib.request.Request(host + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read())
    return data, time.monotonic() - t0


def read_file(path, root):
    full = os.path.normpath(os.path.join(root, path))
    if not full.startswith(root):
        return "error: path outside working directory"
    with open(full, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--model", default="gemma4:e4b")
    ap.add_argument("--out", required=True)
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    root = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(a.out, exist_ok=True)
    rec = {"host": a.host, "model": a.model, "prompt": PROMPT, "turns": [],
           "start_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    t_start = time.monotonic()
    msgs = [{"role": "user", "content": PROMPT}]
    opts = {"num_thread": a.threads, "temperature": 0}
    body = {"model": a.model, "messages": msgs, "tools": TOOLS, "stream": False, "options": opts}
    resp, dt = post(a.host, body)
    rec["turns"].append({"request": body, "response": resp, "latency_s": round(dt, 3)})
    msg = resp.get("message", {})
    tool_calls = msg.get("tool_calls") or []
    rec["tool_call_made"] = bool(tool_calls)
    if tool_calls:
        msgs.append(msg)
        for tc in tool_calls:
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try: args = json.loads(args)
                except Exception: args = {"path": args}
            path = args.get("path", "fixtures/known.txt")
            content = read_file(path, root) if fn.get("name") == "read_file" else f"error: unknown tool {fn.get('name')}"
            rec["tool_executed"] = {"name": fn.get("name"), "args": args, "result_len": len(content)}
            msgs.append({"role": "tool", "content": content, "tool_name": fn.get("name")})
        body2 = {"model": a.model, "messages": msgs, "tools": TOOLS, "stream": False, "options": opts}
        resp2, dt2 = post(a.host, body2)
        rec["turns"].append({"request": body2, "response": resp2, "latency_s": round(dt2, 3)})
        rec["final_text"] = resp2.get("message", {}).get("content", "")
    else:
        rec["final_text"] = msg.get("content", "")
    rec["wall_s_monotonic"] = round(time.monotonic() - t_start, 3)
    rec["end_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rec["sentinel_in_final"] = "SDW-T2-SENTINEL-7f3a9c2e" in rec["final_text"]
    with open(os.path.join(a.out, "session.json"), "w") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps({k: rec[k] for k in ("tool_call_made", "sentinel_in_final", "wall_s_monotonic")}))


if __name__ == "__main__":
    main()

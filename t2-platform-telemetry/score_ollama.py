#!/usr/bin/env python3
"""Score arm C (Ollama) per trial: what the server log shows vs what the client response carries.

Default-level trials: results/ollama-default-tN/{session.json,journal.txt}
Debug-level trials:   results/ollama-debug-tN/{session.json,log_offset_before.txt,log_offset_after.txt}
                      sliced out of results/ollama-debug-server.log
Stdlib only. Writes results/ollama_scores.json and prints a summary.
"""
import json, os, re, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SENTINEL = "SDW-T2-SENTINEL-7f3a9c2e"
PROMPT = "Read the file fixtures/known.txt and reply with exactly the sentinel token it contains, nothing else."


def score_log(lines):
    text = "\n".join(lines)
    gin = [l for l in lines if "[GIN]" in l]
    chat = [l for l in gin if '"/api/chat"' in l]
    shapes = collections.Counter()
    for l in lines:
        m = re.search(r'source=([\w.]+:\d+)', l)
        shapes[m.group(1) if m else ("GIN" if "[GIN]" in l else "other")] += 1
    return {
        "lines": len(lines), "gin_lines": len(gin), "api_chat_lines": len(chat),
        "F1 user identity": False,
        "F2 session id": False,
        "F3 prompt text": PROMPT in text or "sentinel token" in text,
        "F4 tool name": "read_file" in text,
        "F5 tool args": "fixtures/known.txt" in text,
        "F6 tool output": SENTINEL in text,
        "F7 model id (name per request)": bool(re.search(r'gemma4:e4b', text)),
        "F7b model identity at load (blob digest / arch)": ("blobs/sha256-" in text) or ("architecture=gemma4" in text),
        # debug level: "loading cache slot ... prompt=<n>" is the input token count (equals the client's prompt_eval_count)
        "F8 token counts": bool(re.search(r'eval_count|prompt_eval|tokens?=\d|loading cache slot.*prompt=\d+', text)),
        "F8 input tokens seen in log": [int(x) for x in re.findall(r'loading cache slot.*?prompt=(\d+)', text)],
        "F8 output tokens in log": bool(re.search(r'eval_count|output_tokens|completion_tokens|generated=\d', text)),
        "F3b prompt length (chars) in log": [int(x) for x in re.findall(r'completion request" images=\d+ prompt=(\d+)', text)],
        "F9 cost": False,
        "F10 response text": SENTINEL in text,
        "F11 client ip": any("127.0.0.1" in l for l in chat),
        "F12 timestamps": bool(lines),
        "levels": dict(collections.Counter(re.findall(r'level=(\w+)', text))),
        "distinct_sources": len(shapes), "top_sources": shapes.most_common(8),
        "sample_chat_line": chat[0][-120:] if chat else None,
    }


def score_client(sess):
    turns = sess["turns"]
    last = turns[-1]["response"]
    first = turns[0]["response"]
    keys = sorted(last.keys())
    return {
        "response_keys": keys,
        "F7 model id": last.get("model"),
        "F8 token counts": {"prompt_eval_count": last.get("prompt_eval_count"), "eval_count": last.get("eval_count")},
        "F4/F5 tool call in response": first.get("message", {}).get("tool_calls"),
        "F10 response text has sentinel": SENTINEL in sess.get("final_text", ""),
        "F12 created_at": last.get("created_at"),
        "durations_ns_present": all(k in last for k in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration")),
        "F1/F2/F9 (user, session, cost) in response": any(k in last for k in ("user", "session", "session_id", "cost")),
        "latencies_s": [t["latency_s"] for t in turns], "wall_s_monotonic": sess.get("wall_s_monotonic"),
    }


def main():
    out = {"default": {}, "debug": {}}
    for d in sorted(glob.glob(os.path.join(HERE, "results", "ollama-default-t*"))):
        sess = json.load(open(os.path.join(d, "session.json")))
        lines = open(os.path.join(d, "journal.txt")).read().splitlines() if os.path.exists(os.path.join(d, "journal.txt")) else []
        out["default"][os.path.basename(d)] = {"server_log": score_log(lines), "client": score_client(sess)}
    logp = os.path.join(HERE, "results", "ollama-debug-server.log")
    alllog = open(logp).read().splitlines() if os.path.exists(logp) else []
    for d in sorted(glob.glob(os.path.join(HERE, "results", "ollama-debug-t*"))):
        if not os.path.exists(os.path.join(d, "session.json")):
            continue
        sess = json.load(open(os.path.join(d, "session.json")))
        b = int(open(os.path.join(d, "log_offset_before.txt")).read().strip() or 0)
        a = int(open(os.path.join(d, "log_offset_after.txt")).read().strip() or len(alllog))
        lines = alllog[b:a]
        with open(os.path.join(d, "server_log_slice.txt"), "w") as fh:
            fh.write("\n".join(lines))
        out["debug"][os.path.basename(d)] = {"server_log": score_log(lines), "client": score_client(sess)}
    with open(os.path.join(HERE, "results", "ollama_scores.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    for level, trials in out.items():
        print(f"== {level}")
        for t, r in trials.items():
            s = r["server_log"]
            print(f"  {t}: lines={s['lines']} chat={s['api_chat_lines']} prompt={s['F3 prompt text']} tool={s['F4 tool name']} path={s['F5 tool args']} sentinel={s['F6 tool output']} modelname={s['F7 model id (name per request)']} modelload={s['F7b model identity at load (blob digest / arch)']} tokens={s['F8 token counts']} levels={s['levels']}")
            c = r["client"]
            print(f"      client: model={c['F7 model id']} tokens={c['F8 token counts']} sentinel={c['F10 response text has sentinel']} wall={c['wall_s_monotonic']}s")


if __name__ == "__main__":
    main()

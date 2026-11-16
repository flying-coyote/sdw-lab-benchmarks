#!/usr/bin/env python3
"""QUIET REPLICATION 2026-11-16 LLM-router legs. Prompt text, closed-set parse and choice list are IMPORTED from
the unchanged llm_router.py (sha256 7678d896...60cb), so they are identical by construction. Changes:
  * local model selectable: gemma4:e4b (registered leg; request carries top-level "think": false) or
    phi4:latest (the 11-15 substitute; request body identical to llm_router.py's call_local);
  * every call records host 1-min load, UTC start time, and the model;
  * output to results/quiet-2026-11-16/llm_<leg>[_<model>].jsonl (new files);
  * stop rule (pre-registered): a local leg stops if its first 3 scored calls are all `invalid`.
  python3 -B llm_router_quiet.py --leg local --model gemma4:e4b --subset 01,02
  python3 -B llm_router_quiet.py --leg local --model phi4:latest --subset 01
  python3 -B llm_router_quiet.py --leg agy --subset 01
"""
import argparse, json, subprocess, sys, time
sys.dont_write_bytecode = True
from pathlib import Path
from llm_router import build_prompt, parse

HERE = Path(__file__).parent
Q = HERE / "results" / "quiet-2026-11-16"


def load1():
    return float(open("/proc/loadavg").read().split()[0])


def call_local(model):
    def f(prompt, seed):
        import requests
        body = {"model": model, "stream": False, "keep_alive": "60m",
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0.7, "seed": seed, "num_thread": 8, "num_predict": 16}}
        if model.startswith("gemma4"):
            body["think"] = False
        t0 = time.perf_counter()
        r = requests.post("http://127.0.0.1:11434/api/chat", json=body, timeout=900)
        dt = time.perf_counter() - t0
        r.raise_for_status()
        return r.json()["message"].get("content", ""), dt
    return f


def call_agy(prompt, seed):
    t0 = time.perf_counter()
    p = subprocess.run(["agy", "--model", "gemini-4-hydrogen-high", "--print-timeout", "5m", "-p", prompt],
                       capture_output=True, text=True, timeout=400)
    dt = time.perf_counter() - t0
    return (p.stdout or "") + ("" if p.returncode == 0 else f"\n[rc={p.returncode}] {p.stderr[:300]}"), dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leg", choices=["local", "agy"], required=True)
    ap.add_argument("--model", default="")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--subset", default="01")
    a = ap.parse_args()
    keep = {f"_{s}" for s in a.subset.split(",")}
    corpus = json.loads((HERE / "queries" / "corpus.json").read_text())["queries"]
    sub = [q for q in corpus if q["id"][-3:] in keep]
    tag = a.leg if a.leg == "agy" else f"local_{a.model.split(':')[0]}"
    out_p = Q / f"llm_{tag}.jsonl"
    done = set()
    if out_p.exists():
        for line in out_p.read_text().splitlines():
            d = json.loads(line); done.add((d["id"], d["cell"], d["trial"]))
    call = call_agy if a.leg == "agy" else call_local(a.model)
    n_scored, n_invalid_first = 0, 0
    with out_p.open("a") as f:
        for trial in range(a.trials):
            for q in sub:
                for cell in ("hot", "cold"):
                    if (q["id"], cell, trial) in done:
                        continue
                    seed = 1000 + trial
                    l1, utc = load1(), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    try:
                        reply, dt = call(build_prompt(q["sql"], cell), seed)
                    except Exception as e:
                        reply, dt = f"[error] {str(e)[:200]}", None
                    rec = {"leg": a.leg, "model": a.model or "gemini-4-hydrogen-high", "id": q["id"],
                           "family": q["family"], "cell": cell, "trial": trial, "seed": seed,
                           "pick": parse(reply), "latency_s": round(dt, 3) if dt else None,
                           "load1_before": l1, "utc_start": utc, "reply_head": reply.strip()[:120]}
                    f.write(json.dumps(rec) + "\n"); f.flush()
                    print(rec["id"], cell, trial, rec["pick"], rec["latency_s"], l1, flush=True)
                    n_scored += 1
                    if a.leg == "local" and n_scored <= 3:
                        n_invalid_first += rec["pick"] == "invalid"
                        if n_scored == 3 and n_invalid_first == 3:
                            print("STOP RULE: first 3 scored calls invalid; leg stopped", flush=True)
                            return


if __name__ == "__main__":
    main()

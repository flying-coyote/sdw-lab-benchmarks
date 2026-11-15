#!/usr/bin/env python3
"""Item 2: LLM-router arm at $0 (runs on the host AFTER every engine pass has finished).

Two legs, one prompt (frozen in PREREGISTRATION.md):
  local : Ollama (loopback) gemma4:e4b, temperature 0.7, per-trial seed, num_thread 8, thinking off
  agy   : `agy --model gemini-4-hydrogen-high --print-timeout 5m -p <prompt>` (headless, plan quota, no API spend)
Subsample: the _01 and _02 query of every family (24 queries) x {hot, cold} = 48 decisions x 5 trials.
Closed-set parse: the first of {clickhouse_native, clickhouse_iceberg, starrocks} that appears in the
reply (longest names first); none or more than one distinct name in the first line -> "invalid".
Model output is data: it is parsed only for that token and never executed.
  python3 llm_router.py --leg local|agy [--trials 5] [--subset 01,02]
"""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).parent
RESULTS = HERE / "results"
CHOICES = ["clickhouse_native", "clickhouse_iceberg", "starrocks"]
ROWS = {"lineitem": "59,986,052", "orders": "15,000,000", "customer": "1,500,000", "part": "2,000,000",
        "partsupp": "8,000,000", "supplier": "100,000", "nation": "25", "region": "5",
        "conn": "10,000,000", "conn_enriched": "10,000,000", "dns": "1,000,000", "assets": "14,788",
        "ioc": "5,000"}

PROMPT = """You are the query router in front of a security analytics platform. Pick the engine that will answer this query fastest without failing.

Engines (all on one host, 24 GB memory limit each, engine defaults, no tuning):
- starrocks: StarRocks 4.1, MPP engine with a cost-based optimizer, reading the Iceberg tables through a REST catalog.
- clickhouse_iceberg: ClickHouse 26.5 reading the same Iceberg tables through the icebergS3 table function.
- clickhouse_native: ClickHouse 26.5 reading native MergeTree copies of the same tables (ORDER BY tuple(), no column statistics).

Data tier for this query: {tier_text}

Table row counts: {rows}

Query:
{sql}

Answer with exactly one word on the first line, one of: {choices}{allowed_note}"""

TIER_TEXT = {
    "hot": "HOT (recent window). All three engines hold this data and are allowed.",
    "cold": "COLD (deep history). Only the Iceberg copy exists, so clickhouse_native is NOT allowed.",
}


def build_prompt(sql, cell):
    choices = CHOICES if cell == "hot" else ["clickhouse_iceberg", "starrocks"]
    return PROMPT.format(tier_text=TIER_TEXT[cell], rows=", ".join(f"{k} {v}" for k, v in ROWS.items()),
                         sql=sql.replace("$", ""), choices=", ".join(choices),
                         allowed_note="" if cell == "hot" else " (clickhouse_native is not allowed for this tier).")


def parse(reply):
    first = (reply or "").strip().splitlines()[0].lower() if (reply or "").strip() else ""
    found = [c for c in CHOICES if re.search(r"\b" + c + r"\b", first)]
    return found[0] if len(found) == 1 else "invalid"


def call_local(prompt, seed):
    import requests
    t0 = time.perf_counter()
    # DEVIATION (2026-11-15, after the freeze, before any scored local call): gemma4:e4b on Ollama 0.20.6 put
    # its reasoning in the visible reply even with think=false (and ignored a JSON-enum `format`), so every
    # reply failed the closed-set parse; the local leg runs on phi4:latest (the other T8b model, no thinking
    # channel) over /api/chat. Prompt, parse, temperature, seeds and trials unchanged.
    r = requests.post("http://127.0.0.1:11434/api/chat", json={
        "model": "phi4:latest", "stream": False, "keep_alive": "60m",
        "messages": [{"role": "user", "content": prompt}],
        "options": {"temperature": 0.7, "seed": seed, "num_thread": 8, "num_predict": 16}}, timeout=900)
    dt = time.perf_counter() - t0
    r.raise_for_status()
    return r.json()["message"].get("content", ""), dt


def call_agy(prompt, seed):
    t0 = time.perf_counter()
    p = subprocess.run(["agy", "--model", "gemini-4-hydrogen-high", "--print-timeout", "5m", "-p", prompt],
                       capture_output=True, text=True, timeout=400)
    dt = time.perf_counter() - t0
    return (p.stdout or "") + ("" if p.returncode == 0 else f"\n[rc={p.returncode}] {p.stderr[:300]}"), dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leg", choices=["local", "agy"], required=True)
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--subset", default="01,02")
    ap.add_argument("--ids", default="", help="POST-HOC cliff probe: explicit comma-separated query ids")
    a = ap.parse_args()
    keep = {f"_{s}" for s in a.subset.split(",")}
    corpus = json.loads((HERE / "queries" / "corpus.json").read_text())["queries"]
    if a.ids:
        ids = set(a.ids.split(","))
        sub = [q for q in corpus if q["id"] in ids]
        out_p = RESULTS / f"llm_{a.leg}_cliffprobe_posthoc.jsonl"
    else:
        sub = [q for q in corpus if q["id"][-3:] in keep]
        out_p = RESULTS / f"llm_{a.leg}.jsonl"
    done = set()
    if out_p.exists():
        for line in out_p.read_text().splitlines():
            d = json.loads(line)
            done.add((d["id"], d["cell"], d["trial"]))
    call = call_local if a.leg == "local" else call_agy
    with out_p.open("a") as f:
        for trial in range(a.trials):
            for q in sub:
                for cell in ("hot", "cold"):
                    if (q["id"], cell, trial) in done:
                        continue
                    seed = 1000 + trial
                    try:
                        reply, dt = call(build_prompt(q["sql"], cell), seed)
                    except Exception as e:
                        reply, dt = f"[error] {str(e)[:200]}", None
                    rec = {"leg": a.leg, "id": q["id"], "family": q["family"], "cell": cell, "trial": trial,
                           "seed": seed, "pick": parse(reply), "latency_s": round(dt, 3) if dt else None,
                           "reply_head": reply.strip()[:120]}
                    f.write(json.dumps(rec) + "\n")
                    f.flush()
                    print(rec["id"], cell, trial, rec["pick"], rec["latency_s"], flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Dump the mapping-oracle prompts for the frontier leg (run via claude-opus-4-8 subagents
instead of an external API key). Emits one JSON of {gidx, source, condition, cls, field, gold,
prompt} for all 141 gold items x 5 conditions = 705 prompts — the EXACT prompts run.py feeds
Ollama, so the only variable swapped is the model. Score with score_frontier.py afterwards."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run as R  # noqa: E402

valid = R.load_valid_paths()
items = R.gold_fields(0)  # 0 => no per-source cap => all 141
out, g = [], 0
for cond in R.CONDITIONS:
    for it in items:
        out.append({
            "gidx": g, "source": it["source"], "condition": cond,
            "cls": it["class"], "field": it["field"], "gold": it["gold"],
            "prompt": R.prompt_for(it, cond, valid),
        })
        g += 1
os.makedirs(os.path.join(HERE, "_frontier"), exist_ok=True)
path = os.path.join(HERE, "_frontier", "frontier_prompts.json")
json.dump(out, open(path, "w"))
print(f"items={len(items)} conditions={len(R.CONDITIONS)} total_prompts={len(out)}")
print(f"wrote {path}")

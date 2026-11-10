#!/usr/bin/env python3
"""T9 reducer: per cell, outcome, decider, where the decision was recorded, and the hook-input field list.
Reads runs/<cell>.{stdout,stderr,debug.log,meta.json,transcript.*.jsonl} and evidence/hook_inputs.jsonl."""
import glob, json, os, re, sys
LAB = os.path.dirname(os.path.abspath(__file__)); RUNS = f"{LAB}/runs"; EV = f"{LAB}/evidence"; OUT = f"{LAB}/results"
os.makedirs(OUT, exist_ok=True)
TOKEN = "T9-FIXTURE-NOT-A-SECRET"

ledger = {}
for l in open(f"{EV}/hook_inputs.jsonl"):
    r = json.loads(l); ledger.setdefault(r["cell"], []).append(r)

def jl(path):
    out = []
    for l in open(path):
        l = l.strip()
        if not l: continue
        try: out.append(json.loads(l))
        except Exception: out.append({"_nonjson": l})
    return out

def tool_results(events):
    """tool_use -> (tool_result content, is_error) pairs from stream-json assistant/user messages."""
    uses, results = {}, {}
    for e in events:
        m = e.get("message") or {}
        c0 = m.get("content") if isinstance(m, dict) else None
        for b in (c0 if isinstance(c0, list) else []):
            if isinstance(b, dict) and b.get("type") == "tool_use": uses[b["id"]] = (b.get("name"), b.get("input"), e.get("parent_tool_use_id"))
            if isinstance(b, dict) and b.get("type") == "tool_result":
                c = b.get("content"); txt = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else str(c)
                results[b["tool_use_id"]] = (txt, b.get("is_error"))
    return uses, results

rows = []
for mp in sorted(glob.glob(f"{RUNS}/*.meta.json")):
    cell = os.path.basename(mp).split(".")[0]
    meta = json.load(open(mp))
    events = jl(f"{RUNS}/{cell}.stdout")
    res = next((e for e in events if e.get("type") == "result"), {})
    denied_sys = [e for e in events if e.get("type") == "system" and e.get("subtype") == "permission_denied"]
    uses, results = tool_results(events)
    hooks = ledger.get(cell, [])
    hook_decisions = [(h["input"].get("tool_name"), h.get("decision"), h.get("reason"), bool(h["input"].get("agent_id")), h["input"].get("agent_type"), (h["input"].get("mcp_server") or {}).get("source")) for h in hooks]
    # classify per target tool call
    tr_texts = [(uses.get(uid, (None,))[0], txt[:300], err) for uid, (txt, err) in results.items()]
    hook_said_deny = any(d == "deny" for _, d, *_ in hook_decisions)
    hook_said_allow = any(d == "allow" for _, d, *_ in hook_decisions)
    hook_reason_seen = any(("(hook)" in txt) for _, txt, _ in tr_texts)
    rule_block_seen = any(re.search(r"permission|denied|deny rule|not allowed|blocked", txt, re.I) and "(hook)" not in txt for _, txt, _ in tr_texts)
    marker = meta["forbidden_marker_exists"] or meta["allowed_marker_exists"]
    token_leaked = any(TOKEN in txt for _, txt, _ in tr_texts) or TOKEN in json.dumps(res.get("result", ""))
    pd = res.get("permission_denials") or []
    dbg = open(f"{RUNS}/{cell}.debug.log", errors="replace").read()
    dbg_hook_lines = len(re.findall(r"hook", dbg, re.I))
    dbg_deny_lines = [l for l in dbg.splitlines() if re.search(r"PreToolUse|permission|denied|deny", l, re.I)][:6]
    stderr = open(f"{RUNS}/{cell}.stderr", errors="replace").read()
    otel = [l for l in (open(f"{RUNS}/{cell}.stdout").read() + stderr).splitlines() if "tool_decision" in l or "claude_code." in l]
    if marker: outcome = "RAN (marker created)"
    elif hook_said_deny and hook_reason_seen: outcome = "BLOCKED by hook (reason reached model)"
    elif hook_said_deny: outcome = "BLOCKED by hook (reason not in tool_result text)"
    elif pd and rule_block_seen: outcome = "BLOCKED by permission rule / flow"
    elif pd: outcome = "DENIED by permission flow (no decider named)"
    else: outcome = "OTHER"
    transcripts = glob.glob(f"{RUNS}/{cell}.transcript.*.jsonl")
    tr_hook_mentions = 0; tr_types = set()
    for t in transcripts:
        for e in jl(t):
            tr_types.add(e.get("type"))
            if "hook" in json.dumps(e).lower(): tr_hook_mentions += 1
    rows.append({"cell": cell, "outcome": outcome, "rc": meta["rc"], "forbidden_marker": meta["forbidden_marker_exists"], "allowed_marker": meta["allowed_marker_exists"],
                 "token_leaked": token_leaked, "hook_fires": len(hooks), "hook_decisions": hook_decisions, "hook_input_fields": sorted(set().union(*[set(h["input"].keys()) for h in hooks])) if hooks else [],
                 "hook_env_keys": sorted(set().union(*[set(h["env_keys"]) for h in hooks])) if hooks else [],
                 "permission_denials": [(d.get("tool_name"), (d.get("tool_input") or {}).get("command") or (d.get("tool_input") or {}).get("file_path")) for d in pd],
                 "system_permission_denied_events": len(denied_sys), "tool_results": tr_texts, "num_turns": res.get("num_turns"), "is_error": res.get("is_error"),
                 "cost_usd": res.get("total_cost_usd"), "result_text": (res.get("result") or "")[:400], "debug_hook_lines": dbg_hook_lines, "debug_decision_lines": dbg_deny_lines,
                 "stderr_head": stderr[:300], "otel_lines": otel[:6], "transcript_files": [os.path.basename(t) for t in transcripts], "transcript_entry_types": sorted(x for x in tr_types if x), "transcript_hook_mentions": tr_hook_mentions,
                 "layers": meta["layers"]})
json.dump(rows, open(f"{OUT}/cells.json", "w"), indent=1)
with open(f"{OUT}/cells.md", "w") as f:
    f.write("| cell | outcome | hook fires | hook decisions (tool, decision, agent?, mcp source) | permission_denials | sys permission_denied | turns | cost USD |\n|---|---|---|---|---|---|---|---|\n")
    for r in rows:
        hd = "; ".join(f"{t}:{d or 'none'}{' agent' if a else ''}{' mcp:'+str(s) if s else ''}" for t, d, _, a, _, s in r["hook_decisions"]) or "-"
        f.write(f"| {r['cell']} | {r['outcome']} | {r['hook_fires']} | {hd} | {len(r['permission_denials'])} | {r['system_permission_denied_events']} | {r['num_turns']} | {r['cost_usd']} |\n")
print(open(f"{OUT}/cells.md").read())

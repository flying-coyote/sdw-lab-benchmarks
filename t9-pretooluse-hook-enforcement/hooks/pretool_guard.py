#!/usr/bin/env python3
"""T9 PreToolUse hook (lab fixture). Logs its full stdin to the ledger, then decides per argv flags.
Flags: --deny-bash --deny-file --deny-mcp --deny-echo --allow-touch --exit2 (deny via exit 2 + stderr instead of JSON)."""
import json, os, sys, time
LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence", "hook_inputs.jsonl")
raw = sys.stdin.read()
try:
    data = json.loads(raw)
except Exception:
    data = {"_unparsed": raw}
flags = set(sys.argv[1:])
env_keys = sorted(k for k in os.environ if k.startswith(("CLAUDE", "T9_", "OTEL", "TRACEPARENT")))
rec = {"t": time.time(), "cell": os.environ.get("T9_CELL"), "flags": sorted(flags), "env_keys": env_keys,
       "pid": os.getpid(), "ppid": os.getppid(), "input": data}
tool = data.get("tool_name", "")
ti = data.get("tool_input") or {}
cmd = ti.get("command", "") if isinstance(ti, dict) else ""
paths = " ".join(str(ti.get(k, "")) for k in ("file_path", "path", "pattern", "command", "prompt", "description")) if isinstance(ti, dict) else ""
reason = None
if "--deny-bash" in flags and tool == "Bash" and "t9-forbidden" in cmd:
    reason = "T9 policy: forbidden marker command (hook)"
elif "--deny-file" in flags and "secrets/token.txt" in paths:
    reason = "T9 policy: secrets/token.txt is off limits (hook)"
elif "--deny-mcp" in flags and tool == "mcp__t9fixture__echo":
    reason = "T9 policy: fixture MCP tool denied (hook)"
elif "--deny-echo" in flags and tool == "Bash" and cmd.strip().startswith("echo"):
    reason = "T9 policy: echo denied in subagent test (hook)"
decision = None
if reason:
    decision = "deny"
elif "--allow-touch" in flags and tool == "Bash" and cmd.strip().startswith("touch"):
    decision, reason = "allow", "T9 hook allow for touch (hook)"
rec["decision"] = decision
rec["reason"] = reason
with open(LEDGER, "a") as f:
    f.write(json.dumps(rec) + "\n")
if decision == "deny" and "--exit2" in flags:
    sys.stderr.write(reason + " [exit2]\n")
    sys.exit(2)
if decision:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                             "permissionDecisionReason": reason}}))
sys.exit(0)

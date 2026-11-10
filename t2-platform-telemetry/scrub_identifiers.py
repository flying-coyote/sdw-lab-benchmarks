#!/usr/bin/env python3
"""Post-capture redaction: replace the account identifiers Claude Code emitted (user.email, user.account_uuid,
user.account_id, organization.id, user.id) with fixed placeholders in the raw captures. Presence is what the
bench scores, so the scrub changes no score; it exists because this folder is headed for a public repo."""
import json, glob, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ["user.email", "user.account_uuid", "user.account_id", "organization.id", "user.id"]
vals = {}
for f in glob.glob(os.path.join(HERE, "collector/out/logs.jsonl")):
    for line in open(f):
        for m in re.finditer(r'"key":"(user\.email|user\.account_uuid|user\.account_id|organization\.id|user\.id)","value":\{"stringValue":"([^"]+)"\}', line):
            vals.setdefault(m.group(1), set()).add(m.group(2))
repl = {}
for k, vs in vals.items():
    for i, v in enumerate(sorted(vs)):
        repl[v] = f"<redacted-{k}{'' if len(vs)==1 else '-'+str(i)}>"
files = glob.glob(os.path.join(HERE, "collector/out/*.jsonl")) + glob.glob(os.path.join(HERE, "results/claude-*/events_flat.json")) + glob.glob(os.path.join(HERE, "results/_discarded*/stdout.json"))
n = 0
for f in files:
    s = open(f).read(); o = s
    for v, r in repl.items():
        s = s.replace(v, r)
    if s != o:
        open(f, "w").write(s); n += 1
print(json.dumps({"keys_found": sorted(vals), "distinct_values": {k: len(v) for k, v in vals.items()}, "files_rewritten": n}))

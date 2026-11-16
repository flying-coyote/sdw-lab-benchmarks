#!/usr/bin/env python3
"""POST-HOC CHECK (2026-11-16): how much of the alias mapper's wrong-but-valid count is a matcher artifact?

run.py's `has` matches a token OR a substring of the whole lowercased field name (run.py l.30), so "ts" fires
on `packets`, "text" on `securityContext.*`, "ip" on `DetectDescription`, and CrowdStrike's `event.` envelope
fires the `event` rule. This re-runs the same rule table with whole-token matching, in two variants
(camelCase left whole; camelCase split), both with the `event.` envelope stripped, and counts how many of the
60 adjudicated-"wrong" mappings still come out on a valid non-gold path. No tracked file is modified.
Output: results/alias-whole-token-check-2026-11-16.json
"""
import csv
import importlib.util
import inspect
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("fb", os.path.join(HERE, "frontier_behind_constraint_2026_11_16.py"))
fb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fb)
O, det, valid = fb.oracle, fb.det, fb.valid

src = inspect.getsource(det.candidates)
OLD_HAS = "    has = lambda *xs: any(x in toks or x in f for x in xs)"
OLD_TOK = '    toks = set(re.split(r"[^a-z0-9]+", f)) | {f}'
assert OLD_HAS in src and OLD_TOK in src


def variant(split_camel):
    s = src.replace(OLD_HAS, "    has = lambda *xs: any(x in toks for x in xs)")
    s = s.replace("def candidates(field):\n    f = field.lower()",
                  "def candidates(field):\n    field = field[6:] if field.lower().startswith('event.') else field\n    f = field.lower()")
    if split_camel:
        s = s.replace(OLD_TOK, '    toks = set(re.split(r"[^a-z0-9]+", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", field).lower())) | {f}')
    ns = {"re": re}
    exec(s, ns)
    return ns["candidates"]


def mapper(cands):
    def f(field, cls):
        for c in cands(field):
            if c in valid[cls]:
                return c
        return "unmapped"
    return f


items = O.gold_fields(0)
adj = list(csv.DictReader(open(os.path.join(HERE, "results", "alias-wrong-but-valid-adjudicated-2026-11-16.csv"))))
wrong = {(r["source"], r["field"]): r for r in adj if r["adjudication"] == "wrong"}
out = {"date": "2026-11-16", "n_fields": len(items), "original": {"correct": 23, "mapped": 94, "wrong_adjudicated": len(wrong)}}
for name, split in [("whole_token_camel_whole", False), ("whole_token_camel_split", True)]:
    mp = mapper(variant(split))
    correct = mapped = 0
    still_wrong = []
    for it in items:
        p = mp(it["field"], it["class"])
        if p == "unmapped":
            continue
        mapped += 1
        if O.normalize(p, it["class"]) == O.normalize(it["gold"], it["class"]):
            correct += 1
        elif (it["source"], it["field"]) in wrong:
            still_wrong.append([it["source"], it["field"], p, it["gold"]])
    out[name] = {"correct": correct, "mapped": mapped, "adjudicated_wrong_still_valid_non_gold": len(still_wrong),
                 "rows": still_wrong}
json.dump(out, open(os.path.join(HERE, "results", "alias-whole-token-check-2026-11-16.json"), "w"), indent=2)
for k in ("whole_token_camel_whole", "whole_token_camel_split"):
    print(k, {x: out[k][x] for x in ("correct", "mapped", "adjudicated_wrong_still_valid_non_gold")})

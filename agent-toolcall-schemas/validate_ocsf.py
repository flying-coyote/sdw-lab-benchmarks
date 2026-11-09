#!/usr/bin/env python3
"""POST each OCSF-shaped record to the public OCSF validator (schema.ocsf.io, serves the 1.9.0 release) and save
the verdicts. Records built on main (1.10.0-dev) are expected to fail on attributes added after 1.9.0."""
import json, sys, urllib.request
from collections import Counter
from pathlib import Path
OUT = Path(__file__).resolve().parent / "results"
res = {}
for s in ("ocsf_main", "aos"):
    out = []
    for line in (OUT / f"records_{s}.jsonl").open():
        r = urllib.request.Request("https://schema.ocsf.io/api/v2/validate?profiles=ai_operation",
                                   data=line.encode(), headers={"Content-Type": "application/json"})
        v = json.load(urllib.request.urlopen(r, timeout=60))
        out.append({"errors": [(e["error"], e.get("attribute_path")) for e in v.get("errors", [])],
                    "warnings": [(w["warning"], w.get("attribute_path")) for w in v.get("warnings", [])]})
    res[s] = {"records": len(out),
              "error_kinds": Counter(f"{a}@{b}" for o in out for a, b in o["errors"]),
              "warning_kinds": Counter(f"{a}@{b}" for o in out for a, b in o["warnings"])}
(OUT / "ocsf_validator_1.9.0.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))

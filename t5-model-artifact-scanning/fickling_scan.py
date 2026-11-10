#!/usr/bin/env python3
"""fickling arm of the T5 harness. One file in, one JSON object out on stdout.

Dispatch is the one fickling's own CLI uses for a downloaded Hugging Face file (fickling/cli.py 0.1.12):
a zip goes to `fickling.scan_zip_archive`, anything else to `fickling.scan_file`, both `graceful=True`.
Never unpickles. Exit code mirrors the CLI's --check-safety: 0 clean, 1 unsafe, 2 error.
"""
import json
import sys
import zipfile

import fickling
from fickling.analysis import Severity

path = sys.argv[1]
members = {}
if zipfile.is_zipfile(path):
    res = fickling.scan_zip_archive(path, graceful=True)
    mode = "zip"
else:
    res = {"<file>": fickling.scan_file(path, graceful=True)}
    mode = "raw"
flagged = False
errors = 0
scanned = 0
for name, r in res.items():
    sev = r.severity
    row = {"severity": sev.name, "severity_rank": sev.value[0], "errors": list(r.errors),
           "results": [str(x) for x in r.results]}
    try:
        row["analysis"] = [getattr(a, "message", str(a)) if not isinstance(a, dict) else a for a in
                           (r.results[0].results if r.results and hasattr(r.results[0], "results") else [])]
    except Exception:  # noqa: BLE001 - diagnostic detail only
        pass
    members[name] = row
    if sev > Severity.LIKELY_SAFE:
        flagged = True
    if r.errors:
        errors += 1
    if not r.errors or sev > Severity.LIKELY_SAFE:
        scanned += 1
if mode == "zip" and not res:
    verdict = "skipped"   # zip with no .pkl/.pickle/.bin member: fickling did not look at anything
elif flagged:
    verdict = "flagged"
elif errors and scanned == 0:
    verdict = "error"
else:
    verdict = "clean"
json.dump({"mode": mode, "verdict": verdict, "members": members, "n_members": len(res)}, sys.stdout)
sys.exit({"clean": 0, "skipped": 0, "flagged": 1, "error": 2}[verdict])

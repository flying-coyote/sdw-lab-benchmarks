#!/usr/bin/env python3
"""POST-HOC (2026-11-16), not pre-registered. Re-sends R2's records to the public OCSF validator at two schema
versions, after an external review pointed out that the 1.9.0 result is a version effect:
  - OCSF-main records (built on 1.10.0-dev) against the 1.10.0-dev schema the same server hosts;
  - AOS example-1 records (R2 validated only example 2) against 1.9.0.
Writes results/validator_posthoc_2026-11-16.json."""
import json, urllib.request
from collections import Counter
from pathlib import Path
OUT = Path(__file__).resolve().parent / "results"
res = {}
for rec, ver in (("ocsf_main", "1.10.0-dev"), ("aos_example1", "1.9.0"), ("aos", "1.9.0")):
    counts = Counter()
    for line in (OUT / f"records_{rec}.jsonl").open():
        r = urllib.request.Request(f"https://schema.ocsf.io/{ver}/api/v2/validate?profiles=ai_operation",
                                   data=line.encode(), headers={"Content-Type": "application/json"})
        v = json.load(urllib.request.urlopen(r, timeout=60))
        counts[f"errors={v['error_count']},warnings={v['warning_count']}"] += 1
    res[f"{rec}@{ver}"] = dict(counts)
(OUT / "validator_posthoc_2026-11-16.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))

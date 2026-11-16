#!/usr/bin/env python3
"""Fetch the FULL OCSF 1.8.0 class + object attribute sets from the version-pinned schema API
(post-hoc, 2026-11-16). Used by frontier_behind_constraint_2026_11_16.py to split the frontier
silent-error rate into truly invented paths vs real-1.8.0-but-outside-the-transcribed-subset paths.

Endpoints (same family PROVENANCE.md used for the subset):
  https://schema.ocsf.io/1.8.0/api/classes/<class>
  https://schema.ocsf.io/1.8.0/api/objects            (object list)
  https://schema.ocsf.io/1.8.0/api/objects/<object>
The API's default response includes every profile's attributes (no profile filter is sent), so the
full closure is profile-inclusive. /1.8.0/export/schema refused (legacy-format error), hence per-object.
"""
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "schema-ocsf-1.8.0-api-2026-11-16")
BASE = "https://schema.ocsf.io/1.8.0/api"
CLASSES = ["authentication", "detection_finding", "network_activity", "dns_activity", "http_activity"]


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "lab-bench"}), timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    os.makedirs(os.path.join(OUT, "objects"), exist_ok=True)
    for c in CLASSES:
        json.dump(get(f"{BASE}/classes/{c}"), open(os.path.join(OUT, f"class_{c}.json"), "w"), indent=1, sort_keys=True)
    lst = get(f"{BASE}/objects")
    # extension objects (e.g. win/reg_key) live under /objects/<extension>/<name>; core objects at /objects/<name>
    names = sorted((o.get("extension") + "/" if o.get("extension") else "") + o["name"] for o in lst)
    skipped = []
    for n in names:
        p = os.path.join(OUT, "objects", f"{n.replace('/', '__')}.json")
        if os.path.exists(p):
            continue
        try:
            json.dump(get(f"{BASE}/objects/{n}"), open(p, "w"), indent=1, sort_keys=True)
        except Exception as e:  # recorded, not silently dropped
            skipped.append([n, str(e)])
        time.sleep(0.05)
    version = get(f"{BASE}/version")
    json.dump({"read": "2026-11-16", "api_version_endpoint_now": version, "base": BASE,
               "classes": CLASSES, "n_objects": len(names), "skipped": skipped},
              open(os.path.join(OUT, "FETCH-META.json"), "w"), indent=1)
    print(len(names), "objects;", len(skipped), "skipped", skipped, version)


if __name__ == "__main__":
    main()

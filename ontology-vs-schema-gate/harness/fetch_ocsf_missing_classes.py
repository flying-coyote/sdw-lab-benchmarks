#!/usr/bin/env python3
"""Prereg section 5 (E1): fetch the three OCSF 1.8.0 class definitions the 2026-11-16 fetch
lacks, with the same method as ocsf-deterministic-mapper/fetch_ocsf_1_8_0_full_2026_11_16.py
(GET https://schema.ocsf.io/1.8.0/api/classes/<class>, json.dump indent=1 sort_keys=True).
Written to a SIBLING dir so the pinned manifest of the 2026-11-16 dir (fafebc0d...) is untouched.
Also fetches GET <base>/data_types (the type dictionary) for the S1 families.
"""
import datetime, hashlib, json, os, sys, urllib.request

BASE = "https://schema.ocsf.io/1.8.0/api"
CLASSES = ["process_activity", "file_activity", "account_change"]
OUT = os.path.expanduser("~/sdw-lab-benchmarks/ocsf-deterministic-mapper/schema-ocsf-1.8.0-api-classes-2026-11-17")


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "lab-bench"}), timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {"read": datetime.date.today().isoformat(), "base": BASE, "classes": CLASSES,
            "method": "same as fetch_ocsf_1_8_0_full_2026_11_16.py (classes endpoint, indent=1, sort_keys)",
            "api_version_endpoint_now": get(f"{BASE}/version"), "sha256": {}}
    for c in CLASSES:
        d = get(f"{BASE}/classes/{c}")
        p = os.path.join(OUT, f"class_{c}.json")
        json.dump(d, open(p, "w"), indent=1, sort_keys=True)
        meta["sha256"][f"class_{c}.json"] = hashlib.sha256(open(p, "rb").read()).hexdigest()
        meta.setdefault("uid", {})[c] = d.get("uid")
    # data-type dictionary (base types), for the S1 type families (prereg section 4)
    p = os.path.join(OUT, "data_types.json")
    json.dump(get(f"{BASE}/data_types"), open(p, "w"), indent=1, sort_keys=True)
    meta["sha256"]["data_types.json"] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    json.dump(meta, open(os.path.join(OUT, "FETCH-META.json"), "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    sys.exit(main())

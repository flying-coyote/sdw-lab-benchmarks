"""Arm (c): deprecation counts from the pinned schema exports (H4), plus the tag-tarball
cross-check of class-level deprecations.

Usage: python3 -I count_deprecations.py [--tags-dir DIR]
  DIR holds the extracted ocsf-schema tag tarballs as DIR/<version>/ocsf-schema-<version>/.
Writes results/deprecations.json.
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocsf_full as F  # noqa: E402


def count(d, since):
    classes, slots, names = [], 0, set()
    any_classes, any_slots, any_names = [], 0, set()
    by_since = {}
    for kind in ("classes", "objects"):
        for n, o in d.get(kind, {}).items():
            dep = o.get("@deprecated")
            if dep and kind == "classes":
                any_classes.append(n)
                if dep.get("since") == since:
                    classes.append(n)
            for a, v in (o.get("attributes") or {}).items():
                ad = v.get("@deprecated")
                if ad:
                    any_slots += 1
                    any_names.add(a)
                    by_since[ad.get("since")] = by_since.get(ad.get("since"), 0) + 1
                    if ad.get("since") == since:
                        slots += 1
                        names.add(a)
    objs_dep = sorted(n for n, o in d.get("objects", {}).items() if o.get("@deprecated"))
    return {"classes_deprecated_since_version": sorted(classes),
            "attribute_slots_since_version": slots,
            "attribute_names_since_version": len(names),
            "attribute_names_list": sorted(names),
            "context_any_since": {"classes": sorted(any_classes), "attribute_slots": any_slots,
                                  "attribute_names": len(any_names),
                                  "slots_by_since": dict(sorted(by_since.items(), key=lambda kv: str(kv[0]))),
                                  "objects_deprecated": objs_dep}}


def tag_classes(tags_dir, version):
    root = glob.glob(os.path.join(tags_dir, version, "ocsf-schema-*"))
    if not root:
        return None
    out = []
    for p in glob.glob(os.path.join(root[0], "events", "**", "*.json"), recursive=True):
        with open(p) as f:
            j = json.load(f)
        dep = j.get("@deprecated")
        if dep:
            out.append({"name": j.get("name"), "since": dep.get("since"), "file": os.path.relpath(p, root[0])})
    return sorted(out, key=lambda r: r["name"] or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags-dir")
    a = ap.parse_args()
    res = {}
    for v in ("1.8.0", "1.9.0"):
        res[v] = {}
        for prof in (False, True):
            d, p = F.load_export(v, profiles=prof)
            res[v]["profiles" if prof else "noprofile"] = {"export": os.path.relpath(p, F.ROOT),
                                                           "sha256": F.sha256(p), **count(d, v)}
        if a.tags_dir:
            res[v]["tag_events_with_class_deprecation"] = tag_classes(a.tags_dir, v)
    out = os.path.join(F.ROOT, "results", "deprecations.json")
    with open(out, "w") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    for v in res:
        for k in ("noprofile", "profiles"):
            r = res[v][k]
            print(v, k, "classes", r["classes_deprecated_since_version"], "slots", r["attribute_slots_since_version"],
                  "names", r["attribute_names_since_version"])
        print(v, "tag events with class @deprecated:", res[v].get("tag_events_with_class_deprecation"))


if __name__ == "__main__":
    main()

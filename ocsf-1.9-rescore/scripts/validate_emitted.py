"""Arm (d): strict-validate every leaf path a tool emitted against the OCSF export of the version
the output declares (metadata.version), class from class_uid. Reports invalid and deprecated paths
with record counts. Bench-injected keys (`_id`, `unmapped.*`) are skipped.

Usage: python3 -I validate_emitted.py --emitted PATH --label NAME [--version V]
Writes results/emitted-paths-<label>.json.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocsf_full as F  # noqa: E402


def leaves(o, prefix=""):
    if isinstance(o, dict):
        for k, v in o.items():
            p = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict) and v:
                yield from leaves(v, p)
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                for item in v:
                    yield from leaves(item, p)
            else:
                yield p, v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emitted", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--version")
    a = ap.parse_args()
    paths = collections.Counter()
    nulls = collections.Counter()
    versions = collections.Counter()
    classes = collections.Counter()
    with open(a.emitted) as f:
        for line in f:
            e = json.loads(line)
            versions[(e.get("metadata") or {}).get("version")] += 1
            classes[e.get("class_uid")] += 1
            seen = set()
            for p, v in leaves(e):
                if p == "_id" or p.startswith("unmapped"):
                    continue
                if p in seen:
                    continue
                seen.add(p)
                paths[p] += 1
                if v is None:
                    nulls[p] += 1
    version = a.version or versions.most_common(1)[0][0]
    schema, sp = F.load_export(version, profiles=True)
    uid2name = {c["uid"]: n for n, c in schema["classes"].items()}
    cls = uid2name[classes.most_common(1)[0][0]]
    rows = []
    for p, c in sorted(paths.items()):
        r = F.resolve(schema, cls, p)
        deps = [d for d in r["deprecations"] if not d["where"].startswith("class-itself:")]
        rows.append({"path": p, "records": c, "null_records": nulls.get(p, 0), "valid": r["valid"],
                     "error": r["error"], "deprecations": deps, "type": r["leaf_type"]})
    out = {"emitted": a.emitted, "emitted_sha256": F.sha256(a.emitted), "declared_versions": dict(versions),
           "validated_against": os.path.relpath(sp, F.ROOT), "class": cls,
           "invalid": [r for r in rows if not r["valid"]],
           "deprecated": [r for r in rows if r["valid"] and r["deprecations"]],
           "all_paths": rows}
    with open(os.path.join(F.ROOT, "results", f"emitted-paths-{a.label}.json"), "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(a.label, "declared", dict(versions), "validated against", version, cls, "paths", len(rows))
    for r in out["invalid"]:
        print("  INVALID", r["path"], r["records"], r["error"])
    for r in out["deprecated"]:
        print("  DEPRECATED", r["path"], r["records"], r["deprecations"])


if __name__ == "__main__":
    main()
